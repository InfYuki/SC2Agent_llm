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


@contextmanager
def recover_human_game(telemetry):
    """Keep the Bot alive until the Human host has observed its result/replay.

    The pinned SDK kills all SC2 processes when either process context exits.
    Both official results and the host replay must exist before the joining Bot
    leaves its loop. Exceptions release the peer; waits have a bounded timeout.
    """
    import sc2.main as engine
    from sc2.protocol import ProtocolError
    from sc2.data import Result
    from sc2.sc2process import SC2Process
    import signal

    original_human = engine._play_game_human
    original_ai = engine._play_game_ai
    original_exit = SC2Process.__aexit__
    human_done, bot_done, replay_done = asyncio.Event(), asyncio.Event(), asyncio.Event()
    failure = []

    async def own_process_exit(process, *args):
        # The SDK's default __aexit__ kills *both* clients. Here each completed
        # host/join context closes only its own process, after its own leave.
        try:
            await process._close_connection()
        finally:
            process._clean()
            signal.signal(signal.SIGINT, signal.SIG_DFL)

    async def human(client, player_id, realtime, game_time_limit):
        save_replay = client.save_replay
        async def save_then_release(*args, **kwargs):
            try:
                return await save_replay(*args, **kwargs)
            finally:
                replay_done.set()
        client.save_replay = save_then_release
        try:
            try:
                result = await original_human(client, player_id, realtime, game_time_limit)
            except ProtocolError as error:
                if not error.is_game_over_error:
                    raise
                await client.observation()
                result = (client._game_result or {}).get(player_id)
                if not isinstance(result, Result):
                    raise
            if not isinstance(result, Result):
                raise RuntimeError("Human loop ended without official Result")
            human_done.set()
            await asyncio.wait_for(bot_done.wait(), 30)
            if failure:
                raise RuntimeError("Bot loop failed") from failure[0]
            return result
        except BaseException as error:
            failure.append(error)
            human_done.set()
            replay_done.set()
            raise

    async def ai(client, player_id, bot, realtime, game_time_limit):
        try:
            try:
                result = await original_ai(client, player_id, bot, realtime, game_time_limit)
            except ProtocolError as error:
                if not error.is_game_over_error:
                    raise
                await client.observation()
                result = (client._game_result or {}).get(player_id)
                if not isinstance(result, Result):
                    raise
                await bot.on_end(result)
            if not isinstance(result, Result):
                raise RuntimeError("Bot loop ended without official Result")
            bot_done.set()
            await asyncio.wait_for(human_done.wait(), 30)
            await asyncio.wait_for(replay_done.wait(), 30)
            if failure:
                raise RuntimeError("Human loop/replay failed") from failure[0]
            return result
        except BaseException as error:
            failure.append(error)
            bot_done.set()
            raise

    engine._play_game_human, engine._play_game_ai = human, ai
    SC2Process.__aexit__ = own_process_exit
    try:
        yield
    finally:
        engine._play_game_human, engine._play_game_ai = original_human, original_ai
        SC2Process.__aexit__ = original_exit
