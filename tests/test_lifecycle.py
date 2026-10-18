from types import SimpleNamespace
import asyncio
import unittest
from unittest.mock import AsyncMock, Mock, patch

import run_local
from bot.lifecycle import recover_completed_game
from sc2.data import Result
from sc2.protocol import ProtocolError, ConnectionAlreadyClosed
import sc2.main as engine


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
    async def test_two_ai_results_wait_for_both_loops_before_cleanup(self):
        host_leave_done = asyncio.Event()
        joiner_done = asyncio.Event()

        async def original(client, player_id, ai, realtime, limit):
            if player_id == 1:
                await host_leave_done.wait()
                return Result.Defeat
            joiner_done.set()
            return Result.Victory

        with patch.object(engine, "_play_game_ai", original), recover_completed_game(
            SimpleNamespace(event=Mock()), expected_players=2
        ):
            host = asyncio.create_task(engine._play_game_ai(None, 1, None, False, None))
            joiner = asyncio.create_task(
                engine._play_game_ai(None, 2, None, False, None)
            )
            await joiner_done.wait()
            await asyncio.sleep(0)
            self.assertFalse(
                joiner.done(), "joiner must not enter global process cleanup"
            )
            host_leave_done.set()
            self.assertEqual(
                await asyncio.gather(host, joiner), [Result.Defeat, Result.Victory]
            )

    async def test_peer_failure_releases_barrier_and_remains_failure(self):
        async def original(client, player_id, ai, realtime, limit):
            if player_id == 1:
                raise ConnectionAlreadyClosed("not a confirmed game end")
            return Result.Victory

        with patch.object(engine, "_play_game_ai", original), recover_completed_game(
            SimpleNamespace(event=Mock()), expected_players=2
        ):
            results = await asyncio.wait_for(
                asyncio.gather(
                    engine._play_game_ai(None, 2, None, False, None),
                    engine._play_game_ai(None, 1, None, False, None),
                    return_exceptions=True,
                ),
                timeout=1,
            )
            self.assertIsInstance(results[0], RuntimeError)
            self.assertIsInstance(results[1], ConnectionAlreadyClosed)

    async def test_missing_sdk_result_is_never_replaced_with_a_local_outcome(self):
        with patch.object(
            engine, "_play_game_ai", AsyncMock(return_value=None)
        ), recover_completed_game(SimpleNamespace(event=Mock())):
            with self.assertRaisesRegex(RuntimeError, "without a player Result"):
                await engine._play_game_ai(None, 1, None, False, None)

    async def test_confirmed_game_over_returns_real_result_and_restores_wrapper(self):
        telemetry = SimpleNamespace(event=Mock())
        client = SimpleNamespace(observation=AsyncMock(), _game_result=None)

        async def refresh():
            client._game_result = {1: Result.Victory}

        client.observation.side_effect = refresh
        ai = SimpleNamespace(on_end=AsyncMock())
        original = AsyncMock(
            side_effect=ProtocolError("['Not supported if game has already ended']")
        )
        with patch.object(engine, "_play_game_ai", original):
            with recover_completed_game(telemetry):
                result = await engine._play_game_ai(client, 1, ai, True, None)
                self.assertEqual(result, Result.Victory)
            self.assertIs(engine._play_game_ai, original)
        client.observation.assert_awaited_once()
        ai.on_end.assert_awaited_once_with(Result.Victory)

    async def test_game_over_without_confirmed_result_still_fails(self):
        client = SimpleNamespace(observation=AsyncMock(), _game_result=None)
        original = AsyncMock(side_effect=ProtocolError("['Game has already ended']"))
        with patch.object(engine, "_play_game_ai", original), recover_completed_game(
            SimpleNamespace(event=Mock())
        ):
            with self.assertRaises(ProtocolError):
                await engine._play_game_ai(
                    client, 1, SimpleNamespace(on_end=AsyncMock()), True, None
                )

    async def test_other_protocol_errors_are_not_hidden(self):
        client = SimpleNamespace(
            observation=AsyncMock(), _game_result={1: Result.Victory}
        )
        original = AsyncMock(side_effect=ProtocolError("['Invalid ability']"))
        with patch.object(engine, "_play_game_ai", original), recover_completed_game(
            SimpleNamespace(event=Mock())
        ):
            with self.assertRaises(ProtocolError):
                await engine._play_game_ai(
                    client, 1, SimpleNamespace(on_end=AsyncMock()), True, None
                )
        client.observation.assert_not_awaited()
