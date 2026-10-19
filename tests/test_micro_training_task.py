"""One targeted task-propagation/resume check; no SC2 process is started."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from envs.sc2_micro_env import SC2MicroEnv, training_task
from envs.gym_sc2_micro_env import GymSC2MicroEnv
from tools.train_micro_ppo import resolve_training_task


class TrainingTaskTest(unittest.TestCase):
    def test_task_propagation_and_resume_contract(self):
        legacy = training_task()
        self.assertEqual((legacy["scenario"], legacy["distance"], legacy["max_game_seconds"]),
                         ("marine-vs-marine", 6.0, 8.0))
        self.assertEqual(resolve_training_task({}), legacy)
        task = training_task(scenario="marine-vs-zergling", max_game_seconds=12)
        self.assertEqual(resolve_training_task({"task": task}), task)
        self.assertEqual(resolve_training_task({"task": task}, scenario="marine-vs-zergling"), task)
        for metadata, override in (({}, {"scenario": "marine-vs-zergling"}),
                                   ({"task": task}, {"scenario": "marine-vs-marine"}),
                                   ({"task": task}, {"distance": 3}),
                                   ({"task": task}, {"max_game_seconds": 8}),
                                   ({"task": task}, {"map_name": "Babylon LE"})):
            with self.assertRaisesRegex(ValueError, "conflicting override"):
                resolve_training_task(metadata, **override)
        with self.assertRaisesRegex(ValueError, "task metadata"):
            resolve_training_task({"task": dict(task, reward_scale=35)})
        for kwargs in ({"distance": float("nan")}, {"max_game_seconds": float("inf")},
                       {"scenario": "unsupported"}):
            with self.assertRaises(ValueError):
                training_task(**kwargs)
        with tempfile.TemporaryDirectory() as directory:
            gym = GymSC2MicroEnv(scenario="marine-vs-zergling", distance=6,
                                max_game_seconds=12, output_root=Path(directory))
            self.assertEqual(gym.task, task)
            # Intercept creation before any worker or game can launch.
            with patch("envs.sc2_micro_env.subprocess.Popen", side_effect=RuntimeError("intercept")) as launch:
                with self.assertRaisesRegex(RuntimeError, "intercept"):
                    gym.reset(seed=42)
            command = launch.call_args.args[0]
            for flag, expected in (("--scenario", "marine-vs-zergling"),
                                   ("--distance", "6.0"), ("--max-game-seconds", "12.0")):
                self.assertEqual(command[command.index(flag) + 1], expected)
            bridge = gym.bridge
            packet = dict(info=dict(task=task, enemy_effective_hp=35.0), decision_id=0,
                          frame=17, mask=[True] * 5)
            info = bridge._info(packet)
            self.assertEqual(info["task"], task)
            self.assertEqual(info["enemy_effective_hp"], 35.0)
            with self.assertRaisesRegex(ValueError, "Worker task"):
                bridge._info(dict(packet, info=dict(task=legacy)))
            gym.close()


if __name__ == "__main__":
    unittest.main()
