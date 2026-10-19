"""Local one/two-target debug scene, fixed 8-loop sampling; no reset/step claim."""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import math
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
from bot.micro import DECISION_LOOPS, clear_segment, context, expert
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
        self.recorder.scenario = self.options.scenario + "-v6"
        if self.options.data_split:
            self.recorder.split = self.options.data_split
        self._health_ready = False
        self._health_written = False
        self._enemy_tags = set()
        self._dead_enemy_tags = set()
        self._enemy_roles = {}
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
            enemy_positions = [right]
            if self.options.enemy_count == 2:
                enemy_positions.append(
                    Point2((left.x + self.options.second_distance, left.y))
                )
            starts = [self.start_location, *self.enemy_start_locations]
            if any(
                min(p.distance_to(start) for p in [left, *enemy_positions]) < 25
                for start in starts
            ):
                continue
            probe = SimpleNamespace(position=left, radius=0.375)
            if (
                self._open_patch(left)
                and all(clear_segment(self, probe, p) for p in enemy_positions)
                and all(
                    self.get_terrain_height(left) == self.get_terrain_height(p)
                    for p in enemy_positions
                )
            ):
                self.scene_goal = right
                self.scene_origin = left
                self.enemy_spawn_positions = enemy_positions
                await self.client.debug_create_unit(
                    [
                        [UnitTypeId.MARINE, 1, left, 1],
                        *[[self.enemy_kind, 1, p, 2] for p in enemy_positions],
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
                        enemy_positions=[list(p) for p in enemy_positions],
                        enemy_count=self.options.enemy_count,
                        second_distance=self.options.second_distance,
                        second_enemy_health_fraction=self.options.second_enemy_health_fraction,
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
        raise RuntimeError("No supported local spawn segment on this map")

    def _open_patch(self, left):
        height = self.get_terrain_height(left)
        obstacles = [
            *self.destructables,
            *self.mineral_field,
            *self.vespene_geyser,
            *self.structures,
        ]
        obstacles = [u for u in obstacles if left.distance_to(u.position) < 24]
        extent = max(
            self.options.distance,
            self.options.second_distance if self.options.enemy_count == 2 else 0,
        )
        for dx in range(-3, int(extent) + 4, 2):
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
        if army and self._scene_tag is None:
            self._scene_tag = army.first.tag
        if self._scene_tag in self.state.dead_units:
            self._finish_scene("marine_dead", True)
            return
        self._dead_enemy_tags.update(self._enemy_tags & self.state.dead_units)
        if self._enemy_tags and self._enemy_tags <= self._dead_enemy_tags:
            self._finish_scene("enemy_dead", True)
            return
        live_tags = self._enemy_tags - self._dead_enemy_tags
        if live_tags - {e.tag for e in enemies}:
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
            enemies = [
                e
                for e in self.enemy_units
                if e.type_id == self.enemy_kind and e.is_visible
            ]
            # Hidden diagnostics cannot identify a tag through an ordinary observation.
            # Only their all-full-health single-target setup is supported.
            if army and self.options.enemy_hidden:
                self._health_ready = True
                self._record_initial(army, enemies)
            elif army and len(enemies) == self.options.enemy_count:
                if not self._enemy_tags:
                    remaining = list(enemies)
                    for role, position in enumerate(self.enemy_spawn_positions):
                        enemy = min(
                            remaining,
                            key=lambda e: (e.position.distance_to(position), e.tag),
                        )
                        self._enemy_roles[enemy.tag] = role
                        remaining.remove(enemy)
                    self._enemy_tags = set(self._enemy_roles)
                targets = [(army.first, self.options.health_fraction)] + [
                    (
                        e,
                        self.options.enemy_health_fraction
                        if self._enemy_roles[e.tag] == 0
                        else self.options.second_enemy_health_fraction,
                    )
                    for e in enemies
                    if e.tag in self._enemy_tags
                ]
                confirmed = (
                    self._health_written
                    and len(targets) == self.options.enemy_count + 1
                    and all(
                        abs(u.health - u.health_max * fraction) <= 0.6
                        for u, fraction in targets
                    )
                )
                if confirmed:
                    self._health_ready = True
                    self._scene_tag = army.first.tag
                    self._record_initial(army, enemies)
                else:
                    # Set each tag independently; heterogeneous health must never
                    # use the SDK's bulk value computed from the first enemy.
                    for unit, fraction in targets:
                        await self.client.debug_set_unit_value(
                            unit, 2, unit.health_max * fraction
                        )
                    self._health_written = True
            if not self._health_ready:
                return
        await super().on_step(iteration)
        if self._scene_stop:
            # Full SC2 match is deliberately truncated after the local scenario.
            # Only scenario_result describes its win/death; never count a match win.
            self.telemetry.stop_reason = "game_time_limit"
            await self.client.leave()

    def _record_initial(self, army, enemies):
        unit = army.first
        ctx = context(self, unit, army, self.scene_goal)
        self.telemetry.write_json(
            "initial_scene_observation.json",
            dict(
                game_loop=int(self.state.game_loop),
                initialization_confirmed=self._health_ready,
                friendly_tag=unit.tag,
                friendly_position=list(unit.position),
                health=float(unit.health),
                visible_enemy_count=len(enemies),
                enemy_positions=[list(e.position) for e in enemies],
                enemies=[
                    dict(
                        tag=e.tag,
                        role=self._enemy_roles.get(e.tag),
                        position=list(e.position),
                        health=float(e.health),
                        health_max=float(e.health_max),
                        distance=float(unit.distance_to(e)),
                        in_range=bool(unit.target_in_range(e)),
                    )
                    for e in enemies
                ],
                nearest_tag=ctx.nearest.tag if ctx.nearest else None,
                weakest_tag=ctx.weakest.tag if ctx.weakest else None,
                weapon_cooldown=float(unit.weapon_cooldown),
                obs=list(ctx.obs),
                mask=list(ctx.mask),
                expert_action=int(expert(unit, ctx)),
            ),
        )

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


def scenario_distance(value):
    distance = float(value)
    if not math.isfinite(distance) or not 0 < distance <= 10:
        raise argparse.ArgumentTypeError("distance must be finite and in (0,10]")
    return distance


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
    parser.add_argument("--policy", choices=["rule", "bc", "ppo"], default="rule")
    parser.add_argument("--bc-model", default=None, help="Prototype model directory; invalid models fall back to kite rules.")
    parser.add_argument("--ppo-model", default=None, help="Exported NumPy PPO actor; invalid models fall back to kite rules.")
    parser.add_argument("--distance", type=scenario_distance, default=6.0)
    parser.add_argument("--enemy-hidden", action="store_true")
    parser.add_argument("--enemy-count", type=int, choices=[1, 2], default=1)
    parser.add_argument("--second-distance", type=float, default=8.0)
    parser.add_argument("--second-enemy-health-fraction", type=float, default=0.5)
    parser.add_argument("--health-fraction", type=float, default=1.0)
    parser.add_argument("--enemy-health-fraction", type=float, default=1.0)
    parser.add_argument(
        "--data-split", choices=["train", "validation", "test"], default=None
    )
    parser.add_argument("--max-game-seconds", type=float, default=45)
    parser.add_argument("--run-id", default=None)
    args = parser.parse_args()
    if args.policy in {"bc", "ppo"} and args.expert != "kite":
        parser.error("BC/PPO policy requires the five-action kite adapter (--expert kite)")
    if args.max_game_seconds <= 0:
        parser.error("A finite positive scenario time limit is required")
    if not (0.2 < args.health_fraction <= 1 and 0 < args.enemy_health_fraction <= 1):
        parser.error("Own health fraction must be (0.2,1]; enemy health must be (0,1]")
    if not (
        args.distance + 1 <= args.second_distance <= 10
        and 0 < args.second_enemy_health_fraction <= 1
    ):
        if args.enemy_count == 2:
            parser.error(
                "Second target distance must be at least near distance + 1 and <=10; health in (0,1]"
            )
    if args.enemy_hidden and (
        args.enemy_count != 1
        or args.health_fraction != 1
        or args.enemy_health_fraction != 1
    ):
        parser.error("Hidden diagnostic requires one enemy and full initial health")
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
        **vars(args), mode={"bc": "rule_bc", "ppo": "rule_ppo", "rule": "micro_rule"}[args.policy],
        game_step=DECISION_LOOPS, micro_max_units=1
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
        with recover_completed_game(telemetry, expected_players=2):
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
