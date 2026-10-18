"""Versioned NumPy BC actor with strict observation and action contracts."""
import hashlib
import json
from pathlib import Path

import numpy as np

POLICY_VERSION = "marine-bc-numpy-v1"
SHAPES = {
    "w1": (16, 64), "b1": (64,), "w2": (64, 64),
    "b2": (64,), "w3": (64, 5), "b3": (5,),
}


class NumpyBCPolicy:
    @classmethod
    def load(cls, directory):
        directory = Path(directory)
        metadata = json.loads((directory / "metadata.json").read_text(encoding="utf-8"))
        contract = dict(
            format=POLICY_VERSION, feature_version="marine-16-v1",
            action_version="marine-5-v1", decision_game_loops=8,
            architecture=[16, 64, 64, 5], activation="tanh",
            normalization="marine-16-v1",
        )
        for key, value in contract.items():
            if metadata.get(key) != value:
                raise ValueError("BC contract mismatch: " + key)
        path = directory / "weights.npz"
        if hashlib.sha256(path.read_bytes()).hexdigest() != metadata.get("weights_sha256"):
            raise ValueError("BC weights hash mismatch")
        with np.load(path, allow_pickle=False) as archive:
            if set(archive.files) != set(SHAPES):
                raise ValueError("BC weight keys mismatch")
            weights = {}
            for key, shape in SHAPES.items():
                value = archive[key]
                if value.shape != shape or value.dtype != np.float32 or not np.isfinite(value).all():
                    raise ValueError("Invalid BC weights: " + key)
                weights[key] = value.copy()
        policy = cls()
        policy.weights, policy.metadata = weights, metadata
        return policy

    def logits(self, obs):
        x = np.asarray(obs, dtype=np.float32)
        if x.shape != (16,) or not np.isfinite(x).all() or (np.abs(x) > 1).any():
            raise ValueError("Invalid marine-16-v1 observation")
        w = self.weights
        with np.errstate(over="raise", invalid="raise"):
            h = np.tanh(x @ w["w1"] + w["b1"])
            h = np.tanh(h @ w["w2"] + w["b2"])
            result = h @ w["w3"] + w["b3"]
        if result.shape != (5,) or not np.isfinite(result).all():
            raise ValueError("Invalid BC logits")
        return result

    def action(self, obs, mask):
        mask = np.asarray(mask)
        if mask.shape != (5,) or mask.dtype != np.bool_ or not mask[4]:
            raise ValueError("Invalid marine-5-v1 action mask")
        return int(np.argmax(np.where(mask, self.logits(obs), -np.inf)))
