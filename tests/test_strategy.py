from copy import deepcopy
import json
from pathlib import Path
import tempfile
import threading
import time
import unittest
from unittest.mock import patch

from bot.llm_client import EXAMPLE, Settings, Worker, request
from bot.strategy import Director, PlanError, combat_goal, parse_plan


def payload(**changes):
    value = deepcopy(EXAMPLE)
    value.update(request_id="r1", snapshot_seq=1, **changes)
    return json.dumps(value)


class StrategyTests(unittest.TestCase):
    def test_strict_schema(self):
        self.assertEqual(parse_plan(payload(), "r1", 1).base_target, 4)
        cases = [
            dict(extra="code"),
            dict(snapshot_seq=True),
            dict(snapshot_seq=2),
            dict(request_id="other"),
            dict(economy={"worker_target": True, "base_target": 2}),
            dict(economy={"worker_target": 48, "base_target": 5}),
            dict(production_profile="battlecruiser"),
            dict(research_priority=["stim"]),
            dict(
                squad_tasks=[
                    {"squad_id": "main", "task": "attack", "target_id": "own_main"}
                ]
            ),
            dict(
                squad_tasks=[
                    {"squad_id": "main", "task": ["attack"], "target_id": "enemy_main"}
                ]
            ),
            dict(attack_gate={"min_army_supply": 0}),
            dict(reason_summary="x" * 161),
        ]
        for change in cases:
            with self.subTest(change=change), self.assertRaises(PlanError):
                value = deepcopy(EXAMPLE)
                value.update(request_id="r1", snapshot_seq=1)
                value.update(change)
                parse_plan(json.dumps(value), "r1", 1)
        for bad in [
            "",
            "{}",
            "null",
            '{"x": NaN}',
            '{"x":1,"x":2}',
            "```json\n{}\n```",
        ]:
            with self.subTest(bad=bad), self.assertRaises(PlanError):
                parse_plan(bad, "r1", 1)

    def test_commitment_and_freshness(self):
        first = parse_plan(payload(), "r1", 1)
        second = parse_plan(payload(stance="pressure"), "r1", 1)
        director = Director()
        self.assertEqual(director.offer(first, 0, 10), "active")
        self.assertEqual(director.offer(second, 15, 20), "pending")
        self.assertEqual(director.current(39), first)
        self.assertEqual(director.current(40), second)
        self.assertIsNone(director.current(61))
        self.assertEqual(director.offer(first, 0, 46), "expired")

    def test_renewal_does_not_delay_commitment_forever(self):
        plan = parse_plan(payload(), "r1", 1)
        director = Director()
        director.offer(plan, 0, 10)
        self.assertEqual(director.offer(plan, 15, 20), "renewed")
        self.assertEqual(director.committed_at, 10)

    def test_emergency_and_attack_gate(self):
        plan = parse_plan(
            payload(
                squad_tasks=[
                    {"squad_id": "main", "task": "attack", "target_id": "enemy_main"}
                ]
            ),
            "r1",
            1,
        )
        self.assertIsNone(combat_goal(plan, True, 40))
        self.assertIsNone(combat_goal(None, False, 40))
        self.assertEqual(combat_goal(plan, False, 10), ("rally", "own_natural"))
        self.assertEqual(combat_goal(plan, False, 30), ("attack", "enemy_main"))

    def test_worker_is_nonblocking_single_request(self):
        entered, release = threading.Event(), threading.Event()

        def slow(settings, snapshot):
            entered.set()
            release.wait(2)
            return {"ok": True, "content": "{}"}

        worker = Worker(Settings("private"), slow)
        start = time.monotonic()
        self.assertTrue(worker.submit("snapshot"))
        self.assertLess(time.monotonic() - start, 0.2)
        self.assertTrue(entered.wait(0.5))
        self.assertFalse(worker.submit("second"))
        self.assertIsNone(worker.poll())
        worker.close()
        release.set()
        worker.thread.join(0.5)
        self.assertTrue(worker.poll()["ok"])
        self.assertFalse(worker.submit("after_close"))

    def test_worker_sanitizes_unexpected_exception(self):
        def broken(*args):
            raise RuntimeError("private credential")

        worker = Worker(Settings("private"), broken)
        worker.submit("{}")
        worker.thread.join(0.5)
        self.assertEqual(worker.poll(), {"ok": False, "error": "worker_error"})

    def test_http_errors_do_not_expose_server_body_or_key(self):
        settings = Settings("secret-test-key")
        self.assertNotIn(settings.api_key, repr(settings))
        with patch("bot.llm_client.requests.post") as post:
            response = post.return_value.__enter__.return_value
            response.status_code = 401
            response.text = "secret-test-key"
            result = request(settings, "{}")
            self.assertNotIn(settings.api_key, json.dumps(result))
            self.assertEqual(result["error"], "http_status")
        with patch(
            "bot.llm_client.requests.post",
            side_effect=__import__("requests").Timeout("secret-test-key"),
        ):
            self.assertEqual(request(settings, "{}")["error"], "network_timeout")

    def test_model_content_key_is_redacted(self):
        with patch("bot.llm_client.requests.post") as post:
            response = post.return_value.__enter__.return_value
            response.status_code = 200
            response.json.return_value = {
                "choices": [{"message": {"content": "private-key"}}],
                "usage": {"prompt_tokens": 42},
            }
            result = request(Settings("private-key"), "{}")
            self.assertEqual(result["content"], "[REDACTED]")
            self.assertEqual(result["usage"], {"prompt_tokens": 42})
