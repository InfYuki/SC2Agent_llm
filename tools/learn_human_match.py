"""Learn once from a fresh human match; run with the separate training Python.

LLM learning means bounded cross-match experience in the next prompt, not remote
weight fine-tuning. PPO uses sampled behavior actions from one frozen checkpoint,
never BC labels, argmax evaluation traces or replays from previous opponents.
"""
import argparse
from collections import defaultdict
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def read_json(path, default=None):
    path = Path(path)
    return json.loads(path.read_text(encoding="utf-8")) if path.is_file() else default


def write_json(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=False,
                                    allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def completed_result(summary):
    return (summary.get("status") == "completed" and not summary.get("error")
            and not summary.get("stop_reason")
            and summary.get("result") in {"Result.Victory", "Result.Defeat", "Result.Tie"})


def update_strategy_memory(run_dir, memory_dir, summary):
    """Store observations and conditional advice, without claiming causation."""
    path = memory_dir / "strategy_memory.json"
    marker = run_dir / "human_strategy_consumed.json"
    if marker.is_file():
        return {"status": "already_recorded", "path": str(path)}
    memory = read_json(path, {"format": "human-strategy-memory-v1", "matches_seen": 0,
                              "recent_matches": [], "lessons": []})
    if memory.get("format") != "human-strategy-memory-v1":
        raise ValueError("Unsupported strategy memory format")
    if any(row.get("run_id") == run_dir.name for row in memory["recent_matches"]):
        return {"status": "already_recorded", "path": str(path)}
    strategy = read_json(run_dir / "strategy_summary.json", {})
    counters = strategy.get("counters", {})
    plans, attacks, threat_times = [], [], []
    events = run_dir / "events.jsonl"
    if events.is_file():
        for line in events.read_text(encoding="utf-8").splitlines():
            event = json.loads(line)
            if event.get("event") == "llm_plan" and event.get("status") in {"active", "renewed", "pending"}:
                plan = event.get("plan", {})
                plans.append({key: plan.get(key) for key in
                              ("task", "min_army_supply", "worker_target", "base_target")})
            snapshot = event.get("snapshot", {})
            if event.get("event") == "llm_request" and snapshot.get("base_under_attack"):
                threat_times.append(snapshot.get("game_seconds"))
            if event.get("event") == "llm_plan" and event.get("plan", {}).get("task") == "attack":
                attacks.append(event.get("game_seconds"))
    notes = ["Only visible-state evidence is available; past opponent behavior may change."]
    if summary["result"] == "Result.Defeat":
        notes.append("The previous match was lost; do not repeat its goals blindly. Reassess visible threats and army size.")
    elif summary["result"] == "Result.Victory":
        notes.append("The previous match was won. Reuse its goals only if current visible conditions are comparable; seek safe earlier pressure.")
    if threat_times:
        notes.append("The human threatened our base in the previous match. Scout and defend when current visible threats justify it.")
    if not attacks:
        notes.append("No attack plan was recorded last match. Avoid indefinite rally when there is no visible threat and sufficient army exists.")
    record = dict(run_id=run_dir.name, result=summary["result"],
                  game_seconds=summary.get("game_span_seconds"), enemy_race="Terran",
                  llm_requests=counters.get("requests", 0),
                  llm_valid_plans=counters.get("valid_plans", 0),
                  peak_workers=summary.get("peak_workers"), peak_marines=summary.get("peak_marines"),
                  peak_bases=summary.get("peak_bases"), notes=notes,
                  plan_outcomes=[dict(plan, result=summary["result"]) for plan in plans[-4:]])
    memory.update(updated_at_utc=datetime.now(timezone.utc).isoformat(),
                  matches_seen=memory.get("matches_seen", 0) + 1,
                  recent_matches=(memory["recent_matches"] + [record])[-8:])
    memory["lessons"] = list(dict.fromkeys(notes + memory.get("lessons", [])))[:8]
    write_json(path, memory)
    write_json(marker, {"run_id": run_dir.name, "memory": str(path)})
    return {"status": "updated", "path": str(path), "matches_seen": memory["matches_seen"],
            "mechanism": "cross-match prompt memory; no remote model weight update"}


def load_rollout(run_dir, checkpoint):
    import numpy as np
    metadata = read_json(run_dir / "human_training.json", {})
    if (metadata.get("format") != "human-match-training-v1"
            or metadata.get("sampling") != "stochastic-masked-categorical-v1"
            or metadata.get("checkpoint_sha256") != sha(checkpoint)):
        raise ValueError("Training rollout/checkpoint identity or sampling mismatch")
    if metadata.get("learning_exclusion"):
        raise ValueError("This run is permanently excluded from learning")
    rows = []
    for line in (run_dir / "human_ppo_rollout.jsonl").read_text(encoding="utf-8").splitlines():
        row = json.loads(line)
        for key in ("obs", "next_obs"):
            values = np.asarray(row[key], dtype=np.float32)
            if values.shape != (16,) or not np.isfinite(values).all() or np.any(abs(values) > 1.00001):
                raise ValueError("Invalid observation")
        for key in ("mask", "next_mask"):
            if (not isinstance(row[key], list) or len(row[key]) != 5
                    or any(type(value) is not bool for value in row[key]) or not any(row[key])):
                raise ValueError("Invalid action mask")
        if type(row["action"]) is not int or not 0 <= row["action"] < 5 or not row["mask"][row["action"]]:
            raise ValueError("Illegal sampled action")
        if any(type(row.get(key)) not in (int, float) or not np.isfinite(row[key])
               for key in ("reward", "old_log_prob")):
            raise ValueError("Invalid reward or behavior log probability")
        if any(type(row.get(key)) is not bool for key in ("terminated", "truncated")):
            raise ValueError("Invalid episode boundary")
        if (not isinstance(row.get("trajectory_id"), str) or type(row.get("step")) is not int
                or type(row.get("game_loop")) is not int or type(row.get("next_game_loop")) is not int
                or row["next_game_loop"] <= row["game_loop"]):
            raise ValueError("Invalid trajectory identity/time")
        rows.append(row)
    return rows, metadata


def train_ppo(run_dir, checkpoint, output, memory_dir, *, epochs=2, min_samples=8):
    import numpy as np
    import torch
    from sb3_contrib import MaskablePPO
    from tools.export_micro_ppo import export_actor
    from tools.train_micro_ppo import actor_sha256

    consumed = run_dir / "human_learning_consumed.json"
    if consumed.is_file():
        return {"status": "already_consumed", "record": read_json(consumed)}
    rows, metadata = load_rollout(run_dir, checkpoint)
    if len(rows) < min_samples:
        return {"status": "skipped", "reason": "insufficient_valid_on_policy_samples",
                "samples": len(rows), "minimum": min_samples}
    if output.exists():
        raise ValueError("Candidate output already exists; refuse overwrite or duplicate update")
    model = MaskablePPO.load(checkpoint, device="cpu")
    model.policy.set_training_mode(False)
    # Verify that the collection actor is exactly this checkpoint, beyond merely
    # trusting a supplied pathname or a low-precision probability comparison.
    source_actor = Path(metadata.get("actor", ""))
    actor_meta = read_json(source_actor / "metadata.json", {})
    if (actor_meta.get("weights_sha256") != metadata.get("actor_weights_sha256")
            or not (source_actor / "weights.npz").is_file()
            or sha(source_actor / "weights.npz") != metadata.get("actor_weights_sha256")
            or actor_meta.get("producer", {}).get("source_checkpoint_sha256") != sha(checkpoint)):
        raise ValueError("Collection actor/checkpoint provenance mismatch")
    from bot.micro_ppo import NumpyPPOPolicy
    source = NumpyPPOPolicy.load(source_actor)
    layers = list(model.policy.mlp_extractor.policy_net)
    for index, layer in enumerate((layers[0], layers[2], model.policy.action_net), 1):
        if (not np.array_equal(layer.weight.detach().cpu().numpy().T, source.weights[f"w{index}"])
                or not np.array_equal(layer.bias.detach().cpu().numpy(), source.weights[f"b{index}"])):
            raise ValueError("Checkpoint actor differs from collection actor")
    obs = torch.tensor(np.array([r["obs"] for r in rows]), dtype=torch.float32)
    next_obs = torch.tensor(np.array([r["next_obs"] for r in rows]), dtype=torch.float32)
    actions = torch.tensor([r["action"] for r in rows], dtype=torch.long)
    masks = np.array([r["mask"] for r in rows], dtype=bool)
    old_logp = torch.tensor([r["old_log_prob"] for r in rows], dtype=torch.float32)
    with torch.no_grad():
        values, checked_logp, _ = model.policy.evaluate_actions(obs, actions, action_masks=masks)
        next_values = model.policy.predict_values(next_obs).flatten()
    discrepancy = float((checked_logp - old_logp).abs().max())
    if discrepancy > 1e-4:
        raise ValueError("Behavior probabilities do not match the fixed collection checkpoint")
    values = values.flatten()
    advantages = torch.zeros(len(rows))
    trajectories = defaultdict(list)
    for index, row in enumerate(rows):
        trajectories[row["trajectory_id"]].append(index)
    for indices in trajectories.values():
        indices.sort(key=lambda i: rows[i]["step"])
        if len({rows[i]["step"] for i in indices}) != len(indices):
            raise ValueError("Duplicate trajectory step")
        gae = 0.0
        following = None
        for index in reversed(indices):
            row = rows[index]
            discount = 0.99 ** ((row["next_game_loop"] - row["game_loop"]) / 8)
            contiguous = (following is not None and not row["terminated"] and not row["truncated"]
                          and rows[following]["step"] == row["step"] + 1
                          and rows[following]["game_loop"] == row["next_game_loop"]
                          and rows[following]["obs"] == row["next_obs"])
            bootstrap = 0.0 if row["terminated"] else float(next_values[index])
            delta = row["reward"] + discount * bootstrap - float(values[index])
            gae = delta + (discount * 0.95 * gae if contiguous else 0.0)
            advantages[index] = gae
            following = index
    returns = advantages + values
    advantages = (advantages - advantages.mean()) / (advantages.std(unbiased=False) + 1e-8)
    before = actor_sha256(model)
    model.policy.set_training_mode(True)
    torch.manual_seed(42)
    metrics = []
    for _ in range(epochs):
        for batch in torch.randperm(len(rows)).split(64):
            predicted, logp, entropy = model.policy.evaluate_actions(
                obs[batch], actions[batch], action_masks=masks[batch.numpy()])
            ratio = torch.exp(logp - old_logp[batch])
            policy_loss = -torch.minimum(advantages[batch] * ratio,
                                        advantages[batch] * ratio.clamp(0.8, 1.2)).mean()
            value_loss = torch.nn.functional.mse_loss(predicted.flatten(), returns[batch])
            loss = policy_loss + 0.5 * value_loss - 0.01 * entropy.mean()
            if not torch.isfinite(loss):
                raise ValueError("Non-finite PPO loss")
            model.policy.optimizer.zero_grad()
            loss.backward()
            torch.nn.utils.clip_grad_norm_(model.policy.parameters(), 0.5)
            model.policy.optimizer.step()
            metrics.append(float(loss.detach()))
    after = actor_sha256(model)
    if before == after:
        raise ValueError("PPO actor weights did not change")
    model.num_timesteps += len(rows)
    model._n_updates += epochs
    output.mkdir(parents=True, exist_ok=False)
    saved = output / "model.zip"
    model.save(saved)
    source_meta = read_json(checkpoint.parent / "metadata.json", {})
    source_meta.update(format="human-match-maskable-ppo-v1", checkpoint_sha256=sha(saved),
                       parent_checkpoint={"path": str(checkpoint), "sha256": sha(checkpoint)},
                       initialization="human_match_on_policy_update",
                       task_semantics="Human-match Marine ownership segments; not scripted micro curriculum",
                       human_match_training={"source_run_id": run_dir.name, "samples": len(rows),
                                             "epochs": epochs, "reward_version": metadata.get("reward_version"),
                                             "source_rollout_sha256": sha(run_dir / "human_ppo_rollout.jsonl")})
    # Prior scripted-task declarations no longer describe the new training mix.
    source_meta.pop("task", None)
    source_meta.pop("curriculum", None)
    write_json(output / "metadata.json", source_meta)
    actor_meta = export_actor(model, saved, output / "actor")
    report = dict(status="updated", samples=len(rows), trajectories=len(trajectories), epochs=epochs,
                  algorithm="masked clipped PPO with per-ownership GAE; sampled fixed behavior policy",
                  behavior_log_prob_max_error=discrepancy, actor_before_sha256=before,
                  actor_after_sha256=after, checkpoint=str(saved), actor=str(output / "actor"),
                  final_loss=metrics[-1], optimizer_steps=len(metrics),
                  strength_improvement="not evaluated")
    pointer = dict(format="human-ppo-latest-v1", checkpoint=str(saved), actor=str(output / "actor"),
                   source_run_id=run_dir.name, checkpoint_sha256=sha(saved),
                   actor_weights_sha256=actor_meta["weights_sha256"])
    # Consumed marker precedes pointer publication: interruption cannot silently
    # train the same match again. A complete candidate remains manually usable.
    write_json(consumed, dict(source_run_id=run_dir.name, candidate=pointer, update=report))
    write_json(memory_dir / "ppo_latest.json", pointer)
    return report


def learn(run_dir, checkpoint, output, memory_dir, *, epochs=2, min_samples=8):
    run_dir, checkpoint = Path(run_dir).resolve(), Path(checkpoint).resolve()
    output, memory_dir = Path(output).resolve(), Path(memory_dir).resolve()
    summary = read_json(run_dir / "summary.json", {})
    report = dict(source_run_id=run_dir.name,
                  llm={"status": "skipped", "reason": "match_not_naturally_completed"},
                  ppo={"status": "skipped", "reason": "match_not_naturally_completed"})
    metadata = read_json(run_dir / "human_training.json", {})
    eligible = (metadata.get("format") == "human-match-training-v1"
                and metadata.get("enemy_race") == "Terran"
                and not metadata.get("learning_exclusion"))
    if not eligible:
        for key in ("llm", "ppo"):
            report[key]["reason"] = "not_an_authorized_human_training_run"
    if eligible and completed_result(summary):
        for key, operation in (
            ("llm", lambda: update_strategy_memory(run_dir, memory_dir, summary)),
            ("ppo", lambda: train_ppo(run_dir, checkpoint, output, memory_dir,
                                      epochs=epochs, min_samples=min_samples)),
        ):
            try:
                report[key] = operation()
            except Exception as error:
                report[key] = dict(status="failed", error=type(error).__name__, detail=str(error))
        # Replay study is separate from on-policy PPO. Exact schemas only by
        # default; only an explicit locally configured compatibility pair may
        # override an unsupported build. Existing verified studies can reapply.
        try:
            from tools.analyze_human_replay import analyze, update_memory
            study = run_dir / "replay_analysis" / "opponent_profile.json"
            if study.is_file():
                profile = read_json(study)
                if (profile.get("source_run_id") != run_dir.name
                        or profile.get("replay_sha256") != sha(run_dir / "game.SC2Replay")):
                    raise ValueError("Stored replay study identity mismatch")
                update_memory(memory_dir, profile)
            else:
                profile = analyze(run_dir, memory_dir=memory_dir)
            report["replay_study"] = dict(status="updated", path=str(study),
                mechanism="post-match full-information historical strategy memory, never PPO rollout",
                actual_replay_build=profile["actual_replay_build"],
                decoder_schema_build=profile["decoder_schema_build"],
                compatibility_override=profile["compatibility_override"],
                decoder_selection=profile.get("decoder_selection", "previous_verified_profile"))
        except (ImportError, ValueError, FileNotFoundError) as error:
            report["replay_study"] = dict(status="skipped", reason=str(error))
        except Exception as error:
            report["replay_study"] = dict(status="failed", error=type(error).__name__, detail=str(error))
    write_json(run_dir / "learning_report.json", report)
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    for name in ("run-dir", "checkpoint", "output", "memory-dir"):
        parser.add_argument("--" + name, type=Path, required=True)
    parser.add_argument("--epochs", type=int, default=2, choices=range(1, 5))
    parser.add_argument("--min-samples", type=int, default=8)
    args = parser.parse_args()
    if args.min_samples < 2:
        parser.error("--min-samples must be at least 2")
    report = learn(args.run_dir, args.checkpoint, args.output, args.memory_dir,
                   epochs=args.epochs, min_samples=args.min_samples)
    print(json.dumps(report, indent=2))
    return int(any(report[key]["status"] == "failed" for key in ("llm", "ppo")))


if __name__ == "__main__":
    raise SystemExit(main())
