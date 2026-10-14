import asyncio
from types import SimpleNamespace
import unittest
from unittest.mock import AsyncMock

from sc2.ids.ability_id import AbilityId
from sc2.unit import UnitOrder
from s2clientprotocol import data_pb2, raw_pb2
from bot.compat import install_live_abilities


class LiveAbilitiesTest(unittest.TestCase):
    def test_real_game_4135_order_is_not_silently_converted_to_null(self):
        proto = raw_pb2.UnitOrder(ability_id=4135, target_unit_tag=123, progress=0.25)
        data = SimpleNamespace(abilities={})
        # The locked SDK still directly indexes its static-filtered ability map.
        with self.assertRaises(KeyError):
            UnitOrder.from_proto(proto, SimpleNamespace(game_data=data))
        live = data_pb2.AbilityData(
            ability_id=4135,
            link_name="WorkerStopIdleAbilityVespene",
            button_name="Gather",
        )
        client = SimpleNamespace(
            _execute=AsyncMock(
                return_value=SimpleNamespace(data=SimpleNamespace(abilities=[live]))
            )
        )
        asyncio.run(install_live_abilities(client, data, lambda value: None))
        order = UnitOrder.from_proto(proto, SimpleNamespace(game_data=data))
        self.assertEqual(order.ability.id.value, 4135)
        self.assertNotEqual(order.ability.id, AbilityId.NULL_NULL)
        self.assertEqual((order.target, order.progress), (123, 0.25))

    def test_observation_only_unknown_order_remains_readable(self):
        data = SimpleNamespace(abilities={})
        client = SimpleNamespace(
            _execute=AsyncMock(
                return_value=SimpleNamespace(data=SimpleNamespace(abilities=[]))
            )
        )
        reports = []
        asyncio.run(install_live_abilities(client, data, reports.append))
        order = UnitOrder.from_proto(
            raw_pb2.UnitOrder(ability_id=99999), SimpleNamespace(game_data=data)
        )
        self.assertEqual(order.ability.id.value, 99999)
        self.assertEqual(len(reports), 1)
