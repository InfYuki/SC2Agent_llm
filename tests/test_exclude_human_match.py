import json
from pathlib import Path
import tempfile
import unittest

from tools.exclude_human_match import exclude, read, write


class ExclusionTest(unittest.TestCase):
    def test_remove_aggregate_lessons_preserve_successor_and_idempotent(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            run, memory = root / "aborted", root / "memory"
            write(run / "human_training.json", {"format": "human-match-training-v1"})
            write(run / "learning_report.json", {"ppo": {"status": "skipped", "samples": 0}})
            write(memory / "strategy_memory.json", dict(matches_seen=2, recent_matches=[
                dict(run_id="aborted", notes=["false victory lesson"]),
                dict(run_id="valid", notes=["valid retained lesson"])], lessons=["false victory lesson"]))
            write(memory / "ppo_latest.json", {"source_run_id": "valid"})
            before = (memory / "ppo_latest.json").read_bytes()
            report = exclude(run, memory, "aborted by user")
            self.assertTrue((Path(report["backup"]) / "strategy_memory.json").exists())
            for _ in range(2):
                exclude(run, memory, "aborted by user")
            current = read(memory / "strategy_memory.json")
            self.assertEqual(current["matches_seen"], 1)
            self.assertEqual(current["lessons"], ["valid retained lesson"])
            self.assertEqual((memory / "ppo_latest.json").read_bytes(), before)
            write(run / "learning_report.json", {"ppo": {"status": "updated"}})
            with self.assertRaisesRegex(ValueError, "lineage"):
                exclude(run, memory, "unsafe rollback")
