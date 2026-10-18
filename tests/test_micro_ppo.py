"""One cheap in-memory PPO/checkpoint check; never starts SC2."""
import json
from pathlib import Path
import tempfile
import unittest

from sb3_contrib import MaskablePPO

import gymnasium as gym
import numpy as np

from envs.gym_sc2_micro_env import RolloutDiscardError
from tools.train_micro_ppo import policy_sha256, train


class TinyMaskedEnv(gym.Env):
    observation_space = gym.spaces.Box(-1, 1, (16,), dtype=np.float32)
    action_space = gym.spaces.Discrete(5)

    def __init__(self, failure=False):
        self.failure = failure
        self.episode = 0

    def action_masks(self):
        return np.array([True, False, False, False, True])

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        self.episode += 1
        self.step_count = 0
        return np.full(16, 0.25, dtype=np.float32), {}

    def step(self, action):
        if self.failure:
            raise RolloutDiscardError(dict(system_failure=True, rollout_discard=True,
                                          reason="injected_worker_failure"))
        self.step_count += 1
        info = dict(episode_id=str(self.episode), decision_id=self.step_count,
                    frame=self.step_count * 8, output_dir="in-memory-test",
                    reason="fixture_end" if self.step_count == 4 else None,
                    official_close_confirmed=True)
        return (np.full(16, 0.25, dtype=np.float32),
                1.0 if action == 0 else -0.25, self.step_count == 4, False, info)


class PPOCheckpointTest(unittest.TestCase):
    def test_resume_preserves_parent_optimizer_and_cumulative_steps(self):
        with tempfile.TemporaryDirectory() as directory:
            parent = Path(directory) / "parent"
            train(parent, worker_python="unused-fixture", environment=TinyMaskedEnv())
            original = (parent / "model.zip").read_bytes()
            parent_model = MaskablePPO.load(parent / "model.zip", device="cpu")
            child = Path(directory) / "child"
            report = train(child, resume=parent, worker_python="unused-fixture",
                           environment=TinyMaskedEnv())
            self.assertEqual((report["initial_timesteps"], report["additional_steps"],
                              report["cumulative_timesteps"]), (32, 32, 64))
            self.assertEqual(report["initial_policy_sha256"], policy_sha256(parent_model))
            self.assertEqual(report["initial_updates"], parent_model._n_updates)
            self.assertTrue(report["optimizer_steps_before"])
            self.assertEqual(report["optimizer_steps_before"], [int(state["step"]) for state in
                             parent_model.policy.optimizer.state.values() if "step" in state])
            self.assertTrue(all(after > before for before, after in zip(
                report["optimizer_steps_before"], report["optimizer_steps_after"])))
            self.assertEqual(report["hyperparameter_source"], "parent_checkpoint")
            self.assertEqual(report["reload"]["probability_max_abs_error"], 0)
            self.assertEqual(MaskablePPO.load(child / "model.zip").num_timesteps, 64)
            self.assertEqual((parent / "model.zip").read_bytes(), original)
            rows = [json.loads(line) for line in
                    (child / "training_transitions.jsonl").read_text().splitlines()]
            self.assertEqual((rows[0]["step"], rows[-1]["step"]), (33, 64))
            with self.assertRaisesRegex(ValueError, "conflicting override"):
                train(Path(directory) / "conflict", resume=parent / "model.zip", n_steps=64,
                      worker_python="unused-fixture", environment=TinyMaskedEnv())
            failed = Path(directory) / "failed"
            with self.assertRaises(RolloutDiscardError):
                train(failed, resume=parent / "model.zip", worker_python="unused-fixture",
                      environment=TinyMaskedEnv(failure=True))
            self.assertFalse((failed / "model.zip").exists())
            self.assertEqual((parent / "model.zip").read_bytes(), original)

    def test_update_reload_and_failed_rollout(self):
        with tempfile.TemporaryDirectory() as directory:
            good = Path(directory) / "good"
            report = train(good, worker_python="unused-fixture", environment=TinyMaskedEnv())
            self.assertEqual(report["actual_steps"], 32)
            self.assertTrue(report["actor_parameters_changed"])
            self.assertTrue(report["reload"]["masked_action_equal"])
            self.assertLessEqual(report["reload"]["probability_max_abs_error"], 1e-7)
            self.assertTrue((good / "model.zip").exists())
            bad = Path(directory) / "bad"
            with self.assertRaises(RolloutDiscardError):
                train(bad, worker_python="unused-fixture", environment=TinyMaskedEnv(failure=True))
            self.assertFalse((bad / "model.zip").exists())
            failed = json.loads((bad / "failed_report.json").read_text(encoding="utf-8"))
            self.assertEqual(failed["successful_steps_observed"], 0)
            self.assertTrue(failed["failure_info"]["rollout_discard"])


if __name__ == "__main__":
    unittest.main()
