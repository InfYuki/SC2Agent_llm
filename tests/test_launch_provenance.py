"""Run the real manifest/finish path with no game, API or PATH Git dependency."""
from contextlib import nullcontext
import json
import os
from pathlib import Path
import sys
import tempfile
from types import SimpleNamespace
import unittest
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path[:0] = [str(ROOT), str(ROOT / "ares-sc2/src"), str(ROOT / "ares-sc2")]

import run_local
from bot import provenance
from sc2.data import Result


class LaunchProvenanceTest(unittest.TestCase):
    def test_main_without_path_git_and_without_any_git(self):
        original_cwd = Path.cwd()
        real_git = provenance.find_git()
        self.assertIsNotNone(real_git, "Local smoke check expects an installed Git")
        try:
            for available in (True, False):
                with self.subTest(git_available=available), tempfile.TemporaryDirectory() as temporary:
                    root = Path(temporary)
                    (root / "bot").mkdir()
                    (root / "bot/example.py").write_text("x = 1\n")
                    (root / ".env.local").write_text("DO_NOT_HASH")
                    map_path = root / "map.SC2Map"
                    map_path.write_bytes(b"map")
                    # Preserve real repository Git lookup for the installed-Git case;
                    # use the temporary source tree for the fully unavailable case.
                    gather = provenance.source_provenance
                    def metadata(_):
                        return gather(ROOT if available else root)
                    with patch.dict(os.environ, {"PATH": ""}), \
                         patch.object(provenance.shutil, "which", return_value=None), \
                         patch.object(provenance, "find_git", return_value=real_git if available else None), \
                         patch.object(provenance, "source_provenance", side_effect=metadata), \
                         patch.object(run_local, "ROOT", root), \
                         patch.object(run_local, "create_bot", return_value=None), \
                         patch.object(run_local.os, "chdir"), \
                         patch.object(run_local.importlib.metadata, "version", return_value="test"), \
                         patch("sc2.maps.get", return_value=SimpleNamespace(path=map_path)), \
                         patch("sc2.main.run_game", return_value=[Result.Defeat, Result.Victory]) as game, \
                         patch("bot.lifecycle.recover_human_game", return_value=nullcontext()), \
                         patch.object(sys, "argv", ["run_local.py", "--mode", "llm_ppo", "--human-training",
                                                    "--human-checkpoint", "fake.zip", "--run-id", "smoke"]):
                        self.assertEqual(run_local.main(), 0)
                        game.assert_called_once()
                    manifest = json.loads((root / "artifacts/runs/smoke/manifest.json").read_text())
                    self.assertEqual(manifest["human_match_results"]["bot_result"], "Result.Victory")
                    self.assertTrue(manifest["source_hashes"])
                    if available:
                        self.assertIsNotNone(manifest["project_commit"])
                        self.assertEqual(manifest["provenance_warnings"], [])
                    else:
                        self.assertIsNone(manifest["project_commit"])
                        self.assertIsNone(manifest["dirty_diff_sha256"])
                        self.assertTrue(manifest["provenance_warnings"])
                        self.assertEqual(list(manifest["source_hashes"]), ["bot/example.py"])
        finally:
            os.chdir(original_cwd)


if __name__ == "__main__":
    unittest.main()
