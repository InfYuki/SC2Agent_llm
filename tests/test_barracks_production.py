"""Barracks profile, real macro wiring and non-Marine ownership checks."""
from collections import Counter
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import run_local
from sc2.ids.unit_typeid import UnitTypeId as U
from sc2.position import Point2
from ares.behaviors.macro import GasBuildingController, TechUp, SpawnController, MacroPlan
from bot.arbiter import OrderArbiter
from bot.llm_client import EXAMPLE, SYSTEM
from bot.production import PRODUCTION_PROFILES, needs_gas
from bot.rule_bot import RuleBot
from bot.strategy import parse_plan, PlanError
from bot.terran_support import FirstInfantryReserve, FirstSupportReserve, SupportController, composition
from tests.test_terran_support import Units as BaseUnits, Unit


class Units(BaseUnits):
    def filter(self, predicate):
        return Units(u for u in self if predicate(u))


class BarracksProductionTest(unittest.TestCase):
    def test_every_profile_is_selectable_and_wires_correct_tech(self):
        all_kinds = set()
        for profile, spec in PRODUCTION_PROFILES.items():
            payload = deepcopy(EXAMPLE)
            payload.update(request_id='barracks', production_profile=profile)
            parsed = parse_plan(json.dumps(payload), 'barracks', 1)
            self.assertEqual(parsed.production_profile, profile)
            self.assertIn(profile, SYSTEM)
            self.assertAlmostEqual(sum(x[1] for x in spec), 1)
            all_kinds.update(composition(profile))
            behaviors = []
            fake = SimpleNamespace(
                register_behavior=behaviors.append, start_location=Point2((0, 0)),
                economic_goals=lambda: (24, 1), research_priorities=lambda: (), economy_status={'workers_per_gas': 3},
                economy_under_attack=lambda: False, production_profile=lambda: profile,
                supply_workers=24, ready_townhalls=[1], time=110,
                expansion_budget=SimpleNamespace(reserve=lambda *a, **k: False),
                _saving_expansion=False, telemetry=SimpleNamespace(event=Mock()),
                state=SimpleNamespace(game_loop=0), _last_combat_frame=0)
            RuleBot.play_step(fake, 0)
            macros = behaviors[-1].macros
            self.assertEqual(any(isinstance(x, GasBuildingController) for x in macros), needs_gas(profile))
            tech = {x.desired_tech for x in macros if isinstance(x, TechUp)}
            self.assertEqual(tech, set(composition(profile)) - {U.MARINE})
            if profile not in {'marine_basic', 'marine_tank_medivac'}:
                self.assertTrue(any(isinstance(x, FirstInfantryReserve) for x in macros))
                self.assertFalse(any(isinstance(x, FirstSupportReserve) for x in macros))
        self.assertTrue({U.MARINE, U.MARAUDER, U.REAPER, U.GHOST} <= all_kinds)
        payload['production_profile'] = 'nuke_everything'
        with self.assertRaises(PlanError):
            parse_plan(json.dumps(payload), 'barracks', 1)

    def test_reservation_and_existing_infantry_rules_do_not_touch_ppo(self):
        fake = SimpleNamespace(
            minerals=49, vespene=25, structures=Units([Unit(10, U.BARRACKS)]),
            structure_present_or_pending=lambda _: False, units=Units(),
            already_pending=lambda _: 0, tech_ready_for_unit=lambda _: False,
            telemetry=SimpleNamespace(counts=Counter()))
        reserve = FirstInfantryReserve('ghost_support')
        spawn = Mock(spec=SpawnController)
        self.assertTrue(MacroPlan([reserve, spawn]).execute(fake, {}, None))
        spawn.execute.assert_not_called()
        # TechLab funded, then Academy is the next needed dependency.
        fake.structures[0].has_techlab = True
        fake.minerals, fake.vespene = 149, 50
        self.assertTrue(reserve.execute(fake, {}, None))
        fake.minerals = 150
        self.assertFalse(reserve.execute(fake, {}, None))
        # Reaper needs no addon/Factory, only its own 50/50 budget.
        fake.structures[0].has_techlab = False
        fake.minerals, fake.vespene = 50, 49
        fake.tech_ready_for_unit = lambda kind: kind == U.REAPER
        self.assertTrue(FirstInfantryReserve('reaper_pressure').execute(fake, {}, None))
        fake.vespene = 50
        self.assertFalse(FirstInfantryReserve('reaper_pressure').execute(fake, {}, None))
        # Existing new units are controlled even with no Marine (or after the
        # production profile is switched back); Marine issue path stays empty.
        infantry = Units([Unit(1, U.MARAUDER), Unit(2, U.REAPER), Unit(3, U.GHOST)])
        bot = SimpleNamespace(
            units=infantry, enemy_units=Units(), townhalls=Units(),
            enemy_structures=Units(), arbiter=OrderArbiter(), _last_order={},
            start_location=Point2((0, 0)), strategy_state='attack', support=SupportController(),
            strategic_order=lambda army: ('attack', Point2((20, 0))),
            issue_combat_orders=Mock(), telemetry=SimpleNamespace(counts=Counter(), event=Mock()))
        RuleBot._combat(bot, 80)
        self.assertEqual(list(bot.issue_combat_orders.call_args.args[0]), [])
        self.assertEqual([u.commands[-1][0] for u in infantry], ['attack'] * 3)
        self.assertEqual(bot.arbiter.conflicts, 0)
        # A previously issued Marine PPO command keeps its ownership/issued bit
        # when the rule controller extends the owner map for other infantry.
        bot.arbiter.begin_step({99: 'micro_ppo'})
        self.assertTrue(bot.arbiter.allow(99, 'micro_ppo'))
        bot.support.step(bot, infantry, 'attack', Point2((20, 0)), 100)
        self.assertEqual(bot.arbiter.owners[99], 'micro_ppo')
        self.assertIn(99, bot.arbiter.issued)
        self.assertEqual(bot.arbiter.conflicts, 0)
        bot.arbiter.begin_step({})
        bot.support.step(bot, infantry, 'retreat', Point2((0, 0)), 120)
        self.assertEqual([u.commands[-1][0] for u in infantry], ['move'] * 3)


if __name__ == '__main__':
    unittest.main()
