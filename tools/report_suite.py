"""Summarize an actual acceptance suite without inventing missing matches."""
import argparse
import csv
import json
import math
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--suite", type=Path, default=None)
    args = parser.parse_args()
    folder = args.suite or Path(
        json.loads((ROOT / "artifacts/suites/latest.json").read_text())["output_dir"]
    )
    state = json.loads((folder / "summary.json").read_text())
    rows = []
    for item in state["matches"]:
        config, summary = item["config"], item["summary"]
        rows.append(
            dict(
                run_id=item["run_id"],
                map=config["map"],
                seed=config["seed"],
                result=summary["result"],
                status=summary["status"],
                game_seconds=summary["game_span_seconds"],
                wall_seconds=summary["wall_span_seconds"],
                workers=summary["peak_workers"],
                marines=summary["peak_marines"],
                bases=summary["peak_bases"],
                on_step_p95_ms=summary["on_step_p95_seconds"] * 1000,
                command_conflicts=summary["counters"].get("command_conflicts", 0),
            )
        )
    if rows:
        with (folder / "matches.csv").open(
            "w", encoding="utf-8-sig", newline=""
        ) as stream:
            writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
            writer.writeheader()
            writer.writerows(rows)
    wins = sum(row["result"] == "Result.Victory" for row in rows)
    n = len(rows)
    interval = None
    if n:
        z = 1.95996398454
        p = wins / n
        center = (p + z * z / (2 * n)) / (1 + z * z / n)
        radius = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / (1 + z * z / n)
        interval = [center - radius, center + radius]
    metrics = dict(
        suite_id=state["suite_id"],
        suite_status=state["status"],
        completed=n,
        planned=len(state["maps"]) * len(state["seeds"]),
        wins=wins,
        win_rate=wins / n if n else None,
        wilson_95=interval,
        current=state["current"],
        failure=state["failure"],
    )
    (folder / "metrics.json").write_text(
        json.dumps(metrics, indent=2), encoding="utf-8"
    )
    print(json.dumps(metrics, indent=2))


if __name__ == "__main__":
    main()
