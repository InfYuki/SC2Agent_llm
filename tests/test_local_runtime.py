import json
from pathlib import Path
import tempfile
import unittest

from bot.arbiter import OrderArbiter
from bot.telemetry import Telemetry
from bot.budget import ExpansionBudget


class LocalRuntimeTest(unittest.TestCase):
    def test_expansion_saving_has_deadline_and_retry(self):
        budget = ExpansionBudget(save_seconds=30, retry_seconds=30)
        self.assertTrue(budget.reserve(120, True))
        self.assertTrue(budget.reserve(149, True))
        self.assertFalse(budget.reserve(150, True))
        self.assertFalse(budget.reserve(179, True))
        self.assertTrue(budget.reserve(180, True))

    def test_expansion_started_or_defense_releases_saving(self):
        budget = ExpansionBudget()
        self.assertTrue(budget.reserve(120, True))
        self.assertFalse(budget.reserve(121, False))
        self.assertTrue(budget.reserve(122, True))
        self.assertFalse(budget.reserve(123, True, under_attack=True))
        self.assertFalse(budget.reserve(124, True))

    def test_one_owner_and_one_command_per_step(self):
        arbiter = OrderArbiter()
        arbiter.begin_step({42: "rule_combat"})
        self.assertFalse(arbiter.allow(42, "macro"))
        self.assertTrue(arbiter.allow(42, "rule_combat"))
        self.assertFalse(arbiter.allow(42, "rule_combat"))
        arbiter.begin_step({42: "rl"})
        self.assertFalse(arbiter.allow(42, "rule_combat"))
        self.assertTrue(arbiter.allow(42, "rl"))

    def test_timed_leave_is_truncated_instead_of_normal_defeat(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            trace = Telemetry(path)
            trace.stop_reason = "game_time_limit"
            trace.finish("Defeat")
            result = json.loads((path / "summary.json").read_text())
            self.assertEqual(result["status"], "truncated")

    def test_framework_swallowed_exception_is_still_recorded_as_crash(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            trace = Telemetry(path)
            try:
                raise KeyError(4135)
            except KeyError:
                trace.fail("after_step")
            trace.finish("Defeat")
            result = json.loads((path / "summary.json").read_text())
            self.assertEqual(result["status"], "crashed")
            self.assertIn("4135", result["error"]["traceback"])

    def test_artifacts_never_overwrite_existing_run(self):
        with tempfile.TemporaryDirectory() as tmp:
            path = Path(tmp) / "run"
            trace = Telemetry(path)
            trace.finish("Victory")
            with self.assertRaises(FileExistsError):
                Telemetry(path)
