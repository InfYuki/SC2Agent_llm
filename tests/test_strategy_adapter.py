"""Exercise the SC2 adapter with deterministic time and transport failures."""
from collections import Counter
import json
from pathlib import Path
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import run_local  # Ares submodule import paths
from bot.arbiter import OrderArbiter
from bot.llm_bot import StrategicBot
from bot.llm_client import EXAMPLE
from bot.rule_bot import RuleBot
from bot.strategy import Director, parse_plan


class StrategyAdapterTests(unittest.TestCase):
    def bot(self, mode="llm"):
        bot = object.__new__(StrategicBot)
        bot.options = SimpleNamespace(mode=mode, llm_max_calls=2)
        bot.telemetry = SimpleNamespace(
            counts=Counter(callbacks=100), event=Mock(), write_json=Mock()
        )
        bot.worker = Mock()
        bot.worker.poll.return_value = None
        bot.director = Director()
        bot._seq = 0
        bot._last_snapshot = -100
        bot._last_query_game = -100
        bot._last_query_wall = -100
        bot._retry_at = 0
        bot._failures = 0
        bot._inflight = None
        bot._deadline_reported = False
        bot._plan = None
        bot._source = None
        bot._callbacks_at_request = 0
        bot._candidate_id = None
        bot._goal_progress = None
        bot.strategy_state = "rally"
        bot.supply_army = 0
        bot.supply_workers = 12
        bot.ready_townhalls = []
        bot._llm_closed = False
        bot.stats = Counter()
        bot.latencies = []
        # BotAI.time is derived from state.game_loop.
        bot.state = SimpleNamespace(game_loop=224)
        bot.snapshot = Mock(return_value={"snapshot_seq": 1})
        return bot

    def plan(self):
        value = dict(EXAMPLE, request_id="r", snapshot_seq=1)
        return parse_plan(json.dumps(value), "r", 1)

    def test_shadow_never_applies_and_expired_live_plan_falls_back(self):
        for mode in ("shadow", "llm"):
            bot = self.bot(mode)
            bot.director.offer(self.plan(), 0, 0)
            with patch.object(RuleBot, "play_step"), patch(
                "bot.llm_bot.time.monotonic", return_value=100
            ):
                bot.play_step(1)
                self.assertEqual(bot._plan is not None, mode == "llm")
                bot.state.game_loop = 2240
                bot.play_step(2)
                self.assertIsNone(bot._plan)

    def test_deadline_and_failure_keep_fresh_plan_without_queueing(self):
        bot = self.bot()
        bot.director.offer(self.plan(), 0, 0)
        bot._inflight = ("r", 1, 0)
        bot._last_query_wall = 100
        with patch.object(RuleBot, "play_step"), patch(
            "bot.llm_bot.time.monotonic", return_value=121
        ):
            bot.play_step(1)
        self.assertIsNotNone(bot._plan)
        self.assertEqual(bot.stats["response_deadlines"], 1)
        bot.worker.submit.assert_not_called()
        bot.worker.poll.return_value = {
            "ok": True,
            "content": json.dumps(dict(EXAMPLE, request_id="r", snapshot_seq=1)),
        }
        bot._poll(122)
        self.assertEqual(bot.stats["late_discarded"], 1)
        self.assertEqual(bot.stats["failures"], 1)

    def test_bad_json_is_failure_and_previous_plan_survives(self):
        bot = self.bot()
        bot.director.offer(self.plan(), 0, 0)
        bot._inflight = ("r", 1, 0)
        bot._last_query_wall = 100
        bot.worker.poll.return_value = {"ok": True, "content": "{}"}
        bot._poll(101)
        self.assertEqual(bot.stats["invalid_plans"], 1)
        self.assertIsNotNone(bot.director.current(10))
        self.assertEqual(bot._retry_at, 106)

    def test_emergency_defense_precedes_llm_attack_in_real_executor(self):
        target = SimpleNamespace(x=10, y=20)
        unit = SimpleNamespace(tag=42, is_idle=True, attack=Mock(return_value=True))
        bot = SimpleNamespace(
            units=lambda _: [unit],
            arbiter=OrderArbiter(),
            _last_order={},
            enemy_units=SimpleNamespace(
                filter=lambda predicate: SimpleNamespace(
                    closest_to=lambda _: SimpleNamespace(position=target)
                )
            ),
            start_location=target,
            strategy_state="attack",
            time=200,
            strategic_order=Mock(
                side_effect=AssertionError("LLM must not preempt defense")
            ),
            telemetry=SimpleNamespace(counts=Counter(), event=Mock()),
        )
        RuleBot._combat(bot, 100)
        self.assertEqual(bot.strategy_state, "defend")
        bot.strategic_order.assert_not_called()
        unit.attack.assert_called_once_with(target)
        self.assertEqual(bot.arbiter.conflicts, 0)

    def test_rule_hooks_do_not_load_llm_or_require_credentials(self):
        bot = SimpleNamespace(ready_townhalls=[1, 2])
        self.assertEqual(RuleBot.economic_goals(bot), (44, 2))
        self.assertIsNone(RuleBot.strategic_order(bot, []))
