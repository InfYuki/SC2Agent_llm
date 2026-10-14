"""One reproducible realtime Rule/Rule versus LLM/Rule engineering pilot."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from zoneinfo import ZoneInfo


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--map", default="Ancient Cistern LE")
    parser.add_argument("--wall-timeout", type=int, default=1200)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[1]
    pair_id = "strategy_" + datetime.now(ZoneInfo("Asia/Shanghai")).strftime(
        "%Y%m%d_%H%M%S"
    )
    output = root / "artifacts" / "strategy_pairs" / pair_id
    output.mkdir(parents=True, exist_ok=False)
    sources = [
        root / "run_local.py",
        root / "config.yml",
        root / "poetry.lock",
        *sorted((root / "bot").rglob("*.py")),
    ]
    hashes = {
        str(p.relative_to(root))
        .replace("\\", "/"): hashlib.sha256(p.read_bytes())
        .hexdigest()
        for p in sources
    }
    result = dict(
        pair_id=pair_id,
        status="running",
        scope="engineering pilot; n=1, no strength inference",
        config=vars(args),
        source_hashes=hashes,
        runs=[],
    )
    target = output / "summary.json"

    def save():
        target.write_text(json.dumps(result, indent=2), encoding="utf-8")

    (root / "artifacts" / "latest_strategy_pair.json").write_text(
        json.dumps({"path": str(target)}), encoding="utf-8"
    )
    save()
    for mode in ("rule", "llm"):
        current = {
            name: hashlib.sha256((root / name).read_bytes()).hexdigest()
            for name in hashes
        }
        if current != hashes:
            result["status"] = "source_changed"
            save()
            return 1
        command = [
            sys.executable,
            "-s",
            "-u",
            str(root / "tools" / "probe.py"),
            "--wall-timeout",
            str(args.wall_timeout),
            "--mode",
            mode,
            "--realtime",
            "--max-game-seconds",
            "0",
            "--map",
            args.map,
            "--seed",
            str(args.seed),
            "--llm-max-calls",
            "60",
        ]
        process = subprocess.run(
            command,
            cwd=root,
            env=dict(os.environ, PYTHONNOUSERSITE="1", PYTHONIOENCODING="utf-8"),
            capture_output=True,
            text=True,
        )
        (output / f"{mode}.log").write_text(
            process.stdout + process.stderr, encoding="utf-8"
        )
        if process.returncode:
            result.update(status="failed", failed_mode=mode)
            save()
            print("Failed pilot:", target, flush=True)
            return 1
        probe = json.loads(process.stdout.strip().splitlines()[-1])
        run = root / "artifacts" / "runs" / probe["run_id"]
        summary = json.loads((run / "summary.json").read_text())
        strategy = (
            json.loads((run / "strategy_summary.json").read_text())
            if mode == "llm"
            else None
        )
        accepted = (
            summary["status"] == "completed"
            and summary["error"] is None
            and 0.95 <= summary["game_to_wall_ratio"] <= 1.05
            and summary["peak_bases"] <= 2
            and summary["counters"].get("command_conflicts", 0) == 0
            and (run / "game.SC2Replay").stat().st_size > 1024
        )
        if strategy:
            counts = strategy["counters"]
            accepted = (
                accepted
                and counts.get("valid_plans", 0) > 0
                and counts.get("llm_steps", 0) > 0
                and counts.get("combat_goal_steps", 0) > 0
                and counts.get("economy_goal_steps", 0) > 0
                and counts.get("callbacks_while_waiting", 0) > 0
            )
        result["runs"].append(
            dict(
                mode=mode,
                probe=probe,
                summary=summary,
                strategy=strategy,
                accepted=accepted,
            )
        )
        save()
        print(
            json.dumps(dict(mode=mode, run_id=probe["run_id"], accepted=accepted)),
            flush=True,
        )
        if not accepted:
            result["status"] = "failed"
            save()
            return 1
    result["status"] = "completed"
    save()
    print("Completed pilot:", target, flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
