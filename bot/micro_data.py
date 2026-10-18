"""Frame-aligned demonstration records; unconfirmed commands are not BC labels."""
from collections import Counter
import hashlib
import json
from sc2.ids.ability_id import AbilityId

from bot.micro import (
    ACTION_VERSION,
    DECISION_LOOPS,
    EXPERT_VERSION,
    FEATURE_VERSION,
    SCENARIO_VERSION,
)


class Recorder:
    def __init__(self, output, seed, scenario=SCENARIO_VERSION, *,
                 policy_version=EXPERT_VERSION, bc_labels=True):
        self.output = output
        self.match_id = output.name
        # All units and engagements in a match always share the split.
        bucket = int(hashlib.sha256(self.match_id.encode()).hexdigest()[:8], 16) % 10
        self.split = "train" if bucket < 8 else "validation" if bucket == 8 else "test"
        self.seed = seed
        self.scenario = scenario
        self.policy_version = policy_version
        self.bc_labels = bc_labels
        self.pending = {}
        self.episodes = {}
        self.sequence = Counter()
        self.counts = Counter()
        self.file = (output / "micro_transitions.jsonl").open("x", encoding="utf-8")
        self.closed = False

    def start(self, tag, frame):
        if tag not in self.episodes:
            self.sequence[tag] += 1
            self.episodes[tag] = f"{self.match_id}:{tag}:{self.sequence[tag]}:{frame}"

    def begin(
        self, tag, frame, ctx, requested, executed, result, target=None, ability=None
    ):
        if tag in self.pending:
            raise RuntimeError("Pending transition was not finalized")
        self.start(tag, frame)
        self.pending[tag] = dict(
            match_id=self.match_id,
            engagement_id=self.episodes[tag],
            unit_tag=tag,
            game_loop=frame,
            obs=ctx.obs,
            mask=ctx.mask,
            requested_action=int(requested),
            executed_action=int(executed),
            command_result=result,
            target_tag=getattr(target, "tag", None),
            target_position=list(target)
            if target is not None and hasattr(target, "x")
            else None,
            ability_id=ability,
            confirmed_game_loop=None,
            seed=self.seed,
            split=self.split,
            versions=dict(
                feature=FEATURE_VERSION,
                action=ACTION_VERSION,
                expert=EXPERT_VERSION if self.bc_labels else None,
                policy=self.policy_version,
                scenario=self.scenario,
                decision_game_loops=DECISION_LOOPS,
            ),
        )

    def feedback(self, state):
        for error in state.action_errors:
            row = self.pending.get(error.unit_tag)
            if row and row["ability_id"] is not None:
                row["command_result"] = "engine_rejected"
                row["engine_error"] = error.result
        for command in state.actions_unit_commands:
            for tag in command.unit_tags:
                row = self.pending.get(tag)
                if (
                    not row
                    or row["command_result"] != "queued"
                    or command.game_loop < row["game_loop"]
                ):
                    continue
                # Attack and move may be redirected by the engine to specific IDs.
                ids = {row["ability_id"]}
                ids.update(
                    {AbilityId.ATTACK_ATTACK.value, AbilityId.ATTACK.value}
                    if row["executed_action"] in (0, 1)
                    else {AbilityId.MOVE_MOVE.value, AbilityId.MOVE.value}
                )
                if command.ability_id not in ids:
                    continue
                if (
                    row["target_tag"] is not None
                    and command.target_unit_tag != row["target_tag"]
                ):
                    continue
                point = command.target_world_space_pos
                expected = row["target_position"]
                if expected is not None and (
                    point is None
                    or abs(point.x - expected[0]) > 0.1
                    or abs(point.y - expected[1]) > 0.1
                ):
                    continue
                row["command_result"] = "engine_confirmed"
                row["confirmed_game_loop"] = command.game_loop

    def finish(
        self, tag, frame, ctx=None, *, terminated=False, truncated=False, reason=None
    ):
        row = self.pending.pop(tag, None)
        if row:
            if row["command_result"] == "queued":
                row["command_result"] = "engine_unconfirmed"
            row.update(
                next_game_loop=frame,
                actual_game_loops=frame - row["game_loop"],
                next_obs=ctx.obs if ctx else None,
                next_mask=ctx.mask if ctx else None,
                terminated=terminated,
                truncated=truncated,
                end_reason=reason,
                next_observation_valid=ctx is not None,
                reward=None,
                reward_version="not_implemented",
            )
            row["bc_eligible"] = (
                self.bc_labels
                and row["command_result"] in {"engine_confirmed", "hold"}
                and frame - row["game_loop"] == DECISION_LOOPS
                and not truncated
            )
            self.file.write(json.dumps(row, allow_nan=False) + "\n")
            self.file.flush()
            self.counts["transitions"] += 1
            self.counts[row["command_result"]] += 1
            self.counts["bc_eligible"] += int(row["bc_eligible"])
            self.counts["terminated"] += int(terminated)
            self.counts["truncated"] += int(truncated)
        if terminated or truncated:
            self.episodes.pop(tag, None)

    def close(self, frame, reason):
        if self.closed:
            return
        for tag in list(self.pending):
            self.finish(tag, frame, truncated=True, reason=reason)
        self.file.close()
        self.closed = True
        (self.output / "micro_summary.json").write_text(
            json.dumps(
                dict(
                    match_id=self.match_id,
                    seed=self.seed,
                    split=self.split,
                    counters=dict(self.counts),
                    reward="not_implemented",
                    scenario=self.scenario,
                    policy_version=self.policy_version,
                    expert_labels=self.bc_labels,
                ),
                indent=2,
            ),
            encoding="utf-8",
        )
