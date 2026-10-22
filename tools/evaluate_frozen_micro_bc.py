"""Offline diagnostics for two already frozen BC models; never trains or selects."""
import argparse
import hashlib
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bot.micro_bc import NumpyBCPolicy
from tools.train_micro_bc import load_dataset, loss_gradient, sha256

NEW_CASES = {"dual_zergling_validation": "validation", "dual_zergling_test": "test"}


def row_keys(data, with_mask=False):
    # Source observations already are normalized marine-16-v1 float32 values.
    # Canonical little endian bytes, no rounding; +0 and -0 mean the same state.
    obs = data["obs"].astype("<f4", copy=True)
    obs[obs == 0] = 0
    return [row.tobytes() + (data["mask"][i].tobytes() if with_mask else b"")
            for i, row in enumerate(obs)]


def overlap(data, left, right, keys):
    indexed = {}
    for i in right:
        indexed.setdefault(keys[i], []).append(int(i))
    evidence = [dict(left_row=int(i), right_rows=indexed[keys[i]],
                     canonical_sha256=hashlib.sha256(keys[i]).hexdigest())
                for i in left if keys[i] in indexed]
    return dict(left_samples=len(left), right_samples=len(right),
                matched_left_rows=len(evidence),
                matching_pairs=sum(len(e["right_rows"]) for e in evidence), evidence=evidence)


def duplicate_audit(data, historical_count, cases):
    old = {s: np.flatnonzero((np.arange(len(data["obs"])) < historical_count) &
                            (data["split"] == s)) for s in ("train", "validation", "test")}
    new = {case: np.flatnonzero(data["group"] == case) for case in cases}
    result = {}
    for mode in ("obs", "obs_plus_mask"):
        keys = row_keys(data, mode == "obs_plus_mask")
        historical = {f"{a}_vs_{b}": overlap(data, old[a], old[b], keys)
                      for a, b in (("train", "validation"), ("train", "test"), ("validation", "test"))}
        added = {f"{case}_vs_old_{s}": overlap(data, indices, old[s], keys)
                 for case, indices in new.items() for s in old}
        a, b = cases
        added[f"{a}_vs_{b}"] = overlap(data, new[a], new[b], keys)
        result[mode] = dict(historical_cross_split=historical, new_vs_history_and_each_other=added)
    result["new_heldout_independent"] = all(
        not item["matching_pairs"] for mode in ("obs", "obs_plus_mask")
        for item in result[mode]["new_vs_history_and_each_other"].values())
    result["comparison"] = "exact source NPZ float32 obs; signed zero canonicalized; next_obs excluded"
    return result


def preserved_history(baseline, merged, baseline_dir, merged_dir):
    count = len(baseline["obs"])
    if count != 93:
        raise ValueError("Expected complete historical 93-sample baseline")
    # Include game_loop and any future exporter arrays, not just loader's subset.
    with np.load(Path(baseline_dir) / "demonstrations.npz", allow_pickle=False) as a, np.load(
            Path(merged_dir) / "demonstrations.npz", allow_pickle=False) as b:
        if set(a.files) != set(b.files):
            raise ValueError("Historical array schema changed")
        for key in a.files:
            if not np.array_equal(a[key], b[key][:count]):
                raise ValueError("Historical 93-row prefix changed: " + key)
    splits = {}
    for split in ("validation", "test"):
        historical = np.flatnonzero(baseline["split"] == split)
        preserved = all(np.array_equal(baseline[k][historical], merged[k][historical]) for k in baseline)
        splits[split] = dict(rows=historical.tolist(), samples=len(historical), order_and_content_preserved=preserved)
    return dict(samples=count, all_npz_arrays_prefix_preserved=True, old_heldout=splits)


def evaluate(dataset, baseline, models, labels, cases):
    if len(models) != 2 or len(labels) != 2 or len(set(labels)) != 2:
        raise ValueError("Provide exactly two models with distinct explicit labels")
    if len(cases) != 2 or set(cases) != set(NEW_CASES):
        raise ValueError("Explicitly select the two new heldout cases")
    data, metadata = load_dataset(dataset)
    old, old_meta = load_dataset(baseline)
    preservation = preserved_history(old, data, baseline, dataset)
    count = len(old["obs"])
    if any(g not in cases for g in data["group"][count:]):
        raise ValueError("Unexpected added groups")
    missing_cases = []
    for case in cases:
        indices = np.flatnonzero(data["group"] == case)
        if not len(indices):
            missing_cases.append(case)
            continue
        if ((indices < count).any() or
                set(data["split"][indices].tolist()) != {NEW_CASES[case]} or
                metadata["group_splits"].get(case) != NEW_CASES[case]):
            raise ValueError("Missing or incorrectly assigned heldout case: " + case)
    paths = [Path(p) for p in models]
    before = [{name: sha256(p / name) for name in ("weights.npz", "metadata.json")} for p in paths]
    policies = [NumpyBCPolicy.load(p) for p in paths]
    metrics = {}
    for case in cases:
        indices = np.flatnonzero(data["group"] == case)
        obs, mask, action = (data[k][indices] for k in ("obs", "mask", "action"))
        case_result = dict(split=NEW_CASES[case], samples=len(indices), rows=indices.tolist(),
                           status="missing_eligible_samples" if not len(indices) else "evaluated",
                           label_counts={str(a): int(np.sum(action == a)) for a in range(5)}, models={})
        predictions = []
        for label, policy in zip(labels, policies):
            if not len(indices):
                case_result["models"][label] = dict(samples=0, masked_loss=None, masked_accuracy=None,
                    action_recall={str(a): None for a in range(5)},
                    action_confusion_true_rows_predicted_columns=np.zeros((5, 5), dtype=int).tolist())
                continue
            predicted = np.array([policy.action(o, m) for o, m in zip(obs, mask)])
            predictions.append(predicted)
            confusion = np.zeros((5, 5), dtype=np.int64)
            np.add.at(confusion, (action, predicted), 1)
            case_result["models"][label] = dict(
                **loss_gradient(policy.weights, obs, mask, action, gradients=False),
                action_recall={str(a): float(np.mean(predicted[action == a] == a))
                               if np.any(action == a) else None for a in range(5)},
                action_confusion_true_rows_predicted_columns=confusion.tolist())
        case_result["two_model_agreement"] = float(np.mean(predictions[0] == predictions[1])) if predictions else None
        metrics[case] = case_result
    after = [{name: sha256(p / name) for name in ("weights.npz", "metadata.json")} for p in paths]
    if before != after:
        raise RuntimeError("Frozen model files changed during evaluation")
    duplicates = duplicate_audit(data, count, cases)
    independent = duplicates["new_heldout_independent"] and not missing_cases
    duplicates["new_heldout_independent"] = independent
    return dict(format="frozen-micro-bc-heldout-v1", diagnostic_only=True,
        training_updates=0, epoch_selection=False, promotion=False,
        dataset_sha256=metadata["dataset_sha256"], baseline_sha256=old_meta["dataset_sha256"],
        preservation=preservation,
        models=[dict(label=label, path=str(p.resolve()), sha256_before=a, sha256_after=b,
                     files_unchanged=a == b) for label, p, a, b in zip(labels, paths, before, after)],
        cases=metrics, duplicate_audit=duplicates,
        qualification=dict(independent_heldout=independent, missing_eligible_cases=missing_cases,
            reason="rejected_missing_eligible_samples" if missing_cases else
                "no_exact_observation_overlap" if independent else "rejected_exact_observation_overlap",
            scope="exact observation independence only; no training-readiness or combat-benefit claim"))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--dataset", type=Path, required=True)
    parser.add_argument("--baseline-dataset", type=Path, required=True)
    parser.add_argument("--model", type=Path, action="append", required=True)
    parser.add_argument("--label", action="append", required=True)
    parser.add_argument("--case", choices=list(NEW_CASES), action="append", required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    if args.output.exists():
        raise FileExistsError("Use a new evaluation report path")
    report = evaluate(args.dataset, args.baseline_dataset, args.model, args.label, args.case)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with args.output.open("x", encoding="utf-8") as stream:
        stream.write(json.dumps(report, indent=2, allow_nan=False) + "\n")
    print(json.dumps(dict(output=str(args.output), qualification=report["qualification"])))


if __name__ == "__main__":
    main()
