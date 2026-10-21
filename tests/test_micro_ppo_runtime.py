"""Focused checks for the Torch-free PPO deployment boundary."""
from collections import Counter
import hashlib
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import numpy as np
import run_local  # Ares import paths
from bot.micro import Action, Context
from bot.micro_bc import SHAPES
from bot.micro_bot import MicroRuleBot
from bot.micro_ppo import NumpyPPOPolicy, POLICY_VERSION, enemy_domain, enemy_domain_reason
from bot.rule_bot import RuleBot


class MicroPPORuntimeTests(unittest.TestCase):
    def test_optional_enemy_domain_guard_before_ownership(self):
        def task(scenario="marine-vs-zergling", count=1):
            return dict(scenario=scenario, enemy_count=count)

        def metadata(tasks):
            return dict(producer=dict(task=task(), curriculum=dict(
                format="marine-micro-curriculum-v1", selection="round-robin", tasks=tasks)))

        single = enemy_domain(metadata([task()]))  # current 256 declarations
        double = enemy_domain(metadata([task(), task(count=2)]))  # 448 declarations
        zergling = SimpleNamespace(type_id=SimpleNamespace(name="ZERGLING"))
        marine = SimpleNamespace(type_id=SimpleNamespace(name="MARINE"))
        ctx = Context(tuple([0] * 16), (True,) * 5,
                      enemies=(zergling, zergling), supported=True)
        self.assertEqual(enemy_domain_reason(single, ctx), "outside_domain")
        self.assertEqual(enemy_domain_reason(double, ctx), "accepted")
        mixed = Context(ctx.obs, ctx.mask, enemies=(zergling, marine), supported=True)
        self.assertEqual(enemy_domain_reason(double, mixed), "mixed_enemies")
        pairs = enemy_domain(metadata([task(), task("marine-vs-marine", 2)]))
        self.assertEqual(enemy_domain_reason(pairs, ctx), "outside_domain")
        self.assertEqual(enemy_domain(dict(producer=dict(task=task())))["status"], "known")
        invalid = [
            {}, dict(producer={}),
            metadata([task(), {}]), metadata([task(), task(count=True)]),
            metadata([task(), task(count=1.0)]), metadata([task(count=9)]),
            metadata([task(count=3)]),
            metadata([task("unknown")]), metadata([]),
            dict(producer=dict(task=task(), curriculum=None)),
            dict(producer=dict(task=task(), curriculum=dict(
                format="marine-micro-curriculum-v1", tasks=[task()]))),
            dict(producer=dict(task=task(), curriculum=dict(
                format="marine-micro-curriculum-v1", selection="unknown", tasks=[task()]))),
        ]
        for value in invalid:
            with self.subTest(metadata=value):
                domain = enemy_domain(value)
                self.assertEqual(domain["status"], "unknown")
                self.assertEqual(domain["pairs"], [])
                self.assertEqual(enemy_domain_reason(domain, ctx), "unknown_domain")
        # Parent provenance and BC declarations never expand the current domain.
        value = metadata([task()])
        value["producer"]["task"] = task(count=2)
        value["producer"]["parent_task"] = task(count=2)
        self.assertEqual(enemy_domain(value), single)

        with tempfile.TemporaryDirectory() as tmp:
            telemetry = SimpleNamespace(output=Path(tmp), counts=Counter(), event=Mock())
            options = SimpleNamespace(seed=42, mode="llm_ppo", ppo_model="unused", micro_max_units=1)
            policy = Mock(metadata=metadata([task()]))
            policy.metadata["weights_sha256"] = "a" * 64
            policy.action.return_value = int(Action.HOLD)

            def base_init(bot, options, telemetry):
                bot.options, bot.telemetry = options, telemetry
                bot.arbiter, bot._last_order = Mock(), {}

            with patch.object(RuleBot, "__init__", base_init), patch.object(NumpyPPOPolicy, "load", return_value=policy):
                bot = MicroRuleBot(options, telemetry)
            self.assertFalse(bot._ppo_enemy_domain_guard)  # missing option stays compatible
            bot.issue_rule_order, bot._execute_micro = Mock(), Mock()
            unit = SimpleNamespace(tag=1, health_percentage=1)
            for domain, context_value, enabled, accepted in [
                (single, ctx, True, False), (double, ctx, True, True),
                (double, mixed, True, False), (enemy_domain({}), ctx, True, False),
                (enemy_domain({}), ctx, False, True),
            ]:
                with self.subTest(domain=domain, enabled=enabled, accepted=accepted):
                    bot._ppo_enemy_domain, bot._ppo_enemy_domain_guard = domain, enabled
                    bot.controlled, bot._released_at = set(), {}
                    policy.action.reset_mock()
                    bot.issue_rule_order.reset_mock()
                    with patch("bot.micro_bot.context", return_value=context_value):
                        bot.issue_combat_orders([unit], "attack", None, 32)
                    self.assertEqual(bot.controlled, {1} if accepted else set())
                    self.assertEqual(policy.action.call_count, int(accepted))
                    self.assertEqual(bot.issue_rule_order.call_count, int(not accepted))
            self.assertEqual(telemetry.counts["micro_owned_decisions"], 2)
            self.assertEqual(telemetry.counts["ppo_inference_decisions"], 2)
            self.assertEqual(telemetry.counts["ppo_enemy_domain_outside_domain"], 1)
            self.assertEqual(telemetry.counts["ppo_enemy_domain_unknown_domain"], 1)
            self.assertEqual(telemetry.counts["ppo_rule_fallback_decisions"], 0)
            bot.recorder.close(32, "test")

    def test_hash_provenance_and_masked_actor(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            weights = {key: np.zeros(shape, np.float32) for key, shape in SHAPES.items()}
            weights["b3"][:] = [10, 9, 8, 7, 6]
            np.savez(directory / "weights.npz", **weights)
            metadata = dict(
                format=POLICY_VERSION, feature_version="marine-16-v1",
                action_version="marine-5-v1", decision_game_loops=8,
                architecture=[16, 64, 64, 5], activation="tanh",
                normalization="marine-16-v1",
                weights_sha256=hashlib.sha256((directory / "weights.npz").read_bytes()).hexdigest(),
                producer=dict(algorithm="MaskablePPO", source_checkpoint_sha256="a" * 64,
                              versions={key: "test" for key in
                                        ("torch", "stable-baselines3", "sb3-contrib", "numpy")}),
            )
            path = directory / "metadata.json"
            path.write_text(json.dumps(metadata), encoding="utf-8")
            policy = NumpyPPOPolicy.load(directory)
            mask = [False, False, True, True, True]
            self.assertEqual(policy.action([0] * 16, mask), 2)
            probabilities = policy.probabilities([0] * 16, mask)
            np.testing.assert_array_equal(probabilities[:2], [0, 0])
            self.assertAlmostEqual(float(probabilities.sum()), 1.0, places=6)
            for bad in ([1] * 5, [False] * 5, [True] * 4):
                with self.assertRaises(ValueError):
                    policy.action([0] * 16, bad)
            metadata["producer"]["algorithm"] = "BC"
            path.write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "provenance"):
                NumpyPPOPolicy.load(directory)
            metadata["producer"]["algorithm"] = "MaskablePPO"
            path.write_text(json.dumps(metadata), encoding="utf-8")
            with (directory / "weights.npz").open("ab") as stream:
                stream.write(b"corrupt")
            with self.assertRaisesRegex(ValueError, "PPO weights hash"):
                NumpyPPOPolicy.load(directory)

    def test_fallback_and_records_keep_ppo_provenance(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = SimpleNamespace(output=Path(tmp), counts=Counter(), event=Mock())
            options = SimpleNamespace(seed=42, mode="rule_ppo", ppo_model=str(Path(tmp) / "missing"))

            def base_init(bot, options, telemetry):
                bot.options, bot.telemetry = options, telemetry

            with patch.object(RuleBot, "__init__", base_init):
                bot = MicroRuleBot(options, telemetry)
            ctx = Context(tuple([0] * 16), (False, False, False, False, True))
            with patch("bot.micro_bot.expert", return_value=Action.HOLD):
                self.assertEqual(bot.choose_micro_action(None, ctx), Action.HOLD)
                broken = Mock()
                broken.action.side_effect = ValueError("bad inference")
                bot._ppo_policy = broken
                for _ in range(2):
                    self.assertEqual(bot.choose_micro_action(None, ctx), Action.HOLD)
                self.assertEqual(broken.action.call_count, 1)
            self.assertEqual(telemetry.counts["ppo_load_fallback"], 1)
            self.assertEqual(telemetry.counts["ppo_inference_fallback"], 1)
            self.assertEqual(telemetry.counts["ppo_rule_fallback_decisions"], 3)
            bot.recorder.begin(1, 8, ctx, Action.HOLD, Action.HOLD, "hold")
            bot.recorder.finish(1, 16, ctx)
            bot.recorder.close(16, "test")
            row = json.loads((Path(tmp) / "micro_transitions.jsonl").read_text())
            self.assertFalse(row["bc_eligible"])
            self.assertIsNone(row["versions"]["expert"])
            self.assertEqual(row["versions"]["policy"], POLICY_VERSION)


if __name__ == "__main__":
    unittest.main()
