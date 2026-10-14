from collections import Counter
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch
import asyncio

import run_local
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from bot.arbiter import OrderArbiter
from tools.run_micro_scenario import ScenarioBot
from bot.micro_bot import MicroRuleBot


class Army(list):
    @property
    def first(self):
        return self[0]


class ScenarioTests(unittest.TestCase):
    def test_invisible_enemy_during_health_setup_still_obeys_time_limit(self):
        bot = object.__new__(ScenarioBot)
        bot._health_ready = False
        bot.options = SimpleNamespace(max_game_seconds=1)
        bot.state = SimpleNamespace(game_loop=1000)
        with patch.object(MicroRuleBot, "on_step", new_callable=AsyncMock) as step:
            asyncio.run(bot.on_step(7))
            step.assert_awaited_once_with(7)

    def test_native_amove_uses_arbiter_and_never_fabricates_discrete_labels(self):
        bot = object.__new__(ScenarioBot)
        marine = SimpleNamespace(
            tag=1, health_percentage=1, health=45, position=Point2((10, 10))
        )
        enemy = SimpleNamespace(
            tag=2,
            type_id=UnitTypeId.ZERGLING,
            is_visible=True,
            position=Point2((16, 10)),
        )
        bot.options = SimpleNamespace(expert="amove")
        bot.recorder = Mock()
        bot.units = lambda kind: Army([marine])
        bot.enemy_units = [enemy]
        bot.enemy_kind = UnitTypeId.ZERGLING
        bot._scene_tag = bot._enemy_tag = None
        bot._last_combat_frame = -100
        bot.state = SimpleNamespace(game_loop=8, dead_units=set())
        bot.scene_goal = Point2((16, 10))
        bot.arbiter = OrderArbiter()
        bot.telemetry = SimpleNamespace(counts=Counter(), write_json=Mock())
        bot.issue_rule_order = Mock()
        bot.issue_combat_orders = Mock()
        bot.play_step(1)
        bot.issue_rule_order.assert_called_once_with(
            marine, "attack", bot.scene_goal, 8
        )
        bot.issue_combat_orders.assert_not_called()
        bot.recorder.begin.assert_not_called()
        self.assertEqual(bot.arbiter.owners, {1: "rule_combat"})


if __name__ == "__main__":
    unittest.main()
