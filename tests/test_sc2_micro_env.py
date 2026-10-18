"""Small contract checks only; these do not constitute real SC2 validation."""
import unittest
from envs.micro_ipc import HOLD_MASK, message, validate_state
from envs.sc2_micro_env import SC2MicroEnv


class MicroEnvContractTests(unittest.TestCase):
    def test_stale_frame_and_episode_are_rejected(self):
        packet = message("transition", "episode", 1, 16, obs=[0.0] * 16,
                         mask=list(HOLD_MASK), reward=0.0,
                         terminated=False, truncated=False, info={})
        validate_state(packet, episode_id="episode", decision_id=1,
                       kind="transition", previous_frame=8)
        for kwargs in ({"episode_id": "old", "previous_frame": 8},
                       {"episode_id": "episode", "previous_frame": 0}):
            with self.assertRaises(ValueError):
                validate_state(packet, decision_id=1, kind="transition", **kwargs)

    def test_failure_discards_rollout_without_fabricated_observation(self):
        env = SC2MicroEnv()
        env.episode_id = "episode"
        env.output_dir = "not-started"
        env._done = False
        env._state = message("ready", "episode", 0, 8, obs=[0.0] * 16,
                             mask=list(HOLD_MASK), reward=0.0,
                             terminated=False, truncated=False, info={})
        class BrokenConnection:
            def send(self, packet):
                raise EOFError("worker disconnected")
            def close(self):
                pass
        env._connection = BrokenConnection()
        obs, reward, terminated, truncated, info = env.step(4)
        self.assertIsNone(obs)
        self.assertEqual(reward, 0)
        self.assertFalse(terminated)
        self.assertTrue(truncated)
        self.assertTrue(info["rollout_discard"])
        with self.assertRaises(RuntimeError):
            env.step(4)


if __name__ == "__main__":
    unittest.main()
