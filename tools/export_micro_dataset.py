"""Freeze audited expert demonstrations for later BC; does not train a model."""
import argparse
from collections import Counter
import hashlib
import json
from pathlib import Path
import numpy as np

ROOT = Path(__file__).resolve().parents[1]



def check_learning_exclusion(directory, digest):
    sidecar = directory / "learning_exclusion.json"
    if not sidecar.exists():
        return  # Legacy expert demonstrations predate exclusion sidecars.
    try:
        record = json.loads(sidecar.read_text(encoding="utf-8"))
        hashes = record["raw_sha256"]
        if (not isinstance(record["excluded_from_future_training"], bool)
                or not isinstance(hashes, dict)
                or hashes.get("micro_transitions.jsonl") != digest
                or record.get("run_id", directory.name) != directory.name):
            raise ValueError("Invalid learning exclusion sidecar")
        for name, expected in hashes.items():
            path = directory / name
            if (not isinstance(name, str) or Path(name).name != name
                    or not isinstance(expected, str) or not path.is_file()
                    or hashlib.sha256(path.read_bytes()).hexdigest() != expected):
                raise ValueError("Learning exclusion raw SHA mismatch")
        if record["excluded_from_future_training"]:
            raise ValueError("Run explicitly excluded from future training: " + directory.name)
    except (KeyError, TypeError, json.JSONDecodeError) as error:
        raise ValueError("Invalid learning exclusion sidecar") from error

def export(summary_path, output, *, additional_summaries=()):
    summary_paths = [Path(summary_path), *(Path(p) for p in additional_summaries)]
    output = Path(output)
    if output.exists():
        raise FileExistsError("Use a new dataset output directory; never overwrite datasets")
    suites, source_suites = [], []
    for source_index, path in enumerate(summary_paths):
        content = path.read_bytes()
        suite = json.loads(content)
        if (suite["status"] != "passed"
                or any(r.get("passed") is not True or r.get("status", "passed") != "passed"
                       for r in suite["runs"])
                or suite.get("selected", {}).get("run_count", len(suite["runs"])) != len(suite["runs"])):
            raise ValueError("Only a fully passed frozen suite can be exported")
        suites.append(suite)
        source_suites.append(dict(
            source_index=source_index, path=str(path.resolve()),
            sha256=hashlib.sha256(content).hexdigest(), status=suite["status"],
            run_count=len(suite["runs"]),
            expert_run_count=sum(r["expert"] == "kite" for r in suite["runs"]),
            runs=[dict(run_index=i, run_id=r["run_id"], expert=r["expert"],
                       case=r.get("case"), split=r.get("split"),
                       audited_raw_sha256=r.get("audit", {}).get("source_sha256"),
                       passed=r["passed"], status=r.get("status", "passed"))
                  for i, r in enumerate(suite["runs"])],
        ))
    rows, inputs, group_splits = [], [], {}
    expert_versions, scenario_versions = set(), set()
    run_ids, raw_sources = {}, {}
    duplicate_references = 0
    references = ((source_index, run_index, run)
                  for source_index, suite in enumerate(suites)
                  for run_index, run in enumerate(suite["runs"]))
    for source_index, run_index, run in references:
        if run["expert"] != "kite":
            continue
        group, split = run["case"], run["split"]
        if split not in {"train", "validation", "test"}:
            raise ValueError("Unsupported data split")
        if group in group_splits and group_splits[group] != split:
            raise ValueError("Same scenario group leaked across splits")
        group_splits[group] = split
        path = ROOT / "artifacts/runs" / run["run_id"] / "micro_transitions.jsonl"
        raw = path.read_bytes()
        digest = hashlib.sha256(raw).hexdigest()
        if digest != run["audit"]["source_sha256"]:
            raise ValueError("Audited input changed: " + run["run_id"])
        check_learning_exclusion(path.parent, digest)
        if run["run_id"] in run_ids and run_ids[run["run_id"]][0] != run:
            raise ValueError("Conflicting run identity: " + run["run_id"])
        if raw and digest in raw_sources and raw_sources[digest][0] != (group, split):
            raise ValueError("Same raw content assigned to different case/split")
        # Validate every reference before deduplication, including exclusions and rows.
        run_rows = []
        for line in raw.decode("utf-8").splitlines():
            row = json.loads(line)
            versions = row["versions"]
            if (
                versions["feature"],
                versions["action"],
                versions["decision_game_loops"],
            ) != ("marine-16-v1", "marine-5-v1", 8):
                raise ValueError("Incompatible demonstration contract")
            expert_version, scenario_version = versions.get("expert"), versions.get(
                "scenario"
            )
            if (
                expert_version != "marine-kite-v1"
                or not isinstance(scenario_version, str)
                or not scenario_version
            ):
                raise ValueError("Missing or unsupported demonstration provenance")
            expert_versions.add(expert_version)
            scenario_versions.add(scenario_version)
            if row["split"] != split:
                raise ValueError("Illegal label or inconsistent split")
            if not row["bc_eligible"]:
                continue
            if (
                row["command_result"] not in {"engine_confirmed", "hold"}
                or row["truncated"]
                or row["actual_game_loops"] != 8
            ):
                raise ValueError("Incorrect BC eligibility")
            if (
                not 0 <= row["executed_action"] < 5
                or not row["mask"][row["executed_action"]]
            ):
                raise ValueError("Illegal label or inconsistent split")
            run_rows.append((row, group, split))
        reference = dict(source_index=source_index, run_index=run_index,
                         run_id=run["run_id"], sha256=digest)
        previous = run_ids.get(run["run_id"])
        canonical = previous[1] if previous else (raw_sources.get(digest, (None, None))[1] if raw else None)
        if canonical is not None:
            inputs[canonical]["source_references"].append(reference)
            duplicate_references += 1
        else:
            canonical = len(inputs)
            inputs.append(dict(run_id=run["run_id"], sha256=digest,
                               case=group, split=split, source_references=[reference]))
            rows.extend(run_rows)
        run_ids[run["run_id"]] = (run, canonical)
        if raw:
            raw_sources[digest] = ((group, split), canonical)
    if not rows:
        raise ValueError("No eligible demonstrations")
    output.mkdir(parents=True, exist_ok=False)
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
    split_coverage = {}
    for split in ("train", "validation", "test"):
        actions = Counter(r[0]["executed_action"] for r in rows if r[2] == split)
        split_coverage[split] = dict(
            samples=sum(actions.values()),
            action_counts={str(i): actions[i] for i in range(5)},
            missing_actions=[i for i in range(5) if not actions[i]],
        )
    metadata = dict(
        samples=len(rows),
        feature_version="marine-16-v1",
        action_version="marine-5-v1",
        decision_game_loops=8,
        expert_versions=sorted(expert_versions),
        scenario_versions=sorted(scenario_versions),
        input_files=inputs,
        group_splits=group_splits,
        split_counts=dict(Counter(r[2] for r in rows)),
        split_coverage=split_coverage,
        action_counts=dict(counts),
        missing_actions=[i for i in range(5) if not counts[i]],
        dataset_sha256=hashlib.sha256(dataset.read_bytes()).hexdigest(),
        suite_sha256=source_suites[0]["sha256"] if len(source_suites) == 1 else None,
        source_suites=source_suites,
        source_manifest_sha256=hashlib.sha256(
            json.dumps(source_suites, sort_keys=True).encode("utf-8")
        ).hexdigest(),
        merge_order="summary_argument_order_then_suite_run_order_then_raw_row_order",
        duplicate_references=duplicate_references,
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
    parser.add_argument("--additional-summary", type=Path, action="append", default=[])
    args = parser.parse_args()
    print(json.dumps(export(args.summary, args.output, additional_summaries=args.additional_summary), indent=2))


if __name__ == "__main__":
    main()
