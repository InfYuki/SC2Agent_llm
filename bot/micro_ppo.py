"""Torch-free inference for an explicitly exported MaskablePPO actor."""
import re

import numpy as np

from bot.micro_bc import NumpyBCPolicy

POLICY_VERSION = "marine-ppo-numpy-v1"

# Only scenarios with an explicit homogeneous enemy definition are understood.
# This describes enemy species/count only, not friendly army, HP or geometry.
ENEMY_SCENARIOS = {
    "marine-vs-marine": "MARINE",
    "marine-vs-zergling": "ZERGLING",
}


def enemy_domain(metadata):
    """Read current producer declarations only; malformed sets fail as a whole."""
    result = dict(status="unknown", source=None, reason="missing_task", pairs=[])
    producer = metadata.get("producer") if isinstance(metadata, dict) else None
    if not isinstance(producer, dict):
        return dict(result, reason="invalid_producer")
    if "curriculum" in producer:
        curriculum = producer["curriculum"]
        result["source"] = "curriculum.tasks"
        if (not isinstance(curriculum, dict)
                or curriculum.get("format") != "marine-micro-curriculum-v1"
                or curriculum.get("selection") != "round-robin"
                or not isinstance(curriculum.get("tasks"), list)
                or not curriculum["tasks"]):
            return dict(result, reason="invalid_curriculum")
        tasks = curriculum["tasks"]
    elif "task" in producer:
        result["source"] = "task"
        tasks = [producer["task"]]
    else:
        return result
    pairs = set()
    for task in tasks:
        if not isinstance(task, dict):
            return dict(result, reason="invalid_task")
        scenario, count = task.get("scenario"), task.get("enemy_count")
        if not isinstance(scenario, str) or scenario not in ENEMY_SCENARIOS:
            return dict(result, reason="unsupported_scenario")
        if type(count) is not int or count not in (1, 2):
            return dict(result, reason="invalid_enemy_count")
        pairs.add((ENEMY_SCENARIOS[scenario], count))
    return dict(result, status="known", reason="declared", pairs=[list(p) for p in sorted(pairs)])


def enemy_domain_reason(domain, ctx):
    """Return a bounded audit reason for the same enemies used by context()."""
    if domain["status"] != "known":
        return "unknown_domain"
    names = {enemy.type_id.name for enemy in ctx.enemies}
    if len(names) != 1:
        return "mixed_enemies" if names else "no_enemy"
    pair = [next(iter(names)), len(ctx.enemies)]
    return "accepted" if pair in domain["pairs"] else "outside_domain"


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
