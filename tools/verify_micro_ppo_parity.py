"""Offline SB3/NumPy actor parity on explicitly selected raw transitions.

Run with the existing PPO training Python. No SC2, worker or LLM is started.
Only obs/mask are evaluated; recorded actions, rewards and next_obs are unused.
"""
import argparse
import hashlib
from importlib.metadata import version
import json
import math
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bot.micro_ppo import NumpyPPOPolicy


def sha256(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def validate_row(row):
    if not isinstance(row, dict):
        raise ValueError("transition must be an object")
    versions = row.get("versions")
    if (not isinstance(versions, dict)
            or type(versions.get("decision_game_loops")) is not int
            or any(versions.get(k) != v for k, v in
            {"feature": "marine-16-v1", "action": "marine-5-v1",
             "decision_game_loops": 8}.items())):
        raise ValueError("transition feature/action/decision contract mismatch")
    obs, mask = row.get("obs"), row.get("mask")
    if (not isinstance(obs, list) or len(obs) != 16 or any(
            type(x) not in (int, float) or not math.isfinite(x) or abs(x) > 1
            for x in obs)):
        raise ValueError("obs must contain 16 finite numbers in [-1,1]")
    if (not isinstance(mask, list) or len(mask) != 5
            or any(type(x) is not bool for x in mask) or not any(mask) or not mask[4]):
        raise ValueError("mask must contain 5 booleans with HOLD legal")
    return np.asarray(obs, dtype=np.float32), np.asarray(mask, dtype=np.bool_)


def collect_sources(paths):
    """Deduplicate physical/content-identical files, preserving actual line numbers."""
    sources, duplicates, samples, invalid = [], [], [], []
    seen_hashes, seen_paths = {}, {}
    for supplied in paths:
        path = Path(supplied).resolve(strict=True)
        if path.name != "micro_transitions.jsonl" or not path.is_file():
            raise ValueError("Expected an explicit micro_transitions.jsonl file: " + str(path))
        digest = sha256(path)
        duplicate = seen_paths.get(path) or seen_hashes.get(digest)
        if duplicate is None:
            duplicate = next((s for s in sources if path.samefile(s["path"])), None)
        if duplicate is not None:
            duplicates.append(dict(path=str(path), sha256=digest,
                                   duplicate_of=duplicate["path"]))
            continue
        source = dict(path=str(path), sha256=digest, lines=0, valid_rows=0, invalid_rows=0)
        sources.append(source)
        seen_paths[path] = seen_hashes[digest] = source
        with path.open(encoding="utf-8") as stream:
            for line_number, line in enumerate(stream, 1):
                source["lines"] += 1
                location = dict(source_index=len(sources) - 1, line=line_number)
                try:
                    row = json.loads(line)
                    obs, mask = validate_row(row)
                    # Deliberate source whitelist: no arbitrary raw payload copying.
                    provenance = dict(location, versions={k: row["versions"].get(k)
                        for k in ("feature", "action", "decision_game_loops", "policy", "expert", "scenario")})
                    samples.append((obs, mask, provenance))
                    source["valid_rows"] += 1
                except (ValueError, TypeError, OverflowError) as exc:
                    invalid.append(dict(location, error=str(exc)))
                    source["invalid_rows"] += 1
    return sources, duplicates, samples, invalid


def load_pair(checkpoint, actor):
    import torch
    from sb3_contrib import MaskablePPO

    numpy_policy = NumpyPPOPolicy.load(actor)
    producer = numpy_policy.metadata["producer"]
    if producer["source_checkpoint_sha256"] != sha256(checkpoint):
        raise ValueError("actor source checkpoint SHA256 mismatch")
    installed = {name: version(name) for name in
                 ("torch", "stable-baselines3", "sb3-contrib", "numpy")}
    if producer["versions"] != installed:
        raise ValueError("actor producer versions differ from verification environment")
    model = MaskablePPO.load(checkpoint, device="cpu")
    policy = model.policy
    layers = list(policy.mlp_extractor.policy_net)
    if (model.observation_space.shape != (16,) or model.action_space.n != 5
            or model.observation_space.dtype != np.float32
            or not np.all(model.observation_space.low == -1)
            or not np.all(model.observation_space.high == 1)
            or policy.normalize_images is not True
            or policy.features_extractor.__class__.__name__ != "FlattenExtractor"
            or len(layers) != 4
            or not all(isinstance(layers[i], torch.nn.Linear) for i in (0, 2))
            or not all(isinstance(layers[i], torch.nn.Tanh) for i in (1, 3))
            or [(layers[i].in_features, layers[i].out_features) for i in (0, 2)]
               != [(16, 64), (64, 64)]
            or not isinstance(policy.action_net, torch.nn.Linear)
            or (policy.action_net.in_features, policy.action_net.out_features) != (64, 5)):
        raise ValueError("checkpoint architecture/normalization/space contract mismatch")
    policy.set_training_mode(False)
    return model, numpy_policy, installed


def masked_probabilities(logits, mask):
    masked = np.where(mask, logits, -np.inf)
    result = np.exp(masked - np.max(masked))
    return result / result.sum()


def judge(sb_logits, np_logits, sb_probs, np_probs, mask, tolerance, tie_tolerance):
    arrays = (sb_logits, np_logits, sb_probs, np_probs)
    if any(np.asarray(a).shape != (5,) or not np.isfinite(a).all() for a in arrays):
        raise ValueError("non-finite or incorrectly shaped inference result")
    # SB3 deterministic mode uses probability argmax. Rounding can turn a tiny
    # logit margin into a probability tie; preserve its actual deployed choice.
    left_action = int(np.argmax(sb_probs))
    right_action = int(np.argmax(np.where(mask, np_logits, -np.inf)))
    def gap(values):
        ordered = np.sort(np.asarray(values)[mask])
        return float(ordered[-1] - ordered[-2]) if len(ordered) > 1 else None
    gaps = [gap(sb_logits), gap(np_logits)]
    logit_error = float(np.max(np.abs(sb_logits - np_logits)))
    probability_error = float(np.max(np.abs(sb_probs - np_probs)))
    return dict(logit_max_abs_error=logit_error, probability_max_abs_error=probability_error,
                sb3_action=left_action, numpy_action=right_action,
                action_match=left_action == right_action, top_two_logit_gaps=gaps,
                near_tie=any(g is not None and g <= tie_tolerance for g in gaps),
                passed=logit_error <= tolerance and probability_error <= tolerance
                and left_action == right_action)


def infer(model, numpy_policy, obs, mask, tolerance, tie_tolerance):
    import torch
    with torch.no_grad():
        tensor, _ = model.policy.obs_to_tensor(obs)
        features = model.policy.extract_features(tensor)
        latent = model.policy.mlp_extractor.forward_actor(features)
        # Categorical distribution.logits is normalized; compare action_net itself.
        logits = model.policy.action_net(latent).cpu().numpy()[0]
        probabilities = model.policy.get_distribution(tensor, action_masks=mask).distribution.probs.cpu().numpy()[0]
    return judge(logits, numpy_policy.logits(obs), probabilities,
                 numpy_policy.probabilities(obs, mask), mask, tolerance, tie_tolerance)


def synthetic_samples():
    # Contract extremes; these need not be physically reachable SC2 observations.
    patterns = {"zero": np.zeros(16, np.float32), "one": np.ones(16, np.float32),
                "minus_one": -np.ones(16, np.float32),
                "alternating_extremes": np.asarray([-1, 1] * 8, np.float32)}
    for name, obs in patterns.items():
        for mask_name, mask in (("all_legal", [True] * 5),
                                ("hold_only", [False] * 4 + [True])):
            yield obs, np.asarray(mask), dict(case=name + "/" + mask_name)


def summarize(results):
    return dict(samples=len(results), passed=all(r["passed"] for r in results),
                max_logit_abs_error=max((r["logit_max_abs_error"] for r in results), default=0),
                max_probability_abs_error=max((r["probability_max_abs_error"] for r in results), default=0),
                action_mismatches=sum(not r["action_match"] for r in results),
                near_ties=[r for r in results if r["near_tie"]],
                failures=[r for r in results if not r["passed"]])


def verify(checkpoint, actor, transitions, tolerance=1e-4, min_real_samples=1000,
           tie_tolerance=1e-6):
    if not math.isfinite(tolerance) or tolerance <= 0 or not math.isfinite(tie_tolerance) or tie_tolerance < 0:
        raise ValueError("tolerances must be finite; tolerance > 0 and tie tolerance >= 0")
    if type(min_real_samples) is not int or min_real_samples < 1:
        raise ValueError("min_real_samples must be a positive integer")
    model, numpy_policy, versions = load_pair(checkpoint, actor)
    sources, duplicates, samples, invalid = collect_sources(transitions)
    real_results = [dict(location, **infer(model, numpy_policy, obs, mask, tolerance, tie_tolerance))
                    for obs, mask, location in samples]
    synthetic_results = [dict(location, **infer(model, numpy_policy, obs, mask, tolerance, tie_tolerance))
                         for obs, mask, location in synthetic_samples()]
    real = summarize(real_results)
    real.update(invalid=invalid, invalid_count=len(invalid),
                unique_observations=len({obs.tobytes() for obs, _, _ in samples}),
                unique_observation_masks=len({(obs.tobytes(), mask.tobytes()) for obs, mask, _ in samples}),
                observations=[dict(location) for _, _, location in samples])
    synthetic = summarize(synthetic_results)
    synthetic["cases"] = synthetic_results
    met = len(samples) >= min_real_samples
    passed = bool(met and not invalid and real["passed"] and synthetic["passed"])
    return dict(format="marine-ppo-parity-v1", passed=passed,
                parity_acceptance_for_this_actor=passed,
                real_sample_threshold_met=len(samples) >= 1000,
                real_sample_threshold=1000,
                count_unit="valid source lines after file deduplication; not independent engine states",
                acceptance_mode="default_threshold" if min_real_samples >= 1000 else "explicit_small_sample",
                minimum_real=dict(required=min_real_samples, met=met, status="met" if met else "not_met"),
                tolerance=tolerance, tie_tolerance=tie_tolerance,
                contract=dict(checkpoint=str(Path(checkpoint).resolve()), checkpoint_sha256=sha256(checkpoint),
                              actor=str(Path(actor).resolve()), actor_weights_sha256=numpy_policy.metadata["weights_sha256"],
                              producer_versions=versions, normalization="marine-16-v1",
                              feature_version="marine-16-v1", action_version="marine-5-v1"),
                sources=sources, duplicate_sources=duplicates, real=real, synthetic=synthetic)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("actor", type=Path)
    parser.add_argument("--transitions", type=Path, action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--tolerance", type=float, default=1e-4)
    parser.add_argument("--tie-tolerance", type=float, default=1e-6)
    parser.add_argument("--min-real-samples", type=int, default=1000)
    args = parser.parse_args()
    # Reserve a new output before loading; never overwrite previous evidence.
    with args.output.open("x", encoding="utf-8") as stream:
        try:
            report = verify(args.checkpoint, args.actor, args.transitions, args.tolerance,
                            args.min_real_samples, args.tie_tolerance)
        except Exception as exc:
            report = dict(format="marine-ppo-parity-v1", passed=False,
                          parity_acceptance_for_this_actor=False, real_sample_threshold_met=False,
                          error=dict(type=type(exc).__name__, message=str(exc)))
        json.dump(report, stream, indent=2, allow_nan=False)
        stream.write("\n")
    print(json.dumps({k: report[k] for k in ("passed", "real_sample_threshold_met")}, allow_nan=False))
    return 0 if report["passed"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
