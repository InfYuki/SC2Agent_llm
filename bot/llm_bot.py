"""Visible-state snapshots and nonblocking strategy adapter around RuleBot."""
from collections import Counter
from dataclasses import asdict
import json
from pathlib import Path
import time
from sc2.ids.unit_typeid import UnitTypeId

from bot.llm_client import Settings, Worker
from bot.rule_bot import RuleBot
from bot.production import PRODUCTION_PROFILES
from bot.strategy import Director, PlanError, combat_goal, parse_plan


class StrategicBot(RuleBot):
    def __init__(self, options, telemetry):
        super().__init__(options, telemetry)
        settings = Settings.load(Path(__file__).resolve().parents[1] / ".env.local")
        self.worker = Worker(settings)
        self.director = Director()
        self._seq = 0
        self._last_snapshot = -100.0
        self._last_query_game = -100.0
        self._last_query_wall = -100.0
        self._retry_at = 0.0
        self._failures = 0
        self._inflight = None
        self._deadline_reported = False
        self._memory = {}
        self._plan = None
        self._source = None
        self._llm_closed = False
        self.stats = Counter()
        self.latencies = []
        self._callbacks_at_request = 0
        self._candidate_id = None
        self._goal_progress = None
        self._human_experience = None
        memory_path = getattr(options, "strategy_memory", None)
        if memory_path and Path(memory_path).is_file():
            experience = json.loads(Path(memory_path).read_text(encoding="utf-8"))
            if experience.get("format") != "human-strategy-memory-v1":
                raise ValueError("Invalid human strategy memory format")
            # Bound prompt growth independently of the persisted history.
            self._human_experience = dict(format=experience["format"],
                lessons=experience.get("lessons", [])[-8:],
                recent_matches=experience.get("recent_matches", [])[-4:])
        telemetry.write_json(
            "llm_config.json",
            dict(
                provider="DeepSeek",
                model=settings.model,
                base_url=settings.base_url,
                mode=options.mode,
                snapshot_game_seconds=1,
                query_game_seconds=15,
                min_query_wall_seconds=5,
                response_deadline_wall_seconds=20,
                connect_timeout=5,
                read_timeout=15,
                max_observation_age_game_seconds=45,
                commitment_game_seconds=30,
                max_calls=options.llm_max_calls,
                max_output_tokens=768,
                thinking="disabled",
            ),
        )

    def snapshot(self):
        visible = [u for u in self.enemy_units if u.is_visible]
        structures = [u for u in self.enemy_structures if u.is_visible]
        for unit in visible + structures:
            self._memory[unit.tag] = dict(
                type=unit.type_id.name,
                last_seen=round(self.time, 2),
                x=round(unit.position.x, 1),
                y=round(unit.position.y, 1),
            )
        # Bounded last-seen history. Never refresh it from hidden/snapshot units.
        self._memory = {
            tag: record
            for tag, record in self._memory.items()
            if self.time - record["last_seen"] <= 120
        }
        memory = sorted(
            self._memory.values(), key=lambda r: r["last_seen"], reverse=True
        )[:40]
        return dict(
            snapshot_seq=self._seq,
            game_seconds=round(self.time, 2),
            minerals=int(self.minerals),
            vespene=int(self.vespene),
            supply=dict(
                used=float(self.supply_used),
                cap=float(self.supply_cap),
                army=float(self.supply_army),
                workers=int(self.supply_workers),
            ),
            own_units=dict(Counter(u.type_id.name for u in self.units)),
            own_structures=dict(Counter(u.type_id.name for u in self.structures)),
            pending=dict(
                marines=int(self.already_pending(self.marine_type)),
                marauders=int(self.already_pending(UnitTypeId.MARAUDER)),
                reapers=int(self.already_pending(UnitTypeId.REAPER)),
                ghosts=int(self.already_pending(UnitTypeId.GHOST)),
                siege_tanks=int(self.already_pending(UnitTypeId.SIEGETANK)),
                medivacs=int(self.already_pending(UnitTypeId.MEDIVAC)),
                bases=int(self.structure_pending(self.base_townhall_type)),
            ),
            enemy_visible=dict(Counter(u.type_id.name for u in visible + structures)),
            enemy_memory=memory,
            local_state=self.strategy_state,
            active_plan=asdict(self.director.active) if self.director.active else None,
            available_targets=["own_main", "own_natural", "enemy_main"],
            ready_bases=len(self.ready_townhalls),
            economy_policy=dict(self.economy_status),
            production_profile=self.production_profile(),
            available_production_profiles=list(PRODUCTION_PROFILES),
            available_research=["stimpack"],
            research_status=self.upgrade_status(),
            base_defense=self.base_defense_status(),
            production_compositions={name: {unit: fraction for unit, fraction, _ in spec}
                                     for name, spec in PRODUCTION_PROFILES.items()},
            base_under_attack=any(
                u.can_attack_ground and u.distance_to(b) < 25
                for u in visible
                for b in self.townhalls
            ),
        )

    def _failure(self, now, category):
        self._failures += 1
        self._retry_at = now + min(60, 5 * 2 ** min(self._failures - 1, 4))
        self.stats["failures"] += 1
        self.telemetry.event(
            "llm_failure",
            category=category,
            retry_in_wall_seconds=self._retry_at - now,
            game_seconds=float(self.time),
        )

    def _poll(self, now):
        result = self.worker.poll()
        if result is not None and self._inflight:
            identity, seq, captured = self._inflight
            late = self._deadline_reported or now - self._last_query_wall > 20
            content = result.pop("content", "")
            self.stats["responses"] += 1
            self.stats["callbacks_while_waiting"] += (
                int(self.telemetry.counts["callbacks"]) - self._callbacks_at_request
            )
            self.latencies.append(
                result.get("latency_seconds", now - self._last_query_wall)
            )
            self.telemetry.event(
                "llm_response",
                request_id=identity,
                snapshot_seq=seq,
                captured_game_seconds=captured,
                game_seconds=float(self.time),
                deadline_exceeded=late,
                **result,
            )
            self._inflight = None
            if late:
                if not self._deadline_reported:
                    self._failure(now, "response_deadline")
                self.stats["late_discarded"] += 1
            elif not result["ok"]:
                self._failure(now, result.get("error", "response"))
            else:
                try:
                    plan = parse_plan(content, identity, seq)
                    status = self.director.offer(plan, captured, float(self.time))
                    self.stats["valid_plans"] += 1
                    self.stats["plan_" + status] += 1
                    self._failures = 0
                    self._retry_at = now
                    self.telemetry.event(
                        "llm_plan",
                        status=status,
                        plan=asdict(plan),
                        captured_game_seconds=captured,
                        game_seconds=float(self.time),
                    )
                except PlanError as error:
                    self.stats["invalid_plans"] += 1
                    self._failure(now, "schema_" + str(error))
        if (
            self._inflight
            and now - self._last_query_wall > 20
            and not self._deadline_reported
        ):
            self._deadline_reported = True
            self.stats["response_deadlines"] += 1
            self._failure(now, "response_deadline")

    def play_step(self, iteration):
        now = time.monotonic()
        self._poll(now)
        candidate = self.director.current(float(self.time))
        identity = candidate.request_id if candidate else None
        if identity != self._candidate_id:
            self.telemetry.event(
                "plan_transition",
                previous=self._candidate_id,
                current=identity,
                status="active" if candidate else "expired",
                game_seconds=float(self.time),
            )
            if self._candidate_id and candidate is None:
                self.stats["expired_active_plans"] += 1
            self._candidate_id = identity
        self._plan = candidate if self.options.mode in {"llm", "llm_ppo"} else None
        source = "llm" if self._plan else "rule"
        if source != self._source:
            self.telemetry.event(
                "strategy_source", source=source, game_seconds=float(self.time)
            )
            self._source = source
        self.stats[source + "_steps"] += 1
        if self.time - self._last_snapshot >= 1:
            self._seq += 1
            self._last_snapshot = float(self.time)
            snapshot = self.snapshot()
            if self._human_experience:
                snapshot["previous_human_match_experience"] = self._human_experience
            self.telemetry.write_json("latest_strategy_snapshot.json", snapshot)
            if (
                self.time - self._last_query_game >= 15
                and now - self._last_query_wall >= 5
                and now >= self._retry_at
                and not self._inflight
                and self.stats["requests"] < self.options.llm_max_calls
            ):
                identity = f"strategy-{self._seq}"
                snapshot["request_id"] = identity
                payload = json.dumps(snapshot, separators=(",", ":"), ensure_ascii=True)
                if self.worker.submit(payload):
                    self._inflight = (identity, self._seq, float(self.time))
                    self._last_query_game, self._last_query_wall = float(self.time), now
                    self._deadline_reported = False
                    self._callbacks_at_request = int(self.telemetry.counts["callbacks"])
                    self.stats["requests"] += 1
                    self.telemetry.event(
                        "llm_request",
                        request_id=identity,
                        snapshot=snapshot,
                        input_characters=len(payload),
                    )
        super().play_step(iteration)
        if self._plan:
            progress = (
                "emergency_defense"
                if self.strategy_state == "defend" and self._plan.task != "defend"
                else "await_army"
                if self._plan.task == "attack"
                and self.supply_army < self._plan.min_army_supply
                else "active",
                self.supply_workers
                >= self.economy_status.get("worker_target", self._plan.worker_target),
                len(self.ready_townhalls) >= self.economy_status.get("base_target", self._plan.base_target),
            )
            if progress != self._goal_progress:
                self.telemetry.event(
                    "goal_progress",
                    request_id=self._plan.request_id,
                    combat=progress[0],
                    workers_satisfied=progress[1],
                    bases_satisfied=progress[2],
                    game_seconds=float(self.time),
                )
                self._goal_progress = progress

    def requested_economic_goals(self):
        if not self._plan:
            return super().requested_economic_goals()
        self.stats["economy_goal_steps"] += 1
        return (
            self._plan.worker_target,
            self._plan.base_target,
        )

    def research_priorities(self):
        return self._plan.research_priority if self._plan else super().research_priorities()

    def production_profile(self):
        return self._plan.production_profile if self._plan else super().production_profile()

    def defense_policy(self):
        return self._plan.base_defense if self._plan else super().defense_policy()

    def orbital_enabled(self):
        return self._plan.orbital_command if self._plan else super().orbital_enabled()

    def strategic_order(self, army):
        goal = combat_goal(self._plan, False, float(self.supply_army))
        if goal is None:
            return None
        task, target_id = goal
        self.stats["combat_goal_steps"] += 1
        if task == "attack":
            return "attack", self.attack_target(army)
        bases = self.ready_townhalls
        target = self.start_location
        if target_id == "own_natural" and bases:
            target = bases.furthest_to(self.start_location).position
        if task == "rally":
            target = target.towards(self.game_info.map_center, 8)
        return task, target

    def close_strategy(self, result=None):
        if self._llm_closed:
            return
        self._llm_closed = True
        self.worker.close()
        self.telemetry.write_json(
            "strategy_summary.json",
            dict(
                mode=self.options.mode,
                counters=dict(self.stats),
                latency_seconds=self.latencies,
                request_inflight_at_exit=bool(self._inflight),
                end_result=str(result) if result is not None else None,
                active_plan=asdict(self.director.active)
                if self.director.active
                else None,
                pending_plan=asdict(self.director.pending[0])
                if self.director.pending
                else None,
            ),
        )

    async def on_end(self, result):
        self.close_strategy(result)
        await super().on_end(result)
