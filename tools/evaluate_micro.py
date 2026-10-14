"""Frozen paired local scene coverage; all games run serially, without LLM."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.report_micro import audit

CASES = [
    dict(
        id="zerg_close",
        scenario="marine-vs-zergling",
        distance=3,
        health=1,
        seed=42,
        split="train",
        limit=45,
    ),
    dict(
        id="zerg_medium",
        scenario="marine-vs-zergling",
        distance=6,
        health=1,
        seed=11,
        split="validation",
        limit=45,
    ),
    dict(
        id="marine_close",
        scenario="marine-vs-marine",
        distance=3,
        health=1,
        seed=42,
        split="train",
        limit=45,
    ),
    dict(
        id="marine_hurt",
        scenario="marine-vs-marine",
        distance=6,
        health=0.5,
        seed=11,
        split="test",
        limit=45,
    ),
    dict(
        id="zerg_hurt",
        scenario="marine-vs-zergling",
        distance=3,
        health=0.5,
        seed=21,
        split="validation",
        limit=45,
    ),
    dict(
        id="marine_medium",
        scenario="marine-vs-marine",
        distance=6,
        health=1,
        seed=31,
        split="test",
        limit=45,
    ),
    dict(
        id="unseen",
        scenario="marine-vs-zergling",
        distance=6,
        hidden=True,
        health=1,
        seed=41,
        split="test",
        limit=3,
    ),
    dict(
        id="time_limit",
        scenario="marine-vs-zergling",
        distance=6,
        health=1,
        seed=51,
        split="train",
        limit=0.6,
    ),
]


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--suite-id", default=datetime.now().strftime("micro_%Y%m%d_%H%M%S")
    )
    args = parser.parse_args()
    base = ROOT / "artifacts" / "micro_suites"
    output = (base / args.suite_id).resolve()
    if not output.is_relative_to(base.resolve()) or output == base.resolve():
        parser.error("suite-id must stay inside artifacts/micro_suites")
    output.mkdir(parents=True, exist_ok=False)
    sources = {
        str(p.relative_to(ROOT)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in [*(ROOT / "bot").glob("*.py"), ROOT / "tools/run_micro_scenario.py"]
    }
    suite = dict(
        version="marine-coverage-v4",
        cases=CASES,
        source_hashes=sources,
        runs=[],
        status="running",
    )

    def save():
        (output / "summary.json").write_text(
            json.dumps(suite, indent=2), encoding="utf-8"
        )

    save()
    for case in CASES:
        for expert in ("amove", "kite"):
            assert all(
                hashlib.sha256((ROOT / name).read_bytes()).hexdigest() == value
                for name, value in sources.items()
            )
            run_id = f"{args.suite_id}_{case['id']}_{expert}"
            command = [
                sys.executable,
                "-s",
                "-u",
                str(ROOT / "tools/run_micro_scenario.py"),
                "--scenario",
                case["scenario"],
                "--expert",
                expert,
                "--distance",
                str(case["distance"]),
                "--health-fraction",
                str(case["health"]),
                "--seed",
                str(case["seed"]),
                "--data-split",
                case["split"],
                "--max-game-seconds",
                str(case["limit"]),
                "--run-id",
                run_id,
            ]
            if case.get("hidden"):
                command.append("--enemy-hidden")
            print(f"Running {case['id']} / {expert}", flush=True)
            with (output / (run_id + ".log")).open("w", encoding="utf-8") as log:
                process = subprocess.Popen(
                    command, cwd=ROOT, stdout=log, stderr=subprocess.STDOUT
                )
                try:
                    code = process.wait(timeout=120)
                except (subprocess.TimeoutExpired, KeyboardInterrupt):
                    subprocess.run(
                        ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                        capture_output=True,
                    )
                    suite["status"] = "system_failure"
                    save()
                    raise
            directory = ROOT / "artifacts/runs" / run_id
            summary = json.loads((directory / "summary.json").read_text())
            result = json.loads((directory / "scenario_result.json").read_text())
            checked = audit(directory)
            expected_empty = expert == "amove" or case["id"] == "unseen"
            passed = (
                code == 0
                and summary["error"] is None
                and summary["counters"].get("command_conflicts", 0) == 0
                and checked["status"] == ("no_data" if expected_empty else "passed")
                and (directory / "game.SC2Replay").stat().st_size > 0
            )
            suite["runs"].append(
                dict(
                    case=case["id"],
                    expert=expert,
                    split=case["split"],
                    run_id=run_id,
                    passed=passed,
                    result=result,
                    audit=checked,
                )
            )
            save()
            if not passed:
                suite["status"] = "failed"
                save()
                raise RuntimeError(f"Scene engineering check failed: {run_id}")
    suite["status"] = "passed"
    suite["outcomes"] = {
        expert: dict(
            Counter(
                row["result"]["outcome"]
                for row in suite["runs"]
                if row["expert"] == expert
            )
        )
        for expert in ("amove", "kite")
    }
    save()
    print(
        json.dumps(
            dict(
                status=suite["status"],
                outcomes=suite["outcomes"],
                summary=str(output / "summary.json"),
            ),
            indent=2,
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
