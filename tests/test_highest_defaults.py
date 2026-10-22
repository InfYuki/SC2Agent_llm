"""Recommended full-match defaults and descriptive goal ordering; no game/API."""
import copy
import json
import os
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest
from unittest.mock import patch

from tools import run_evaluation_matrix as runner
from tools.report_evaluation_matrix import goal_ranking

ROOT = Path(__file__).resolve().parents[1]


class HighestDefaultsTests(unittest.TestCase):
    def test_defaults_overrides_frozen_commands_and_goal_order(self):
        def config(*args):
            return json.loads(subprocess.check_output(
                [sys.executable, "-s", str(ROOT / "run_local.py"), "--show-config", *args],
                cwd=ROOT, text=True))

        self.assertEqual(config()["difficulty"], "CheatInsane")
        self.assertFalse(config()["ppo_engagement_gate"])
        self.assertEqual(config("--difficulty", "Easy")["difficulty"], "Easy")
        for name, mode in (("run_ppo.cmd", "rule_ppo"), ("run_llm_ppo.cmd", "llm_ppo")):
            text = (ROOT / name).read_text()
            self.assertTrue(text.splitlines()[1].endswith(" %*"))
            if os.name == "nt":
                def wrapper(*args):
                    return json.loads(subprocess.check_output(
                        ["cmd", "/c", str(ROOT / name), "--show-config", *args],
                        cwd=ROOT, env=dict(os.environ, ARES_ENV=str(Path(sys.executable).parent)), text=True))
                default = wrapper()
                self.assertEqual(default["mode"], mode)
                self.assertEqual(Path(default["ppo_model"]).name, "marine_ppo_two_enemy448_20261021")
                self.assertTrue(default["ppo_engagement_gate"])
                self.assertEqual(default["difficulty"], "CheatInsane")
                override = wrapper("--ppo-model", "override-actor", "--no-ppo-engagement-gate", "--difficulty", "Easy")
                self.assertEqual(override["ppo_model"], "override-actor")
                self.assertFalse(override["ppo_engagement_gate"])
                self.assertEqual(override["difficulty"], "Easy")

        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)
            for disabled in (False, True):
                folder = base / str(disabled)
                with patch.object(runner, "model_identity", side_effect=lambda path, kind: {"path": str(path)}), \
                     patch.object(runner, "map_identity", return_value={}), \
                     patch.object(runner, "source_identity", return_value={"python": sys.executable}):
                    args = ["--batch-dir", str(folder)] + (["--no-ppo-engagement-gate"] if disabled else [])
                    self.assertEqual(runner.main(args), 0)
                plan = json.loads((folder / "plan.json").read_text())
                self.assertEqual(plan["common"]["difficulty"], "CheatInsane")
                self.assertEqual(Path(plan["models"]["ppo"]["path"]).name, "marine_ppo_two_enemy448_20261021")
                self.assertEqual(plan["ppo_engagement_gate"], not disabled)
                for attempt in plan["attempts"]:
                    command = runner.command(ROOT, plan, attempt)
                    expected = attempt["experiment"] in ("E3", "E4") and not disabled
                    self.assertEqual("--ppo-engagement-gate" in command, expected)
                old = copy.deepcopy(plan)
                old.pop("ppo_engagement_gate")
                old["common"]["difficulty"] = "Easy"
                for attempt in old["attempts"]:
                    command = runner.command(ROOT, old, attempt)
                    self.assertNotIn("--ppo-engagement-gate", command)
                    self.assertEqual(command[command.index("--difficulty") + 1], "Easy")
                    expected = [sys.executable, "-s", "-u", str(ROOT / "run_local.py"),
                        "--mode", attempt["mode"], "--run-id", attempt["run_id"],
                        "--game-path", old["game_path"], "--llm-max-calls", str(attempt["llm_max_calls"])]
                    for key, value in old["common"].items():
                        if key == "wall_timeout":
                            continue
                        expected += (["--realtime" if value else "--no-realtime"] if key == "realtime"
                                     else ["--" + key.replace("_", "-"), str(value)])
                    kind = "bc" if attempt["experiment"] == "E2" else "ppo" if attempt["experiment"] in ("E3", "E4") else None
                    if kind:
                        expected += [f"--{kind}-model", old["models"][kind]["path"]]
                    self.assertEqual(command, expected)

        def row(name, outcome, seconds, category="completed"):
            return dict(run_id=name, experiment="E3", category=category, outcome=outcome,
                        metrics={"game_seconds": seconds}, identity={},
                        fair_config={"difficulty": "CheatInsane"}, missing_comparison_fields=[])

        rows = [row("long_win", "win", 500), row("short_win", "win", 300),
                row("short_loss", "loss", 300), row("long_loss", "loss", 800),
                row("cap", "unknown", 9999, "truncated"), row("error", "unknown", 9999, "failed"),
                row("draw", "tie", 9999), row("invalid", "unknown", 9999, "unknown")]
        rows += [row(f"duration_{index}", "loss", seconds)
                 for index, seconds in enumerate((None, True, -1, float("nan"), float("inf")))]
        ranking = goal_ranking(rows, 1)
        self.assertEqual([entry["run_id"] for entry in ranking["ranked"]],
                         ["short_win", "long_win", "long_loss", "short_loss"])
        self.assertEqual(len(ranking["unranked"]), 9)


if __name__ == "__main__":
    unittest.main()
