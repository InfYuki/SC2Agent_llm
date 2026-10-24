from collections import Counter
from copy import deepcopy
import json
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch
import run_local
from sc2.ids.unit_typeid import UnitTypeId as U
from sc2.ids.ability_id import AbilityId as A
from sc2.position import Point2
from bot.base_defense import BaseController, BaseDefenses, OrbitalResearch
from bot.llm_client import EXAMPLE
from bot.strategy import parse_plan, PlanError
from bot.arbiter import OrderArbiter


class BaseDefenseTest(unittest.TestCase):
    def test_strategy_orbital_budget_and_static_placement(self):
        value = deepcopy(EXAMPLE)
        value['request_id'] = 'base'
        modern = parse_plan(json.dumps(value), 'base', 1)
        value.pop('base_defense')
        value.pop('orbital_command')
        self.assertEqual(modern, parse_plan(json.dumps(value), 'base', 1))
        value['orbital_command'] = 1
        with self.assertRaises(PlanError):
            parse_plan(json.dumps(value), 'base', 1)
        cc = NS(type_id=U.COMMANDCENTER, is_ready=True, is_idle=True,
                is_flying=False, orders=[], position=Point2((0, 0)), distance_to=lambda _: 0)
        bot = NS(orbital_enabled=lambda: True, supply_workers=22, time=200,
                 tech_requirement_progress=lambda _: 1, townhalls=[cc],
                 can_afford=lambda _: False, telemetry=NS(counts=Counter()))
        research = OrbitalResearch()
        self.assertTrue(research.execute(bot, {}, None))
        bot.time = 209
        self.assertFalse(research.execute(bot, {}, None))  # Cannot starve SCVs indefinitely.
        bot.can_afford = lambda _: True
        with patch('bot.base_defense.UpgradeCCs.execute', return_value=True) as execute:
            self.assertTrue(research.execute(bot, {}, None))
            execute.assert_called_once()
        cc.orders = [NS(ability=NS(id=A.UPGRADETOORBITAL_ORBITALCOMMAND))]
        self.assertFalse(research.execute(bot, {}, None))
        bot.__dict__.update(defense_policy=lambda: 'standard', _saving_expansion=False,
            ready_townhalls=[cc], enemy_units=[], structures=lambda _: [],
            structure_pending=lambda _: 0, structure_present_or_pending=lambda _: False,
            start_location=cc.position, game_info=NS(map_center=Point2((20, 20))),
            mineral_field=[])
        with patch('bot.base_defense.BuildStructure.execute', autospec=True, return_value=True) as build:
            self.assertTrue(BaseDefenses().execute(bot, {}, None))
            request = build.call_args.args[0]
            self.assertEqual(request.structure_id, U.BUNKER)
            self.assertTrue(request.bunker)
            self.assertFalse(request.production)
            self.assertFalse(request.find_alternative)
            bot.can_afford = lambda _: False
            self.assertFalse(BaseDefenses().execute(bot, {}, None))
            self.assertEqual(build.call_count, 1)
            bot.can_afford = lambda _: True
            bot.time = 450
            bot.structures = lambda kind: [cc] if kind == U.BUNKER else []
            self.assertTrue(BaseDefenses().execute(bot, {}, None))
            self.assertEqual(build.call_args.args[0].structure_id, U.MISSILETURRET)
            self.assertTrue(build.call_args.args[0].missile_turret)

    def test_orbital_scan_priority_mule_and_safe_mining(self):
        controller = BaseController()
        orbital = Mock(tag=1, type_id=U.ORBITALCOMMAND, is_ready=True, is_flying=False, energy=75)
        orbital.distance_to.return_value = 2
        patch_mineral = NS(mineral_contents=1000, distance_to=lambda _: 2)
        bot = NS(townhalls=[orbital], structures=lambda _: [], enemy_units=[],
                 mineral_field=[patch_mineral], telemetry=NS(counts=Counter(), event=Mock()))
        controller.orbital_step(bot, 100)
        orbital.assert_called_once_with(A.CALLDOWNMULE_CALLDOWNMULE, patch_mineral)
        hidden = Mock(is_visible=True, is_cloaked=True, is_burrowed=False,
                      is_revealed=False, can_attack_ground=True, position=Point2((2, 2)))
        hidden.distance_to.return_value = 3
        bot.enemy_units = [hidden]
        controller.orbital_step(bot, 140)
        self.assertEqual(orbital.call_args.args[0], A.SCANNERSWEEP_SCAN)
        before = orbital.call_count
        controller.orbital_step(bot, 180)  # Retain energy while a scan is active/recent.
        self.assertEqual(orbital.call_count, before)
        bot.enemy_units = [Mock(is_visible=True, is_cloaked=False, is_burrowed=False,
                               can_attack_ground=True)]
        bot.enemy_units[0].distance_to.return_value = 3
        controller.orbital_step(bot, 1000)
        self.assertEqual(orbital.call_count, before)  # Do not call MULE into combat.

    def test_garrison_closes_real_ppo_context_before_authorized_load(self):
        from bot.micro_bot import MicroRuleBot
        controller = BaseController()
        bunker = NS(tag=9)
        controller.load_targets[7] = bunker
        unit = Mock(tag=7, type_id=U.MARINE, health=45, health_percentage=1.)
        ctx = NS(supported=True, obs=(0.,) * 16, mask=(True,) * 5)
        order = []
        bot = object.__new__(MicroRuleBot)
        bot.__dict__.update(state=NS(upgrades=set()), base_controller=controller,
            arbiter=OrderArbiter(), telemetry=NS(counts=Counter(), event=Mock()),
            _last_order={}, _micro_disabled=False, _ppo_requested=False,
            _ppo_engagement_gate=False, _released_at={}, controlled={7},
            options=NS(micro_max_units=4), recorder=NS(pending={7: object()}, finish=Mock()),
            choose_micro_action=Mock(), _authorized_tag=None)
        bot.recorder.finish.side_effect = lambda *a, **kw: order.append('finish')
        def load(ability, target):
            self.assertEqual(bot._authorized_tag, 7)
            self.assertEqual((ability, target), (A.SMART, bunker))
            order.append('load')
            return True
        unit.side_effect = load
        with patch('bot.micro_bot.context', return_value=ctx):
            bot.issue_combat_orders([unit], 'defend', None, 100)
        self.assertEqual(order, ['finish', 'load'])
        bot.recorder.finish.assert_called_once_with(7, 100, ctx, truncated=True, reason='bunker_loading')
        bot.choose_micro_action.assert_not_called()
        self.assertEqual(bot.controlled, set())
        self.assertEqual(bot.arbiter.conflicts, 0)
        self.assertIsNone(bot._authorized_tag)


if __name__ == '__main__':
    unittest.main()
