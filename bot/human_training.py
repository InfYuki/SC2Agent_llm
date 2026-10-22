"""Fresh fixed-policy rollout recording for explicit human training matches."""
import hashlib
import json
import math
from pathlib import Path

import numpy as np

from bot.micro import effective_health, visible
from bot.micro_data import Recorder


class HumanRecorder(Recorder):
    def __init__(self, bot, policy, checkpoint):
        super().__init__(bot.telemetry.output, bot.options.seed, policy_version=policy.policy_version, bc_labels=False)
        self.bot, self.policy = bot, policy
        self.rng = np.random.default_rng(bot.options.seed)
        self.samples, self.health, self.indices = {}, {}, {}
        self.rollout = (self.output / "human_ppo_rollout.jsonl").open("x", encoding="utf-8")
        checkpoint = Path(checkpoint).resolve()
        checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
        if checkpoint_hash != policy.metadata["producer"]["source_checkpoint_sha256"]:
            raise ValueError("Human PPO actor does not match the training checkpoint")
        bot.telemetry.write_json("human_training.json", dict(
            format="human-match-training-v1", checkpoint=str(checkpoint),
            actor=str(Path(bot.options.ppo_model).resolve()),
            checkpoint_sha256=checkpoint_hash, actor_weights_sha256=policy.metadata["weights_sha256"],
            sampling="stochastic-masked-categorical-v1", enemy_race="Terran",
            reward_version="visible-tracked-hp-v1",
            reward_description="(tracked visible enemy HP loss - own HP loss)/45 + 0.5 confirmed enemy death - own death; hidden enemies never treated as killed",
            decision_timing="actual observed game loops; realtime may skip frames",
        ))

    def sample(self, tag, ctx):
        probabilities = self.policy.probabilities(ctx.obs, ctx.mask).astype(np.float64)
        probabilities /= probabilities.sum()
        action = int(self.rng.choice(5, p=probabilities))
        self.samples[tag] = (action, float(math.log(probabilities[action])))
        return action

    def begin(self, tag, frame, ctx, requested, executed, result, target=None, ability=None):
        super().begin(tag, frame, ctx, requested, executed, result, target, ability)
        sample = self.samples.pop(tag, None)
        if sample is None or sample[0] != int(requested) or result in {"arbiter_rejected", "local_rejected"}:
            self.pending[tag]["human_sample_valid"] = False
            return
        # Repeated orders remain a valid sampled action: preservation is the
        # environment's execution semantics, not a new behavior-policy action.
        self.pending[tag].update(human_sample_valid=True, old_log_prob=sample[1])
        unit = self.bot.units.find_by_tag(tag)
        self.health[tag] = (effective_health(unit), {e.tag: effective_health(e) for e in ctx.enemies})

    def finish(self, tag, frame, ctx=None, *, terminated=False, truncated=False, reason=None):
        row = self.pending.get(tag)
        if row:
            trajectory = row["engagement_id"]
            hp = self.health.pop(tag, None)
            dead = self.bot.state.dead_units if hasattr(self.bot, "state") else set()
            unit = self.bot.units.find_by_tag(tag)
            own_dead = tag in dead
            valid = (row.get("human_sample_valid") and hp is not None and ctx is not None
                     and frame > row["game_loop"] and not own_dead)
            # A confirmed unit death needs no bootstrap observation.
            if row.get("human_sample_valid") and hp is not None and own_dead:
                valid = frame > row["game_loop"]
                terminated, truncated = True, False
            if valid:
                own_hp = 0 if own_dead else effective_health(unit) if unit else hp[0]
                current = {e.tag: e for e in self.bot.enemy_units if visible(e)}
                damage, kills = 0.0, 0
                for enemy_tag, previous in hp[1].items():
                    if enemy_tag in dead:
                        damage += previous
                        kills += 1
                    elif enemy_tag in current:
                        damage += max(0.0, previous - effective_health(current[enemy_tag]))
                reward = (damage - max(0.0, hp[0] - own_hp)) / 45 + 0.5 * kills - int(own_dead)
                index = self.indices.get(trajectory, 0)
                sample = dict(trajectory_id=trajectory, step=index, obs=row["obs"], mask=row["mask"],
                              action=row["requested_action"], old_log_prob=row["old_log_prob"], reward=reward,
                              next_obs=ctx.obs if ctx else [0.0] * 16,
                              next_mask=ctx.mask if ctx else [False] * 4 + [True],
                              terminated=terminated, truncated=truncated,
                              game_loop=row["game_loop"], next_game_loop=frame,
                              executed_action=row["executed_action"], command_result=row["command_result"],
                              end_reason=reason)
                self.rollout.write(json.dumps(sample, allow_nan=False) + "\n")
                self.rollout.flush()
                self.indices[trajectory] = index + 1
                self.bot.telemetry.counts["human_ppo_samples"] += 1
            else:
                self.bot.telemetry.counts["human_ppo_discarded_endpoints"] += 1
                # Never bridge an unobserved/invalid interval in a trajectory.
                self.episodes.pop(tag, None)
        super().finish(tag, frame, ctx, terminated=terminated, truncated=truncated, reason=reason)

    def close(self, frame, reason):
        if self.closed:
            return
        super().close(frame, reason)
        self.rollout.close()
