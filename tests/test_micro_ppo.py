"""One cheap in-memory PPO/checkpoint check; never starts SC2."""
import json
from pathlib import Path
import tempfile
import unittest

from sb3_contrib import MaskablePPO

import gymnasium as gym
import numpy as np
import torch

from envs.gym_sc2_micro_env import RolloutDiscardError
from tools.train_micro_ppo import initialize_bc_actor, policy_sha256, resume_checkpoint, train
from tools.train_micro_bc import initialize


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
    def test_bc_actor_transfer_and_exclusive_initialization(self):
        import hashlib
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            bc, dataset = root / "bc", root / "dataset"
            bc.mkdir()
            dataset.mkdir()
            weights = initialize(5)
            np.savez(bc / "weights.npz", **weights)
            count = 6
            obs = np.random.default_rng(3).uniform(-1, 1, (count, 16)).astype(np.float32)
            masks = np.array([[True, False, True, False, True]] * count)
            np.savez(dataset / "demonstrations.npz", obs=obs, mask=masks,
                     action=np.zeros(count, dtype=np.int64),
                     group=np.array(["a", "a", "b", "b", "c", "c"]),
                     split=np.array(["train", "train", "validation", "validation", "test", "test"]))
            sha = lambda path: hashlib.sha256(path.read_bytes()).hexdigest()
            contract = dict(feature_version="marine-16-v1", action_version="marine-5-v1",
                            decision_game_loops=8)
            splits = dict(train=2, validation=2, test=2)
            (dataset / "metadata.json").write_text(json.dumps(dict(
                **contract, dataset_sha256=sha(dataset / "demonstrations.npz"),
                samples=count, split_counts=splits,
                group_splits=dict(a="train", b="validation", c="test"))))
            metadata = dict(**contract, format="marine-bc-numpy-v1", architecture=[16, 64, 64, 5],
                            activation="tanh", normalization="marine-16-v1",
                            weights_sha256=sha(bc / "weights.npz"),
                            dataset_sha256=sha(dataset / "demonstrations.npz"),
                            dataset_metadata_sha256=sha(dataset / "metadata.json"), sample_counts=splits)
            (bc / "metadata.json").write_text(json.dumps(metadata))
            model = MaskablePPO("MlpPolicy", TinyMaskedEnv(), n_steps=32, batch_size=16,
                seed=42, policy_kwargs=dict(net_arch=dict(pi=[64, 64], vf=[64, 64]),
                                           activation_fn=torch.nn.Tanh))
            critic = {key: value.clone() for key, value in model.policy.state_dict().items()
                      if key.startswith(("mlp_extractor.value_net", "value_net"))}
            transfer = initialize_bc_actor(model, bc, dataset)
            self.assertEqual(transfer["parity_samples"], count)
            self.assertLess(transfer["logits_max_abs_error"], 1e-5)
            self.assertLess(transfer["masked_probability_max_abs_error"], 1e-6)
            self.assertTrue(transfer["masked_actions_equal"])
            for index, layer in enumerate((model.policy.mlp_extractor.policy_net[0],
                    model.policy.mlp_extractor.policy_net[2], model.policy.action_net), 1):
                np.testing.assert_array_equal(layer.weight.detach().numpy(), weights[f"w{index}"].T)
                np.testing.assert_array_equal(layer.bias.detach().numpy(), weights[f"b{index}"])
            self.assertTrue(all(torch.equal(value, model.policy.state_dict()[key])
                                for key, value in critic.items()))
            self.assertFalse(model.policy.optimizer.state)
            original = (bc / "weights.npz").read_bytes()
            report = train(root / "warmstart", init_bc=bc, init_bc_dataset=dataset,
                           worker_python="unused-fixture", environment=TinyMaskedEnv())
            self.assertEqual(report["initialization"], "bc_actor")
            self.assertEqual(report["initial_timesteps"], 0)
            self.assertFalse(report["optimizer_steps_before"])
            self.assertTrue(report["parameters_finite"] and report["actor_parameters_changed"])
            checkpoint, saved_metadata, _ = resume_checkpoint(root / "warmstart")
            self.assertEqual(checkpoint.name, "model.zip")
            self.assertTrue(saved_metadata["bc_weights_used"])
            self.assertEqual(saved_metadata["bc_initialization"]["weights_sha256"],
                             metadata["weights_sha256"])
            self.assertTrue((root / "warmstart" / "initialization_report.json").exists())
            self.assertEqual((bc / "weights.npz").read_bytes(), original)
            with self.assertRaisesRegex(ValueError, "mutually exclusive"):
                train(root / "invalid", resume="unused", init_bc=bc, worker_python="unused")
            metadata["normalization"] = "unsupported"
            (bc / "metadata.json").write_text(json.dumps(metadata))
            with self.assertRaisesRegex(ValueError, "normalization"):
                initialize_bc_actor(model, bc, dataset)

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
