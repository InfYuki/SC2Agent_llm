"""One combined offline parity check; no training, game, worker or network."""
import copy
import json
from pathlib import Path
import shutil
import tempfile
import unittest

import gymnasium as gym
import numpy as np
from sb3_contrib import MaskablePPO

from tools.export_micro_ppo import export_actor
from tools.verify_micro_ppo_parity import (
    collect_sources, judge, load_pair, masked_probabilities, validate_row, verify,
)


class InMemoryEnv(gym.Env):
    observation_space = gym.spaces.Box(-1, 1, (16,), dtype=np.float32)
    action_space = gym.spaces.Discrete(5)


class PPOParityTest(unittest.TestCase):
    def test_combined_offline_contract_parity_and_accounting(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            checkpoint, actor = root / "checkpoint.zip", root / "actor"
            model = MaskablePPO("MlpPolicy", InMemoryEnv(), seed=42, device="cpu",
                                policy_kwargs=dict(net_arch=dict(pi=[64, 64], vf=[64, 64])))
            model.save(checkpoint)
            export_actor(model, checkpoint, actor)
            row = dict(obs=[0.25] * 16, mask=[True, False, True, False, True],
                       versions=dict(feature="marine-16-v1", action="marine-5-v1",
                                     decision_game_loops=8, policy="other-raw-producer"),
                       next_obs=[1.] * 16, bc_eligible=False, reward=None,
                       secret_should_not_be_copied="private")
            source = root / "micro_transitions.jsonl"
            source.write_text(json.dumps(row) + "\n" + json.dumps(row) + "\n", encoding="utf-8")
            copied = root / "copy" / "micro_transitions.jsonl"
            copied.parent.mkdir()
            shutil.copyfile(source, copied)
            report = verify(checkpoint, actor, [source, source, copied], min_real_samples=2)
            self.assertTrue(report["passed"])
            self.assertFalse(report["real_sample_threshold_met"])
            self.assertEqual(report["acceptance_mode"], "explicit_small_sample")
            self.assertEqual(report["real"]["samples"], 2)
            self.assertEqual(report["real"]["unique_observations"], 1)
            self.assertEqual(report["real"]["unique_observation_masks"], 1)
            self.assertEqual(len(report["duplicate_sources"]), 2)
            self.assertEqual(report["real"]["observations"][1]["line"], 2)
            self.assertNotIn("private", json.dumps(report))
            self.assertEqual(report["synthetic"]["samples"], 8)
            self.assertTrue(report["synthetic"]["passed"])
            self.assertTrue(any(c["case"] == "minus_one/hold_only" for c in report["synthetic"]["cases"]))
            default_report = verify(checkpoint, actor, [source])
            self.assertFalse(default_report["passed"])
            self.assertEqual(default_report["minimum_real"]["status"], "not_met")
            self.assertEqual(default_report["real"]["samples"], 2)

            # No parameter changes are needed to exercise tie classification.
            mask = np.array([True, True, False, False, True])
            left = np.array([1., 1. - 1e-8, 0., 0., 0.])
            right = np.array([1. - 1e-8, 1., 0., 0., 0.])
            tied = judge(left, right, masked_probabilities(left, mask),
                         masked_probabilities(right, mask), mask, 1e-4, 1e-6)
            self.assertTrue(tied["near_tie"])
            self.assertFalse(tied["action_match"])
            self.assertFalse(tied["passed"])
            exact = judge(left, left, masked_probabilities(left, mask),
                          masked_probabilities(left, mask), mask, 1e-4, 1e-6)
            self.assertTrue(exact["near_tie"] and exact["passed"])
            rounded_logits = np.array([1. - 1e-8, 1., 0., 0., 0.])
            rounded_probs = np.array([0.5, 0.5, 0., 0., 0.])
            rounded = judge(rounded_logits, rounded_logits, rounded_probs,
                            rounded_probs, mask, 1e-4, 1e-6)
            self.assertEqual((rounded["sb3_action"], rounded["numpy_action"]), (0, 1))
            self.assertFalse(rounded["passed"])

            for patch in (dict(obs=[True] * 16), dict(obs=[float("nan")] * 16),
                          dict(obs=[1.01] * 16), dict(obs=[0.] * 15),
                          dict(mask=[1] * 5), dict(mask=[False] * 5),
                          dict(mask=[True] * 4 + [False]), dict(versions={})):
                with self.subTest(patch=patch), self.assertRaises(ValueError):
                    validate_row(dict(row, **patch))
            source.write_text(json.dumps(row) + "\n{broken\n" + json.dumps(dict(row, obs=[float("inf")] * 16)), encoding="utf-8")
            sources, duplicates, samples, invalid = collect_sources([source])
            self.assertEqual((len(samples), len(invalid), sources[0]["lines"]), (1, 2, 3))
            bad_report = verify(checkpoint, actor, [source], min_real_samples=1)
            self.assertFalse(bad_report["passed"])
            self.assertEqual([item["line"] for item in bad_report["real"]["invalid"]], [2, 3])
            metadata_path = actor / "metadata.json"
            metadata = json.loads(metadata_path.read_text())
            bad_metadata = copy.deepcopy(metadata)
            bad_metadata["producer"]["source_checkpoint_sha256"] = "0" * 64
            metadata_path.write_text(json.dumps(bad_metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "SHA256"):
                load_pair(checkpoint, actor)
            bad_metadata = copy.deepcopy(metadata)
            bad_metadata["producer"]["versions"]["numpy"] = "unsupported"
            metadata_path.write_text(json.dumps(bad_metadata), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "versions"):
                load_pair(checkpoint, actor)
            metadata_path.write_text(json.dumps(dict(metadata, normalization="wrong")), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "normalization"):
                load_pair(checkpoint, actor)


if __name__ == "__main__":
    unittest.main()
