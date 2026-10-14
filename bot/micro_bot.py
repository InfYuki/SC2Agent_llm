"""P3 opt-in expert collection, with the existing frozen rule strategy."""
import time

from sc2.ids.unit_typeid import UnitTypeId

from bot.micro import Action, action_target, context, expert, repeated_order
from bot.micro_data import Recorder
from bot.rule_bot import RuleBot


class MicroRuleBot(RuleBot):
    def __init__(self, options, telemetry):
        super().__init__(options, telemetry)
        self.recorder = Recorder(telemetry.output, options.seed)
        self.controlled = set()
        self._authorized_tag = None
        self._micro_disabled = False
        self._released_at = {}

    def play_step(self, iteration):
        self.recorder.feedback(self.state)
        for tag in set(self.recorder.pending) & self.state.dead_units:
            self.recorder.finish(
                tag, int(self.state.game_loop), terminated=True, reason="unit_death"
            )
            self.controlled.discard(tag)
        super().play_step(iteration)

    def do(self, action, *args, **kwargs):
        # Ares macro still owns workers/buildings. Reject independent Marine
        # commands, including behaviors that execute after play_step.
        tag = action.unit.tag
        if action.unit.type_id == UnitTypeId.MARINE and tag != self._authorized_tag:
            self.telemetry.counts["external_marine_commands_blocked"] += 1
            self.telemetry.event(
                "micro_external_command_blocked",
                unit_tag=tag,
                game_loop=int(self.state.game_loop),
            )
            return False
        return super().do(action, *args, **kwargs)

    async def _give_units_same_order(self, order, unit_tags, target=None):
        marines = {unit.tag for unit in self.units(UnitTypeId.MARINE)}
        allowed = set(unit_tags) - marines
        self.telemetry.counts["external_marine_commands_blocked"] += len(
            set(unit_tags) - allowed
        )
        if allowed:
            return await super()._give_units_same_order(order, allowed, target)

    def issue_rule_order(self, unit, state, target, frame):
        self._authorized_tag = unit.tag
        try:
            super().issue_rule_order(unit, state, target, frame)
        finally:
            self._authorized_tag = None

    def _combat(self, frame):
        # Base exits early with an empty army: finish deaths before that exit.
        alive = {unit.tag for unit in self.units(UnitTypeId.MARINE)}
        dead = self.state.dead_units
        for tag in set(self.recorder.pending) - alive:
            self.recorder.finish(
                tag,
                frame,
                terminated=tag in dead,
                truncated=tag not in dead,
                reason="unit_death" if tag in dead else "unit_missing",
            )
            self.controlled.discard(tag)
        super()._combat(frame)

    def issue_combat_orders(self, army, state, target, frame):
        started = time.perf_counter()
        contexts = {}
        try:
            if not self._micro_disabled:
                contexts = {
                    unit.tag: context(self, unit, army, target) for unit in army
                }
            eligible = {
                unit.tag
                for unit in army
                if unit.tag in contexts
                and contexts[unit.tag].supported
                and unit.health_percentage > 0.2
                and frame - self._released_at.get(unit.tag, -100) >= 16
                and state in {"attack", "defend"}
            }
        except Exception as exc:
            # Fail closed for this match; never partly continue an invalid policy.
            self._micro_disabled = True
            eligible = set()
            self.telemetry.event(
                "micro_fallback", reason=type(exc).__name__, game_loop=frame
            )
        candidates = sorted(eligible, key=lambda tag: (tag not in self.controlled, tag))
        selected = set(candidates[: self.options.micro_max_units])
        for tag in set(self.recorder.pending):
            ctx = contexts.get(tag)
            remains = tag in selected
            reason = (
                None
                if remains
                else "strategy_retreat"
                if state in {"retreat", "rally"}
                else "control_released"
            )
            self.recorder.finish(tag, frame, ctx, truncated=not remains, reason=reason)
        for tag in selected ^ self.controlled:
            if tag not in selected:
                self._released_at[tag] = frame
            self.telemetry.event(
                "micro_ownership",
                unit_tag=tag,
                game_loop=frame,
                owner="micro_rule" if tag in selected else "rule_combat",
            )
            self._last_order.pop(tag, None)
        self.controlled = selected
        self.arbiter.begin_step(
            {
                unit.tag: "micro_rule" if unit.tag in selected else "rule_combat"
                for unit in army
            }
        )
        for unit in army:
            if unit.tag not in selected:
                # Low health safety exit is local rules, outside the training task.
                fallback_state, fallback_target = state, target
                if unit.health_percentage <= 0.2:
                    fallback_state, fallback_target = "retreat", self.start_location
                self.issue_rule_order(unit, fallback_state, fallback_target, frame)
                continue
            ctx = contexts[unit.tag]
            try:
                requested = expert(unit, ctx)
                self._execute_micro(unit, ctx, requested, army, target, frame)
            except Exception as exc:
                self._micro_disabled = True
                self.telemetry.event(
                    "micro_fallback",
                    unit_tag=unit.tag,
                    reason=type(exc).__name__,
                    game_loop=frame,
                )
                # A reserved/partially queued command must never be followed by a
                # competing fallback command in the same frame. Keep its order;
                # return all ownership to rule control next decision.
                self.recorder.finish(
                    unit.tag, frame, truncated=True, reason="policy_exception"
                )
                self.telemetry.counts["micro_policy_errors"] += 1
        self.telemetry.counts["micro_decision_steps"] += 1
        self.telemetry.counts["micro_owned_decisions"] += len(selected)
        self.telemetry.event(
            "micro_timing",
            game_loop=frame,
            controlled=len(selected),
            elapsed_seconds=time.perf_counter() - started,
        )

    def _execute_micro(self, unit, ctx, requested, army, goal, frame):
        # Rebuild using the same observation/target/path rules at execution time.
        fresh = context(self, unit, army, goal)
        action = requested if fresh.mask[requested] and fresh.supported else Action.HOLD
        target = action_target(fresh, action)
        result = "hold" if action == Action.HOLD else "queued"
        ability = None
        if not self.arbiter.allow(unit.tag, "micro_rule"):
            action, result = Action.HOLD, "arbiter_rejected"
        elif action != Action.HOLD and repeated_order(unit, action, target):
            action, result = Action.HOLD, "order_preserved"
        elif action != Action.HOLD:
            before = len(self.actions)
            self._authorized_tag = unit.tag
            try:
                accepted = (
                    unit.attack(target)
                    if action in (Action.NEAREST, Action.WEAKEST)
                    else unit.move(target)
                )
            finally:
                self._authorized_tag = None
            if accepted and len(self.actions) > before:
                ability = self.actions[-1].ability.value
            else:
                action, result = Action.HOLD, "local_rejected"
        self.recorder.begin(
            unit.tag, frame, ctx, requested, action, result, target, ability
        )
        self.telemetry.counts["micro_action_" + requested.name.lower()] += 1
        self.telemetry.event(
            "micro_command",
            unit_tag=unit.tag,
            owner="micro_rule",
            game_loop=frame,
            requested_action=int(requested),
            executed_action=int(action),
            target_tag=getattr(target, "tag", None),
            command_result=result,
        )

    def close_micro(self, reason=None):
        frame = int(self.state.game_loop) if hasattr(self, "state") else 0
        self.recorder.close(frame, reason or self.telemetry.stop_reason or "match_end")

    async def on_end(self, result):
        self.close_micro()
        await super().on_end(result)
