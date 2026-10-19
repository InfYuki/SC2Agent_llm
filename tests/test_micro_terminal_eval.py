"""One focused check for the opt-in terminal evaluation boundary."""
from collections import Counter
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import run_local
from bot.arbiter import OrderArbiter
from bot.micro import Action, Context
from bot.micro_bot import MicroRuleBot
from sc2.ids.unit_typeid import UnitTypeId
from tools.run_micro_scenario import ScenarioBot


class Army(list):
    @property
    def first(self):
        return self[0]

    def find_by_tag(self, tag):
        return next((unit for unit in self if unit.tag == tag), None)


class TerminalEvaluationTests(unittest.TestCase):
    def test_opt_in_keeps_policy_below_safety_threshold_and_distinguishes_endings(self):
        unit = SimpleNamespace(tag=1, health_percentage=6 / 45, health=6, shield=0)
        enemy = SimpleNamespace(tag=2, type_id=UnitTypeId.ZERGLING,
                                is_visible=True, is_memory=False, is_snapshot=False,
                                health=0.6, shield=0)
        army = Army([unit])
        ctx = Context(tuple([0] * 16), (False, False, False, False, True), supported=True)
        bot = object.__new__(ScenarioBot)
        bot.options = SimpleNamespace(allow_low_health_eval=False, expert="kite", micro_max_units=1)
        bot.recorder = Mock(pending={})
        bot.units = lambda kind: army
        bot.enemy_units = [enemy]
        bot.enemy_kind = UnitTypeId.ZERGLING
        bot._scene_tag, bot._enemy_tags, bot._dead_enemy_tags = 1, {2}, set()
        bot.state = SimpleNamespace(game_loop=24, dead_units=set())
        bot.scene_goal = object()
        bot._last_combat_frame = 16
        bot.telemetry = SimpleNamespace(counts=Counter(), event=Mock(), write_json=Mock())
        bot._finish_scene = Mock()
        bot.play_step(1)
        bot._finish_scene.assert_called_once_with("low_health_safety_exit", False)

        bot.options.allow_low_health_eval = True
        bot._finish_scene.reset_mock()
        bot._micro_disabled, bot._released_at, bot.controlled, bot._last_order = False, {}, {1}, {}
        bot.arbiter = OrderArbiter()
        bot._ppo_policy = Mock()
        bot._ppo_policy.action.return_value = Action.HOLD
        bot._ppo_requested = True
        bot.issue_rule_order = Mock()
        with patch("tools.run_micro_scenario.context", return_value=ctx), patch("bot.micro_bot.context", return_value=ctx) as fresh:
            bot.play_step(2)
        bot._finish_scene.assert_not_called()
        bot._ppo_policy.action.assert_called_once_with(ctx.obs, ctx.mask)
        self.assertEqual(fresh.call_count, 2)  # ownership context plus execution-time mask
        self.assertEqual(bot.controlled, {1})
        self.assertEqual(bot.telemetry.counts["ppo_inference_decisions"], 1)
        bot.issue_rule_order.assert_not_called()
        bot.recorder.begin.assert_called_once()
        self.assertEqual(bot.recorder.begin.call_args.args[3:6], (Action.HOLD, Action.HOLD, "hold"))
        self.assertFalse(MicroRuleBot.terminal_evaluation(bot))  # production hook stays safe
        with self.assertRaisesRegex(RuntimeError, "ppo_inference_failure"):
            bot._ppo_fallback("inference", ValueError("bad model"))

        bot.state.dead_units = {2}
        bot.enemy_units = []
        bot.play_step(3)
        bot._finish_scene.assert_called_once_with("enemy_dead", True)
        self.assertEqual(bot._evaluation_health()["enemy_effective_hp"], 0)
        bot._finish_scene.reset_mock()
        bot.state.dead_units = {1}
        army.clear()
        bot.play_step(4)
        bot._finish_scene.assert_called_once_with("marine_dead", True)
        self.assertEqual(bot._evaluation_health()["own_effective_hp"], 0)

        bot._scene_outcome = None
        bot.telemetry.stop_reason = "game_time_limit"
        bot.close_micro("game_time_limit")
        result = bot.telemetry.write_json.call_args.args[1]
        self.assertEqual(result["outcome"], "game_time_limit")
        self.assertTrue(result["truncated"])
        self.assertFalse(result["terminated"])


if __name__ == "__main__":
    unittest.main()
