import hashlib
import json
from pathlib import Path
import tempfile
import unittest

import numpy as np

from tools import train_micro_bc as bc


class BCTrainingTests(unittest.TestCase):
    def test_masked_gradient_matches_finite_difference(self):
        weights = {
            key: value.astype(np.float64) for key, value in bc.initialize(7).items()
        }
        obs = np.random.default_rng(8).uniform(-1, 1, (3, 16))
        mask = np.array([[True, False, True, True, True]] * 3)
        action = np.array([0, 2, 4])
        _, gradient = bc.loss_gradient(weights, obs, mask, action, gradients=True)
        for key, index in (
            ("w1", (2, 3)),
            ("w2", (5, 4)),
            ("w3", (6, 0)),
            ("b3", (1,)),
        ):
            original = weights[key][index]
            weights[key][index] = original + 1e-5
            above = bc.loss_gradient(weights, obs, mask, action)["masked_loss"]
            weights[key][index] = original - 1e-5
            below = bc.loss_gradient(weights, obs, mask, action)["masked_loss"]
            weights[key][index] = original
            self.assertAlmostEqual(
                (above - below) / 2e-5, gradient[key][index], places=6
            )
        self.assertTrue(np.all(gradient["w3"][:, 1] == 0))

    def test_rejects_group_leakage_even_with_valid_hash(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            path = root / "demonstrations.npz"
            np.savez_compressed(
                path,
                obs=np.zeros((3, 16), np.float32),
                mask=np.ones((3, 5), bool),
                action=np.zeros(3, np.int64),
                group=np.array(["same", "same", "test"]),
                split=np.array(["train", "validation", "test"]),
            )
            meta = dict(
                **bc.CONTRACT,
                samples=3,
                split_counts=dict(train=1, validation=1, test=1),
                group_splits=dict(same="train", test="test"),
                dataset_sha256=hashlib.sha256(path.read_bytes()).hexdigest()
            )
            (root / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")
            with self.assertRaisesRegex(ValueError, "leakage"):
                bc.load_dataset(root)


if __name__ == "__main__":
    unittest.main()
