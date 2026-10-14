"""Sequential full-match engineering acceptance, with resumable explicit cases."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parents[1]


def runtime_hashes():
    paths = [
        *sorted((ROOT / "bot").rglob("*.py")),
        ROOT / "run_local.py",
        ROOT / "config.yml",
        ROOT / "poetry.lock",
    ]
    return {
        str(p.relative_to(ROOT))
        .replace("\\", "/"): hashlib.sha256(p.read_bytes())
        .hexdigest()
        for p in paths
    }


def validate_run(run_id, expected_hashes):
    folder = ROOT / "artifacts" / "runs" / run_id
    summary = json.loads((folder / "summary.json").read_text(encoding="utf-8"))
    manifest = json.loads((folder / "manifest.json").read_text(encoding="utf-8"))
    hashes = {k.replace("\\", "/"): v for k, v in manifest["source_hashes"].items()}
    if any(hashes.get(k) != v for k, v in expected_hashes.items()):
        raise ValueError(
            "Runtime source changed; use a new suite instead of mixing candidates"
        )
    if summary["status"] != "completed" or summary["error"] is not None:
        raise ValueError("Run did not finish normally")
    if summary["counters"].get("command_conflicts", 0) or summary["peak_marines"] < 1:
        raise ValueError("Command ownership or production acceptance failed")
    if summary["peak_bases"] > 2:
        raise ValueError("Expansion exceeded the current two-base target")
    replay = folder / "game.SC2Replay"
    if not replay.is_file() or replay.stat().st_size < 1024:
        raise ValueError("Missing replay")
    return dict(run_id=run_id, config=manifest["config"], summary=summary)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--maps", nargs="+", default=["Ancient Cistern LE", "Babylon LE"]
    )
    parser.add_argument("--seeds", nargs="+", type=int, default=[42, 11, 21, 31, 41])
    parser.add_argument("--include-run", action="append", default=[])
    parser.add_argument("--wall-timeout", type=int, default=900)
    args = parser.parse_args()
    suite_id = "rule_" + datetime.now(ZoneInfo("Asia/Shanghai")).strftime(
        "%Y%m%d_%H%M%S"
    )
    output = ROOT / "artifacts" / "suites" / suite_id
    output.mkdir(parents=True, exist_ok=False)
    state = dict(
        suite_id=suite_id,
        status="running",
        runtime_hashes=runtime_hashes(),
        maps=args.maps,
        seeds=args.seeds,
        matches=[],
        current=None,
        failure=None,
    )

    def save():
        target = output / "summary.json"
        temporary = target.with_suffix(".tmp")
        temporary.write_text(json.dumps(state, indent=2), encoding="utf-8")
        temporary.replace(target)

    save()
    (output.parent / "latest.json").write_text(
        json.dumps(dict(output_dir=str(output))), encoding="utf-8"
    )
    try:
        for run_id in args.include_run:
            item = validate_run(run_id, state["runtime_hashes"])
            c = item["config"]
            if (
                c["mode"] != "rule"
                or c["realtime"]
                or c["seed"] not in args.seeds
                or c["map"] not in args.maps
            ):
                raise ValueError(
                    "Included run does not belong to this fixed-step rule suite"
                )
            state["matches"].append(item)
        done = {
            (item["config"]["map"], item["config"]["seed"]) for item in state["matches"]
        }
        env = dict(
            os.environ,
            PYTHONNOUSERSITE="1",
            PYTHONIOENCODING="utf-8",
            PYTHONUNBUFFERED="1",
        )
        for map_name in args.maps:
            for seed in args.seeds:
                if (map_name, seed) in done:
                    continue
                if runtime_hashes() != state["runtime_hashes"]:
                    raise ValueError("Runtime source changed during suite")
                index = len(state["matches"])
                run_id = f"{suite_id}_{index:02d}"
                state["current"] = dict(run_id=run_id, map=map_name, seed=seed)
                save()
                print("Starting", json.dumps(state["current"]), flush=True)
                command = [
                    sys.executable,
                    "-s",
                    "-u",
                    str(ROOT / "run_local.py"),
                    "--mode",
                    "rule",
                    "--no-realtime",
                    "--max-game-seconds",
                    "0",
                    "--map",
                    map_name,
                    "--seed",
                    str(seed),
                    "--run-id",
                    run_id,
                ]
                started = time.perf_counter()
                with (output / f"{run_id}.log").open("w", encoding="utf-8") as log:
                    process = subprocess.Popen(
                        command, cwd=ROOT, env=env, stdout=log, stderr=subprocess.STDOUT
                    )
                    try:
                        code = process.wait(timeout=args.wall_timeout)
                    except (subprocess.TimeoutExpired, KeyboardInterrupt):
                        subprocess.run(
                            ["taskkill", "/PID", str(process.pid), "/T", "/F"],
                            capture_output=True,
                        )
                        process.wait()
                        raise
                if code:
                    raise ValueError(f"Game process failed: {code}")
                item = validate_run(run_id, state["runtime_hashes"])
                item["process_seconds"] = time.perf_counter() - started
                state["matches"].append(item)
                save()
                print(
                    "Completed",
                    len(state["matches"]),
                    item["summary"]["result"],
                    flush=True,
                )
        state["current"] = None
        state["status"] = "passed"
    except BaseException as exc:
        state["status"] = "failed"
        state["failure"] = dict(type=type(exc).__name__, message=str(exc))
        save()
        raise
    save()
    print("Suite report:", output / "summary.json", flush=True)


if __name__ == "__main__":
    main()
