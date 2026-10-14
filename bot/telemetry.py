"""Per-run diagnostics, kept independent of the game framework."""
from collections import Counter
import json
from pathlib import Path
import time
import traceback


class Telemetry:
    def __init__(self, output):
        self.output = Path(output)
        self.output.mkdir(parents=True, exist_ok=False)
        self.events = (self.output / "events.jsonl").open("w", encoding="utf-8")
        self.counts = Counter()
        self.error = None
        self.stop_reason = None
        self.first_wall = self.first_game = None
        self.last_wall = self.last_game = None
        self.last_snapshot_game = -100
        self.steps = []
        self.peak_workers = self.peak_marines = self.peak_bases = 0
        self.finished = False

    def write_json(self, name, value):
        target = self.output / name
        temporary = target.with_suffix(target.suffix + ".tmp")
        temporary.write_text(
            json.dumps(value, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        temporary.replace(target)

    def event(self, kind, **fields):
        if not self.events.closed:
            self.events.write(
                json.dumps(dict(event=kind, wall_time=time.time(), **fields)) + "\n"
            )
            self.events.flush()

    def fail(self, phase):
        self.error = dict(phase=phase, traceback=traceback.format_exc())
        self.event("exception", **self.error)

    def observe(self, bot, elapsed):
        now, game = time.perf_counter(), float(bot.time)
        if self.first_wall is None:
            self.first_wall, self.first_game = now, game
        self.last_wall, self.last_game = now, game
        self.counts["callbacks"] += 1
        self.steps.append(elapsed)
        workers, marines, bases = (
            bot.workers.amount,
            bot.units(bot.marine_type).amount,
            bot.townhalls.amount,
        )
        self.peak_workers = max(self.peak_workers, workers)
        self.peak_marines = max(self.peak_marines, marines)
        self.peak_bases = max(self.peak_bases, bases)
        if game - self.last_snapshot_game >= 1:
            self.last_snapshot_game = game
            snapshot = dict(
                game_seconds=game,
                game_loop=int(bot.state.game_loop),
                minerals=int(bot.minerals),
                vespene=int(bot.vespene),
                workers=workers,
                marines=marines,
                bases=bases,
                supply_used=bot.supply_used,
                supply_cap=bot.supply_cap,
                structures=dict(Counter(u.type_id.name for u in bot.structures)),
                strategy=getattr(bot, "strategy_state", "template"),
                enemy_visible=bot.enemy_units.filter(lambda u: u.is_visible).amount,
                counters=dict(self.counts),
            )
            self.write_json("latest_state.json", snapshot)
            self.event("state", **snapshot)

    def finish(self, result=None):
        if self.finished:
            return
        self.finished = True
        wall = self.last_wall - self.first_wall if self.first_wall is not None else 0
        game = self.last_game - self.first_game if self.first_game is not None else 0
        ordered = sorted(self.steps)
        percentile = (
            lambda q: ordered[min(len(ordered) - 1, int(q * (len(ordered) - 1)))]
            if ordered
            else None
        )
        status = (
            "crashed"
            if self.error
            else "truncated"
            if self.stop_reason == "game_time_limit"
            else "interrupted"
            if self.stop_reason
            else "completed"
            if result is not None
            else "incomplete"
        )
        self.write_json(
            "summary.json",
            dict(
                status=status,
                result=str(result) if result else None,
                stop_reason=self.stop_reason,
                error=self.error,
                counters=dict(self.counts),
                game_span_seconds=game,
                wall_span_seconds=wall,
                game_to_wall_ratio=game / wall if wall else None,
                on_step_p50_seconds=percentile(0.5),
                on_step_p95_seconds=percentile(0.95),
                on_step_p99_seconds=percentile(0.99),
                on_step_max_seconds=max(ordered) if ordered else None,
                peak_workers=self.peak_workers,
                peak_marines=self.peak_marines,
                peak_bases=self.peak_bases,
            ),
        )
        self.events.close()
