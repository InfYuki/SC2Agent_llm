"""One offline merge acceptance check; no SC2, optimization or API calls."""
import copy
import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np

from tools import export_micro_dataset as exporter
from tools.train_micro_bc import load_dataset


class MultiSuiteMergeCheck(unittest.TestCase):
    def test_merge_acceptance(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)

            def write_suite(name, runs):
                path = root / (name + ".json")
                path.write_text(json.dumps(dict(status="passed", runs=runs)), encoding="utf-8")
                return path

            def make_run(name, split, count, group=None):
                path = root / "artifacts/runs" / name / "micro_transitions.jsonl"
                path.parent.mkdir(parents=True)
                rows = [dict(
                    obs=[i / 100] * 16, mask=[True] * 5, executed_action=i % 5,
                    split=split, game_loop=(i + 1) * 8, bc_eligible=True,
                    command_result="engine_confirmed", actual_game_loops=8,
                    truncated=False, versions=dict(feature="marine-16-v1",
                        action="marine-5-v1", decision_game_loops=8,
                        expert="marine-kite-v1", scenario="marine-two-targets-v6"),
                ) for i in range(count)]
                path.write_text("".join(json.dumps(row) + "\n" for row in rows), encoding="utf-8")
                return dict(expert="kite", run_id=name, case=group or name, split=split,
                            passed=True, status="passed", audit=dict(
                                source_sha256=hashlib.sha256(path.read_bytes()).hexdigest()))

            old_runs = [make_run("old_" + split, split, count)
                        for split, count in (("train", 32), ("validation", 24), ("test", 26))]
            new_run = make_run("new_train", "train", 11)
            old = write_suite("old", old_runs)
            new = write_suite("new", [new_run])
            # Independent empty raw files are valid audited runs, not shared samples.
            empty_runs = [make_run("empty_a", "train", 0), make_run("empty_b", "test", 0)]
            empty = write_suite("empty", empty_runs)

            with patch.object(exporter, "ROOT", root):
                legacy = exporter.export(old, root / "legacy")
                old_data, _ = load_dataset(root / "legacy")
                merged = exporter.export(old, root / "merged", additional_summaries=[new, empty])
                data, loaded_meta = load_dataset(root / "merged")
                self.assertEqual(merged["samples"], 93)
                self.assertEqual(loaded_meta["split_counts"], dict(train=43, validation=24, test=26))
                self.assertEqual(legacy["suite_sha256"], hashlib.sha256(old.read_bytes()).hexdigest())
                self.assertIsNone(merged["suite_sha256"])
                self.assertEqual([s["path"] for s in merged["source_suites"]],
                                 [str(p.resolve()) for p in (old, new, empty)])
                for split in ("validation", "test"):
                    for key in old_data:
                        np.testing.assert_array_equal(old_data[key][old_data["split"] == split],
                                                      data[key][data["split"] == split])
                duplicate = exporter.export(old, root / "duplicate", additional_summaries=[new, old])
                self.assertEqual(duplicate["samples"], 93)
                self.assertEqual(duplicate["duplicate_references"], 3)
                self.assertEqual(len(duplicate["input_files"][0]["source_references"]), 2)
                with self.assertRaises(FileExistsError):
                    exporter.export(old, root / "legacy")

                # An identical raw under another run ID contributes samples once.
                alias = make_run("alias", "train", 11, "new_train")
                alias_suite = write_suite("alias", [alias])
                dedup = exporter.export(old, root / "alias_merge", additional_summaries=[new, alias_suite])
                self.assertEqual((dedup["samples"], dedup["duplicate_references"]), (93, 1))

                def rejected(name, suite, message):
                    path = root / (name + ".json")
                    path.write_text(json.dumps(suite), encoding="utf-8")
                    with self.subTest(name=name), self.assertRaisesRegex(ValueError, message):
                        exporter.export(old, root / (name + "_out"), additional_summaries=[new, path])
                    self.assertFalse((root / (name + "_out")).exists())

                conflict = copy.deepcopy(new_run)
                conflict["audit"]["source_sha256"] = "0" * 64
                rejected("run_sha_conflict", dict(status="passed", runs=[conflict]), "Audited input changed")
                conflict = dict(new_run, case="different_case")
                rejected("run_identity_conflict", dict(status="passed", runs=[conflict]), "Conflicting run identity")
                rejected("raw_case_conflict", dict(status="passed", runs=[dict(alias, case="different_case")]),
                         "Same raw content")
                rejected("raw_split_conflict", dict(status="passed", runs=[dict(alias, case="another_case", split="test")]),
                         "Same raw content")
                leaked = make_run("leaked", "test", 1, "old_train")
                rejected("group_leak", dict(status="passed", runs=[leaked]), "leaked across splits")
                rejected("failed_suite", dict(status="failed", runs=[new_run]), "fully passed")
                rejected("failed_run", dict(status="passed", runs=[dict(new_run, passed=False)]), "fully passed")
                rejected("selection_count", dict(status="passed", runs=[new_run], selected=dict(run_count=2)),
                         "fully passed")
                sidecar = root / "artifacts/runs/alias/learning_exclusion.json"
                sidecar.write_text(json.dumps(dict(run_id="alias", excluded_from_future_training=True,
                    raw_sha256={"micro_transitions.jsonl": alias["audit"]["source_sha256"]})), encoding="utf-8")
                rejected("excluded_duplicate", dict(status="passed", runs=[alias]), "excluded from future training")
                sidecar.unlink()
                raw_path = root / "artifacts/runs/alias/micro_transitions.jsonl"
                original = raw_path.read_text(encoding="utf-8")
                for name, field, value, message in (
                    ("bad_contract", "versions", dict(feature="future", action="marine-5-v1", decision_game_loops=8), "contract"),
                    ("bad_eligibility", "actual_game_loops", 16, "eligibility"),
                    ("bad_mask", "mask", [False] * 5, "Illegal label"),
                ):
                    row = json.loads(original.splitlines()[0])
                    row[field] = value
                    raw_path.write_text(json.dumps(row) + "\n", encoding="utf-8")
                    changed = copy.deepcopy(alias)
                    changed["audit"]["source_sha256"] = hashlib.sha256(raw_path.read_bytes()).hexdigest()
                    rejected(name, dict(status="passed", runs=[changed]), message)


if __name__ == "__main__":
    unittest.main()
