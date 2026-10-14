"""Scoped compatibility for a confirmed game-over race in the pinned SDK."""
from contextlib import contextmanager


@contextmanager
def recover_completed_game(telemetry):
    import sc2.main as engine
    from sc2.protocol import ProtocolError

    original = engine._play_game_ai

    async def play(client, player_id, ai, realtime, game_time_limit):
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

    engine._play_game_ai = play
    try:
        yield
    finally:
        engine._play_game_ai = original
