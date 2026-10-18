"""One real reset/step/close episode; no PPO, mock, or parallel game launch."""
import argparse
import json
from pathlib import Path
import sys
import time

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from envs.sc2_micro_env import SC2MicroEnv


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--game-path", default=r"C:\Program Files (x86)\StarCraft II")
    parser.add_argument("--max-game-seconds", type=float, default=20)
    parser.add_argument("--map", default="Ancient Cistern LE")
    args = parser.parse_args()
    started = time.monotonic()
    transitions = []
    with SC2MicroEnv(game_path=args.game_path, map_name=args.map,
                     max_game_seconds=args.max_game_seconds) as env:
        obs, reset_info = env.reset(seed=args.seed)
        print(json.dumps(dict(event="reset", observation=obs, info=reset_info)), flush=True)
        while True:
            # Simple deterministic legal attacker; this is bridge validation, not training.
            mask = env.action_masks()
            action = next((a for a in (0, 1, 3, 4) if mask[a]), 4)
            obs, reward, terminated, truncated, info = env.step(action)
            row = dict(action=action, obs=obs, reward=reward, terminated=terminated,
                       truncated=truncated, info=info)
            transitions.append(row)
            if terminated or truncated:
                break
        report = dict(seed=args.seed, reset_info=reset_info, transitions=transitions,
                      steps=len(transitions), reward=sum(t["reward"] for t in transitions),
                      wall_seconds=time.monotonic() - started,
                      system_failure=bool(info.get("system_failure")),
                      training_performed=False, gymnasium_compatible=False)
        destination = env.output_dir / "smoke_report.json"
        destination.write_text(json.dumps(report, indent=2), encoding="utf-8")
        print(json.dumps(dict(event="done", report=str(destination), steps=report["steps"],
                              reward=report["reward"], info=info)), flush=True)
        return 1 if report["system_failure"] else 0


if __name__ == "__main__":
    raise SystemExit(main())
