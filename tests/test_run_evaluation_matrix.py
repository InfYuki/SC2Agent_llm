"""One consolidated runner contract test: no games, model imports or HTTP."""
import argparse
import copy
import hashlib
import json
from pathlib import Path
import subprocess
import tempfile
import unittest
from unittest.mock import patch, Mock

from tools import run_evaluation_matrix as runner


class MatrixRunnerTests(unittest.TestCase):
    def test_frozen_dryrun_budget_failure_resume_timeout_and_lock(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            maps = root / "Maps"
            maps.mkdir()
            installed = maps / "Ancient Cistern LE.SC2Map"
            installed.write_bytes(b"map")
            model = root / "model"
            model.mkdir()
            (model / "weights.npz").write_bytes(b"not-loaded-by-stdlib-planner")
            metadata = dict(format="marine-bc-numpy-v1", feature_version="marine-16-v1",
                action_version="marine-5-v1", decision_game_loops=8, architecture=[16, 64, 64, 5],
                activation="tanh", normalization="marine-16-v1",
                weights_sha256=hashlib.sha256((model / "weights.npz").read_bytes()).hexdigest())
            (model / "metadata.json").write_text(json.dumps(metadata))
            identity = dict(python="python", source_hashes={"run_local.py": "frozen"})
            args = argparse.Namespace(modes=["E4", "E0", "E1", "E2", "E3"],
                bc_model=str(model), ppo_model=str(model), llm_max_calls=5, game_path=str(root))
            original_model = runner.model_identity

            def fake_model(path, kind):
                return original_model(path, "bc")

            with patch.object(runner, "source_identity", return_value=identity), \
                 patch.object(runner, "model_identity", side_effect=fake_model):
                plan = runner.make_plan(root, args, "batch")
                self.assertEqual([a["experiment"] for a in plan["attempts"]], list(runner.MODES))
                self.assertEqual([a["llm_max_calls"] for a in plan["attempts"]], [0, 3, 0, 0, 2])
                state = dict(plan_sha256=runner.digest(plan), attempts=[
                    dict(run_id=a["run_id"], experiment=a["experiment"], status="pending") for a in plan["attempts"]])
                runner.validate(root, plan, state)
                installed.write_bytes(b"changed map")
                with self.assertRaisesRegex(ValueError, "installed map changed"):
                    runner.validate(root, plan, state)
                installed.write_bytes(b"map")
                changed = copy.deepcopy(plan)
                changed["common"]["seed"] += 1
                with self.assertRaisesRegex(ValueError, "plan changed"):
                    runner.validate(root, changed, state)
                with patch.object(runner, "source_identity", return_value={"changed": True}):
                    with self.assertRaisesRegex(ValueError, "source/interpreter"):
                        runner.validate(root, plan, state)
                (model / "weights.npz").write_bytes(b"changed")
                with self.assertRaisesRegex(ValueError, "weights hash"):
                    runner.validate(root, plan, state)
                (model / "weights.npz").write_bytes(b"not-loaded-by-stdlib-planner")

                folder = root / "batch"
                folder.mkdir()
                # Prior ambiguous launch must never be replayed; later modes continue after failure.
                state["attempts"][0]["status"] = "running"
                processes = [Mock(pid=100 + n) for n in range(3)]
                processes[0].wait.return_value = 1
                processes[1].wait.side_effect = subprocess.TimeoutExpired("mock", 600)
                processes[2].wait.return_value = 0
                # E3's foreign run path is preserved, so it consumes no subprocess.
                collision = root / "artifacts/runs/batch_E3"
                collision.mkdir(parents=True)
                marker = collision / "keep"
                marker.write_text("untouched")
                with patch.object(runner.os, "name", "nt"), \
                     patch.object(runner.subprocess, "Popen", side_effect=processes) as launch, \
                     patch.object(runner, "kill_owned") as kill:
                    self.assertEqual(runner.execute(root, folder, plan, state), 1)
                    self.assertEqual(launch.call_count, 3)
                    kill.assert_called_once_with(processes[1])
                    self.assertEqual([a["status"] for a in state["attempts"]],
                                     ["interrupted", "failed", "timeout", "collision", "unknown"])
                    self.assertEqual(marker.read_text(), "untouched")
                    self.assertEqual(runner.execute(root, folder, plan, state), 1)
                    self.assertEqual(launch.call_count, 3)  # No final outcome is retried.
                self.assertEqual(sum(state["counts"].values()), 5)
                report = json.loads((folder / "report.json").read_text())
                self.assertEqual(report["totals"]["attempts"], 4)  # Foreign collision evidence excluded.

            # Exercise public default: all arms, total cap zero, no Popen or bot imports.
            dry = root / "dry"
            frozen = dict(identity)
            with patch.object(runner, "ROOT", root), \
                 patch.object(runner, "source_identity", return_value=frozen), \
                 patch.object(runner, "model_identity", return_value={"path": str(model), "sha256": {}}), \
                 patch.object(runner.subprocess, "Popen") as launch:
                self.assertEqual(runner.main(["--batch-dir", str(dry), "--game-path", str(root)]), 0)
                launch.assert_not_called()
                dry_plan = json.loads((dry / "plan.json").read_text())
                self.assertEqual(dry_plan["llm_total_call_cap"], 0)
                self.assertEqual(len(dry_plan["attempts"]), 5)
                self.assertEqual(runner.main(["--batch-dir", str(dry), "--game-path", str(root)]), 2)
                global_lock = root / "artifacts/evaluation_runner_execution.lock"
                global_lock.write_text('{"pid":456}')
                self.assertEqual(runner.main(["--resume", str(dry), "--execute"]), 2)
                self.assertTrue(global_lock.exists())
                self.assertFalse((dry / "execution.lock").exists())
                global_lock.unlink()
                (dry / "execution.lock").write_text('{"pid":123}')
                self.assertEqual(runner.main(["--resume", str(dry), "--execute"]), 2)
                launch.assert_not_called()
                self.assertTrue((dry / "execution.lock").exists())


if __name__ == "__main__":
    unittest.main()
