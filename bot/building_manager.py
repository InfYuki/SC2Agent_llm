"""Local fix for Ares 3.15.0: finish an expansion job before testing blockage.

The upstream construction loop checks whether a townhall site is occupied before
retiring a job whose townhall has just finished. Its own completed base can then
be interpreted as a blocked site and the builder sent to an unwanted third base.
"""
from ares.consts import ID, TARGET, UnitRole
from ares.managers.building_manager import BuildingManager as UpstreamBuildingManager


class BuildingManager(UpstreamBuildingManager):
    # Keep the canonical class name: Ares Mediator routes requests by class name.
    def _handle_construction_orders(self):
        for tag, job in list(self.building_tracker.items()):
            target = job.get(TARGET)
            if target is None:
                continue
            if any(
                base.type_id == job[ID]
                and base.position.distance_to(target.position) < 1.5
                for base in self.ai.townhalls.ready
            ):
                self.building_counter[job[ID]] -= 1
                del self.building_tracker[tag]
                if tag in self.manager_mediator.get_unit_role_dict[UnitRole.BUILDING]:
                    self.manager_mediator.assign_role(tag=tag, role=UnitRole.GATHERING)
                self.ai.telemetry.counts["retired_completed_expansion_jobs"] += 1
        return super()._handle_construction_orders()
