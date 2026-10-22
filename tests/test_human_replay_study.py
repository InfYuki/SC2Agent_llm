"""One offline check: persisted replay evidence reaches the actual LLM payload."""
from collections import Counter
import json
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace as NS
import unittest
from unittest.mock import Mock, patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "ares-sc2" / "src"), str(ROOT / "ares-sc2")]

from bot.llm_bot import StrategicBot
from bot.rule_bot import RuleBot
from tools.analyze_human_replay import update_memory


class HumanReplayStudyTest(unittest.TestCase):
    def test_replay_memory_reaches_request_without_api(self):
        profile = dict(format="human-replay-profile-v1", source_run_id="studied-human-game",
            evidence_scope="post-match replay; not live vision", replay_sha256="a" * 64,
            actual_replay_build=98370, decoder_schema_build=98310, compatibility_override=True,
            peak_workers=51, milestones=[dict(seconds=237.232, event="created", unit="SiegeTank", ordinal=1)],
            cumulative_units_created={"Marine": 44, "SiegeTank": 7, "Medivac": 6})
        with tempfile.TemporaryDirectory() as temporary:
            memory = Path(temporary)
            update_memory(memory, profile)
            update_memory(memory, profile)
            self.assertEqual(len(json.loads((memory / "strategy_memory.json").read_text())["recent_matches"]), 1)
            options = NS(mode="llm", llm_max_calls=1, strategy_memory=str(memory / "strategy_memory.json"))
            telemetry = NS(counts=Counter(), event=Mock(), write_json=Mock())
            def base_init(bot, options, telemetry):
                bot.options, bot.telemetry = options, telemetry
                bot.state = NS(game_loop=0)
            with patch.object(RuleBot, "__init__", base_init), \
                 patch("bot.llm_bot.Settings.load", return_value=NS(model="offline", base_url="offline")), \
                 patch("bot.llm_bot.Worker") as worker:
                bot = StrategicBot(options, telemetry)
            bot._poll = Mock()
            bot.snapshot = Mock(return_value={})
            bot.worker.submit.return_value = True
            with patch.object(RuleBot, "play_step", return_value=None):
                bot.play_step(0)
            payload = json.loads(bot.worker.submit.call_args.args[0])
            actual = payload["previous_human_match_experience"]["recent_matches"][-1]["postmatch_replay_profile"]
            self.assertEqual(actual["army_created"]["SiegeTank"], 7)
            self.assertEqual(actual["milestones"][0]["seconds"], 237.232)
            self.assertIn("not live vision", actual["evidence_scope"])


if __name__ == "__main__":
    unittest.main()
