"""Tiny real-SC2 MaskablePPO update and checkpoint round trip (CPU).

Run with the separate training interpreter; --worker-python selects the locked
Ares runtime. Initialization is random unless --init-bc is explicit. This is an
engineering prototype, not a combat-strength evaluation.
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
from envs.sc2_micro_env import SCENARIOS, training_task, normalize_training_task, normalize_curriculum

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


def actor_sha256(model):
    digest = hashlib.sha256()
    for key, value in sorted(model.policy.state_dict().items()):
        if key.startswith(("mlp_extractor.policy_net", "action_net")):
            digest.update(key.encode())
            digest.update(value.detach().cpu().numpy().tobytes())
    return digest.hexdigest()


def initialize_bc_actor(model, directory, dataset):
    """Copy only the validated BC actor, then verify every frozen observation."""
    from bot.micro_bc import NumpyBCPolicy
    from tools.train_micro_bc import load_dataset

    directory, dataset = Path(directory).resolve(), Path(dataset).resolve()
    bc = NumpyBCPolicy.load(directory)
    data, dataset_meta = load_dataset(dataset)
    metadata_hash = hashlib.sha256((directory / "metadata.json").read_bytes()).hexdigest()
    dataset_meta_hash = hashlib.sha256((dataset / "metadata.json").read_bytes()).hexdigest()
    if (bc.metadata.get("dataset_sha256") != dataset_meta["dataset_sha256"]
            or bc.metadata.get("dataset_metadata_sha256") != dataset_meta_hash
            or bc.metadata.get("sample_counts") != dataset_meta["split_counts"]):
        raise ValueError("BC source dataset provenance mismatch")
    policy = model.policy
    layers = list(policy.mlp_extractor.policy_net)
    if (len(layers) != 4 or not isinstance(layers[0], torch.nn.Linear)
            or not isinstance(layers[1], torch.nn.Tanh)
            or not isinstance(layers[2], torch.nn.Linear)
            or not isinstance(layers[3], torch.nn.Tanh)
            or not isinstance(policy.action_net, torch.nn.Linear)
            or policy.features_extractor.__class__.__name__ != "FlattenExtractor"
            or model.observation_space.shape != (16,) or model.action_space.n != 5
            or not np.all(model.observation_space.low == -1)
            or not np.all(model.observation_space.high == 1)):
        raise ValueError("BC transfer requires the fixed actor and marine normalization")
    if model.num_timesteps or model._n_updates or policy.optimizer.state:
        raise ValueError("BC initialization requires a new PPO and fresh optimizer")
    critic = {key: value.clone() for key, value in policy.state_dict().items()
              if key.startswith(("mlp_extractor.value_net", "value_net"))}
    with torch.no_grad():
        for index, layer in enumerate((layers[0], layers[2], policy.action_net), 1):
            weight, bias = bc.weights[f"w{index}"].T, bc.weights[f"b{index}"]
            if tuple(layer.weight.shape) != weight.shape or tuple(layer.bias.shape) != bias.shape:
                raise ValueError("BC transfer layer shape mismatch")
            layer.weight.copy_(torch.from_numpy(weight.copy()))
            layer.bias.copy_(torch.from_numpy(bias.copy()))
    if not critic or any(not torch.equal(value, policy.state_dict()[key])
                         for key, value in critic.items()):
        raise ValueError("BC transfer changed the independently initialized critic")
    logits_error = probability_error = 0.0
    initial_actions, initial_probabilities = [], []
    for obs, mask in zip(data["obs"], data["mask"]):
        expected_logits = bc.logits(obs)
        legal = np.where(mask, expected_logits, -np.inf)
        expected_probability = np.exp(legal - legal.max())
        expected_probability /= expected_probability.sum()
        with torch.no_grad():
            tensor, _ = policy.obs_to_tensor(obs)
            actual_logits = policy.action_net(policy.mlp_extractor.forward_actor(
                policy.extract_features(tensor))).cpu().numpy()[0]
        actual_probability, action = probe(model, obs, mask)
        initial_actions.append(action)
        initial_probabilities.append(actual_probability.tolist())
        logits_error = max(logits_error, float(np.max(np.abs(actual_logits - expected_logits))))
        probability_error = max(probability_error, float(np.max(np.abs(
            actual_probability - expected_probability))))
        if (not np.isfinite(actual_logits).all() or logits_error > 1e-5
                or probability_error > 1e-6 or action != bc.action(obs, mask)):
            raise ValueError("BC to PPO initialization parity failed")
    return dict(path=str(directory), metadata_sha256=metadata_hash,
                weights_sha256=bc.metadata["weights_sha256"],
                dataset=str(dataset), dataset_sha256=dataset_meta["dataset_sha256"],
                dataset_metadata_sha256=dataset_meta_hash,
                parity_samples=len(data["obs"]), logits_max_abs_error=logits_error,
                masked_probability_max_abs_error=probability_error,
                masked_actions_equal=True, critic_unchanged=True,
                masked_actions=initial_actions, masked_probabilities=initial_probabilities,
                optimizer_state_empty=True, initial_actor_sha256=actor_sha256(model),
                interpretation="Frozen observations check transfer only; not expert PPO rollouts or formal 1000-observation acceptance.")


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
                    critic_hidden_layers=[64, 64], activation="tanh")
    for key, value in expected.items():
        if metadata.get(key) != value:
            raise ValueError(f"Incompatible resume metadata: {key}")
    if metadata.get("bc_weights_used") not in (True, False):
        raise ValueError("Resume requires explicit BC provenance")
    if metadata["bc_weights_used"]:
        provenance = metadata.get("bc_initialization")
        if not isinstance(provenance, dict) or any(
                not isinstance(provenance.get(key), str) or len(provenance[key]) != 64
                for key in ("metadata_sha256", "weights_sha256", "dataset_sha256")):
            raise ValueError("Resume requires BC source hashes")
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


def resolve_training_task(metadata=None, allow_task_change=False, **requested):
    """Inherit the recorded task; legacy checkpoints mean the old Marine task."""
    inherited = metadata.get("task") if metadata is not None else None
    baseline = training_task() if inherited is None else normalize_training_task(inherited)
    values = {}
    for key in ("scenario", "distance", "max_game_seconds", "map_name", "own_health_fraction", "enemy_health_fraction",
                "enemy_count", "second_distance", "second_enemy_health_fraction"):
        value = requested.get(key)
        baseline_value = baseline.get("health_fraction" if key == "own_health_fraction" else key)
        if metadata is not None and not allow_task_change and value is not None and value != baseline_value:
            raise ValueError(f"Resume inherits task {key}={baseline_value}; conflicting override")
        values[key] = baseline_value if value is None else value
    if values["enemy_count"] == 1:
        # An explicitly allowed 2 -> 1 switch drops inherited second-target fields.
        # Explicit second-target overrides still fail in the task validator.
        for key in ("second_distance", "second_enemy_health_fraction"):
            if requested.get(key) is None:
                values[key] = None
    return training_task(**values)


def resolve_task_set(metadata=None, *, curriculum=None, allow_task_change=False, **requested):
    """Freeze one task set before launching SC2; changes require an explicit flag."""
    parent_curriculum = (normalize_curriculum(metadata["curriculum"])
                         if metadata and metadata.get("curriculum") is not None else None)
    parent_task = resolve_training_task(metadata)
    if parent_curriculum and parent_task != parent_curriculum["tasks"][0]:
        raise ValueError("Parent task differs from curriculum compatibility task")
    supplied = any(value is not None for value in requested.values())
    if curriculum is not None:
        if supplied:
            raise ValueError("--curriculum cannot be combined with individual task overrides")
        selected = normalize_curriculum(curriculum)
        task = selected["tasks"][0]
    elif parent_curriculum is not None and not supplied:
        selected, task = parent_curriculum, parent_task
    else:
        selected = None
        task = resolve_training_task(metadata, allow_task_change=allow_task_change, **requested)
    parent_tasks = parent_curriculum["tasks"] if parent_curriculum else [parent_task]
    new_tasks = selected["tasks"] if selected else [task]
    changed = metadata is not None and (parent_tasks != new_tasks or bool(parent_curriculum) != bool(selected))
    if changed and not allow_task_change:
        raise ValueError("Resume task set conflicting override; --allow-task-change is required")
    def digest(tasks):
        return hashlib.sha256(json.dumps(tasks, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()).hexdigest()
    change = (dict(explicitly_allowed=True, parent_tasks=parent_tasks, new_tasks=new_tasks,
                   parent_task_set_sha256=digest(parent_tasks), new_task_set_sha256=digest(new_tasks))
              if changed else None)
    return task, selected, change


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
                   curriculum_index=info.get("curriculum_index"), episode_index=info.get("episode_index"),
                   task=info.get("task"), own_effective_hp=info.get("own_effective_hp"),
                   enemy_effective_hp=info.get("enemy_effective_hp"),
                   own_hp_loss=info.get("own_hp_loss"), enemy_hp_loss=info.get("enemy_hp_loss"),
                   reward_scale=info.get("reward_scale"), terminal_reward=info.get("terminal_reward"),
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
                task=info.get("task"), curriculum_index=info.get("curriculum_index"),
                episode_index=info.get("episode_index"),
                reward=self.episode_rewards[episode_id], reason=info.get("reason"),
                time_limit_truncated=bool(info.get("TimeLimit.truncated")),
                official_close_confirmed=bool(info.get("official_close_confirmed")),
                worker_close=info.get("worker_close"),
                output_dir=info["output_dir"],
            ))
        return True


def train(output, *, worker_python, game_path=r"C:\Program Files (x86)\StarCraft II",
          map_name=None, max_game_seconds=None, scenario=None, distance=None, seed=None,
          own_health_fraction=None, enemy_health_fraction=None, enemy_count=None,
          second_distance=None, second_enemy_health_fraction=None, curriculum=None, allow_task_change=False,
          total_timesteps=32, n_steps=None, batch_size=None, n_epochs=None,
          learning_rate=None, resume=None, init_bc=None, init_bc_dataset=None, environment=None):
    if resume is not None and init_bc is not None:
        raise ValueError("--init-bc and --resume are mutually exclusive")
    if init_bc_dataset is not None and init_bc is None:
        raise ValueError("--init-bc-dataset requires --init-bc")
    parent = resume_checkpoint(resume) if resume is not None else None
    if curriculum is not None and not isinstance(curriculum, dict):
        curriculum = json.loads(Path(curriculum).read_text(encoding="utf-8-sig"))
    task, curriculum, task_change = resolve_task_set(
        parent[1] if parent else None, curriculum=curriculum, allow_task_change=allow_task_change,
        map_name=map_name, max_game_seconds=max_game_seconds, scenario=scenario, distance=distance,
        own_health_fraction=own_health_fraction, enemy_health_fraction=enemy_health_fraction,
        enemy_count=enemy_count, second_distance=second_distance,
        second_enemy_health_fraction=second_enemy_health_fraction)
    task_semantics = "compatibility_default; curriculum governs reset" if curriculum else "single fixed task"
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
        worker_python=worker_python, game_path=game_path, map_name=task["map_name"],
        max_game_seconds=task["max_game_seconds"], scenario=task["scenario"],
        distance=task["distance"], own_health_fraction=task["health_fraction"],
        enemy_health_fraction=task["enemy_health_fraction"], enemy_count=task["enemy_count"],
        second_distance=task.get("second_distance"),
        second_enemy_health_fraction=task.get("second_enemy_health_fraction"), curriculum=curriculum,
        output_root=output / "episodes")
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
        bc_initialization = initialize_bc_actor(
            model, init_bc, init_bc_dataset or ROOT / "artifacts/micro_datasets/p3_v7_formal_20261018_115352_dataset"
        ) if init_bc is not None else (parent[1].get("bc_initialization") if parent else None)
        initial_steps, initial_updates = model.num_timesteps, model._n_updates
        initial_policy_hash = policy_sha256(model)
        initial_actor_hash = actor_sha256(model)
        optimizer_steps_before = [int(state["step"]) for state in
                                  model.policy.optimizer.state.values() if "step" in state]
        write_json(output / "task_manifest.json", dict(
            task=task, curriculum=curriculum, task_semantics=task_semantics, task_change=task_change,
            parent_checkpoint=(dict(path=str(parent[0]), sha256=parent[2]) if parent else None),
            initial_timesteps=initial_steps, requested_additional_timesteps=total_timesteps,
            selection_start_index=0, reset_semantics="Cold environment reset; curriculum restarts at index 0; no trajectory replay."))
        if init_bc is not None:
            write_json(output / "initialization_report.json", dict(
                task=task,
                initialization="bc_actor", initial_timesteps=initial_steps,
                initial_policy_sha256=initial_policy_hash, initial_actor_sha256=initial_actor_hash,
                optimizer_steps_before=optimizer_steps_before, bc_initialization=bc_initialization))
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
        if init_bc is not None:
            source = Path(bc_initialization["path"])
            if (hashlib.sha256((source / "metadata.json").read_bytes()).hexdigest()
                    != bc_initialization["metadata_sha256"]
                    or hashlib.sha256((source / "weights.npz").read_bytes()).hexdigest()
                    != bc_initialization["weights_sha256"]):
                raise ValueError("Original BC files changed during training")
        metadata = dict(
            task=task, curriculum=curriculum, task_semantics=task_semantics, task_change=task_change,
            curriculum_cursor_semantics="Each run restarts at index 0; parent trajectory is not replayed.",
            format="marine-maskable-ppo-sb3-v1", feature_version="marine-16-v1",
            action_version="marine-5-v1", decision_game_loops=8,
            reward_version="effective-hp-delta-45-terminal-1-v1",
            normalization="marine-16-v1", actor_layers=[16, 64, 64, 5],
            critic_hidden_layers=[64, 64], activation="tanh", seed=seed,
            initialization="resume" if parent else ("bc_actor" if init_bc is not None else "random"),
            bc_weights_used=bool(bc_initialization), bc_initialization=bc_initialization,
            dataset=(bc_initialization["dataset_sha256"] if bc_initialization else None),
            parent_checkpoint=(dict(path=str(parent[0]), sha256=parent[2]) if parent else None),
            initial_policy_sha256=initial_policy_hash,
            initial_actor_sha256=initial_actor_hash,
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
            task=task, curriculum=curriculum, task_semantics=task_semantics, task_change=task_change,
            status="success", actual_steps=model.num_timesteps,
            initial_timesteps=initial_steps, additional_steps=model.num_timesteps - initial_steps,
            cumulative_timesteps=model.num_timesteps, initial_updates=initial_updates,
            initial_policy_sha256=initial_policy_hash,
            initial_actor_sha256=initial_actor_hash,
            initialization=metadata["initialization"], bc_initialization=bc_initialization,
            original_bc_unchanged=True if init_bc is not None else None,
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
            active_error = sys.exc_info()[1]
            try:
                env.close()
            except Exception as close_error:
                if active_error is None:
                    raise
                active_error.add_note(f"Environment cleanup also failed: {close_error}")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("output", type=Path)
    parser.add_argument("--worker-python", type=Path, required=True)
    parser.add_argument("--game-path", default=r"C:\Program Files (x86)\StarCraft II")
    parser.add_argument("--map", help="New run default: Ancient Cistern LE; resume inherits task")
    parser.add_argument("--max-game-seconds", type=float, help="New run default: 8; resume inherits task")
    parser.add_argument("--scenario", choices=SCENARIOS, help="New run default: marine-vs-marine; resume inherits task")
    parser.add_argument("--distance", type=float, help="New run default: 6; resume inherits task")
    parser.add_argument("--own-health-fraction", type=float)
    parser.add_argument("--enemy-health-fraction", type=float)
    parser.add_argument("--enemy-count", type=int, choices=[1, 2], help="New run default: 1; resume inherits task")
    parser.add_argument("--second-distance", type=float)
    parser.add_argument("--second-enemy-health-fraction", type=float)
    parser.add_argument("--curriculum", type=Path, help="Frozen round-robin task JSON; resume inherits embedded curriculum")
    parser.add_argument("--allow-task-change", action="store_true", help="Explicitly authorize a recorded resume task-set change")
    initialization = parser.add_mutually_exclusive_group()
    initialization.add_argument("--resume", type=Path, help="Parent model directory or .zip with adjacent metadata.json; inherits hyperparameters")
    initialization.add_argument("--init-bc", type=Path, help="Initialize a new PPO actor from a validated BC directory")
    parser.add_argument("--init-bc-dataset", type=Path, help="Frozen BC source dataset for transfer parity; defaults to the v7 dataset")
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
        scenario=args.scenario, distance=args.distance,
        own_health_fraction=args.own_health_fraction, enemy_health_fraction=args.enemy_health_fraction,
        enemy_count=args.enemy_count, second_distance=args.second_distance,
        second_enemy_health_fraction=args.second_enemy_health_fraction,
        curriculum=args.curriculum, allow_task_change=args.allow_task_change,
        total_timesteps=args.total_timesteps, n_steps=args.n_steps,
        batch_size=args.batch_size, n_epochs=args.n_epochs,
        learning_rate=args.learning_rate, resume=args.resume, init_bc=args.init_bc,
        init_bc_dataset=args.init_bc_dataset), indent=2, allow_nan=False))


if __name__ == "__main__":
    main()
