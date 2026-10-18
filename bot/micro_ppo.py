"""Torch-free inference for an explicitly exported MaskablePPO actor."""
import re

import numpy as np

from bot.micro_bc import NumpyBCPolicy

POLICY_VERSION = "marine-ppo-numpy-v1"


class NumpyPPOPolicy(NumpyBCPolicy):
    policy_version = POLICY_VERSION
    label = "PPO"

    @classmethod
    def load(cls, directory):
        policy = super().load(directory)
        producer = policy.metadata.get("producer", {})
        if (producer.get("algorithm") != "MaskablePPO"
                or not re.fullmatch(r"[0-9a-f]{64}", producer.get("source_checkpoint_sha256", ""))
                or not isinstance(producer.get("versions"), dict)
                or not all(producer["versions"].get(key) for key in
                           ("torch", "stable-baselines3", "sb3-contrib", "numpy"))):
            raise ValueError("PPO producer provenance missing or invalid")
        return policy

    def probabilities(self, obs, mask):
        # action() performs the same strict bool mask validation as runtime.
        self.action(obs, mask)
        mask = np.asarray(mask)
        logits = self.logits(obs)
        masked = np.where(mask, logits, -np.inf)
        probabilities = np.exp(masked - np.max(masked))
        return probabilities / probabilities.sum()
