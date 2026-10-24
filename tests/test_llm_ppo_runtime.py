"""One offline integration check for E4 composition; no credentials or API calls."""
from collections import Counter
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, PropertyMock, patch

import run_local
from bot.llm_bot import StrategicBot
from bot.llm_ppo_bot import LLMPPOBot
from bot.micro import Action, Context
from bot.micro_bot import MicroRuleBot
from bot.rule_bot import RuleBot
from bot.strategy import Strategy


class LLMPPORuntimeTest(unittest.TestCase):
    def test_composition_calls_both_adapters_and_keeps_old_routes(self):
        # Test the cooperative initializers and real strategic/micro step chain.
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = SimpleNamespace(
                output=Path(tmp), counts=Counter(), event=Mock(), write_json=Mock()
            )
            options = SimpleNamespace(
                mode="llm_ppo", seed=42, ppo_model="offline-model", llm_max_calls=0,
                micro_max_units=4,
            )
            actor = Mock(metadata={"weights_sha256": "offline", "producer": {}})
            actor.action.return_value = Action.HOLD

            def base_init(bot, options, telemetry):
                bot.options, bot.telemetry = options, telemetry
                bot.state = SimpleNamespace(game_loop=0, dead_units=set())
                bot.strategy_state = "rally"
                bot.economy_status = {}
                bot.supply_army, bot.supply_workers = 10, 20

            with (
                patch.object(RuleBot, "__init__", base_init),
                patch("bot.llm_bot.Settings.load", return_value=SimpleNamespace(model="offline", base_url="offline")),
                patch("bot.llm_bot.Worker") as worker,
                patch("bot.micro_ppo.NumpyPPOPolicy.load", return_value=actor) as load,
            ):
                bot = run_local.create_bot(options, telemetry)
            self.assertIsInstance(bot, LLMPPOBot)
            load.assert_called_once_with("offline-model")
            worker.assert_called_once()
            self.assertTrue(bot._ppo_requested)
            self.assertFalse(bot.recorder.bc_labels)
            plan = Strategy("offline", 1, "pressure", 18, 1, "attack", "enemy_main", 6, "test")
            bot.director.offer(plan, 0, 0)
            bot._poll = Mock()
            bot.snapshot = Mock(return_value={})
            bot.attack_target = Mock(return_value="army-goal")
            context = Context(tuple([0] * 16), (False, False, False, False, True))
            calls = []

            def macro_and_combat(bot, iteration):
                # Test strategic request routing, not the independent local
                # saturation policy (covered in test_economy).
                calls.append((bot.requested_economic_goals(), bot.strategic_order(None)))
                self.assertEqual(bot.choose_micro_action(None, context), Action.HOLD)

            with (
                patch.object(RuleBot, "play_step", macro_and_combat),
                patch.object(LLMPPOBot, "ready_townhalls", new_callable=PropertyMock, return_value=[object()], create=True),
                patch.object(bot.recorder, "feedback") as feedback,
            ):
                bot.play_step(0)
            feedback.assert_called_once_with(bot.state)
            self.assertEqual(calls, [((18, 1), ("attack", "army-goal"))])
            self.assertIs(bot._plan, plan)
            self.assertEqual(bot.stats["llm_steps"], 1)
            self.assertEqual(telemetry.counts["ppo_inference_decisions"], 1)
            actor.action.assert_called_once()
            bot.recorder.close(0, "offline_check")

        # All pre-existing mode routes and the default stay unchanged.
        for modes, cls in [
            (("rule",), RuleBot), (("shadow", "llm"), StrategicBot),
            (("micro_rule", "rule_bc", "rule_ppo"), MicroRuleBot),
        ]:
            with patch.object(cls, "__init__", return_value=None):
                for mode in modes:
                    self.assertIs(type(run_local.create_bot(SimpleNamespace(mode=mode), None)), cls)
        output = io.StringIO()
        with patch("sys.argv", ["run_local.py", "--show-config"]), redirect_stdout(output):
            self.assertEqual(run_local.main(), 0)
        self.assertEqual(json.loads(output.getvalue())["mode"], "rule")


if __name__ == "__main__":
    unittest.main()
