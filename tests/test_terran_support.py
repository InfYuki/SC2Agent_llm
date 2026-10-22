"""Small offline checks for the mixed production and support command boundary."""
from collections import Counter
from copy import deepcopy
import json
from types import SimpleNamespace
import unittest
from unittest.mock import Mock
import run_local  # initializes the pinned Ares source path

from sc2.ids.unit_typeid import UnitTypeId as U
from sc2.position import Point2
from bot.arbiter import OrderArbiter
from bot.llm_client import EXAMPLE
from bot.strategy import parse_plan
from bot.terran_support import FirstSupportReserve, SupportController, composition
from bot.rule_bot import RuleBot
from ares.behaviors.macro import MacroPlan, SpawnController, TechUp


class Units(list):
    def __call__(self, kind):
        return self.of_type({kind})

    def of_type(self, kinds):
        return Units(u for u in self if u.type_id in kinds)

    @property
    def ready(self):
        return Units(u for u in self if u.is_ready)

    @property
    def center(self):
        return Point2((sum(u.position.x for u in self) / len(self),
                       sum(u.position.y for u in self) / len(self)))


class Unit:
    def __init__(self, tag, kind, position=(0, 0)):
        self.tag, self.type_id, self.position = tag, kind, Point2(position)
        self.is_idle = self.is_ready = self.is_visible = True
        self.is_flying = self.can_attack_air = self.has_techlab = False
        self.is_biological = kind == U.MARINE
        self.health = self.health_max = 45
        self.health_percentage = 1.0
        self.energy = 100
        self.orders = []
        self.commands = []

    def distance_to(self, other):
        return self.position.distance_to(getattr(other, "position", other))

    def __call__(self, ability, target=None):
        self.commands.append((ability.name, target))
        return True

    def move(self, target):
        self.commands.append(("move", target))
        return True

    def attack(self, target):
        self.commands.append(("attack", target))
        return True


class TerranSupportTest(unittest.TestCase):
    def test_mixed_macro_reserves_resources_and_keeps_marine_contract(self):
        payload = deepcopy(EXAMPLE)
        payload.update(request_id="test", snapshot_seq=1)
        plan = parse_plan(json.dumps(payload), "test", 1)
        self.assertEqual(plan.production_profile, "marine_tank_medivac")
        payload["production_profile"] = "marine_basic"
        old = parse_plan(json.dumps(payload), "test", 1)
        self.assertNotEqual(old.intent, plan.intent)
        self.assertEqual(set(composition(old.production_profile)), {U.MARINE})
        fake = SimpleNamespace(
            minerals=149, vespene=100, structures=Units(),
            structure_present_or_pending=lambda _: False,
            telemetry=SimpleNamespace(counts=Counter()),
        )
        # MacroPlan short circuits before Marine spawn: the last mineral is saved.
        spawn = Mock(spec=SpawnController)
        reserve = FirstSupportReserve()
        macro = MacroPlan([reserve, spawn])
        self.assertTrue(macro.execute(fake, {}, None))
        spawn.execute.assert_not_called()
        fake.minerals = 150
        self.assertFalse(reserve.execute(fake, {}, None))

        # Build actual production plan, without Ares initialization or game/API.
        behaviors = []
        bot = SimpleNamespace(
            register_behavior=behaviors.append, start_location=Point2((0, 0)),
            economic_goals=lambda: (22, 1), production_profile=lambda: "marine_tank_medivac",
            supply_workers=20, ready_townhalls=[object()], townhalls=[object()], time=110,
            strategy_state="develop",
            expansion_budget=SimpleNamespace(reserve=lambda *a, **k: False),
            _saving_expansion=False, telemetry=SimpleNamespace(event=Mock()),
            state=SimpleNamespace(game_loop=0), _last_combat_frame=0,
        )
        RuleBot.play_step(bot, 0)
        macros = behaviors[-1].macros
        self.assertLess(next(i for i, x in enumerate(macros) if isinstance(x, FirstSupportReserve)),
                        next(i for i, x in enumerate(macros) if isinstance(x, SpawnController)))
        self.assertEqual([x.desired_tech for x in macros if isinstance(x, TechUp)],
                         [U.SIEGETANK, U.MEDIVAC])

        tank, med, marine = Unit(1, U.SIEGETANK), Unit(2, U.MEDIVAC), Unit(3, U.MARINE)
        marine.health, marine.health_percentage = 20, 20 / 45
        enemy = Unit(4, U.MARINE, (9, 0))
        arbiter = OrderArbiter()
        arbiter.begin_step({marine.tag: "micro_rule"})
        arbiter.allow(marine.tag, "micro_rule")
        support = SupportController()
        runtime = SimpleNamespace(units=Units([tank, med, marine]), enemy_units=Units([enemy]),
                                  enemy_structures=Units(), arbiter=arbiter,
                                  start_location=Point2((0, 0)),
                                  telemetry=SimpleNamespace(counts=Counter(), event=Mock()))
        support.step(runtime, Units([tank, marine]), "attack", Point2((30, 0)), 100)
        self.assertEqual(tank.commands[-1][0], "SIEGEMODE_SIEGEMODE")
        self.assertEqual(med.commands[-1][0], "MEDIVACHEAL_HEAL")
        self.assertIs(med.commands[-1][1], marine)
        self.assertEqual(arbiter.owners[marine.tag], "micro_rule")
        self.assertIn(marine.tag, arbiter.issued)
        self.assertEqual(arbiter.conflicts, 0)
        tank.type_id = U.SIEGETANKSIEGED
        runtime.enemy_units = Units()
        arbiter.begin_step({})
        support.step(runtime, Units([tank]), "attack", Point2((30, 0)), 200)
        self.assertEqual(tank.commands[-1][0], "UNSIEGE_UNSIEGE")
        # No Marines remains valid: support still moves; no fake PPO observation.
        runtime.units = Units([med])
        arbiter.begin_step({})
        support.step(runtime, Units(), "rally", runtime.start_location, 240)
        self.assertEqual(med.commands[-1][0], "move")


if __name__ == "__main__":
    unittest.main()
