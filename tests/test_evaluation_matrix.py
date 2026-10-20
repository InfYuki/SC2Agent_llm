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
                if mode in ("llm", "llm_ppo"):
                    (folder / "llm_config.json").write_text(json.dumps(dict(
                        provider="DeepSeek", model="model", api_key="secret-key-must-not-leak",
                        base_url="https://user:secret-password@api.example/v1?token=secret-query",
                        headers={"Authorization": "Bearer secret-header"})))
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
            self.assertNotIn("secret-", json.dumps(report))
            self.assertNotIn("base_url", json.dumps(report))
            self.assertNotIn("Authorization", json.dumps(report))
            self.assertEqual(report["attempts"][0]["identity"]["llm_identity_status"], "not_applicable")
            llm_identity = report["attempts"][1]["identity"]
            self.assertEqual(llm_identity["llm_configured_model"], "model")
            self.assertEqual(llm_identity["llm_requested_model"], "model")
            self.assertIsNone(llm_identity["llm_response_model"])
            self.assertFalse(llm_identity["llm_remote_behavior_frozen"])
            self.assertIn("llm_config.json", report["attempts"][1]["evidence_sha256"])

            # Mock the existing SC2-ping artifact and configured-only LLM artifact;
            # neither needs an import of BotAI/Settings or any network request.
            restored = run("restored", "llm", game_build=None)
            (restored / "compatibility-report.json").write_text(json.dumps(dict(
                sc2_base_build=98370, ignored_sensitive_field="secret-sc2")))
            (restored / "events.jsonl").write_text(json.dumps(dict(
                event="llm_response", ok=True, model="not-an-explicit-response-identity",
                content="secret-response", headers={"Authorization": "secret-response-header"})))
            restored_row = build_report([restored])["attempts"][0]
            self.assertEqual(restored_row["fair_config"]["game_build"], 98370)
            self.assertEqual(restored_row["identity"]["llm_model"], "model")
            self.assertIsNone(restored_row["identity"]["llm_requested_model"])
            self.assertIsNone(restored_row["identity"]["llm_response_model"])
            self.assertIn("runtime SC2 ping", restored_row["identity"]["identity_evidence"]["game_build"][0]["source"])
            self.assertIn("compatibility-report.json", restored_row["evidence_sha256"])
            self.assertNotIn("secret-", json.dumps(restored_row))
            manifest = json.loads((restored / "manifest.json").read_text())
            manifest["game_build"] = 123
            (restored / "manifest.json").write_text(json.dumps(manifest))
            conflict = build_report([e3, restored])
            self.assertEqual(conflict["attempts"][1]["fair_config"]["game_build"], 123)
            self.assertEqual(len(conflict["attempts"][1]["identity"]["identity_evidence"]["game_build"]), 2)
            self.assertIn("identity_conflict:game_build", conflict["attempts"][1]["missing_comparison_fields"])
            self.assertFalse(any(g["cross_mode_config_match"] for g in conflict["comparison_groups"]))
            (restored / "llm_config.json").unlink()
            (restored / "events.jsonl").write_text(json.dumps(dict(event="llm_request", model="legacy-model")))
            legacy = build_report([restored])["attempts"][0]
            self.assertEqual(legacy["identity"]["llm_model"], "legacy-model")
            self.assertIn("llm_configured_provider", legacy["missing_comparison_fields"])
            (restored / "llm_config.json").write_text(json.dumps(dict(provider="OtherProvider", model="model")))
            manifest["game_build"] = 123
            (restored / "compatibility-report.json").unlink()
            (restored / "events.jsonl").write_text(json.dumps(dict(event="llm_request", model="model")))
            provider_difference = build_report([e4, restored])
            self.assertFalse(provider_difference["comparison_groups"][0]["shared_intervention_identities_match"])
            self.assertFalse(provider_difference["comparison_groups"][0]["cross_mode_config_match"])
            manifest["config"].update(llm_model="manifest-model", llm_provider="OtherProvider")
            (restored / "manifest.json").write_text(json.dumps(manifest))
            (restored / "events.jsonl").write_text("\n".join(json.dumps(event) for event in (
                dict(event="llm_request", model="requested-model"),
                dict(event="llm_response", response_model="reported-model", api_key="secret-response-key"))))
            distinct = build_report([restored])["attempts"][0]
            self.assertEqual(distinct["identity"]["llm_configured_model"], "manifest-model")
            self.assertEqual(distinct["identity"]["llm_requested_model"], "requested-model")
            self.assertEqual(distinct["identity"]["llm_response_model"], "reported-model")
            self.assertIn("identity_conflict:llm_configured_model", distinct["missing_comparison_fields"])
            self.assertIn("configured_requested_model_mismatch", distinct["missing_comparison_fields"])
            self.assertNotIn("secret-", json.dumps(distinct))
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
