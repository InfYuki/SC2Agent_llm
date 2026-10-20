"""Opt-in real SC2 action bridge; never produces expert training labels."""
import asyncio
import json

from sc2.ids.unit_typeid import UnitTypeId

from bot.micro import Action, DECISION_LOOPS, context, effective_health
from envs.micro_ipc import PROTOCOL
from tools.run_micro_scenario import ScenarioBot

REWARD_VERSION = "effective-hp-delta-45-terminal-1-v1"


class MicroEnvBot(ScenarioBot):
    def __init__(self, options, telemetry, connection, episode_id, action_timeout=15):
        super().__init__(options, telemetry)
        self.connection = connection
        self.episode_id = episode_id
        self.action_timeout = action_timeout
        self.limit_seconds = options.max_game_seconds
        # The environment owns truncation, after observing the actual boundary.
        options.max_game_seconds = 1e6
        self.recorder.bc_labels = False
        self.recorder.policy_version = "external-training-action-v1"
        self._decision_id = 0
        self._previous = None
        self._pending_action = None
        self._env_finished = False
        self._budget_close_identity = None
        self._rollout = (telemetry.output / "rl_rollout.jsonl").open("x", encoding="utf-8")

    def play_step(self, iteration):
        # ScenarioBot's initialization still runs, but its expert/safety policy
        # must not act while the environment is waiting for its caller.
        self.recorder.feedback(self.state)

    def _message(self, kind, **fields):
        return dict(protocol=PROTOCOL, type=kind, episode_id=self.episode_id,
                    decision_id=self._decision_id, unit_slot=0,
                    frame=int(self.state.game_loop), **fields)

    def _receive_action(self):
        if not self.connection.poll(self.action_timeout):
            raise TimeoutError("action_timeout")
        message = self.connection.recv()
        kind = message.get("type") if isinstance(message, dict) else None
        expected = self._message(kind if kind == "close" else "action")
        if not isinstance(message, dict) or any(message.get(k) != v for k, v in expected.items()):
            raise ValueError("stale_or_invalid_action_identity")
        if kind == "close":
            self._budget_close_identity = expected
            return None
        action = message.get("action")
        if type(action) is not int or action not in range(5):
            raise ValueError("invalid_action")
        return Action(action)

    async def on_step(self, iteration):
        if self._env_finished:
            return
        await super().on_step(iteration)
        if not self._health_ready:
            return
        frame = int(self.state.game_loop)
        army = self.units(UnitTypeId.MARINE)
        marine = army.find_by_tag(self._scene_tag)
        self._dead_enemy_tags.update(self._enemy_tags & self.state.dead_units)
        dead = self._scene_tag in self.state.dead_units
        won = bool(self._enemy_tags) and self._enemy_tags <= self._dead_enemy_tags
        enemies = {e.tag: e for e in self.enemy_units if e.is_visible and not e.is_memory and not e.is_snapshot}
        unseen = bool((self._enemy_tags - self._dead_enemy_tags) - enemies.keys())
        reason = ("marine_dead" if dead else "enemy_dead" if won else
                  "friendly_missing" if marine is None else "enemy_not_visible" if unseen else
                  "scenario_time_limit" if self.time >= self.limit_seconds else None)
        terminated = dead or won
        truncated = reason is not None and not terminated
        ctx = context(self, marine, army, self.scene_goal) if marine else None
        own_hp = 0.0 if dead else effective_health(marine) if marine else None
        enemy_hp = sum(effective_health(enemies[tag]) for tag in self._enemy_tags - self._dead_enemy_tags) if not unseen else None
        info = dict(reason=reason, next_observation_valid=ctx is not None,
                    task=getattr(self.options, "training_task", None), reward_scale=45.0,
                    observed_enemies=[dict(type_id=enemies[tag].type_id.value,
                                           type_name=enemies[tag].type_id.name,
                                           health=float(enemies[tag].health),
                                           health_max=float(enemies[tag].health_max),
                                           ground_range=float(enemies[tag].ground_range))
                                      for tag in sorted(self._enemy_tags & enemies.keys())],
                    reward_version=REWARD_VERSION, own_effective_hp=own_hp,
                    enemy_effective_hp=enemy_hp, rollout_discard=bool(unseen or (marine is None and not dead)),
                    provenance="real-sc2-external-action", expert_labels=False,
                    decision_game_loops=DECISION_LOOPS, command_conflicts=self.arbiter.conflicts)
        reward = 0.0
        kind = "ready"
        if self._previous is not None:
            kind = "transition"
            previous = self._previous
            elapsed = frame - previous["frame"]
            if elapsed != DECISION_LOOPS:
                raise RuntimeError(f"unexpected_decision_interval:{elapsed}")
            own_loss = previous["own_hp"] - own_hp if own_hp is not None else 0.0
            enemy_loss = previous["enemy_hp"] - enemy_hp if enemy_hp is not None else 0.0
            terminal_reward = float(won) - float(dead)
            reward = (enemy_loss - own_loss) / 45.0 + terminal_reward
            row = dict(self.recorder.pending.get(self._scene_tag, {}))
            info.update(previous_frame=previous["frame"], previous_decision_id=self._decision_id,
                        actual_game_loops=elapsed, own_hp_loss=own_loss, enemy_hp_loss=enemy_loss,
                        terminal_reward=terminal_reward, reward_scale=45.0,
                        requested_action=row.get("requested_action"),
                        executed_action=row.get("executed_action"), command_result=row.get("command_result"),
                        confirmed_game_loop=row.get("confirmed_game_loop"))
            self.recorder.finish(self._scene_tag, frame, ctx, terminated=terminated,
                                 truncated=truncated, reason=reason)
            self._decision_id += 1
        if self._previous is None and reason:
            raise RuntimeError("scene_ended_before_first_decision:" + reason)
        message = self._message(kind, obs=list(ctx.obs) if ctx else None,
                                mask=list(ctx.mask) if ctx else [False, False, False, False, True],
                                reward=reward, terminated=terminated, truncated=truncated, info=info)
        if kind == "transition":
            self._rollout.write(json.dumps(dict(message, source_obs=self._previous["obs"],
                                                source_mask=self._previous["mask"]), allow_nan=False) + "\n")
            self._rollout.flush()
        self.connection.send(message)
        if reason:
            self._env_finished = True
            self._finish_scene(reason, terminated)
            self.telemetry.stop_reason = "game_time_limit"
            await self.client.leave()
            return
        requested = await asyncio.to_thread(self._receive_action)
        if requested is None:
            self._env_finished = True
            self.telemetry.stop_reason = "training_budget_close"
            self._finish_scene("training_budget_close", False)
            await self.client.leave()
            return
        if not ctx.mask[requested]:
            raise ValueError("masked_action")
        self.arbiter.begin_step({marine.tag: "micro_rule"})
        self._execute_micro(marine, ctx, requested, army, self.scene_goal, frame)
        self._previous = dict(frame=frame, own_hp=own_hp, enemy_hp=enemy_hp,
                              obs=list(ctx.obs), mask=list(ctx.mask))

    def close_micro(self, reason=None):
        super().close_micro(reason)
        if not self._rollout.closed:
            self._rollout.close()
