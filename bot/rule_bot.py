"""P1 candidate: Ares macro and a single Marine A-move controller."""
from ares.behaviors.macro import (
    AutoSupply,
    BuildStructure,
    BuildWorkers,
    ExpansionController,
    MacroPlan,
    Mining,
    ProductionController,
    SpawnController,
)
from ares.consts import UnitRole
from ares.managers.hub import Hub
from ares.managers.manager_mediator import ManagerMediator
from sc2.ids.unit_typeid import UnitTypeId

from bot.arbiter import OrderArbiter
from bot.budget import ExpansionBudget
from bot.building_manager import BuildingManager
from bot.probe import InstrumentedAresBot


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

    async def on_building_construction_complete(self, unit):
        await super().on_building_construction_complete(unit)
        self.telemetry.counts["completed_" + unit.type_id.name] += 1

    def play_step(self, iteration):
        # Ares Mining excludes builders via its mediator roles. No distribute_workers
        # or raw worker build commands are issued by this bot.
        self.register_behavior(Mining())
        plan = MacroPlan()
        plan.add(AutoSupply(self.start_location))
        worker_target, base_target = self.economic_goals()
        plan.add(BuildWorkers(to_count=worker_target))
        plan.add(BuildStructure(self.start_location, UnitTypeId.BARRACKS, to_count=1))
        needs_expansion = (
            self.time > 120
            and self.supply_workers >= 20
            and self.townhalls.amount < base_target
        )
        saving = self.expansion_budget.reserve(
            float(self.time),
            needs_expansion,
            under_attack=self.strategy_state == "defend",
        )
        if saving != self._saving_expansion:
            self.telemetry.event(
                "expansion_reservation", active=saving, game_seconds=float(self.time)
            )
        self._saving_expansion = saving
        if needs_expansion:
            plan.add(
                ExpansionController(
                    to_count=base_target, max_pending=1, prioritize=saving
                )
            )
        if not saving:
            plan.add(SpawnController(self.army_composition))
            plan.add(
                ProductionController(
                    self.army_composition,
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
        army = self.units(UnitTypeId.MARINE)
        self.arbiter.begin_step({unit.tag: "rule_combat" for unit in army})
        alive = {unit.tag for unit in army}
        self._last_order = {
            tag: value for tag, value in self._last_order.items() if tag in alive
        }
        if not army:
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
        for unit in army:
            action = "move" if state in {"retreat", "rally"} else "attack"
            signature = (action, round(target.x, 1), round(target.y, 1))
            old = self._last_order.get(unit.tag)
            if old and old[0] == signature and frame - old[1] < 45 and not unit.is_idle:
                continue
            if self.arbiter.allow(unit.tag, "rule_combat"):
                command = unit.move(target) if action == "move" else unit.attack(target)
                self._last_order[unit.tag] = (signature, frame)
                self.telemetry.counts["combat_commands"] += 1
                if not command:
                    self.telemetry.counts["combat_command_rejected"] += 1
        self.telemetry.counts["command_conflicts"] = self.arbiter.conflicts

    def economic_goals(self):
        return min(48, 22 * len(self.ready_townhalls)), 2

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
