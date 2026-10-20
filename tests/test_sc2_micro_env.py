"""Small contract checks only; these do not constitute real SC2 validation."""
import unittest
import asyncio
import json
from pathlib import Path
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch
from envs.micro_ipc import HOLD_MASK, message, validate_state
from envs.sc2_micro_env import MicroEnvCloseError, SC2MicroEnv


class MicroEnvContractTests(unittest.TestCase):
    def test_budget_close_handshake_cleanup_and_no_extra_transition(self):
        from bot.micro_env_bot import MicroEnvBot
        from tools.run_micro_scenario import ScenarioBot

        state = message("ready", "episode", 0, 8)
        ack = message("closed", "episode", 0, 8,
                      info=dict(reason="training_budget_close"))
        for failure in (None, "timeout", "identity", "exit"):
            with self.subTest(failure=failure):
                env = SC2MicroEnv(step_timeout=0.1)
                env.episode_id = "episode"
                env._state, env._done = state, False
                connection, process = Mock(), Mock()
                env._connection, env._process = connection, process
                connection.poll.return_value = failure != "timeout"
                connection.recv.return_value = dict(ack, frame=0) if failure == "identity" else ack
                process.poll.side_effect = lambda: process.returncode
                process.returncode = None
                def wait(timeout):
                    process.returncode = 1 if failure == "exit" else 0
                    return process.returncode
                process.wait.side_effect = wait
                with patch("envs.sc2_micro_env.subprocess.run") as kill_tree:
                    if failure:
                        with self.assertRaises(MicroEnvCloseError):
                            env.close()
                    else:
                        env.close()
                        self.assertEqual(env.close_info["worker_exit_code"], 0)
                        self.assertTrue(env._close_confirmed)
                    if failure in ("timeout", "identity"):
                        self.assertTrue(kill_tree.called or process.kill.called)
                    else:
                        kill_tree.assert_not_called()
                        process.kill.assert_not_called()
                env.close()
                connection.send.assert_called_once_with(message("close", "episode", 0, 8))
                connection.close.assert_called_once()
                self.assertIsNone(env._state)
                self.assertIsNone(env._process)

        # A natural boundary already acknowledged by step() must not resend.
        env = SC2MicroEnv()
        env._process, env._connection = Mock(), Mock()
        env._process.poll.return_value = 0
        env._close_confirmed = True
        connection = env._connection
        env.close()
        connection.send.assert_not_called()

        # Exercise the actual async control branch at a ready waiting point.
        bot = MicroEnvBot.__new__(MicroEnvBot)
        bot.connection = Mock()
        bot.connection.poll.return_value = True
        bot.connection.recv.return_value = message("close", "episode", 0, 8)
        bot.episode_id, bot._decision_id, bot.action_timeout = "episode", 0, 1
        bot._env_finished, bot._health_ready, bot._previous = False, True, None
        bot._budget_close_identity = None
        bot.state = SimpleNamespace(game_loop=8, dead_units=set())
        bot._scene_tag, bot._enemy_tags, bot._dead_enemy_tags = 1, set(), set()
        bot.units = Mock(return_value=Mock(find_by_tag=Mock(return_value=object())))
        bot.enemy_units, bot.limit_seconds, bot.scene_goal = [], 100, None
        bot.options = SimpleNamespace(training_task={})
        bot.telemetry, bot.arbiter, bot._rollout = Mock(), Mock(conflicts=0), Mock()
        bot.client = SimpleNamespace(leave=AsyncMock())
        bot._finish_scene, bot._execute_micro = Mock(), Mock()
        with patch.object(ScenarioBot, "on_step", new=AsyncMock()), \
                patch("bot.micro_env_bot.context", return_value=SimpleNamespace(obs=[0.0]*16, mask=list(HOLD_MASK))), \
                patch("bot.micro_env_bot.effective_health", return_value=45):
            asyncio.run(bot.on_step(0))
        self.assertEqual(bot._decision_id, 0)
        self.assertEqual(bot._budget_close_identity, message("close", "episode", 0, 8))
        self.assertEqual(bot.telemetry.stop_reason, "training_budget_close")
        bot.client.leave.assert_awaited_once()
        bot._execute_micro.assert_not_called()
        bot._rollout.write.assert_not_called()
        self.assertIsNone(bot._previous)
        self.assertEqual(bot.connection.send.call_args.args[0]["type"], "ready")
        bot.connection.recv.return_value = message("close", "old-episode", 0, 8)
        with self.assertRaises(ValueError):
            bot._receive_action()

        # Run the real inherited MicroRuleBot -> InstrumentedAresBot on_end
        # chain. Only the underlying Ares hook is mocked; it must not finish
        # summary/events before the worker has both official SDK results.
        from ares import AresBot
        from sc2.data import Result
        from tools.sc2_micro_worker import WorkerTelemetry
        with tempfile.TemporaryDirectory() as directory:
            bot.telemetry = WorkerTelemetry(Path(directory) / "game")
            bot.telemetry.stop_reason = "training_budget_close"
            bot._scene_outcome = "training_budget_close"
            bot.recorder = Mock()
            with patch.object(AresBot, "on_end", new=AsyncMock()):
                asyncio.run(bot.on_end(Result.Defeat))
            self.assertFalse(bot.telemetry.finished)
            self.assertFalse(bot.telemetry.events.closed)
            summary_path = bot.telemetry.output / "summary.json"
            self.assertFalse(summary_path.exists())
            bot.telemetry.event("training_budget_close", official_results="SDK results")
            bot.telemetry.finish_worker()
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
            self.assertEqual(summary["stop_reason"], "training_budget_close")
            self.assertEqual(summary["status"], "interrupted")
            self.assertIsNone(summary["result"])
            self.assertTrue(bot.telemetry.events.closed)

        original = ValueError("original failure")
        env = SC2MicroEnv()
        with patch.object(env, "close", side_effect=MicroEnvCloseError("close failed")):
            env.__exit__(ValueError, original, None)
        self.assertIn("close failed", original.__notes__[0])

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
