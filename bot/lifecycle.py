"""Scoped game-over recovery and coordinated cleanup for the pinned SDK."""
import asyncio
from contextlib import contextmanager


@contextmanager
def recover_completed_game(telemetry, *, expected_players=1):
    import sc2.main as engine
    from sc2.protocol import ProtocolError
    from sc2.data import Result

    if expected_players < 1:
        raise ValueError("expected_players must be positive")

    original = engine._play_game_ai
    finished = 0
    failed = None
    all_finished = asyncio.Event()

    async def confirmed_play(client, player_id, ai, realtime, game_time_limit):
        try:
            return await original(client, player_id, ai, realtime, game_time_limit)
        except ProtocolError as error:
            if not error.is_game_over_error:
                raise
            # The error text alone is insufficient evidence of a result. Refresh
            # the official observation and require this player's actual result.
            await client.observation()
            result = (client._game_result or {}).get(player_id)
            if result is None:
                raise
            telemetry.event(
                "confirmed_game_end_race", player_id=player_id, result=str(result)
            )
            await ai.on_end(result)
            return result

    async def play(client, player_id, ai, realtime, game_time_limit):
        nonlocal finished, failed
        try:
            result = await confirmed_play(
                client, player_id, ai, realtime, game_time_limit
            )
            if not isinstance(result, Result):
                raise RuntimeError("SDK AI loop ended without a player Result")
        except BaseException as error:
            failed = error
            all_finished.set()
            raise
        finished += 1
        if finished >= expected_players:
            all_finished.set()
        # In the pinned SDK each SC2Process context exits via a global kill_all.
        # A finished joiner must not enter cleanup while the host still awaits
        # its leave response. Preserve both SDK results; never infer a result
        # from the scene outcome or a disconnected socket.
        await all_finished.wait()
        if failed is not None:
            raise RuntimeError(
                "Another AI loop failed before coordinated cleanup"
            ) from failed
        return result

    engine._play_game_ai = play
    try:
        yield
    finally:
        engine._play_game_ai = original
