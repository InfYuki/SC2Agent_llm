"""Pure strategic contract and lifecycle. No SC2 or networking dependencies."""
from dataclasses import dataclass
import json


class PlanError(ValueError):
    pass


def exact(value, keys):
    if type(value) is not dict or set(value) != set(keys.split()):
        raise PlanError("fields")


def integer(value, low, high):
    if type(value) is not int or not low <= value <= high:
        raise PlanError("integer_range")
    return value


@dataclass(frozen=True)
class Strategy:
    request_id: str
    snapshot_seq: int
    stance: str
    worker_target: int
    base_target: int
    task: str
    target_id: str
    min_army_supply: int
    reason_summary: str
    production_profile: str = "marine_tank_medivac"

    @property
    def intent(self):
        return (
            self.stance,
            self.worker_target,
            self.base_target,
            self.task,
            self.target_id,
            self.min_army_supply,
            self.production_profile,
        )


def parse_plan(content, request_id, snapshot_seq):
    def pairs(items):
        result = {}
        for key, value in items:
            if key in result:
                raise PlanError("duplicate_key")
            result[key] = value
        return result

    try:
        value = json.loads(
            content,
            object_pairs_hook=pairs,
            parse_constant=lambda _: (_ for _ in ()).throw(PlanError("nonfinite")),
        )
    except (ValueError, TypeError, RecursionError):
        raise PlanError("json") from None
    exact(
        value,
        "schema_version request_id snapshot_seq stance economy production_profile research_priority squad_tasks attack_gate reason_summary",
    )
    if value["schema_version"] != "strategy-v1" or value["request_id"] != request_id:
        raise PlanError("identity")
    if integer(value["snapshot_seq"], 1, 10000000) != snapshot_seq:
        raise PlanError("snapshot")
    if value["stance"] not in ("develop", "defend_then_expand", "pressure"):
        raise PlanError("stance")
    if (
        type(value["production_profile"]) is not str
        or value["production_profile"] not in {"marine_basic", "marine_tank_medivac"}
        or value["research_priority"] != []
    ):
        raise PlanError("unsupported_tech")
    economy = value["economy"]
    exact(economy, "worker_target base_target")
    workers = integer(economy["worker_target"], 16, 80)
    bases = integer(economy["base_target"], 1, 4)
    tasks = value["squad_tasks"]
    if type(tasks) is not list or len(tasks) != 1:
        raise PlanError("squad_count")
    task = tasks[0]
    exact(task, "squad_id task target_id")
    targets = {
        "attack": {"enemy_main"},
        "defend": {"own_main", "own_natural"},
        "rally": {"own_main", "own_natural"},
        "retreat": {"own_main", "own_natural"},
    }
    if (
        task["squad_id"] != "main"
        or type(task["task"]) is not str
        or task["task"] not in targets
    ):
        raise PlanError("task")
    if (
        type(task["target_id"]) is not str
        or task["target_id"] not in targets[task["task"]]
    ):
        raise PlanError("target")
    exact(value["attack_gate"], "min_army_supply")
    gate = integer(value["attack_gate"]["min_army_supply"], 6, 60)
    reason = value["reason_summary"]
    if type(reason) is not str or len(reason) > 160:
        raise PlanError("reason")
    return Strategy(
        request_id,
        snapshot_seq,
        value["stance"],
        workers,
        bases,
        task["task"],
        task["target_id"],
        gate,
        reason,
        value["production_profile"],
    )


class Director:
    """Commitment delays changes; freshness always wins over commitment."""

    def __init__(self, ttl=45.0, commitment=30.0):
        self.ttl, self.commitment = ttl, commitment
        self.active = None
        self.pending = None
        self.committed_at = -1e9
        self.source_time = -1e9

    def offer(self, plan, captured_at, now):
        if now < captured_at or now - captured_at > self.ttl:
            return "expired"
        self.current(now)
        if self.active and self.active.intent == plan.intent:
            self.active, self.source_time = plan, captured_at
            self.pending = None
            return "renewed"
        if self.active and now - self.committed_at < self.commitment:
            self.pending = (plan, captured_at)
            return "pending"
        self.active, self.source_time, self.committed_at = plan, captured_at, now
        self.pending = None
        return "active"

    def current(self, now):
        if self.active and now - self.source_time > self.ttl:
            self.active = None
        if self.pending:
            plan, captured = self.pending
            if now - captured > self.ttl:
                self.pending = None
            elif self.active is None or now - self.committed_at >= self.commitment:
                self.active, self.source_time, self.committed_at = plan, captured, now
                self.pending = None
        return self.active


def combat_goal(plan, emergency, army_supply):
    """None delegates to local rules, including emergency defense."""
    if emergency or plan is None:
        return None
    if plan.task == "attack" and army_supply < plan.min_army_supply:
        return "rally", "own_natural"
    return plan.task, plan.target_id
