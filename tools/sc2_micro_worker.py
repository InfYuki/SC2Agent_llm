"""One isolated SC2 episode, owned and bounded by SC2MicroEnv."""
import argparse
import hashlib
from multiprocessing.connection import Client
import os
from pathlib import Path
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run_local
from sc2 import maps
from sc2.data import Race
from sc2.main import run_game
from sc2.player import Bot
from bot.lifecycle import recover_completed_game
from bot.micro import DECISION_LOOPS
from bot.micro_env_bot import MicroEnvBot, PROTOCOL
from bot.telemetry import Telemetry
from tools.run_micro_scenario import Opponent
from envs.sc2_micro_env import SCENARIOS, training_task


class WorkerTelemetry(Telemetry):
    """Defer inherited on_end finalization until both SDK players return."""

    def finish(self, result=None):
        # InstrumentedAresBot.on_end calls this before run_game returns.
        # The worker owns the final result/stop classification and summary.
        pass

    def finish_worker(self, result=None):
        super().finish(result)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--episode-id", required=True)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--output-dir", required=True)
    parser.add_argument("--game-path", required=True)
    parser.add_argument("--max-game-seconds", type=float, default=20)
    parser.add_argument("--map", default="Ancient Cistern LE")
    parser.add_argument("--scenario", choices=SCENARIOS, default="marine-vs-marine")
    parser.add_argument("--distance", type=float, default=6.0)
    parser.add_argument("--health-fraction", type=float, default=1.0)
    parser.add_argument("--enemy-health-fraction", type=float, default=1.0)
    parser.add_argument("--enemy-count", type=int, choices=[1, 2], default=1)
    parser.add_argument("--second-distance", type=float)
    parser.add_argument("--second-enemy-health-fraction", type=float)
    args = parser.parse_args()
    if not 0 < args.max_game_seconds <= 120:
        parser.error("max-game-seconds must be in (0,120]")
    task = training_task(scenario=args.scenario, distance=args.distance,
                         max_game_seconds=args.max_game_seconds, map_name=args.map,
                         own_health_fraction=args.health_fraction,
                         enemy_health_fraction=args.enemy_health_fraction, enemy_count=args.enemy_count,
                         second_distance=args.second_distance,
                         second_enemy_health_fraction=args.second_enemy_health_fraction)
    os.environ["SC2PATH"] = str(Path(args.game_path).resolve())
    os.chdir(ROOT)
    connection = Client((os.environ["SC2_MICRO_HOST"], int(os.environ["SC2_MICRO_PORT"])),
                        family="AF_INET", authkey=bytes.fromhex(os.environ["SC2_MICRO_AUTHKEY"]))
    # Parent owns the episode root and worker.log; Telemetry owns a new child.
    telemetry = WorkerTelemetry(Path(args.output_dir) / "game")
    scene_args = dict(vars(args), second_distance=task.get("second_distance", 8.0),
                      second_enemy_health_fraction=task.get("second_enemy_health_fraction", 0.5))
    options = SimpleNamespace(**scene_args, training_task=task,
                              enemy_hidden=False,
                              data_split=None, expert="kite", policy="external", mode="micro_env",
                              game_step=DECISION_LOOPS, micro_max_units=1, realtime=False)
    bot = None
    try:
        bot = MicroEnvBot(options, telemetry, connection, args.episode_id)
        settings = maps.get(args.map)
        telemetry.write_json("manifest.json", dict(config=vars(args), task=task, protocol=PROTOCOL,
            provenance="real-sc2-external-action", expert_labels=False,
            project_commit=run_local.git("rev-parse", "HEAD"), python=sys.executable,
            map_sha256=hashlib.sha256(Path(settings.path).read_bytes()).hexdigest(),
            decision_game_loops=DECISION_LOOPS))
        with recover_completed_game(telemetry, expected_players=2):
            enemy_race = Race.Zerg if args.scenario == "marine-vs-zergling" else Race.Terran
            result = run_game(settings, [Bot(Race.Terran, bot), Bot(enemy_race, Opponent())],
                              realtime=False, random_seed=args.seed,
                              save_replay_as=str(telemetry.output / "game.SC2Replay"))
        budget_close = bot._budget_close_identity
        # The leave handshake still requires both official SDK results, but a
        # budget stop is not a combat win/loss in the training summary.
        if budget_close:
            telemetry.event("training_budget_close", official_results=str(result))
        bot.close_micro()
        telemetry.finish_worker(None if budget_close else result)
        identity = budget_close or bot._message("closed")
        connection.send(dict(identity, type="closed", info=dict(
            reason="training_budget_close" if budget_close else "episode_boundary",
            official_results=str(result))))
        return 0
    except Exception as exc:
        telemetry.fail("micro_env_worker")
        telemetry.finish_worker()
        try:
            connection.send(dict(protocol=PROTOCOL, type="error", episode_id=args.episode_id,
                                 decision_id=getattr(bot, "_decision_id", 0), unit_slot=0,
                                 frame=int(bot.state.game_loop) if bot and hasattr(bot, "state") else 0,
                                 info=dict(reason=type(exc).__name__ + ":" + str(exc), rollout_discard=True)))
        except (EOFError, OSError):
            pass
        raise
    finally:
        if bot is not None:
            bot.close_micro("system_failure" if telemetry.error else None)
        connection.close()


if __name__ == "__main__":
    raise SystemExit(main())
