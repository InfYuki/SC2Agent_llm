"""Freeze audited expert demonstrations for later BC; does not train a model."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]


def export(summary_path, output):
    suite = json.loads(summary_path.read_text(encoding="utf-8"))
    if suite["status"] != "passed":
        raise ValueError("Only a fully passed frozen suite can be exported")
    output.mkdir(parents=True, exist_ok=False)
    rows, inputs, group_splits = [], [], {}
    for run in suite["runs"]:
        if run["expert"] != "kite":
            continue
        path = ROOT / "artifacts/runs" / run["run_id"] / "micro_transitions.jsonl"
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        if digest != run["audit"]["source_sha256"]:
            raise ValueError("Audited input changed: " + run["run_id"])
        inputs.append(dict(run_id=run["run_id"], sha256=digest))
        for line in path.read_text(encoding="utf-8").splitlines():
            row = json.loads(line)
            versions = row["versions"]
            if (
                versions["feature"],
                versions["action"],
                versions["decision_game_loops"],
            ) != ("marine-16-v1", "marine-5-v1", 8):
                raise ValueError("Incompatible demonstration contract")
            if not row["bc_eligible"]:
                continue
            if (
                row["command_result"] not in {"engine_confirmed", "hold"}
                or row["truncated"]
                or row["actual_game_loops"] != 8
            ):
                raise ValueError("Incorrect BC eligibility")
            group = run["case"]
            split = run["split"]
            if group in group_splits and group_splits[group] != split:
                raise ValueError("Same scenario group leaked across splits")
            group_splits[group] = split
            if row["split"] != split or not row["mask"][row["executed_action"]]:
                raise ValueError("Illegal label or inconsistent split")
            rows.append((row, group, split))
    if not rows:
        raise ValueError("No eligible demonstrations")
    dataset = output / "demonstrations.npz"
    np.savez_compressed(
        dataset,
        obs=np.array([r[0]["obs"] for r in rows], dtype=np.float32),
        mask=np.array([r[0]["mask"] for r in rows], dtype=bool),
        action=np.array([r[0]["executed_action"] for r in rows], dtype=np.int64),
        game_loop=np.array([r[0]["game_loop"] for r in rows], dtype=np.int64),
        group=np.array([r[1] for r in rows]),
        split=np.array([r[2] for r in rows]),
    )
    counts = Counter(r[0]["executed_action"] for r in rows)
    metadata = dict(
        samples=len(rows),
        feature_version="marine-16-v1",
        action_version="marine-5-v1",
        decision_game_loops=8,
        input_files=inputs,
        group_splits=group_splits,
        split_counts=dict(Counter(r[2] for r in rows)),
        action_counts=dict(counts),
        missing_actions=[i for i in range(5) if not counts[i]],
        dataset_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
        suite_sha256=hashlib.sha256(summary_path.read_bytes()).hexdigest(),
        training_readiness="not_established",
        models_trained=False,
    )
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2), encoding="utf-8"
    )
    return metadata


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("summary", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    print(json.dumps(export(args.summary, args.output), indent=2))


if __name__ == "__main__":
    main()
