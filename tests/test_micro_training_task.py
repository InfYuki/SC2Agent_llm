"""One targeted task-propagation/resume check; no SC2 process is started."""
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from envs.sc2_micro_env import SC2MicroEnv, training_task
from envs.gym_sc2_micro_env import GymSC2MicroEnv
from tools.train_micro_ppo import resolve_training_task, resolve_task_set


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
        partial = training_task(scenario="marine-vs-zergling", distance=8, max_game_seconds=12,
                                own_health_fraction=0.6, enemy_health_fraction=0.75)
        self.assertEqual((partial["health_fraction"], partial["enemy_health_fraction"]), (0.6, 0.75))
        curriculum = dict(format="marine-micro-curriculum-v1", selection="round-robin",
                          tasks=[task, dict(task, distance=8.0), partial])
        with self.assertRaisesRegex(ValueError, "allow-task-change"):
            resolve_task_set({"task": task}, curriculum=curriculum)
        anchor, frozen, change = resolve_task_set({"task": task}, curriculum=curriculum, allow_task_change=True)
        self.assertEqual(anchor, task)
        self.assertEqual(change["parent_tasks"], [task])
        self.assertEqual(change["new_tasks"], curriculum["tasks"])
        self.assertNotEqual(change["parent_task_set_sha256"], change["new_task_set_sha256"])
        self.assertEqual(resolve_task_set({"task": task, "curriculum": frozen})[:2], (task, frozen))
        with self.assertRaisesRegex(ValueError, "allow-task-change"):
            resolve_task_set({"task": task, "curriculum": frozen}, distance=6)
        for kwargs in ({"distance": float("nan")}, {"max_game_seconds": float("inf")},
                       {"scenario": "unsupported"}, {"own_health_fraction": 0.2},
                       {"enemy_health_fraction": float("nan")}):
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
            # Select the fixed sequence without launching a worker, using the real
            # bridge task contracts and a stub reset only.
            def fake_reset(bridge, **kwargs):
                return [0.0] * 16, dict(task=bridge.task)
            gym = GymSC2MicroEnv(curriculum=curriculum, output_root=Path(directory))
            with patch.object(SC2MicroEnv, "reset", fake_reset):
                for episode_index in range(7):
                    _, info = gym.reset(seed=42)
                    self.assertEqual(info["curriculum_index"], episode_index % 3)
                    self.assertEqual(info["episode_index"], episode_index)
                    self.assertEqual(info["task"], curriculum["tasks"][episode_index % 3])
            gym.close()
            gym = GymSC2MicroEnv(own_health_fraction=0.6, enemy_health_fraction=0.75,
                                output_root=Path(directory))
            with patch("envs.sc2_micro_env.subprocess.Popen", side_effect=RuntimeError("intercept")) as launch:
                with self.assertRaisesRegex(RuntimeError, "intercept"):
                    gym.reset(seed=42)
            command = launch.call_args.args[0]
            self.assertEqual(command[command.index("--health-fraction") + 1], "0.6")
            self.assertEqual(command[command.index("--enemy-health-fraction") + 1], "0.75")
            gym.close()


if __name__ == "__main__":
    unittest.main()
