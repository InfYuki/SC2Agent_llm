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
                feature="marine-16-v1", action="marine-5-v1", decision_game_loops=8
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


if __name__ == "__main__":
    unittest.main()
