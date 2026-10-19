"""Explicit, reproducible local entry point; defaults to a full realtime match."""
import argparse
from datetime import datetime
import hashlib
import importlib.metadata
import json
import os
from pathlib import Path
import subprocess
import sys
import time
from zoneinfo import ZoneInfo

ROOT = Path(__file__).resolve().parent
sys.path[:0] = [str(ROOT / "ares-sc2" / "src"), str(ROOT / "ares-sc2")]


def git(*args):
    return subprocess.check_output(["git", *args], cwd=ROOT, text=True).strip()


def create_bot(options, telemetry):
    """Select the explicit composition without changing the default rule bot."""
    if options.mode == "llm_ppo":
        from bot.llm_ppo_bot import LLMPPOBot

        return LLMPPOBot(options, telemetry)
    if options.mode == "template":
        from bot.probe import InstrumentedAresBot

        return InstrumentedAresBot(options, telemetry)
    if options.mode in {"micro_rule", "rule_bc", "rule_ppo"}:
        from bot.micro_bot import MicroRuleBot

        return MicroRuleBot(options, telemetry)
    if options.mode in {"shadow", "llm"}:
        from bot.llm_bot import StrategicBot

        return StrategicBot(options, telemetry)
    from bot.rule_bot import RuleBot

    return RuleBot(options, telemetry)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--mode",
        choices=["template", "rule", "shadow", "llm", "micro_rule", "rule_bc", "rule_ppo", "llm_ppo"],
        default="rule",
    )
    parser.add_argument("--micro-max-units", type=int, choices=range(1, 5), default=4)
    parser.add_argument("--bc-model", default=None, help="Prototype BC model directory; missing/invalid models use rule micro.")
    parser.add_argument("--ppo-model", default=None, help="Exported NumPy PPO actor directory; missing/invalid models use rule micro.")
    parser.add_argument("--llm-max-calls", type=int, default=60)
    parser.add_argument(
        "--game-path",
        default=os.getenv("SC2PATH", r"C:\Program Files (x86)\StarCraft II"),
    )
    parser.add_argument("--map", default="Ancient Cistern LE")
    parser.add_argument(
        "--opponent", choices=["Zerg", "Terran", "Protoss"], default="Zerg"
    )
    parser.add_argument(
        "--difficulty",
        choices=[
            "VeryEasy",
            "Easy",
            "Medium",
            "MediumHard",
            "Hard",
            "Harder",
            "VeryHard",
        ],
        default="Medium",
    )
    parser.add_argument(
        "--realtime", action=argparse.BooleanOptionalAction, default=True
    )
    parser.add_argument("--game-step", type=int, default=8)
    parser.add_argument(
        "--max-game-seconds",
        type=float,
        default=0,
        help="Explicit test limit; 0 runs until the match ends.",
    )
    parser.add_argument("--seed", type=int, default=None)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--show-config", action="store_true")
    options = parser.parse_args()
    if (
        options.game_step < 1
        or options.max_game_seconds < 0
        or options.llm_max_calls < 0
    ):
        parser.error("game-step must be positive; max-game-seconds must be nonnegative")
    config = vars(options).copy()
    print(json.dumps(config, ensure_ascii=True, indent=2), flush=True)
    if options.show_config:
        return 0
    os.chdir(ROOT)
    os.environ["SC2PATH"] = str(Path(options.game_path).resolve())
    from sc2 import maps
    from sc2.data import AIBuild, Difficulty, Race
    from sc2.main import run_game
    from sc2.player import Bot, Computer
    from bot.telemetry import Telemetry
    from bot.lifecycle import recover_completed_game

    map_settings = maps.get(options.map)
    run_id = options.run_id or datetime.now(ZoneInfo("Asia/Shanghai")).strftime(
        "%Y%m%d_%H%M%S_%f"
    )
    base = ROOT / "artifacts" / "runs"
    output = (base / run_id).resolve()
    if not output.is_relative_to(base.resolve()) or output == base.resolve():
        raise ValueError("run-id must name a directory inside artifacts/runs")
    telemetry = Telemetry(output)
    names = git("ls-files", "--cached", "--others", "--exclude-standard", "-z").split(
        "\0"
    )
    source_hashes = {
        name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest()
        for name in names
        if name and (ROOT / name).is_file()
    }
    manifest = dict(
        config=config,
        started_utc=datetime.now(ZoneInfo("UTC")).isoformat(),
        python=sys.executable,
        python_version=sys.version,
        project_commit=git("rev-parse", "HEAD"),
        ares_commit=git("-C", "ares-sc2", "rev-parse", "HEAD"),
        dirty_diff_sha256=hashlib.sha256(
            subprocess.check_output(["git", "diff", "HEAD"], cwd=ROOT)
        ).hexdigest(),
        source_hashes=source_hashes,
        map_sha256=hashlib.sha256(Path(map_settings.path).read_bytes()).hexdigest(),
        packages={
            name: importlib.metadata.version(name)
            for name in [
                "ares-sc2",
                "burnysc2",
                "map-analyzer",
                "cython-extensions-sc2",
                "numpy",
            ]
        },
    )
    telemetry.write_json("manifest.json", manifest)
    (ROOT / "artifacts" / "latest_run.json").write_text(
        json.dumps(dict(output_dir=str(output)), indent=2), encoding="utf-8"
    )
    ai = create_bot(options, telemetry)
    print("Run output:", output, flush=True)
    started = time.perf_counter()
    try:
        with recover_completed_game(telemetry):
            result = run_game(
                map_settings,
                [
                    Bot(Race.Terran, ai, "LocalMarineRule"),
                    Computer(
                        Race[options.opponent],
                        Difficulty[options.difficulty],
                        AIBuild.Macro,
                    ),
                ],
                realtime=options.realtime,
                random_seed=options.seed,
                save_replay_as=str(output / "game.SC2Replay"),
            )
        telemetry.finish(result)
    except KeyboardInterrupt:
        telemetry.stop_reason = "user_interrupt"
        telemetry.finish()
        return 130
    except Exception:
        if telemetry.error is None:
            telemetry.fail("run_game")
        telemetry.finish()
        raise
    finally:
        if hasattr(ai, "close_micro"):
            ai.close_micro("system_failure" if telemetry.error else None)
        if hasattr(ai, "close_strategy"):
            ai.close_strategy()
        manifest["process_game_seconds"] = time.perf_counter() - started
        telemetry.write_json("manifest.json", manifest)
    return 1 if telemetry.error else 0


if __name__ == "__main__":
    raise SystemExit(main())
