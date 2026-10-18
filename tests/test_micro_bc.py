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
from bot.micro_bc import NumpyBCPolicy, POLICY_VERSION, SHAPES
from bot.micro_bot import MicroRuleBot
from bot.rule_bot import RuleBot


class MicroBCTests(unittest.TestCase):
    def model(self, directory):
        weights = {key: np.zeros(shape, dtype=np.float32) for key, shape in SHAPES.items()}
        weights["b3"][:] = [10, 9, 8, 7, 6]
        np.savez(directory / "weights.npz", **weights)
        metadata = dict(
            format=POLICY_VERSION, feature_version="marine-16-v1",
            action_version="marine-5-v1", decision_game_loops=8,
            architecture=[16, 64, 64, 5], activation="tanh",
            normalization="marine-16-v1", prototype=True,
            weights_sha256=hashlib.sha256((directory / "weights.npz").read_bytes()).hexdigest(),
        )
        (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
        return metadata

    def test_load_forward_and_masked_argmax(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.model(directory)
            policy = NumpyBCPolicy.load(directory)
            np.testing.assert_array_equal(policy.logits([0] * 16), [10, 9, 8, 7, 6])
            self.assertEqual(policy.action([0] * 16, [False, False, True, True, True]), 2)

    def test_corrupt_weights_and_contract_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            metadata = self.model(directory)
            with (directory / "weights.npz").open("ab") as stream:
                stream.write(b"changed")
            with self.assertRaisesRegex(ValueError, "hash"):
                NumpyBCPolicy.load(directory)
            self.model(directory)
            metadata["feature_version"] = "future"
            (directory / "metadata.json").write_text(json.dumps(metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "contract"):
                NumpyBCPolicy.load(directory)

    def test_invalid_mask_and_nonfinite_observation_rejected(self):
        with tempfile.TemporaryDirectory() as tmp:
            directory = Path(tmp)
            self.model(directory)
            policy = NumpyBCPolicy.load(directory)
            for mask in ([True] * 4, [False] * 5, [1] * 5):
                with self.subTest(mask=mask), self.assertRaises(ValueError):
                    policy.action([0] * 16, mask)
            with self.assertRaises(ValueError):
                policy.action([float("nan")] * 16, [True] * 5)

    def test_fallback_once_and_bc_records_never_expert_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            telemetry = SimpleNamespace(output=Path(tmp), event=Mock(), counts=__import__("collections").Counter())
            options = SimpleNamespace(seed=42, mode="rule_bc", bc_model=str(Path(tmp) / "missing"))

            def base_init(bot, options, telemetry):
                bot.options, bot.telemetry = options, telemetry

            with patch.object(RuleBot, "__init__", base_init):
                bot = MicroRuleBot(options, telemetry)
            ctx = Context(tuple([0] * 16), (False, False, False, False, True))
            with patch("bot.micro_bot.expert", return_value=Action.HOLD):
                self.assertEqual(bot.choose_micro_action(None, ctx), Action.HOLD)
                policy = Mock()
                policy.action.side_effect = ValueError("bad inference")
                bot._bc_policy = policy
                for _ in range(2):
                    self.assertEqual(bot.choose_micro_action(None, ctx), Action.HOLD)
                self.assertEqual(policy.action.call_count, 1)
            self.assertEqual(telemetry.counts["bc_load_fallback"], 1)
            self.assertEqual(telemetry.counts["bc_inference_fallback"], 1)
            bot.recorder.begin(1, 8, ctx, Action.HOLD, Action.HOLD, "hold")
            bot.recorder.finish(1, 16, ctx)
            bot.recorder.close(16, "test")
            row = json.loads((Path(tmp) / "micro_transitions.jsonl").read_text())
            self.assertFalse(row["bc_eligible"])
            self.assertIsNone(row["versions"]["expert"])
            self.assertEqual(row["versions"]["policy"], POLICY_VERSION)


if __name__ == "__main__":
    unittest.main()
