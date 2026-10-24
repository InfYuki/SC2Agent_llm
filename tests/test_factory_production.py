"""Factory dependency budgets and real command/ownership integration."""
from collections import Counter
from types import SimpleNamespace
import unittest
from unittest.mock import Mock

import run_local
from sc2.ids.ability_id import AbilityId as A
from sc2.ids.unit_typeid import UnitTypeId as U
from sc2.position import Point2
from sc2.game_data import Cost
from sc2.dicts.unit_train_build_abilities import TRAIN_INFO
from ares.behaviors.macro import MacroPlan, SpawnController
from bot.arbiter import OrderArbiter
from bot.rule_bot import RuleBot
from bot.terran_support import FirstFactoryReserve, FactoryMorphBudget, SupportController
from tests.test_barracks_production import Units
from tests.test_terran_support import Unit


class FactoryProductionTest(unittest.TestCase):
    def test_dependencies_budget_and_morph_counting(self):
        self.assertTrue(TRAIN_INFO[U.FACTORY][U.CYCLONE]['requires_techlab'])
        self.assertEqual(TRAIN_INFO[U.FACTORY][U.HELLIONTANK]['required_building'], U.ARMORY)
        self.assertTrue(TRAIN_INFO[U.FACTORY][U.THOR]['requires_techlab'])
        existing = set()
        prices = {U.FACTORY: Cost(150, 100), U.ARMORY: Cost(150, 100),
                  U.FACTORYTECHLAB: Cost(50, 25), U.THOR: Cost(300, 200)}
        factory = Unit(20, U.FACTORY)
        fake = SimpleNamespace(structures=Units([factory]), units=Units(),
            structure_present_or_pending=lambda kind: kind in existing,
            tech_ready_for_unit=lambda kind: kind == U.THOR,
            calculate_cost=lambda kind: prices[kind], already_pending=lambda _: 0,
            minerals=149, vespene=100, telemetry=SimpleNamespace(counts=Counter()))
        reserve = FirstFactoryReserve('factory_thor_hellbat')
        spawn = Mock(spec=SpawnController)
        self.assertTrue(MacroPlan([reserve, spawn]).execute(fake, {}, None))
        spawn.execute.assert_not_called()
        fake.minerals = 150
        self.assertFalse(reserve.execute(fake, {}, None))
        existing.add(U.FACTORY)
        fake.minerals = 149
        self.assertTrue(reserve.execute(fake, {}, None))  # Armory
        existing.add(U.ARMORY)
        fake.minerals, fake.vespene = 49, 25
        self.assertTrue(reserve.execute(fake, {}, None))  # attached lab
        factory.has_techlab = True
        fake.minerals, fake.vespene = 299, 200
        self.assertTrue(reserve.execute(fake, {}, None))  # first Thor
        fake.units.append(Unit(1, U.THORAP))
        self.assertFalse(reserve.execute(fake, {}, None))  # existing alternate form
        fake.units = Units([Unit(2, U.HELLION)])
        fake.structures.append(Unit(21, U.ARMORY))
        self.assertTrue(FactoryMorphBudget('factory_thor_hellbat').execute(fake, {}, None))
        fake.units[0].type_id = U.HELLIONTANK
        self.assertFalse(FactoryMorphBudget('factory_thor_hellbat').execute(fake, {}, None))

    def test_factory_units_keep_rules_and_use_real_morph_abilities(self):
        hellion, mine, cyclone, thor = (Unit(1, U.HELLION), Unit(2, U.WIDOWMINE),
                                      Unit(3, U.CYCLONE), Unit(4, U.THOR))
        bc = Unit(90, U.BATTLECRUISER, (6, 0))
        bc.is_flying = bc.is_massive = True
        bc.can_attack_ground = True
        bot = SimpleNamespace(units=Units([hellion, mine, cyclone, thor]),
            structures=Units([Unit(21, U.ARMORY)]), enemy_units=Units([bc]), enemy_structures=Units(),
            townhalls=Units(), arbiter=OrderArbiter(), _last_order={}, strategy_state='attack',
            support=SupportController(), start_location=Point2((0, 0)),
            production_profile=lambda: 'factory_thor_hellbat',
            strategic_order=lambda _: ('attack', Point2((30, 0))), issue_combat_orders=Mock(),
            telemetry=SimpleNamespace(counts=Counter(), event=Mock()))
        RuleBot._combat(bot, 100)
        self.assertEqual(list(bot.issue_combat_orders.call_args.args[0]), [])
        self.assertEqual(hellion.commands[-1][0], A.MORPH_HELLBAT.name)
        self.assertEqual(mine.commands[-1][0], A.BURROWDOWN_WIDOWMINE.name)  # air triggers too
        self.assertEqual(cyclone.commands[-1][0], 'attack')
        self.assertEqual(thor.commands[-1][0], A.MORPH_THORHIGHIMPACTMODE.name)
        hellion.type_id, mine.type_id, thor.type_id = U.HELLIONTANK, U.WIDOWMINEBURROWED, U.THORAP
        bot.arbiter.begin_step({99: 'micro_ppo'})
        self.assertTrue(bot.arbiter.allow(99, 'micro_ppo'))
        bot.support.step(bot, bot.units, 'attack', Point2((30, 0)), 140)
        self.assertEqual(thor.commands[-1], ('attack', bc))
        self.assertEqual(len(mine.commands), 1)  # don't overwrite automatic mine fire
        self.assertEqual(bot.arbiter.owners[99], 'micro_ppo')
        self.assertIn(99, bot.arbiter.issued)
        self.assertEqual(bot.arbiter.conflicts, 0)
        bot.enemy_units = Units()
        bot.arbiter.begin_step({})
        bot.support.step(bot, bot.units, 'attack', Point2((30, 0)), 300)
        self.assertEqual(mine.commands[-1][0], A.BURROWUP_WIDOWMINE.name)
        bot.production_profile = lambda: 'factory_hellion_cyclone'
        bot.arbiter.begin_step({})
        bot.support.step(bot, bot.units, 'retreat', Point2((0, 0)), 340)
        self.assertEqual(hellion.commands[-1][0], A.MORPH_HELLION.name)
        self.assertEqual(thor.commands[-1][0], 'move')


if __name__ == '__main__':
    unittest.main()
