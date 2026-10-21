"""Gymnasium adapter for the real, separately hosted single-Marine bridge."""
import gymnasium as gym
import numpy as np

from envs.micro_ipc import HOLD_MASK
from envs.sc2_micro_env import SC2MicroEnv, normalize_curriculum


class RolloutDiscardError(RuntimeError):
    """Abort collection before an invalid transition reaches the rollout buffer."""

    def __init__(self, info):
        self.info = dict(info)
        super().__init__("SC2 rollout discarded: " + str(info.get("reason", "invalid transition")))


class GymSC2MicroEnv(gym.Env):
    metadata = {"render_modes": []}

    def __init__(self, *, bridge=None, curriculum=None, **bridge_kwargs):
        super().__init__()
        if bridge is not None and curriculum is not None:
            raise ValueError("Curriculum requires owned bridges")
        self.curriculum = normalize_curriculum(curriculum) if curriculum is not None else None
        self._bridge_kwargs = bridge_kwargs
        self._episode_index = -1
        self.bridge = bridge if bridge is not None else SC2MicroEnv(**bridge_kwargs)
        self.task = getattr(self.bridge, "task", None)
        self.observation_space = gym.spaces.Box(-1.0, 1.0, (16,), dtype=np.float32)
        self.action_space = gym.spaces.Discrete(5)
        self._absorbing = False

    def _reject_invalid(self, info):
        if info.get("system_failure") or info.get("rollout_discard"):
            self.close()
            raise RolloutDiscardError(info)

    def _observation(self, obs):
        result = np.asarray(obs, dtype=np.float32)
        if not self.observation_space.contains(result):
            self.close()
            raise RolloutDiscardError({"reason": "invalid_gym_observation", "rollout_discard": True})
        return result

    def reset(self, *, seed=None, options=None):
        super().reset(seed=seed)
        episode_seed = int(seed) if seed is not None else int(self.np_random.integers(0, 2**31))
        self._episode_index += 1
        if self.curriculum is not None:
            self.bridge.close()
            self._curriculum_index = self._episode_index % len(self.curriculum["tasks"])
            task = self.curriculum["tasks"][self._curriculum_index]
            kwargs = dict(self._bridge_kwargs)
            kwargs.update({key: task[key] for key in
                ("scenario", "distance", "max_game_seconds", "map_name", "enemy_health_fraction")})
            kwargs["own_health_fraction"] = task["health_fraction"]
            kwargs["enemy_count"] = task["enemy_count"]
            for key in ("second_distance", "second_enemy_health_fraction"):
                kwargs[key] = task.get(key)
            self.bridge = SC2MicroEnv(**kwargs)
            self.task = self.bridge.task
        self._absorbing = False
        obs, info = self.bridge.reset(seed=episode_seed, options=options)
        self._reject_invalid(info)
        return self._observation(obs), self._episode_info(dict(info, scenario_seed=episode_seed))

    def _episode_info(self, info):
        if self.curriculum is not None:
            info.update(curriculum_index=self._curriculum_index, episode_index=self._episode_index)
        return info

    def action_masks(self):
        return np.asarray(HOLD_MASK if self._absorbing else self.bridge.action_masks(), dtype=np.bool_)

    def step(self, action):
        obs, reward, terminated, truncated, info = self.bridge.step(action)
        self._reject_invalid(info)
        info = self._episode_info(dict(info))
        if obs is None:
            if not terminated:
                self.close()
                raise RolloutDiscardError(dict(info, reason="missing_nonterminal_observation", rollout_discard=True))
            # No value bootstrap at a true terminal; this is a synthetic dead slot.
            self._absorbing = True
            obs = np.zeros(16, dtype=np.float32)
            info.update(absorbing_observation=True, observation_source="absorbing_terminal",
                        action_mask=HOLD_MASK, next_observation_valid=False)
        return self._observation(obs), float(reward), bool(terminated), bool(truncated), info

    def close(self):
        self.bridge.close()
