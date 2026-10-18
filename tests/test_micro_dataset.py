import hashlib
import json
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

import numpy as np
from tools import export_micro_dataset as exporter


class DatasetTests(unittest.TestCase):
    def prepare(self, root):
        directory = root / "artifacts/runs/example"
        directory.mkdir(parents=True)
        row = dict(
            obs=[0.0] * 16,
            mask=[True] * 5,
            executed_action=1,
            split="train",
            game_loop=8,
            bc_eligible=True,
            command_result="engine_confirmed",
            actual_game_loops=8,
            truncated=False,
            versions=dict(
                feature="marine-16-v1",
                action="marine-5-v1",
                decision_game_loops=8,
                expert="marine-kite-v1",
                scenario="marine-vs-marine-v4",
            ),
        )
        data = directory / "micro_transitions.jsonl"
        data.write_text(json.dumps(row) + "\n")
        summary = root / "summary.json"
        summary.write_text(
            json.dumps(
                dict(
                    status="passed",
                    runs=[
                        dict(
                            expert="kite",
                            run_id="example",
                            case="same_case",
                            split="train",
                            audit=dict(
                                source_sha256=hashlib.sha256(
                                    data.read_bytes()
                                ).hexdigest()
                            ),
                        )
                    ],
                )
            )
        )
        return summary, data

    def rewrite_run(self, summary, data, rows):
        data.write_text("".join(json.dumps(row) + "\n" for row in rows))
        suite = json.loads(summary.read_text())
        for run in suite["runs"]:
            if run["run_id"] == data.parent.name:
                run["audit"]["source_sha256"] = hashlib.sha256(
                    data.read_bytes()
                ).hexdigest()
        summary.write_text(json.dumps(suite))

    def test_export_can_be_loaded_without_pickle_and_preserves_masks_and_split(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary, data = self.prepare(root)
            with patch.object(exporter, "ROOT", root):
                result = exporter.export(summary, root / "dataset")
            with np.load(
                root / "dataset/demonstrations.npz", allow_pickle=False
            ) as values:
                self.assertEqual(values["obs"].shape, (1, 16))
                self.assertEqual(values["action"].tolist(), [1])
                self.assertEqual(values["split"].tolist(), ["train"])
                self.assertTrue(values["mask"][0, 1])
            self.assertEqual(result["missing_actions"], [0, 2, 3, 4])

    def test_export_rejects_data_modified_after_audit(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary, data = self.prepare(root)
            data.write_text(data.read_text() + "\n")
            with patch.object(exporter, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "Audited input changed"):
                    exporter.export(summary, root / "dataset")

    def test_export_rejects_incompatible_contract_even_for_ineligible_rows(self):
        for key, value in (
            ("feature", "future-features"),
            ("action", "future-actions"),
            ("decision_game_loops", 16),
        ):
            with self.subTest(key=key), tempfile.TemporaryDirectory() as tmp:
                root = Path(tmp)
                summary, data = self.prepare(root)
                row = json.loads(data.read_text())
                row["versions"][key] = value
                row["bc_eligible"] = False
                self.rewrite_run(summary, data, [row])
                with patch.object(exporter, "ROOT", root):
                    with self.assertRaisesRegex(
                        ValueError, "Incompatible demonstration contract"
                    ):
                        exporter.export(summary, root / "dataset")

    def test_export_rejects_same_case_across_splits_even_without_labels(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary, data = self.prepare(root)
            suite = json.loads(summary.read_text())
            other = root / "artifacts/runs/other/micro_transitions.jsonl"
            other.parent.mkdir()
            other.write_text("")
            suite["runs"].append(
                dict(
                    expert="kite",
                    run_id="other",
                    case="same_case",
                    split="test",
                    audit=dict(
                        source_sha256=hashlib.sha256(other.read_bytes()).hexdigest()
                    ),
                )
            )
            summary.write_text(json.dumps(suite))
            with patch.object(exporter, "ROOT", root):
                with self.assertRaisesRegex(ValueError, "leaked across splits"):
                    exporter.export(summary, root / "dataset")

    def test_split_coverage_and_actual_version_sets_do_not_imply_training_readiness(
        self,
    ):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            summary, data = self.prepare(root)
            original = json.loads(data.read_text())
            rows = []
            for action in range(5):
                row = dict(original, executed_action=action)
                row["versions"] = dict(
                    original["versions"], scenario="marine-two-targets-v5"
                )
                rows.append(row)
            self.rewrite_run(summary, data, rows)
            suite = json.loads(summary.read_text())
            other = root / "artifacts/runs/other/micro_transitions.jsonl"
            other.parent.mkdir()
            row = dict(original, executed_action=0, split="test")
            other.write_text(json.dumps(row) + "\n")
            suite["runs"].append(
                dict(
                    expert="kite",
                    run_id="other",
                    case="other_case",
                    split="test",
                    audit=dict(
                        source_sha256=hashlib.sha256(other.read_bytes()).hexdigest()
                    ),
                )
            )
            summary.write_text(json.dumps(suite))
            with patch.object(exporter, "ROOT", root):
                result = exporter.export(summary, root / "dataset")
            self.assertEqual(result["samples"], 6)
            self.assertEqual(result["missing_actions"], [])
            self.assertEqual(result["training_readiness"], "not_established")
            self.assertEqual(result["expert_versions"], ["marine-kite-v1"])
            self.assertEqual(
                result["scenario_versions"],
                ["marine-two-targets-v5", "marine-vs-marine-v4"],
            )
            self.assertEqual(
                result["split_coverage"]["train"],
                dict(
                    samples=5,
                    action_counts={str(i): 1 for i in range(5)},
                    missing_actions=[],
                ),
            )
            self.assertEqual(
                result["split_coverage"]["test"],
                dict(
                    samples=1,
                    action_counts={str(i): int(i == 0) for i in range(5)},
                    missing_actions=[1, 2, 3, 4],
                ),
            )
            self.assertEqual(
                result["split_coverage"]["validation"],
                dict(
                    samples=0,
                    action_counts={str(i): 0 for i in range(5)},
                    missing_actions=list(range(5)),
                ),
            )


if __name__ == "__main__":
    unittest.main()
