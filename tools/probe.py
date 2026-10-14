"""Run an owned local game with a wall-clock watchdog and an independent log."""
import argparse
from datetime import datetime
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--wall-timeout", type=int, default=600)
    args, game_args = parser.parse_known_args()
    root = Path(__file__).resolve().parents[1]
    run_id = "probe_" + datetime.now(ZoneInfo("Asia/Shanghai")).strftime(
        "%Y%m%d_%H%M%S_%f"
    )
    folder = root / "artifacts" / "probes"
    folder.mkdir(parents=True, exist_ok=True)
    env = dict(
        os.environ, PYTHONIOENCODING="utf-8", PYTHONNOUSERSITE="1", PYTHONUNBUFFERED="1"
    )
    command = [
        sys.executable,
        "-s",
        "-u",
        str(root / "run_local.py"),
        "--run-id",
        run_id,
        *game_args,
    ]
    start = time.perf_counter()
    with (folder / f"{run_id}.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(
            command, cwd=root, env=env, stdout=log, stderr=subprocess.STDOUT
        )
        try:
            code = process.wait(timeout=args.wall_timeout)
        except subprocess.TimeoutExpired:
            subprocess.run(
                ["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True
            )
            process.wait()
            code = "wall_timeout"
    result = dict(
        run_id=run_id,
        exit_code=code,
        process_seconds=time.perf_counter() - start,
        command=command,
        log=str(folder / f"{run_id}.log"),
    )
    (folder / f"{run_id}.json").write_text(
        json.dumps(result, indent=2), encoding="utf-8"
    )
    print(json.dumps(result), flush=True)
    return 0 if code == 0 else 1


if __name__ == "__main__":
    raise SystemExit(main())
