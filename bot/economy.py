"""Bounded economy policy; all worker orders remain owned by Ares Mining."""
from dataclasses import dataclass


@dataclass(frozen=True)
class EconomyDecision:
    worker_target: int
    base_target: int
    workers_per_gas: int
    mineral_capacity: int
    reason: str


class EconomyPolicy:
    def __init__(self):
        self.gas_workers = 3

    def decide(self, *, seconds, workers, ready_bases, mineral_patches,
               refineries, minerals, gas, mixed, requested_workers=72,
               requested_bases=4):
        # Keep one worker per refinery during surplus, so tech never loses all gas.
        if not mixed:
            self.gas_workers = 0
        elif gas < 250 or gas < minerals + 100:
            self.gas_workers = 3
        elif gas >= 600 and gas > 2 * minerals + 200:
            self.gas_workers = 1
        elif self.gas_workers == 0:
            self.gas_workers = 3
        capacity = 2 * mineral_patches
        # Replace workers after casualties, capped by *remaining* local resources.
        slots = min(80, capacity + self.gas_workers * refineries + 2)
        worker_target = min(slots, max(requested_workers, capacity + 2))
        # A plan is an aspiration, subject to expansion timing and saturation.
        stage = 1 + int(seconds >= 120) + int(seconds >= 360) + int(seconds >= 540)
        saturated = workers >= max(20, int(capacity * .8))
        depleted = ready_bases > 0 and mineral_patches < 6 * ready_bases
        floor = min(4, ready_bases + int(saturated or depleted))
        bases = min(stage, max(requested_bases, floor), 4)
        reason = 'depleted' if depleted else ('saturated' if saturated else 'developing')
        return EconomyDecision(max(0, worker_target), max(1, bases), self.gas_workers,
                               capacity, reason)
