from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock, Mock, patch

import run_local
from bot.lifecycle import recover_completed_game
from sc2.data import Result
from sc2.protocol import ProtocolError
import sc2.main as engine


class LifecycleTests(unittest.IsolatedAsyncioTestCase):
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
