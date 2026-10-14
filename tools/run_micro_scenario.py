"""Single local 1v1 debug scenario, fixed 8-loop sampling; no reset/step claim."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
import run_local  # fixed Ares import paths
from sc2 import maps
from sc2.bot_ai import BotAI
from sc2.data import Race
from sc2.ids.unit_typeid import UnitTypeId
from sc2.main import run_game
from sc2.player import Bot
from sc2.position import Point2
from bot.lifecycle import recover_completed_game
from bot.micro import DECISION_LOOPS, clear_segment, context
from bot.micro_bot import MicroRuleBot
from bot.telemetry import Telemetry


class Opponent(BotAI):
    async def on_step(self, iteration):
        self.client.game_step = DECISION_LOOPS
        for unit in self.units:
            if (
                unit.type_id in {UnitTypeId.ZERGLING, UnitTypeId.MARINE}
                and self.enemy_units
            ):
                target = self.enemy_units.closest_to(unit)
                if not unit.orders or unit.orders[0].target != target.tag:
                    unit.attack(target)


class ScenarioBot(MicroRuleBot):
    async def on_start(self):
        try:
            await self._setup_scene()
        except Exception:
            self.telemetry.fail("scenario_setup")
            raise

    async def _setup_scene(self):
        await super().on_start()
        self.recorder.scenario = self.options.scenario + "-v4"
        if self.options.data_split:
            self.recorder.split = self.options.data_split
        self._health_ready = (
            self.options.health_fraction == 1
            and self.options.enemy_health_fraction == 1
        )
        self._scene_tag = self._enemy_tag = None
        self._scene_stop = False
        self._scene_outcome = None
        self.enemy_kind = (
            (
                UnitTypeId.ZERGLINGBURROWED
                if self.options.enemy_hidden
                else UnitTypeId.ZERGLING
            )
            if self.options.scenario == "marine-vs-zergling"
            else UnitTypeId.MARINE
        )
        center = self.game_info.map_center
        self.spawn_rejects = Counter()
        # Both spawns on one traversable plateau. Generation uses terrain only;
        # policies still see only normal observations.
        area = self.game_info.playable_area
        positions = [
            Point2((x, y))
            for y in range(int(area.y + 8), int(area.y + area.height - 8), 4)
            for x in range(int(area.x + 8), int(area.x + area.width - 14), 4)
        ]
        positions.sort(key=lambda point: (point.distance_to(center), point.x, point.y))
        for left in positions:
            right = Point2((left.x + self.options.distance, left.y))
            starts = [self.start_location, *self.enemy_start_locations]
            if any(
                min(left.distance_to(start), right.distance_to(start)) < 25
                for start in starts
            ):
                continue
            probe = SimpleNamespace(position=left, radius=0.375)
            if (
                self._open_patch(left)
                and clear_segment(self, probe, right)
                and self.get_terrain_height(left) == self.get_terrain_height(right)
            ):
                self.scene_goal = right
                self.scene_origin = left
                await self.client.debug_create_unit(
                    [
                        [UnitTypeId.MARINE, 1, left, 1],
                        [self.enemy_kind, 1, right, 2],
                    ]
                )
                self.telemetry.write_json(
                    "scenario.json",
                    dict(
                        version=self.recorder.scenario,
                        friendly="MARINE",
                        enemy=self.enemy_kind.name,
                        friendly_position=list(left),
                        enemy_position=list(right),
                        seed=self.options.seed,
                        decision_game_loops=DECISION_LOOPS,
                        time_limit_seconds=self.options.max_game_seconds,
                        opponent_script="visible-nearest-attack-v1",
                        macro="disabled",
                        expert=self.options.expert,
                        requested_distance=self.options.distance,
                        health_fraction=self.options.health_fraction,
                        enemy_health_fraction=self.options.enemy_health_fraction,
                        enemy_hidden=self.options.enemy_hidden,
                        split=self.recorder.split,
                    ),
                )
                return
        self.telemetry.write_json("spawn_rejections.json", dict(self.spawn_rejects))
        raise RuntimeError("No supported 1v1 spawn segment on this map")

    def _open_patch(self, left):
        height = self.get_terrain_height(left)
        obstacles = [
            *self.destructables,
            *self.mineral_field,
            *self.vespene_geyser,
            *self.structures,
        ]
        obstacles = [u for u in obstacles if left.distance_to(u.position) < 24]
        for dx in range(-3, int(self.options.distance) + 4, 2):
            for dy in range(-3, 4, 2):
                point = Point2((left.x + dx, left.y + dy))
                if (
                    not self.in_pathing_grid(point)
                    or self.get_terrain_height(point) != height
                ):
                    self.spawn_rejects["terrain"] += 1
                    return False
                if any(
                    point.distance_to(u.position) < u.radius + 1.0 for u in obstacles
                ):
                    self.spawn_rejects["obstacle"] += 1
                    return False
        return True

    def _finish_scene(self, outcome, terminated):
        frame = int(self.state.game_loop)
        for tag in list(self.recorder.pending):
            marine = self.units(UnitTypeId.MARINE).find_by_tag(tag)
            ctx = (
                context(self, marine, self.units(UnitTypeId.MARINE), self.scene_goal)
                if marine
                else None
            )
            self.recorder.finish(
                tag,
                frame,
                ctx,
                terminated=terminated,
                truncated=not terminated,
                reason=outcome,
            )
        self._scene_outcome = outcome
        self._scene_stop = True
        self.telemetry.write_json(
            "scenario_result.json",
            dict(
                outcome=outcome,
                terminated=terminated,
                truncated=not terminated,
                game_loop=frame,
                game_seconds=float(self.time),
            ),
        )

    def play_step(self, iteration):
        # Deliberately bypass RuleBot's economy/production and strategic state.
        self.recorder.feedback(self.state)
        army = self.units(UnitTypeId.MARINE)
        enemies = [
            e for e in self.enemy_units if e.type_id == self.enemy_kind and e.is_visible
        ]
        if army and not getattr(self, "_initial_scene_recorded", False):
            self._initial_scene_recorded = True
            self.telemetry.write_json(
                "initial_scene_observation.json",
                dict(
                    game_loop=int(self.state.game_loop),
                    friendly_position=list(army.first.position),
                    health=float(army.first.health),
                    visible_enemy_count=len(enemies),
                    enemy_positions=[list(e.position) for e in enemies],
                ),
            )
        if army and self._scene_tag is None:
            self._scene_tag = army.first.tag
        if enemies and self._enemy_tag is None:
            self._enemy_tag = enemies[0].tag
        if self._scene_tag in self.state.dead_units:
            self._finish_scene("marine_dead", True)
            return
        if self._enemy_tag in self.state.dead_units:
            self._finish_scene("enemy_dead", True)
            return
        if self._enemy_tag is not None and not enemies:
            self._finish_scene("enemy_not_visible", False)
            return
        if army and army.first.health_percentage <= 0.2:
            self._finish_scene("low_health_safety_exit", False)
            return
        frame = int(self.state.game_loop)
        if army and enemies and frame - self._last_combat_frame >= DECISION_LOOPS:
            self._last_combat_frame = frame
            self.strategy_state = "attack"
            if self.options.expert == "kite":
                self.issue_combat_orders(army, "attack", self.scene_goal, frame)
            else:
                # Native attack-move is a separate baseline, not a fabricated
                # five-action BC label. It uses the same ownership gate.
                self.arbiter.begin_step({u.tag: "rule_combat" for u in army})
                for unit in army:
                    self.issue_rule_order(unit, "attack", self.scene_goal, frame)
            self.telemetry.counts["command_conflicts"] = self.arbiter.conflicts

    async def on_step(self, iteration):
        if not self._health_ready:
            if self.time >= self.options.max_game_seconds:
                await super().on_step(iteration)
                return
            army = self.units(UnitTypeId.MARINE)
            enemies = self.enemy_units.filter(
                lambda e: e.type_id == self.enemy_kind and e.is_visible
            )
            if army and enemies:
                await self.client.debug_set_unit_value(
                    army, 2, army.first.health_max * self.options.health_fraction
                )
                await self.client.debug_set_unit_value(
                    enemies,
                    2,
                    enemies.first.health_max * self.options.enemy_health_fraction,
                )
                self._health_ready = True
            return
        await super().on_step(iteration)
        if self._scene_stop:
            # Full SC2 match is deliberately truncated after the local scenario.
            # Only scenario_result describes its win/death; never count a match win.
            self.telemetry.stop_reason = "game_time_limit"
            await self.client.leave()

    def close_micro(self, reason=None):
        if getattr(self, "_scene_outcome", None) is None:
            self.telemetry.write_json(
                "scenario_result.json",
                dict(
                    outcome=reason or self.telemetry.stop_reason or "match_end",
                    terminated=False,
                    truncated=True,
                    game_loop=int(self.state.game_loop),
                ),
            )
        super().close_micro(reason)


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--scenario",
        choices=["marine-vs-zergling", "marine-vs-marine"],
        default="marine-vs-zergling",
    )
    parser.add_argument(
        "--game-path",
        default=os.environ.get("SC2PATH", r"C:\Program Files (x86)\StarCraft II"),
    )
    parser.add_argument("--map", default="Ancient Cistern LE")
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--realtime", action="store_true")
    parser.add_argument("--expert", choices=["kite", "amove"], default="kite")
    parser.add_argument("--distance", type=float, choices=[3.0, 6.0, 10.0], default=6.0)
    parser.add_argument("--enemy-hidden", action="store_true")
    parser.add_argument("--health-fraction", type=float, default=1.0)
    parser.add_argument("--enemy-health-fraction", type=float, default=1.0)
    parser.add_argument(
        "--data-split", choices=["train", "validation", "test"], default=None
    )
    parser.add_argument("--max-game-seconds", type=float, default=45)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    if args.max_game_seconds <= 0:
        parser.error("A finite positive scenario time limit is required")
    if not (0.2 < args.health_fraction <= 1 and 0 < args.enemy_health_fraction <= 1):
        parser.error("Own health fraction must be (0.2,1]; enemy health must be (0,1]")
    os.environ["SC2PATH"] = str(Path(args.game_path).resolve())
    os.chdir(ROOT)
    run_id = args.run_id or "scenario_" + datetime.now(timezone.utc).strftime(
        "%Y%m%d_%H%M%S_%f"
    )
    base = ROOT / "artifacts" / "runs"
    output = (base / run_id).resolve()
    if not output.is_relative_to(base.resolve()) or output == base.resolve():
        parser.error("run-id must stay in artifacts/runs")
    telemetry = Telemetry(output)
    options = SimpleNamespace(
        **vars(args), mode="micro_rule", game_step=DECISION_LOOPS, micro_max_units=1
    )
    bot = ScenarioBot(options, telemetry)
    settings = maps.get(args.map)
    manifest = dict(
        config=vars(args),
        python=sys.executable,
        realtime=args.realtime,
        project_commit=run_local.git("rev-parse", "HEAD"),
        ares_commit=run_local.git("-C", "ares-sc2", "rev-parse", "HEAD"),
        dependency_lock_sha256=hashlib.sha256(
            (ROOT / "poetry.lock").read_bytes()
        ).hexdigest(),
        map_sha256=hashlib.sha256(Path(settings.path).read_bytes()).hexdigest(),
        source_hashes={
            str(path.relative_to(ROOT)): hashlib.sha256(path.read_bytes()).hexdigest()
            for path in [*(ROOT / "bot").glob("*.py"), Path(__file__)]
        },
    )
    telemetry.write_json("manifest.json", manifest)
    print("Run output:", output, flush=True)
    try:
        with recover_completed_game(telemetry):
            result = run_game(
                settings,
                [
                    Bot(Race.Terran, bot),
                    Bot(
                        Race.Zerg
                        if args.scenario == "marine-vs-zergling"
                        else Race.Terran,
                        Opponent(),
                    ),
                ],
                realtime=args.realtime,
                random_seed=args.seed,
                save_replay_as=str(output / "game.SC2Replay"),
            )
        telemetry.finish(result)
    except Exception:
        if telemetry.error is None:
            telemetry.fail("scenario_runner")
        telemetry.finish()
        raise
    finally:
        bot.close_micro("system_failure" if telemetry.error else None)
    return 1 if telemetry.error else 0


if __name__ == "__main__":
    raise SystemExit(main())
