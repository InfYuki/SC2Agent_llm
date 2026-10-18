"""Tiny real-SC2 MaskablePPO update and checkpoint round trip (CPU).

Run with the separate training interpreter; --worker-python selects the locked
Ares runtime. This is a randomly initialized engineering baseline, not BC or a
combat-strength evaluation. No dependency installation happens here.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

try:
    import numpy as np
    import torch
    from sb3_contrib import MaskablePPO
    from stable_baselines3.common.callbacks import BaseCallback
    from envs.gym_sc2_micro_env import GymSC2MicroEnv
except ModuleNotFoundError as exc:
    raise SystemExit(
        "Use the separate training Python with requirements-ppo.txt installed; "
        f"missing dependency: {exc.name}"
    ) from exc


def write_json(path, value):
    path.write_text(json.dumps(value, indent=2, allow_nan=False), encoding="utf-8")


def probe(model, obs, mask):
    with torch.no_grad():
        tensor, _ = model.policy.obs_to_tensor(obs)
        probabilities = model.policy.get_distribution(
            tensor, action_masks=mask
        ).distribution.probs.cpu().numpy()[0]
    action, _ = model.predict(obs, action_masks=mask, deterministic=True)
    action = int(action)
    if not np.isfinite(probabilities).all() or not mask[action]:
        raise ValueError("Non-finite policy or masked prediction")
    if np.any(probabilities[~mask] != 0):
        raise ValueError("Policy assigned probability to a masked action")
    return probabilities, action


class TraceCallback(BaseCallback):
    def __init__(self, environment, destination):
        super().__init__()
        self.environment = environment
        self.destination = destination
        self.rows = []
        self.episodes = []
        self.episode_rewards = {}
        self.probe_obs = self.probe_mask = None

    def _on_training_start(self):
        # learn() has reset once already; probing must not launch another game.
        self.probe_obs = self.model._last_obs[0].copy()
        self.probe_mask = self.environment.action_masks().copy()

    def _on_step(self):
        info = self.locals["infos"][0]
        episode_id = info["episode_id"]
        reward = float(self.locals["rewards"][0])
        self.episode_rewards[episode_id] = self.episode_rewards.get(episode_id, 0.0) + reward
        mask = np.asarray(self.locals["action_masks"][0], dtype=bool)
        action = int(self.locals["actions"][0])
        if not mask[action]:
            raise ValueError("Training selected a masked action")
        row = dict(step=self.num_timesteps, episode_id=episode_id,
                   decision_id=info["decision_id"], frame=info["frame"],
                   previous_frame=info.get("previous_frame"),
                   actual_game_loops=info.get("actual_game_loops"),
                   action=action, action_mask=mask.tolist(), reward=reward,
                   done=bool(self.locals["dones"][0]),
                   reason=info.get("reason"), output_dir=info["output_dir"],
                   system_failure=bool(info.get("system_failure")),
                   rollout_discard=bool(info.get("rollout_discard")))
        self.rows.append(row)
        with self.destination.open("a", encoding="utf-8") as stream:
            stream.write(json.dumps(row, allow_nan=False) + "\n")
        if row["done"]:
            self.episodes.append(dict(
                episode_id=episode_id, steps=sum(r["episode_id"] == episode_id for r in self.rows),
                reward=self.episode_rewards[episode_id], reason=info.get("reason"),
                time_limit_truncated=bool(info.get("TimeLimit.truncated")),
                official_close_confirmed=bool(info.get("official_close_confirmed")),
                worker_close=info.get("worker_close"),
                output_dir=info["output_dir"],
            ))
        return True


def train(output, *, worker_python, game_path=r"C:\Program Files (x86)\StarCraft II",
          map_name="Ancient Cistern LE", max_game_seconds=8, seed=42,
          total_timesteps=32, n_steps=32, batch_size=16, n_epochs=2,
          learning_rate=3e-4, environment=None):
    if n_steps < 2 or batch_size < 2 or n_steps % batch_size:
        raise ValueError("n_steps must be divisible by batch_size, both >= 2")
    if total_timesteps < n_steps or total_timesteps % n_steps or n_epochs < 1:
        raise ValueError("total_timesteps must be a positive multiple of n_steps; epochs >= 1")
    if not np.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    output = Path(output).resolve()
    output.mkdir(parents=True, exist_ok=False)
    started = time.monotonic()
    env = environment if environment is not None else GymSC2MicroEnv(
        worker_python=worker_python, game_path=game_path, map_name=map_name,
        max_game_seconds=max_game_seconds, output_root=output / "episodes")
    trace = TraceCallback(env, output / "training_transitions.jsonl")
    try:
        torch.set_num_threads(1)
        model = MaskablePPO(
            "MlpPolicy", env, n_steps=n_steps, batch_size=batch_size,
            n_epochs=n_epochs, learning_rate=learning_rate, gamma=0.99,
            gae_lambda=0.95, clip_range=0.2, seed=seed, device="cpu", verbose=1,
            policy_kwargs=dict(net_arch=dict(pi=[64, 64], vf=[64, 64]),
                               activation_fn=torch.nn.Tanh))
        initial = {key: value.detach().cpu().clone()
                   for key, value in model.policy.state_dict().items()}
        model.learn(total_timesteps=total_timesteps, callback=trace, use_masking=True)
        final = model.policy.state_dict()
        changes = {key: float(torch.max(torch.abs(value.cpu() - initial[key])))
                   for key, value in final.items()}
        finite = all(bool(torch.isfinite(value).all()) for value in final.values())
        actor_changed = any(value > 0 for key, value in changes.items()
                            if key.startswith(("mlp_extractor.policy_net", "action_net")))
        if not finite or not actor_changed or model._n_updates < 1:
            raise ValueError("No finite actor PPO update was demonstrated")
        probabilities, action = probe(model, trace.probe_obs, trace.probe_mask)
        # Write to an explicitly provisional name until reload verification passes.
        provisional = output / "model.pending.zip"
        model.save(provisional)
        reloaded = MaskablePPO.load(provisional, device="cpu")
        restored_probabilities, restored_action = probe(
            reloaded, trace.probe_obs, trace.probe_mask)
        probability_error = float(np.max(np.abs(probabilities - restored_probabilities)))
        if probability_error > 1e-7 or action != restored_action:
            raise ValueError("Saved policy failed probability/action round trip")
        checkpoint = output / "model.zip"
        provisional.rename(checkpoint)
        metadata = dict(
            format="marine-maskable-ppo-sb3-v1", feature_version="marine-16-v1",
            action_version="marine-5-v1", decision_game_loops=8,
            reward_version="effective-hp-delta-45-terminal-1-v1",
            normalization="marine-16-v1", actor_layers=[16, 64, 64, 5],
            critic_hidden_layers=[64, 64], activation="tanh", seed=seed,
            initialization="random", bc_weights_used=False, dataset=None,
            checkpoint_sha256=hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
            versions={name: version(name) for name in
                      ("numpy", "torch", "gymnasium", "stable-baselines3", "sb3-contrib")},
            training_python=sys.executable, worker_python=str(worker_python),
            training=dict(total_timesteps=total_timesteps, n_steps=n_steps,
                          batch_size=batch_size, n_epochs=n_epochs,
                          learning_rate=learning_rate, gamma=0.99, gae_lambda=0.95,
                          clip_range=0.2, device="cpu"),
            engineering_prototype=True, combat_strength_evaluated=False,
            deployment_exported=False)
        report = dict(
            status="success", actual_steps=model.num_timesteps,
            completed_episodes=trace.episodes, observed_episode_count=len(trace.episode_rewards),
            reward_sum=sum(row["reward"] for row in trace.rows),
            updates=model._n_updates, parameters_finite=finite,
            actor_parameters_changed=actor_changed, parameter_max_abs_changes=changes,
            reload=dict(probability_max_abs_error=probability_error,
                        masked_action_equal=action == restored_action,
                        action=action, observation=trace.probe_obs.tolist(),
                        mask=trace.probe_mask.tolist(), probabilities=probabilities.tolist()),
            training_metrics={key: float(value) for key, value in model.logger.name_to_value.items()
                              if key.startswith("train/") and np.isfinite(value)},
            wall_seconds=time.monotonic() - started,
            rollout_trace=str(trace.destination), checkpoint_sha256=metadata["checkpoint_sha256"],
            interpretation="Engineering update and reload only; no combat-strength evaluation."
        )
        write_json(output / "metadata.json", metadata)
        write_json(output / "training_report.json", report)
        return report
    except Exception as exc:
        # A later report/metadata failure must not leave a success-named model.
        checkpoint = output / "model.zip"
        if checkpoint.exists():
            checkpoint.rename(output / "model.failed.zip")
        write_json(output / "failed_report.json", dict(
            status="failed", error_type=type(exc).__name__, error=str(exc),
            failure_info=getattr(exc, "info", None),
            successful_steps_observed=len(trace.rows), completed_episodes=trace.episodes,
            wall_seconds=time.monotonic() - started, success_checkpoint_valid=False))
        # Do not swallow reset failures or train a system-failure truncation.
        raise
    finally:
        env.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--worker-python", type=Path, required=True)
    parser.add_argument("--game-path", default=r"C:\Program Files (x86)\StarCraft II")
    parser.add_argument("--map", default="Ancient Cistern LE")
    parser.add_argument("--max-game-seconds", type=float, default=8)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--total-timesteps", type=int, default=32)
    parser.add_argument("--n-steps", type=int, default=32)
    parser.add_argument("--batch-size", type=int, default=16)
    parser.add_argument("--n-epochs", type=int, default=2)
    parser.add_argument("--learning-rate", type=float, default=3e-4)
    args = parser.parse_args()
    print(json.dumps(train(
        args.output, worker_python=args.worker_python, game_path=args.game_path,
        map_name=args.map, max_game_seconds=args.max_game_seconds, seed=args.seed,
        total_timesteps=args.total_timesteps, n_steps=args.n_steps,
        batch_size=args.batch_size, n_epochs=args.n_epochs,
        learning_rate=args.learning_rate), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
