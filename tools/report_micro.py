"""Audit real P3 data without launching SC2 or invoking any remote model."""
import argparse
from collections import Counter, defaultdict
import hashlib
import json
import math
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bot.micro import ACTION_VERSION, DECISION_LOOPS, FEATURE_VERSION


def audit(output):
    path = Path(output) / "micro_transitions.jsonl"
    groups = defaultdict(list)
    results, actions, intervals, splits = Counter(), Counter(), Counter(), set()
    errors = []
    total = eligible = 0
    for number, line in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        row = json.loads(line)
        total += 1
        groups[row["engagement_id"]].append(row)
        results[row["command_result"]] += 1
        actions[row["requested_action"]] += 1
        intervals[row["actual_game_loops"]] += 1
        splits.add(row["split"])
        eligible += int(row["bc_eligible"])

        def require(condition, message):
            if not condition:
                errors.append(f"row {number}: {message}")

        for key in ("obs", "next_obs"):
            vector = row[key]
            if vector is not None:
                require(
                    len(vector) == 16
                    and all(math.isfinite(v) and -1 <= v <= 1 for v in vector),
                    key,
                )
        mask = row["mask"]
        require(
            len(mask) == 5 and all(type(v) is bool for v in mask) and mask[4], "mask"
        )
        require(
            0 <= row["requested_action"] < 5 and mask[row["requested_action"]],
            "requested action",
        )
        require(
            0 <= row["executed_action"] < 5 and mask[row["executed_action"]],
            "executed action",
        )
        require(row["next_game_loop"] >= row["game_loop"], "frame order")
        require(
            row["actual_game_loops"] == row["next_game_loop"] - row["game_loop"],
            "frame interval",
        )
        require(not (row["terminated"] and row["truncated"]), "episode flags")
        require(
            row["next_observation_valid"] == (row["next_obs"] is not None),
            "next observation validity",
        )
        require(
            row["versions"]["feature"] == FEATURE_VERSION
            and row["versions"]["action"] == ACTION_VERSION,
            "versions",
        )
        if row["command_result"] == "engine_confirmed":
            require(
                row["game_loop"] <= row["confirmed_game_loop"] <= row["next_game_loop"],
                "confirmation frame",
            )
        if row["bc_eligible"]:
            require(
                row["command_result"] in {"engine_confirmed", "hold"}
                and row["actual_game_loops"] == DECISION_LOOPS
                and not row["truncated"],
                "BC eligibility",
            )
    require_one_split = len(splits) <= 1
    if not require_one_split:
        errors.append("match spans data splits")
    for episode, rows in groups.items():
        for before, after in zip(rows, rows[1:]):
            if (
                before["terminated"]
                or before["truncated"]
                or before["next_game_loop"] != after["game_loop"]
            ):
                errors.append(f"episode discontinuity: {episode}")
            if before["next_obs"] != after["obs"]:
                errors.append(f"observation discontinuity: {episode}")
        if not (rows[-1]["terminated"] or rows[-1]["truncated"]):
            errors.append(f"episode has no closing boundary: {episode}")
    summary = json.loads((Path(output) / "summary.json").read_text(encoding="utf-8"))
    if summary["counters"].get("command_conflicts", 0) or summary["error"]:
        errors.append("game error or command conflict")
    if summary["counters"].get("micro_policy_errors", 0):
        errors.append("micro policy exception")
    report = dict(
        status="failed" if errors else "passed" if total else "no_data",
        transitions=total,
        episodes=len(groups),
        bc_eligible=eligible,
        command_results=dict(results),
        requested_actions=dict(actions),
        game_loop_intervals=dict(intervals),
        split=sorted(splits),
        errors=errors,
        source_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),
        match_status=summary["status"],
        match_result=summary["result"],
        learning_readiness="not_evaluated",
        reward="not_implemented",
    )
    (Path(output) / "micro_audit.json").write_text(
        json.dumps(report, indent=2), encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    report = audit(args.output)
    print(json.dumps(report, indent=2))
    return 0 if report["status"] == "passed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
