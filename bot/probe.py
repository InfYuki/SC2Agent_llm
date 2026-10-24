"""The unmodified template's game hooks plus lifecycle diagnostics."""
import time
from sc2.ids.unit_typeid import UnitTypeId
from ares import AresBot
from bot.compat import install_live_abilities


class InstrumentedAresBot(AresBot):
    marine_type = UnitTypeId.MARINE

    def __init__(self, options, telemetry):
        self.options = options
        self.telemetry = telemetry
        self._chat_runtime = None
        super().__init__(game_step_override=options.game_step)

    async def on_start(self):
        try:
            self._runtime_abilities = []
            await install_live_abilities(
                self.client, self.game_data, self._runtime_abilities.append
            )
            self.telemetry.write_json("runtime_abilities.json", self._runtime_abilities)

            def record_ability(value):
                self._runtime_abilities.append(value)
                self.telemetry.write_json(
                    "runtime_abilities.json", self._runtime_abilities
                )

            self.game_data.abilities.report = record_ability
            await super().on_start()
            self.telemetry.write_json(
                "compatibility-report.json",
                dict(
                    sc2_base_build=self.base_build,
                    runtime_ability_count=len(self._runtime_abilities),
                    enum_has_4135=4135
                    in __import__(
                        "sc2.ids.ability_id", fromlist=["AbilityId"]
                    ).AbilityId._value2member_map_,
                    ability_4135_name=self.game_data.abilities[4135].friendly_name,
                ),
            )
            self.telemetry.event(
                "started",
                mode=self.options.mode,
                realtime=self.realtime,
                game_step=self.client.game_step,
            )
            from bot.banter_runtime import start_banter
            self._chat_runtime = start_banter(self)
        except Exception:
            self.telemetry.fail("on_start")
            raise

    def play_step(self, iteration):
        pass

    async def on_step(self, iteration):
        start = time.perf_counter()
        try:
            await super().on_step(iteration)
            if (
                self.options.max_game_seconds
                and self.time >= self.options.max_game_seconds
            ):
                self.telemetry.stop_reason = "game_time_limit"
                self.telemetry.observe(self, time.perf_counter() - start)
                await self.client.leave()
                return
            self.play_step(iteration)
            chat = getattr(self, "_chat_runtime", None)
            if chat is not None:
                try:
                    await chat.step()
                except Exception:
                    # Chat errors are deliberately outside gameplay telemetry.
                    print("Game chat stopped; gameplay continues.", flush=True)
                    self.close_chat()
            self.telemetry.observe(self, time.perf_counter() - start)
        except Exception:
            self.telemetry.fail("on_step")
            raise

    async def _after_step(self):
        try:
            return await super()._after_step()
        except Exception:
            self.telemetry.fail("after_step")
            raise

    async def on_end(self, result):
        try:
            await super().on_end(result)
        except Exception:
            self.telemetry.fail("on_end")
            raise
        finally:
            self.close_chat()
            self.telemetry.finish(result)

    def close_chat(self):
        chat = getattr(self, "_chat_runtime", None)
        self._chat_runtime = None
        if chat is not None:
            try:
                chat.close()
            except Exception:
                pass
