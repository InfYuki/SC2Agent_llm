"""One local human match followed by bounded learning in the training runtime."""
import argparse
from datetime import datetime
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))


def configuration(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--training-python", type=Path, default=Path(os.getenv("SC2_TRAINING_PYTHON", str(ROOT.parent / "sc2-ares-training" / "Scripts" / "python.exe"))))
    parser.add_argument("--memory-dir", type=Path, default=ROOT / "artifacts" / "human_training" / "memory")
    parser.add_argument("--checkpoint", type=Path)
    parser.add_argument("--actor", type=Path)
    parser.add_argument("--run-id", default=None)
    parser.add_argument("--learn", choices=("ask", "yes", "no"), default="ask", help="Post-match learning decision; default asks, only explicit yes learns.")
    parser.add_argument("--learn-run", help="Decide learning for an existing run ID without starting SC2.")
    parser.add_argument("--show-config", action="store_true")
    parser.add_argument("--check-only", action="store_true", help="Validate local dependencies, policy identity and LLM settings without opening SC2 or calling the API.")
    args, game_args = parser.parse_known_args(argv)
    reserved = {"--ppo-model", "--human-checkpoint", "--strategy-memory", "--human-training",
                "--mode", "--opponent", "--no-realtime", "--difficulty"}
    if any(token.split("=", 1)[0] in reserved for token in game_args):
        parser.error("Human mode/race/realtime and learning identities are fixed; use --checkpoint with --actor to select a policy")
    if bool(args.checkpoint) != bool(args.actor):
        parser.error("--checkpoint and --actor must be supplied together")
    memory = args.memory_dir.resolve()
    if args.learn_run:
        existing = (ROOT / "artifacts" / "runs" / args.learn_run).resolve()
        if existing.parent != (ROOT / "artifacts" / "runs").resolve():
            parser.error("--learn-run must be a direct run ID")
        metadata = json.loads((existing / "human_training.json").read_text(encoding="utf-8"))
        checkpoint = Path(metadata["checkpoint"])
        learn = [str(args.training_python.resolve()), "-s", "-u", str(ROOT / "tools" / "learn_human_match.py"), "--run-dir", str(existing), "--checkpoint", str(checkpoint), "--output", str(existing / "learning"), "--memory-dir", str(memory)]
        return args, dict(run_id=args.learn_run, run_dir=str(existing), learning_command=learn, learning_mode=args.learn)
    latest = memory / "ppo_latest.json"
    if args.checkpoint:
        checkpoint, actor = args.checkpoint.resolve(), args.actor.resolve()
    elif latest.is_file():
        pointer = json.loads(latest.read_text(encoding="utf-8"))
        if pointer.get("format") != "human-ppo-latest-v1":
            raise ValueError("Invalid latest human PPO pointer")
        checkpoint, actor = Path(pointer["checkpoint"]), Path(pointer["actor"])
        if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != pointer["checkpoint_sha256"]:
            raise ValueError("Latest human checkpoint hash mismatch")
    else:
        checkpoint = ROOT / "artifacts" / "micro_ppo" / "p5_two_enemy448_20261021" / "model.zip"
        actor = ROOT / "artifacts" / "models" / "marine_ppo_two_enemy448_20261021"
    from bot.micro_ppo import NumpyPPOPolicy
    policy = NumpyPPOPolicy.load(actor)
    if hashlib.sha256(checkpoint.read_bytes()).hexdigest() != policy.metadata["producer"]["source_checkpoint_sha256"]:
        raise ValueError("Actor/checkpoint identity mismatch")
    run_id = args.run_id or "human_" + datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    run_dir = (ROOT / "artifacts" / "runs" / run_id).resolve()
    if not run_dir.is_relative_to((ROOT / "artifacts" / "runs").resolve()) or run_dir == (ROOT / "artifacts" / "runs").resolve():
        raise ValueError("run-id must stay inside artifacts/runs")
    game = [sys.executable, "-s", "-u", str(ROOT / "run_local.py"),
            "--mode", "llm_ppo", "--human-training", "--realtime", "--opponent", "Terran",
            "--ppo-model", str(actor), "--human-checkpoint", str(checkpoint),
            "--strategy-memory", str(memory / "strategy_memory.json"),
            "--ppo-engagement-gate", "--llm-max-calls", "240", "--run-id", run_id, *game_args]
    learn = [str(args.training_python.resolve()), "-s", "-u", str(ROOT / "tools" / "learn_human_match.py"),
             "--run-dir", str(run_dir), "--checkpoint", str(checkpoint),
             "--output", str(run_dir / "learning"), "--memory-dir", str(memory)]
    return args, dict(run_id=run_id, human="Terran", agent="Terran / LLM + stochastic PPO", realtime=True,
                      checkpoint=str(checkpoint), actor=str(actor), run_dir=str(run_dir),
                      strategy_memory=str(memory / "strategy_memory.json"), game_command=game,
                      learning_command=learn, learning_mode=args.learn)


def finish_learning(args, config):
    from tools.human_learning_approval import decide
    status = decide(Path(config["run_dir"]), args.learn)
    print("Learning decision: " + status, flush=True)
    if status != "approved":
        print("Match/replay retained; LLM, PPO and replay memory unchanged. Resume with --learn-run " + config["run_id"] + " --learn yes", flush=True)
        return 0
    return subprocess.call(config["learning_command"], cwd=ROOT)


def main(argv=None):
    args, config = configuration(argv)
    print(json.dumps(config, indent=2), flush=True)
    if args.learn_run:
        if args.show_config:
            return 0
        return finish_learning(args, config)
    if args.show_config:
        # Also exercise run_local's validation, without importing/starting SC2.
        return subprocess.call([*config["game_command"], "--show-config"], cwd=ROOT)
    if not args.training_python.is_file():
        raise ValueError("Training Python missing; pass --training-python or SC2_TRAINING_PYTHON")
    subprocess.run([str(args.training_python), "-s", "-c", "import torch, sb3_contrib, numpy"], check=True, cwd=ROOT)
    from bot.llm_client import Settings
    Settings.load(ROOT / ".env.local")  # Validate in memory; never serialize credentials.
    print("Preflight PASS: training dependencies, checkpoint/actor identity and local LLM settings. No API request made.", flush=True)
    if args.check_only:
        return subprocess.call([*config["game_command"], "--show-config"], cwd=ROOT)
    print("Two SC2 windows will open. Play in HumanTerran as Terran; surrender/end normally to save; you will decide whether to learn afterward.", flush=True)
    output = ROOT / "artifacts"
    output.mkdir(exist_ok=True)
    with (output / "last-human-run.log").open("w", encoding="utf-8") as log:
        process = subprocess.Popen(config["game_command"], cwd=ROOT, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, text=True, encoding="utf-8", errors="replace")
        try:
            for line in process.stdout:
                print(line, end="", flush=True)
                log.write(line)
                log.flush()
            code = process.wait()
        except KeyboardInterrupt:
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            return 130
    if code:
        print("Match did not finish cleanly; no PPO update. See artifacts/last-human-run.log.")
        return code
    print("Match saved. Awaiting your learning decision...", flush=True)
    return finish_learning(args, config)


if __name__ == "__main__":
    raise SystemExit(main())
