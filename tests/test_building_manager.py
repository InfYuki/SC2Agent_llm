from collections import Counter
from types import SimpleNamespace
import unittest
from unittest.mock import Mock, patch

import run_local  # Same pinned Ares module search paths as the local launcher.
from ares.consts import ID, TARGET, UnitRole
from ares.managers.building_manager import BuildingManager as UpstreamBuildingManager
from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2
from bot.building_manager import BuildingManager


class BuildingManagerTest(unittest.TestCase):
    def test_completed_base_job_is_retired_before_blocked_location_logic(self):
        manager = BuildingManager.__new__(BuildingManager)
        target = Point2((10, 20))
        base = SimpleNamespace(type_id=UnitTypeId.COMMANDCENTER, position=target)
        manager.ai = SimpleNamespace(
            townhalls=SimpleNamespace(ready=[base]),
            telemetry=SimpleNamespace(counts=Counter()),
        )
        manager.building_tracker = {
            123: {ID: UnitTypeId.COMMANDCENTER, TARGET: target},
            456: {ID: UnitTypeId.COMMANDCENTER, TARGET: Point2((40, 50))},
        }
        manager.building_counter = Counter({UnitTypeId.COMMANDCENTER: 2})
        manager.manager_mediator = SimpleNamespace(
            get_unit_role_dict={UnitRole.BUILDING: {123, 456}}, assign_role=Mock()
        )

        def original_loop(instance):
            self.assertNotIn(123, instance.building_tracker)
            self.assertIn(456, instance.building_tracker)

        with patch.object(
            UpstreamBuildingManager, "_handle_construction_orders", original_loop
        ):
            manager._handle_construction_orders()
        self.assertEqual(manager.building_counter[UnitTypeId.COMMANDCENTER], 1)
        manager.manager_mediator.assign_role.assert_called_once_with(
            tag=123, role=UnitRole.GATHERING
        )
        self.assertEqual(type(manager).__name__, "BuildingManager")
