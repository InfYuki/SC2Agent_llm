"""Approval boundaries; no game, API, model import or learning execution."""
import json
from pathlib import Path
import tempfile
import unittest
from tools.human_learning_approval import decide, learning_block
from tools.learn_human_match import learn


class HumanLearningApproval(unittest.TestCase):
    def test_consent_and_hard_exclusion(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "match"
            run.mkdir()
            self.assertEqual(learning_block(run), "learning_not_approved")
            self.assertEqual(decide(run, interactive=False), "pending")
            self.assertEqual(decide(run, interactive=True, input_fn=lambda _: "maybe"), "pending")
            def eof(_):
                raise EOFError
            self.assertEqual(decide(run, interactive=True, input_fn=eof), "pending")
            self.assertEqual(decide(run, interactive=True, input_fn=lambda _: "n"), "skipped")
            self.assertEqual(decide(run, interactive=True, input_fn=lambda _: "YES"), "approved")
            self.assertIsNone(learning_block(run))
            (run / "learning_excluded.json").write_text("{}")
            with self.assertRaises(ValueError):
                decide(run, "yes")
            self.assertEqual(learning_block(run), "permanently_excluded")

    def test_replay_memory_also_requires_approval(self):
        from unittest.mock import patch
        from tools.analyze_human_replay import update_memory
        with tempfile.TemporaryDirectory() as directory, patch("tools.analyze_human_replay.ROOT", Path(directory)):
            memory = Path(directory) / "memory"
            with self.assertRaises(ValueError):
                update_memory(memory, {"source_run_id": "unapproved"})
            self.assertFalse(memory.exists())

    def test_replay_publication_requires_consent(self):
        from unittest.mock import patch
        from tools.analyze_human_replay import update_memory
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            memory = root / "memory"
            with patch("tools.analyze_human_replay.ROOT", root):
                with self.assertRaisesRegex(ValueError, "learning_not_approved"):
                    update_memory(memory, {"source_run_id": "match"})
                run = root / "artifacts" / "runs" / "match"
                run.mkdir(parents=True)
                (run / "learning_excluded.json").write_text("{}")
                with self.assertRaisesRegex(ValueError, "permanently_excluded"):
                    update_memory(memory, {"source_run_id": "match"})
            self.assertFalse(memory.exists())

    def test_unapproved_learner_does_not_touch_history_or_memory(self):
        with tempfile.TemporaryDirectory() as directory:
            run = Path(directory) / "match"
            run.mkdir()
            history = run / "learning_report.json"
            history.write_text('{"old": true}')
            report = learn(run, run / "missing.zip", run / "output", run / "memory")
            self.assertEqual(report["llm"]["reason"], "learning_not_approved")
            self.assertEqual(report["ppo"]["status"], "skipped")
            self.assertEqual(history.read_text(), '{"old": true}')
            self.assertFalse((run / "memory").exists())
            (run / "human_training.json").write_text(json.dumps({"learning_exclusion": True}))
            self.assertEqual(learning_block(run), "permanently_excluded")

if __name__ == "__main__":
    unittest.main()
