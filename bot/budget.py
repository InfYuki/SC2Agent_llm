"""Bounded saving window so cheap continuous production cannot starve expansion.

Design reference: SmoothBrain's priority_reserve (Myrmecoman/sc2_bot).
This controller is an independent implementation for Ares expansion behaviors.
"""


class ExpansionBudget:
    def __init__(self, save_seconds=30, retry_seconds=30):
        self.save_seconds = save_seconds
        self.retry_seconds = retry_seconds
        self.until = None
        self.retry_at = 0

    def reserve(self, game_time, needs_expansion, under_attack=False):
        if not needs_expansion or under_attack:
            self.until = None
            if under_attack:
                self.retry_at = game_time + 10
            return False
        if self.until is not None and game_time >= self.until:
            self.until = None
            self.retry_at = game_time + self.retry_seconds
            return False
        if self.until is None and game_time >= self.retry_at:
            self.until = game_time + self.save_seconds
        return self.until is not None
