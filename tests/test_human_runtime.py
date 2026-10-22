"""Small offline checks for human collection and two-client cleanup; no SC2 launch."""
import asyncio
import hashlib
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "ares-sc2" / "src"), str(ROOT / "ares-sc2")]

from bot.human_training import HumanRecorder
from bot.lifecycle import recover_human_game
from bot.telemetry import Telemetry
from sc2.data import Result
from tools.run_human_training import configuration


class HumanRuntimeTest(unittest.TestCase):
    def test_sample_record_and_missing_endpoint(self):
        import numpy as np
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            checkpoint = directory / "model.zip"
            checkpoint.write_bytes(b"fixed checkpoint")
            telemetry = Telemetry(directory / "run")
            own = NS(health=45, shield=0)
            enemy = NS(tag=2, health=40, shield=0, is_visible=True, is_memory=False, is_snapshot=False)
            bot = NS(options=NS(seed=7, ppo_model=str(directory)), telemetry=telemetry,
                     units=NS(find_by_tag=lambda tag: own), enemy_units=[enemy], state=NS(dead_units=set()))
            policy = NS(policy_version="test", probabilities=lambda obs, mask: np.array([0, 0, 0, 0, 1.0]),
                        metadata={"weights_sha256": "a" * 64, "producer": {"source_checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest()}})
            recorder = HumanRecorder(bot, policy, checkpoint)
            ctx = NS(obs=(0.0,) * 16, mask=(False, False, False, False, True), enemies=(enemy,))
            action = recorder.sample(1, ctx)
            self.assertEqual(action, 4)
            recorder.begin(1, 8, ctx, action, action, "hold")
            enemy.health = 31
            own.health = 40
            recorder.finish(1, 17, ctx)
            action = recorder.sample(1, ctx)
            recorder.begin(1, 17, ctx, action, action, "hold")
            recorder.finish(1, 23, reason="missing endpoint", truncated=True)
            recorder.close(23, "match_end")
            telemetry.finish(Result.Victory)
            rows = [json.loads(line) for line in (directory / "run" / "human_ppo_rollout.jsonl").read_text().splitlines()]
            self.assertEqual(len(rows), 1)
            self.assertEqual(rows[0]["next_game_loop"] - rows[0]["game_loop"], 9)
            self.assertAlmostEqual(rows[0]["reward"], 4 / 45)
            self.assertEqual(rows[0]["old_log_prob"], 0)

    def test_human_results_replay_and_owned_cleanup(self):
        import sc2.main as engine
        from sc2.sc2process import SC2Process
        events = []
        async def human(*args):
            events.append("human_result")
            return Result.Victory
        async def ai(*args):
            events.append("bot_result")
            return Result.Defeat
        async def save(*args):
            events.append("replay_saved")
        class Process:
            async def _close_connection(self):
                events.append("closed_owned")
            def _clean(self):
                events.append("cleaned_owned")
        async def run():
            client = NS(save_replay=save)
            async def host():
                result = await engine._play_game_human(client, 1, True, None)
                await client.save_replay("fake.SC2Replay")
                return result
            async def join():
                return await engine._play_game_ai(NS(), 2, NS(), True, None)
            results = await asyncio.gather(host(), join())
            await SC2Process.__aexit__(Process(), None, None, None)
            return results
        with patch.object(engine, "_play_game_human", human), patch.object(engine, "_play_game_ai", ai):
            with recover_human_game(NS()):
                self.assertEqual(asyncio.run(run()), [Result.Victory, Result.Defeat])
        self.assertIn("replay_saved", events)
        self.assertEqual(events.count("cleaned_owned"), 1)

    def test_no_identity_override(self):
        with self.assertRaises(SystemExit):
            configuration(["--ppo-model", "other"])


if __name__ == "__main__":
    unittest.main()
