"""One focused production ownership check; no game, training, or API calls."""
from collections import Counter
from contextlib import redirect_stdout
import io
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import run_local
from bot.arbiter import OrderArbiter
from bot.micro import Action, Context
from bot.micro_bot import MicroRuleBot
from bot.ppo_engagement import engagement_check
from bot.rule_bot import RuleBot


class PPOEngagementGateTest(unittest.TestCase):
    def test_gate_geometry_ownership_macro_and_configuration(self):
        def enemy(distance, ground_range=0.1, tag=2):
            return SimpleNamespace(tag=tag, distance=distance, ground_range=ground_range, radius=0.5)

        unit = SimpleNamespace(tag=1, weapon_cooldown=0, ground_range=5, radius=0.5,
                               health_percentage=1, is_idle=False, attack=Mock(return_value=True))
        unit.distance_to = lambda other: other.distance
        cases = [
            ("far_ready", (enemy(9),), 0, False, False, "ready_outside_engagement"),
            ("close", (enemy(6.5),), 0, False, True, "own_attack_range"),
            ("cooldown", (enemy(9),), 4, False, True, "cooldown_active"),
            ("nonnearest_threat", (enemy(8), enemy(9, 8, 3)), 0, False, True, "enemy_threat_range"),
            ("exit_buffer", (enemy(7.3),), 0, True, True, "own_attack_range"),
            ("entry_buffer", (enemy(7.3),), 0, False, False, "ready_outside_engagement"),
            ("unknown", (enemy(9, float("nan")),), 0, False, True, "unknown_geometry"),
            ("missing", (SimpleNamespace(tag=2),), 0, False, True, "unknown_geometry"),
        ]
        for name, enemies, cooldown, owned, accepted, reason in cases:
            with self.subTest(case=name):
                unit.weapon_cooldown = cooldown
                check = engagement_check(unit, enemies, owned)
                self.assertEqual((check["accepted"], check["reason"]), (accepted, reason))
                json.dumps(check, allow_nan=False)

        for mode in ("rule_ppo", "llm_ppo"):
            for enabled in (False, True):
                output = io.StringIO()
                args = ["run_local.py", "--mode", mode, "--show-config"]
                if enabled:
                    args.append("--ppo-engagement-gate")
                with patch("sys.argv", args), redirect_stdout(output):
                    self.assertEqual(run_local.main(), 0)
                self.assertEqual(json.loads(output.getvalue())["ppo_engagement_gate"], enabled)

        with tempfile.TemporaryDirectory() as tmp:
            telemetry = SimpleNamespace(output=Path(tmp), counts=Counter(), event=Mock())
            options = SimpleNamespace(seed=42, mode="rule_ppo", ppo_model="offline", micro_max_units=1,
                                      ppo_engagement_gate=True)
            policy = Mock(metadata=dict(weights_sha256="offline", producer={}))
            policy.action.return_value = Action.HOLD

            def base_init(bot, options, telemetry):
                bot.options, bot.telemetry = options, telemetry
                bot.arbiter, bot._last_order = OrderArbiter(), {}

            with patch.object(RuleBot, "__init__", base_init), patch("bot.micro_ppo.NumpyPPOPolicy.load", return_value=policy):
                bot = MicroRuleBot(options, telemetry)
            goal = SimpleNamespace(x=50, y=60)
            unit.weapon_cooldown = 0

            def ctx(enemies):
                return Context((0,) * 16, (False, False, True, True, True), enemies=enemies, supported=True)

            def execute(unit, context, action, *args):
                bot.recorder.begin(unit.tag, args[-1], context, action, action, "hold")

            bot._execute_micro = execute
            with patch("bot.micro_bot.context", return_value=ctx((enemy(6),))):
                bot.issue_combat_orders([unit], "attack", goal, 32)
            self.assertEqual(bot.controlled, {1})
            self.assertEqual(policy.action.call_count, 1)
            # Even a recent cached macro order must be cleared on owner release.
            bot._last_order[1] = (("attack", 50, 60), 32)
            with patch("bot.micro_bot.context", return_value=ctx((enemy(9),))):
                bot.issue_combat_orders([unit], "attack", goal, 40)
            self.assertEqual(bot.controlled, set())
            self.assertEqual(policy.action.call_count, 1)
            unit.attack.assert_called_once_with(goal)
            self.assertEqual(telemetry.counts["micro_owned_decisions"], 1)
            self.assertEqual(telemetry.counts["ppo_engagement_ready_outside_engagement"], 1)
            self.assertEqual(bot._released_at[1], 40)
            self.assertFalse(bot.recorder.pending)
            rows = [json.loads(line) for line in (Path(tmp) / "micro_transitions.jsonl").read_text().splitlines()]
            self.assertEqual((rows[0]["actual_game_loops"], rows[0]["truncated"], rows[0]["end_reason"]),
                             (8, True, "control_released"))
            # Opt out restores the former far-ready ownership and actor path.
            bot._ppo_engagement_gate = False
            with patch("bot.micro_bot.context", return_value=ctx((enemy(9),))):
                bot.issue_combat_orders([unit], "attack", goal, 56)
            self.assertEqual(bot.controlled, {1})
            self.assertEqual(policy.action.call_count, 2)
            bot.recorder.close(56, "test")


if __name__ == "__main__":
    unittest.main()
