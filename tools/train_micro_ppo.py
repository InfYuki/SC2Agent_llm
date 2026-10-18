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


def policy_sha256(model):
    digest = hashlib.sha256()
    for key, value in sorted(model.policy.state_dict().items()):
        digest.update(key.encode())
        digest.update(value.detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def resume_checkpoint(source):
    """Accept only our versioned checkpoint and its adjacent provenance."""
    source = Path(source).resolve()
    checkpoint = source / "model.zip" if source.is_dir() else source
    if checkpoint.suffix != ".zip" or not checkpoint.is_file():
        raise ValueError("--resume requires a model directory or existing .zip")
    metadata = json.loads((checkpoint.parent / "metadata.json").read_text(encoding="utf-8"))
    expected = dict(format="marine-maskable-ppo-sb3-v1", feature_version="marine-16-v1",
                    action_version="marine-5-v1", decision_game_loops=8,
                    reward_version="effective-hp-delta-45-terminal-1-v1",
                    normalization="marine-16-v1", actor_layers=[16, 64, 64, 5],
                    critic_hidden_layers=[64, 64], activation="tanh", bc_weights_used=False)
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"Incompatible resume metadata: {key}")
    digest = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    if metadata.get("checkpoint_sha256") != digest:
        raise ValueError("Resume checkpoint hash does not match metadata")
    for package in ("stable-baselines3", "sb3-contrib"):
        if metadata.get("versions", {}).get(package) != version(package):
            raise ValueError(f"Resume requires the recorded {package} version")
    for key, value in dict(gamma=0.99, gae_lambda=0.95, clip_range=0.2, device="cpu").items():
        if metadata.get("training", {}).get(key) != value:
            raise ValueError(f"Incompatible resume training metadata: {key}")
    return checkpoint, metadata, digest


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
          map_name="Ancient Cistern LE", max_game_seconds=8, seed=None,
          total_timesteps=32, n_steps=None, batch_size=None, n_epochs=None,
          learning_rate=None, resume=None, environment=None):
    parent = resume_checkpoint(resume) if resume is not None else None
    requested = dict(n_steps=n_steps, batch_size=batch_size, n_epochs=n_epochs,
                     learning_rate=learning_rate)
    defaults = dict(n_steps=32, batch_size=16, n_epochs=2, learning_rate=3e-4)
    effective = parent[1]["training"] if parent else defaults
    for key, value in requested.items():
        if parent and value is not None and value != effective[key]:
            raise ValueError(f"Resume inherits {key}={effective[key]}; conflicting override")
        requested[key] = effective[key] if value is None else value
    n_steps, batch_size, n_epochs, learning_rate = (requested[key] for key in defaults)
    if parent and seed is not None and seed != parent[1]["seed"]:
        raise ValueError("Resume inherits the parent seed; conflicting override")
    seed = parent[1]["seed"] if parent else (42 if seed is None else seed)
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
    environment_closed = False
    try:
        torch.set_num_threads(1)
        model = MaskablePPO.load(parent[0], env=env, device="cpu") if parent else MaskablePPO(
            "MlpPolicy", env, n_steps=n_steps, batch_size=batch_size,
            n_epochs=n_epochs, learning_rate=learning_rate, gamma=0.99,
            gae_lambda=0.95, clip_range=0.2, seed=seed, device="cpu", verbose=1,
            policy_kwargs=dict(net_arch=dict(pi=[64, 64], vf=[64, 64]),
                               activation_fn=torch.nn.Tanh))
        if parent:
            for key, value in requested.items():
                if getattr(model, key) != value:
                    raise ValueError(f"Resume model and metadata disagree: {key}")
            if model.n_envs != 1 or model.policy.net_arch != dict(pi=[64, 64], vf=[64, 64]):
                raise ValueError("Resume requires the single-environment fixed MLP")
            if model.policy.activation_fn is not torch.nn.Tanh:
                raise ValueError("Resume requires tanh activation")
            if (model.gamma != 0.99 or model.gae_lambda != 0.95
                    or float(model.clip_range(1.0)) != 0.2 or model.seed != seed):
                raise ValueError("Resume model and fixed training metadata disagree")
        initial_steps, initial_updates = model.num_timesteps, model._n_updates
        initial_policy_hash = policy_sha256(model)
        optimizer_steps_before = [int(state["step"]) for state in
                                  model.policy.optimizer.state.values() if "step" in state]
        initial = {key: value.detach().cpu().clone()
                   for key, value in model.policy.state_dict().items()}
        model.learn(total_timesteps=total_timesteps, callback=trace, use_masking=True,
                    reset_num_timesteps=not bool(parent))
        final = model.policy.state_dict()
        changes = {key: float(torch.max(torch.abs(value.cpu() - initial[key])))
                   for key, value in final.items()}
        finite = all(bool(torch.isfinite(value).all()) for value in final.values())
        actor_changed = any(value > 0 for key, value in changes.items()
                            if key.startswith(("mlp_extractor.policy_net", "action_net")))
        if not finite or not actor_changed or model._n_updates <= initial_updates:
            raise ValueError("No finite actor PPO update was demonstrated")
        probabilities, action = probe(model, trace.probe_obs, trace.probe_mask)
        # Close the worker before naming any successful checkpoint; close failure
        # is a system failure, not a completed training run.
        env.close()
        environment_closed = True
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
            initialization="resume" if parent else "random", bc_weights_used=False, dataset=None,
            parent_checkpoint=(dict(path=str(parent[0]), sha256=parent[2]) if parent else None),
            initial_policy_sha256=initial_policy_hash,
            initial_timesteps=initial_steps, additional_timesteps=model.num_timesteps - initial_steps,
            cumulative_timesteps=model.num_timesteps,
            hyperparameter_source="parent_checkpoint" if parent else "CLI/defaults",
            resume_semantics="Fresh environment reset; RNG/game trajectory is not replayed.",
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
            initial_timesteps=initial_steps, additional_steps=model.num_timesteps - initial_steps,
            cumulative_timesteps=model.num_timesteps, initial_updates=initial_updates,
            initial_policy_sha256=initial_policy_hash,
            parent_checkpoint=metadata["parent_checkpoint"],
            hyperparameter_source=metadata["hyperparameter_source"],
            optimizer_steps_before=optimizer_steps_before,
            optimizer_steps_after=[int(state["step"]) for state in
                                   model.policy.optimizer.state.values() if "step" in state],
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
        if not environment_closed:
            env.close()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--worker-python", type=Path, required=True)
    parser.add_argument("--game-path", default=r"C:\Program Files (x86)\StarCraft II")
    parser.add_argument("--map", default="Ancient Cistern LE")
    parser.add_argument("--max-game-seconds", type=float, default=8)
    parser.add_argument("--resume", type=Path, help="Parent model directory or .zip with adjacent metadata.json; inherits hyperparameters")
    parser.add_argument("--seed", type=int)
    parser.add_argument("--total-timesteps", type=int, default=32,
                        help="Additional steps for this run, including when resuming")
    parser.add_argument("--n-steps", type=int)
    parser.add_argument("--batch-size", type=int)
    parser.add_argument("--n-epochs", type=int)
    parser.add_argument("--learning-rate", type=float)
    args = parser.parse_args()
    print(json.dumps(train(
        args.output, worker_python=args.worker_python, game_path=args.game_path,
        map_name=args.map, max_game_seconds=args.max_game_seconds, seed=args.seed,
        total_timesteps=args.total_timesteps, n_steps=args.n_steps,
        batch_size=args.batch_size, n_epochs=args.n_epochs,
        learning_rate=args.learning_rate, resume=args.resume), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
