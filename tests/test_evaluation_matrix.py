"""One consolidated offline matrix contract check; no SC2 or model imports."""
import json
from pathlib import Path
import tempfile
import unittest

from tools.report_evaluation_matrix import build_report, FAIR_FIELDS, SHARED_SOURCES


class EvaluationMatrixTests(unittest.TestCase):
    def test_denominators_unknown_missing_and_comparison_boundaries(self):
        with tempfile.TemporaryDirectory() as directory:
            base = Path(directory)

            def run(name, mode, status="completed", result="Result.Victory", **changes):
                folder = base / name
                folder.mkdir()
                config = dict(zip(FAIR_FIELDS, ["map", "Zerg", "Easy", False, 8, 42, 1200, 4]))
                config.update(mode=mode, llm_max_calls=20, secret="must-not-leak")
                manifest = dict(config=config, map_sha256="mapsha", ares_commit="ares",
                                packages={"ares-sc2": "3.15"}, game_build=123,
                                source_hashes={key: "same" for key in SHARED_SOURCES})
                manifest.update(changes)
                (folder / "manifest.json").write_text(json.dumps(manifest))
                (folder / "summary.json").write_text(json.dumps(dict(
                    status=status, result=result, stop_reason=None,
                    error={"phase": "on_step"} if status == "crashed" else None,
                    counters={"micro_owned_decisions": 3, "ppo_inference_decisions": 3})))
                (folder / "strategy_summary.json").write_text(json.dumps({"counters": {"llm_steps": 2}}))
                (folder / "micro_summary.json").write_text(json.dumps({"counters": {"truncated": 5}}))
                (folder / "events.jsonl").write_text(json.dumps({"event": "ppo_model_loaded", "weights_sha256": "actor"}) + "\n" + json.dumps({"event": "llm_request", "model": "model"}))
                return folder

            e3 = run("e3", "rule_ppo")
            e4 = run("e4", "llm_ppo")
            failed = run("failed", "llm_ppo", "crashed", None)
            unknown = run("unknown", "rule", result="unrecognized")
            incomplete = run("missing", "llm", game_build=None)
            changed = run("changed", "rule", game_build=456)
            report = build_report([e3, e4, failed, unknown, incomplete, changed])
            self.assertEqual(report["totals"]["attempts"], 6)
            self.assertEqual(report["totals"]["failed"], 1)
            self.assertEqual(report["totals"]["unknown_results"], 2)
            self.assertEqual(report["totals"]["losses"], 0)
            self.assertEqual(report["matrix"][2]["availability"], "missing")
            self.assertIsNone(report["matrix"][2]["descriptive_win_fraction_known"])
            self.assertEqual(report["matrix"][4]["end_to_end_victory_fraction"], 0.5)
            self.assertEqual(report["totals"]["truncated"], 0)
            self.assertTrue(any(group["cross_mode_config_match"] for group in report["comparison_groups"]))
            self.assertIn("game_build", report["differing_shared_fields"])
            self.assertFalse(report["formal_comparison_ready"])
            self.assertNotIn("must-not-leak", json.dumps(report))
            self.assertEqual(build_report([e3, e3])["totals"]["attempts"], 1)
            self.assertEqual(build_report([e3, e3])["duplicate_inputs_ignored"], ["e3"])
            (incomplete / "manifest.json").unlink()
            absent_manifest = build_report([incomplete])["attempts"][0]
            self.assertEqual(absent_manifest["experiment"], "unmapped")
            self.assertIn("missing:manifest.json", absent_manifest["warnings"])
            self.assertEqual(build_report([incomplete])["totals"]["attempts"], 1)
            (incomplete / "manifest.json").write_text(json.dumps({"config": None, "source_hashes": []}))
            (incomplete / "events.jsonl").write_text("[]\nnull\n")
            malformed = build_report([incomplete])
            self.assertEqual(malformed["totals"]["attempts"], 1)
            self.assertIn("invalid_object:manifest.config", malformed["attempts"][0]["warnings"])
            self.assertIn("invalid_object:event_line", malformed["attempts"][0]["warnings"])


if __name__ == "__main__":
    unittest.main()
