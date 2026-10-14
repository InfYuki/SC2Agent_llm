"""Preserve live ability IDs that predate the SDK's generated enum table."""
from dataclasses import dataclass

from sc2.game_data import AbilityData
from sc2.ids.ability_id import AbilityId
from s2clientprotocol import data_pb2, sc2api_pb2


@dataclass(frozen=True)
class RuntimeAbilityId:
    value: int
    name: str


class RuntimeAbilityData(AbilityData):
    @property
    def id(self):
        remap = self._proto.remaps_to_ability_id
        value = remap or self._proto.ability_id
        # This SDK silently converts an unknown enum value to NULL_NULL.
        return AbilityId._value2member_map_.get(value) or self.exact_id

    @property
    def exact_id(self):
        # Prefer the engine's declared generic ID for an unknown exact ID.
        known = AbilityId._value2member_map_.get(self._proto.ability_id)
        if known is not None:
            return known
        remapped = AbilityId._value2member_map_.get(self._proto.remaps_to_ability_id)
        if remapped is not None and self._proto.remaps_to_ability_id:
            return remapped
        return RuntimeAbilityId(
            self._proto.ability_id, f"RUNTIME_ABILITY_{self._proto.ability_id}"
        )


class RuntimeAbilityMap(dict):
    def __init__(self, game_data, report):
        super().__init__(game_data.abilities)
        self.game_data = game_data
        self.report = report

    def __missing__(self, ability_id):
        # An opaque order stays visible and keeps its target/progress. Never
        # interpret an unknown command as MOVE/SMART or another guessed action.
        proto = data_pb2.AbilityData(
            ability_id=ability_id, friendly_name=f"Unknown live ability {ability_id}"
        )
        ability = self[ability_id] = RuntimeAbilityData(self.game_data, proto)
        self.report(
            dict(
                ability_id=ability_id, remaps_to_ability_id=0, source="observation_only"
            )
        )
        return ability


async def install_live_abilities(client, game_data, report):
    response = await client._execute(data=sc2api_pb2.RequestData(ability_id=True))
    abilities = RuntimeAbilityMap(game_data, report)
    for proto in response.data.abilities:
        if proto.ability_id and proto.ability_id not in abilities:
            abilities[proto.ability_id] = RuntimeAbilityData(game_data, proto)
            report(
                dict(
                    ability_id=proto.ability_id,
                    remaps_to_ability_id=proto.remaps_to_ability_id,
                    link_name=proto.link_name,
                    button_name=proto.button_name,
                    source="engine_data",
                )
            )
    game_data.abilities = abilities
