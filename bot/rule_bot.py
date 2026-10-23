"""P1 candidate: Ares macro and a single Marine A-move controller."""
from ares.behaviors.macro import (
    AutoSupply,
    BuildStructure,
    BuildWorkers,
    ExpansionController,
    GasBuildingController,
    MacroPlan,
    Mining,
    ProductionController,
    SpawnController,
    TechUp,
)
from ares.consts import UnitRole
from ares.managers.hub import Hub
from ares.managers.manager_mediator import ManagerMediator
from sc2.ids.unit_typeid import UnitTypeId

from bot.economy import EconomyPolicy
from bot.arbiter import OrderArbiter
from bot.budget import ExpansionBudget
from bot.building_manager import BuildingManager
from bot.probe import InstrumentedAresBot
from bot.terran_support import FirstSupportReserve, SupportController, SUPPORT_TYPES, TANK_TYPES, composition


class RuleBot(InstrumentedAresBot):
    army_composition = {UnitTypeId.MARINE: {"proportion": 1.0, "priority": 0}}

    def __init__(self, options, telemetry):
        super().__init__(options, telemetry)
        self.arbiter = OrderArbiter()
        self.strategy_state = "develop"
        self._last_combat_frame = -100
        self._last_order = {}
        self._sweep_index = 0
        self.expansion_budget = ExpansionBudget()
        self._saving_expansion = False
        self.support = SupportController()
        self.economy_policy = EconomyPolicy()
        self.economy_status = {}
        self._last_economy_event = -30.0

    def register_managers(self):
        mediator = ManagerMediator()
        self.manager_hub = Hub(
            self,
            self.config,
            mediator,
            building_manager=BuildingManager(self, self.config, mediator),
        )
        self.manager_hub.init_managers()

    async def on_unit_created(self, unit):
        await super().on_unit_created(unit)
        if unit.type_id == UnitTypeId.MARINE:
            self.mediator.assign_role(tag=unit.tag, role=UnitRole.ATTACKING)
            self.telemetry.counts["marines_created"] += 1
        elif unit.type_id in SUPPORT_TYPES:
            self.mediator.assign_role(tag=unit.tag, role=UnitRole.ATTACKING)
            self.telemetry.counts[unit.type_id.name.lower() + "_created"] += 1

    async def on_building_construction_complete(self, unit):
        await super().on_building_construction_complete(unit)
        self.telemetry.counts["completed_" + unit.type_id.name] += 1

    def play_step(self, iteration):
        # Ares Mining excludes builders via its mediator roles. No distribute_workers
        # or raw worker build commands are issued by this bot.
        worker_target, base_target = self.economic_goals()
        self.register_behavior(Mining(workers_per_gas=self.economy_status["workers_per_gas"]))
        plan = MacroPlan()
        plan.add(AutoSupply(self.start_location))
        plan.add(BuildWorkers(to_count=worker_target))
        profile = self.production_profile()
        army_composition = composition(profile)
        mixed = profile == "marine_tank_medivac"
        needs_expansion = (
            self.time > 120
            and (self.supply_workers >= 20
                 or (self.economy_status.get("reason") == "depleted"
                     and self.supply_workers >= 1))
            and len(self.ready_townhalls) + self.structure_pending(self.base_townhall_type) < base_target
            and self.structure_pending(self.base_townhall_type) < 1
            and not self.economy_under_attack()
        )
        saving = self.expansion_budget.reserve(
            float(self.time),
            needs_expansion,
            under_attack=self.economy_under_attack(),
        )
        if saving != self._saving_expansion:
            self.telemetry.event(
                "expansion_reservation", active=saving, game_seconds=float(self.time)
            )
        self._saving_expansion = saving
        if needs_expansion:
            plan.add(
                ExpansionController(
                    to_count=base_target, max_pending=1, prioritize=saving,
                    check_location_is_safe=True
                )
            )
        # Supply and replacement workers precede saving; tech/production cannot
        # consume expansion funds while the bounded reservation is active.
        plan.add(BuildStructure(self.start_location, UnitTypeId.BARRACKS, to_count=1))
        if mixed and self.supply_workers >= 16 and not saving:
            plan.add(GasBuildingController(to_count=min(4, 2 * max(1, len(self.ready_townhalls)))))
        if not saving:
            if mixed and self.time >= 100:
                plan.add(FirstSupportReserve())
                # Tech first, otherwise continuously spawning Marines can spend
                # the minerals needed for the first Factory / Starport / addon.
                plan.add(TechUp(UnitTypeId.SIEGETANK, self.start_location))
                plan.add(TechUp(UnitTypeId.MEDIVAC, self.start_location))
            plan.add(SpawnController(army_composition))
            plan.add(
                ProductionController(
                    army_composition,
                    self.start_location,
                    add_production_at_bank=(300, 0),
                    max_production_structures=8,
                )
            )
        self.register_behavior(plan)
        frame = int(self.state.game_loop)
        if frame - self._last_combat_frame >= 8:
            self._last_combat_frame = frame
            self._combat(frame)

    def _combat(self, frame):
        army = self.units.of_type({UnitTypeId.MARINE} | TANK_TYPES)
        owners = {unit.tag: "rule_combat" for unit in army if unit.type_id == UnitTypeId.MARINE}
        owners.update({unit.tag: "rule_support" for unit in self.units.of_type(SUPPORT_TYPES)})
        self.arbiter.begin_step(owners)
        alive = set(owners)
        self._last_order = {
            tag: value for tag, value in self._last_order.items() if tag in alive
        }
        if not army:
            self.support.step(self, army, "rally", self.start_location, frame)
            return
        threats = self.enemy_units.filter(
            lambda enemy: enemy.is_visible
            and (
                enemy.can_attack_ground
                or enemy.type_id in {UnitTypeId.DRONE, UnitTypeId.SCV, UnitTypeId.PROBE}
            )
            and any(enemy.distance_to(base) < 25 for base in self.townhalls)
        )
        if threats:
            state, target = "defend", threats.closest_to(self.start_location).position
            self.telemetry.counts["emergency_defense_steps"] += 1
        elif (strategic_order := self.strategic_order(army)) is not None:
            state, target = strategic_order
        elif len(army) >= 20 or (self.strategy_state == "attack" and len(army) >= 6):
            state = "attack"
            target = self.attack_target(army)
        else:
            state = (
                "retreat" if self.strategy_state in {"attack", "retreat"} else "rally"
            )
            bases = self.ready_townhalls
            origin = (
                bases.furthest_to(self.start_location).position
                if bases
                else self.start_location
            )
            target = origin.towards(self.game_info.map_center, 8)
        if state != self.strategy_state:
            self.telemetry.event(
                "strategy_changed",
                previous=self.strategy_state,
                current=state,
                game_seconds=float(self.time),
                marines=len(army),
            )
        self.strategy_state = state
        # Keep all Tank/Medivac objects outside the frozen Marine PPO interface.
        self.issue_combat_orders(army.of_type({UnitTypeId.MARINE}), state, target, frame)
        self.support.step(self, army, state, target, frame)
        self.telemetry.counts["command_conflicts"] = self.arbiter.conflicts

    def issue_combat_orders(self, army, state, target, frame):
        for unit in army:
            self.issue_rule_order(unit, state, target, frame)

    def issue_rule_order(self, unit, state, target, frame):
        action = "move" if state in {"retreat", "rally"} else "attack"
        signature = (action, round(target.x, 1), round(target.y, 1))
        old = self._last_order.get(unit.tag)
        if old and old[0] == signature and frame - old[1] < 45 and not unit.is_idle:
            return
        if self.arbiter.allow(unit.tag, "rule_combat"):
            command = unit.move(target) if action == "move" else unit.attack(target)
            self._last_order[unit.tag] = (signature, frame)
            self.telemetry.counts["combat_commands"] += 1
            if not command:
                self.telemetry.counts["combat_command_rejected"] += 1

    def requested_economic_goals(self):
        return 72, 4

    def economy_under_attack(self):
        return any(enemy.is_visible and enemy.can_attack_ground
                   and any(enemy.distance_to(base) < 25 for base in self.townhalls)
                   for enemy in self.enemy_units)

    def economic_goals(self):
        requested_workers, requested_bases = self.requested_economic_goals()
        bases = [base for base in self.ready_townhalls if not base.is_flying]
        patches = sum(1 for patch in self.mineral_field
                      if patch.mineral_contents > 0
                      and any(patch.distance_to(base) < 10 for base in bases))
        refineries = sum(1 for refinery in self.gas_buildings.ready
                         if refinery.vespene_contents > 0
                         and any(refinery.distance_to(base) < 12 for base in bases))
        decision = self.economy_policy.decide(
            seconds=float(self.time), workers=self.supply_workers,
            ready_bases=len(bases), mineral_patches=patches, refineries=refineries,
            minerals=self.minerals, gas=self.vespene,
            mixed=self.production_profile() == "marine_tank_medivac",
            requested_workers=requested_workers, requested_bases=requested_bases)
        self.economy_status = dict(
            requested_workers=requested_workers, requested_bases=requested_bases,
            worker_target=decision.worker_target, base_target=decision.base_target,
            workers_per_gas=decision.workers_per_gas,
            mineral_capacity=decision.mineral_capacity, reason=decision.reason,
            supply_workers=int(self.supply_workers), current_workers=len(self.workers),
            ready_bases=len(bases), mineral_patches=patches,
            pending_bases=int(self.structure_pending(self.base_townhall_type)),
            actual_gas_workers=len(self.mediator.get_worker_to_vespene_dict),
            minerals=int(self.minerals), vespene=int(self.vespene),
            under_attack=self.economy_under_attack())
        if self.time - self._last_economy_event >= 15:
            self.telemetry.event("economy_policy", game_seconds=float(self.time),
                                 **self.economy_status)
            self._last_economy_event = float(self.time)
        return decision.worker_target, decision.base_target

    def production_profile(self):
        return "marine_tank_medivac"

    def strategic_order(self, army):
        return None

    def attack_target(self, army):
        if self.enemy_structures:
            return self.enemy_structures.closest_to(army.center).position
        target = self.enemy_start_locations[0]
        if army.center.distance_to(target) < 8 or self._sweep_index:
            locations = sorted(self.expansion_locations_list, key=lambda p: (p.x, p.y))
            if locations:
                target = locations[self._sweep_index % len(locations)]
                if army.center.distance_to(target) < 8:
                    self._sweep_index += 1
        return target
