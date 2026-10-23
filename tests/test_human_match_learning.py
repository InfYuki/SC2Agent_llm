"""Offline smoke: sampled synthetic transitions update weights, never launch SC2."""
import json
from pathlib import Path
import tempfile
import unittest

try:
    import gymnasium as gym
    import numpy as np
    import torch
    from sb3_contrib import MaskablePPO
except ImportError:
    gym = None

from tools.learn_human_match import learn, read_json, sha, write_json


@unittest.skipIf(gym is None, "Use the separate PPO training Python")
class HumanLearningSmoke(unittest.TestCase):
    def test_update_dedup_and_behavior_mismatch(self):
        from tools.export_micro_ppo import export_actor

        class EmptyEnv(gym.Env):
            observation_space = gym.spaces.Box(-1, 1, (16,), dtype=np.float32)
            action_space = gym.spaces.Discrete(5)

        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "source"
            source.mkdir()
            model = MaskablePPO("MlpPolicy", EmptyEnv(), n_steps=8, batch_size=8,
                                policy_kwargs={"net_arch": {"pi": [64, 64], "vf": [64, 64]},
                                               "activation_fn": torch.nn.Tanh}, seed=7, device="cpu")
            checkpoint = source / "model.zip"
            model.save(checkpoint)
            actor = source / "actor"
            actor_meta = export_actor(model, checkpoint, actor)
            run = root / "match"
            run.mkdir()
            from tools.human_learning_approval import decide
            decide(run, "yes")
            write_json(run / "summary.json", dict(status="completed", result="Result.Defeat",
                                                  stop_reason=None, error=None, game_span_seconds=120))
            write_json(run / "human_training.json", dict(
                format="human-match-training-v1", enemy_race="Terran",
                checkpoint_sha256=sha(checkpoint), actor=str(actor),
                actor_weights_sha256=actor_meta["weights_sha256"],
                sampling="stochastic-masked-categorical-v1"))
            rows = []
            rng = np.random.default_rng(3)
            observations = rng.uniform(-0.4, 0.4, size=(9, 16)).astype(np.float32)
            for index in range(8):
                obs = torch.tensor(observations[index:index + 1])
                mask = np.array([[True, False, True, True, True]])
                with torch.no_grad():
                    distribution = model.policy.get_distribution(obs, action_masks=mask)
                    action = distribution.get_actions()
                    logp = distribution.log_prob(action)
                rows.append(dict(trajectory_id="unit:ownership", step=index,
                                 obs=observations[index].tolist(), mask=mask[0].tolist(),
                                 action=int(action.item()), old_log_prob=float(logp.item()),
                                 reward=(-0.3 if index % 2 else 0.2),
                                 next_obs=observations[index + 1].tolist(), next_mask=mask[0].tolist(),
                                 terminated=index == 7, truncated=False,
                                 game_loop=index * 8, next_game_loop=(index + 1) * 8))
            (run / "human_ppo_rollout.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            output, memory = root / "candidate", root / "memory"
            report = learn(run, checkpoint, output, memory)
            self.assertEqual(report["ppo"]["status"], "updated", report)
            self.assertNotEqual(report["ppo"]["actor_before_sha256"], report["ppo"]["actor_after_sha256"])
            self.assertTrue((output / "actor" / "weights.npz").is_file())
            pointer = (memory / "ppo_latest.json").read_bytes()
            repeated = learn(run, checkpoint, root / "duplicate", memory)
            self.assertEqual(repeated["ppo"]["status"], "already_consumed")
            self.assertEqual(read_json(memory / "strategy_memory.json")["matches_seen"], 1)
            self.assertEqual((memory / "ppo_latest.json").read_bytes(), pointer)
            bad_run = root / "mismatch"
            bad_run.mkdir()
            for name in ("summary.json", "human_training.json"):
                (bad_run / name).write_bytes((run / name).read_bytes())
            rows[0]["old_log_prob"] += 0.5
            (bad_run / "human_ppo_rollout.jsonl").write_text(
                "\n".join(json.dumps(row) for row in rows), encoding="utf-8")
            failed = learn(bad_run, checkpoint, root / "bad_candidate", memory)
            self.assertEqual(failed["ppo"]["status"], "failed")
            self.assertEqual(failed["llm"]["status"], "updated")
            self.assertEqual((memory / "ppo_latest.json").read_bytes(), pointer)


if __name__ == "__main__":
    unittest.main()
