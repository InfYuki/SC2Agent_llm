"""One focused regression check for the optional Windows state snapshot."""
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from bot.telemetry import Telemetry


class TelemetrySnapshotTest(unittest.TestCase):
    def test_optional_snapshot_locks_retry_or_skip_but_other_io_still_fails(self):
        def locked(code):
            error = PermissionError("simulated Windows file lock")
            error.winerror = code
            return error

        with tempfile.TemporaryDirectory() as tmp:
            trace = Telemetry(Path(tmp) / "run")
            target = trace.output / "latest_state.json"
            temporary = trace.output / "latest_state.json.tmp"
            real_replace = Path.replace
            attempts = []

            def briefly_locked(path, destination):
                attempts.append(path)
                if len(attempts) == 1:
                    raise locked(5)
                return real_replace(path, destination)

            try:
                with patch.object(Path, "replace", briefly_locked), patch("bot.telemetry.time.sleep") as sleep:
                    trace.write_json("latest_state.json", {"frame": 1})
                sleep.assert_called_once_with(0.01)
                self.assertEqual(json.loads(target.read_text()), {"frame": 1})
                self.assertEqual(trace.counts["latest_state_lock_retries"], 1)
                self.assertFalse(temporary.exists())

                with patch.object(Path, "replace", side_effect=locked(32)) as replace, patch("bot.telemetry.time.sleep") as sleep:
                    trace.write_json("latest_state.json", {"frame": 2})
                self.assertEqual(replace.call_count, 3)
                self.assertAlmostEqual(sum(call.args[0] for call in sleep.call_args_list), 0.03)
                self.assertEqual(trace.counts["latest_state_lock_skips"], 1)
                self.assertEqual(json.loads(target.read_text()), {"frame": 1})
                self.assertFalse(temporary.exists())
                events = [json.loads(line) for line in (trace.output / "events.jsonl").read_text().splitlines()]
                self.assertEqual(events[-1]["event"], "snapshot_skipped")

                # Other I/O errors, serialization/write failures, and mandatory
                # output locks retain the original strict failure behavior.
                with patch.object(Path, "replace", side_effect=OSError("disk failure")), self.assertRaisesRegex(OSError, "disk failure"):
                    trace.write_json("latest_state.json", {"frame": 3})
                self.assertFalse(temporary.exists())
                with patch.object(Path, "write_text", side_effect=locked(5)), self.assertRaises(PermissionError):
                    trace.write_json("latest_state.json", {"frame": 4})
                with patch.object(Path, "replace", side_effect=locked(5)), self.assertRaises(PermissionError):
                    trace.write_json("summary.json", {})
                with patch.object(trace, "event", side_effect=OSError("event disk failure")), patch.object(Path, "replace", side_effect=locked(5)), patch("bot.telemetry.time.sleep"), self.assertRaisesRegex(OSError, "event disk failure"):
                    trace.write_json("latest_state.json", {"frame": 5})
                self.assertFalse(temporary.exists())
            finally:
                trace.events.close()


if __name__ == "__main__":
    unittest.main()
