"""Economy recovery, depletion and gas policy checks without a live game."""
import unittest
from bot.economy import EconomyPolicy


class EconomyTests(unittest.TestCase):
    def test_recovery_expansion_and_gas_hysteresis(self):
        policy = EconomyPolicy()
        args = dict(seconds=400, workers=44, ready_bases=2, mineral_patches=16,
                    refineries=4, minerals=100, gas=1500, mixed=True,
                    requested_workers=44, requested_bases=2)
        result = policy.decide(**args)
        self.assertEqual((result.base_target, result.workers_per_gas), (3, 1))
        self.assertEqual(result.worker_target, 38)
        args.update(gas=400, minerals=100, workers=20)
        result = policy.decide(**args)
        self.assertEqual(result.workers_per_gas, 1)  # no oscillation in dead band
        self.assertGreater(result.worker_target, args['workers'])
        args.update(gas=200)
        self.assertEqual(policy.decide(**args).workers_per_gas, 3)
        args.update(seconds=600, ready_bases=3, mineral_patches=10, workers=20)
        result = policy.decide(**args)
        self.assertEqual((result.base_target, result.reason), (4, 'depleted'))
        self.assertLessEqual(result.worker_target, 34)
        args.update(seconds=100)
        self.assertEqual(policy.decide(**args).base_target, 1)
        args.update(mixed=False)
        self.assertEqual(policy.decide(**args).workers_per_gas, 0)

    def test_real_macro_wires_staffing_and_keeps_expansion_above_tech(self):
        from types import SimpleNamespace
        from unittest.mock import Mock
        import run_local
        from sc2.position import Point2
        from bot.rule_bot import RuleBot
        from ares.behaviors.macro import (Mining, ExpansionController, BuildWorkers,
                                          AutoSupply, GasBuildingController)
        behaviors = []
        bot = SimpleNamespace(
            register_behavior=behaviors.append, start_location=Point2((0, 0)),
            economic_goals=lambda: (38, 3), economy_status={'workers_per_gas': 1},
            economy_under_attack=lambda: False,
            production_profile=lambda: 'marine_tank_medivac',
            supply_workers=44, ready_townhalls=[1, 2], time=400,
            structure_pending=lambda _: 0, base_townhall_type=1,
            expansion_budget=SimpleNamespace(reserve=lambda *a, **kw: True),
            _saving_expansion=False, telemetry=SimpleNamespace(event=Mock()),
            state=SimpleNamespace(game_loop=0), _last_combat_frame=0)
        RuleBot.play_step(bot, 0)
        self.assertIsInstance(behaviors[0], Mining)
        self.assertEqual(behaviors[0].workers_per_gas, 1)
        macros = behaviors[1].macros
        self.assertIsInstance(macros[0], AutoSupply)
        self.assertIsInstance(macros[1], BuildWorkers)
        self.assertIsInstance(macros[2], ExpansionController)
        self.assertTrue(macros[2].check_location_is_safe)
        self.assertFalse(any(isinstance(x, GasBuildingController) for x in macros))
        # A mined-out base must not require 20 workers before recovery expansion.
        behaviors.clear()
        bot.supply_workers = 2
        bot.economy_status['reason'] = 'depleted'
        RuleBot.play_step(bot, 1)
        self.assertTrue(any(isinstance(x, ExpansionController)
                            for x in behaviors[1].macros))

    def test_strategy_schema_keeps_old_and_accepts_new_goals(self):
        import json
        from copy import deepcopy
        from bot.llm_client import EXAMPLE
        from bot.strategy import parse_plan, PlanError
        payload = deepcopy(EXAMPLE)
        payload.update(request_id='economy', snapshot_seq=1)
        for workers, bases in [(44, 2), (80, 4)]:
            payload['economy'] = dict(worker_target=workers, base_target=bases)
            plan = parse_plan(json.dumps(payload), 'economy', 1)
            self.assertEqual((plan.worker_target, plan.base_target), (workers, bases))
        payload['economy']['base_target'] = 5
        with self.assertRaises(PlanError):
            parse_plan(json.dumps(payload), 'economy', 1)


if __name__ == '__main__':
    unittest.main()
