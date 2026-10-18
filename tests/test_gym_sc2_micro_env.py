"""Small adapter contract checks; no game or runtime dependency changes."""
import unittest
import importlib.util

import numpy as np

from envs.micro_ipc import HOLD_MASK

HAS_GYMNASIUM = importlib.util.find_spec("gymnasium") is not None
if HAS_GYMNASIUM:
    from envs.gym_sc2_micro_env import GymSC2MicroEnv, RolloutDiscardError


class FakeBridge:
    def __init__(self, result):
        self.result = result
        self.closed = False

    def reset(self, **kwargs):
        return [0.5] * 16, {}

    def action_masks(self):
        return HOLD_MASK

    def step(self, action):
        return self.result

    def close(self):
        self.closed = True


@unittest.skipUnless(HAS_GYMNASIUM, "Gymnasium is installed only in the separate training environment")
class GymAdapterTests(unittest.TestCase):
    def test_terminal_absorbing_and_time_limit_bootstrap_observation(self):
        bridge = FakeBridge((None, -1.0, True, False, {}))
        env = GymSC2MicroEnv(bridge=bridge)
        obs, _ = env.reset(seed=42)
        self.assertEqual(obs.dtype, np.float32)
        obs, _, terminated, truncated, info = env.step(4)
        self.assertTrue(terminated)
        self.assertFalse(truncated)
        self.assertTrue(info["absorbing_observation"])
        np.testing.assert_array_equal(obs, np.zeros(16))
        np.testing.assert_array_equal(env.action_masks(), HOLD_MASK)
        bridge.result = ([0.25] * 16, 0.0, False, True, {})
        env.reset(seed=43)
        obs, _, _, truncated, info = env.step(4)
        self.assertTrue(truncated)
        np.testing.assert_array_equal(obs, np.full(16, 0.25))
        self.assertNotIn("absorbing_observation", info)

    def test_system_failure_and_discard_never_return_a_transition(self):
        for flag in ("system_failure", "rollout_discard"):
            bridge = FakeBridge((None, 0.0, False, True, {flag: True, "reason": "broken"}))
            env = GymSC2MicroEnv(bridge=bridge)
            env.reset(seed=42)
            with self.assertRaises(RolloutDiscardError) as caught:
                env.step(4)
            self.assertEqual(caught.exception.info["reason"], "broken")
            self.assertTrue(bridge.closed)
