"""One bounded upgrade and safe rule ability, outside Marine policy actions."""
from ares.behaviors.macro import UpgradeController
from sc2.ids.ability_id import AbilityId
from sc2.ids.buff_id import BuffId
from sc2.ids.unit_typeid import UnitTypeId
from sc2.ids.upgrade_id import UpgradeId


class StimResearch(UpgradeController):
    def execute(self, ai, config, mediator):
        if ai.pending_or_complete_upgrade(UpgradeId.STIMPACK):
            return False
        # Auto TechUp also needs its first addon funded. Without this small
        # reservation, continuous Marine production can starve the TechLab.
        labs = ai.structures(UnitTypeId.BARRACKSTECHLAB)
        if not labs and not ai.structure_present_or_pending(UnitTypeId.BARRACKSTECHLAB):
            if ai.minerals < 50 or ai.vespene < 25:
                ai.telemetry.counts["stim_resource_reservation_steps"] += 1
                return True
        return super().execute(ai, config, mediator)


class StimController:
    def __init__(self):
        self.last_issued = {}

    def ready(self, bot, unit, state, frame):
        if unit.type_id not in {UnitTypeId.MARINE, UnitTypeId.MARAUDER}:
            return False
        if UpgradeId.STIMPACK not in getattr(bot.state, "upgrades", set()):
            return False
        if state not in {"attack", "defend"}:
            return False
        buff = BuffId.STIMPACK if unit.type_id == UnitTypeId.MARINE else BuffId.STIMPACKMARAUDER
        cost = 10 if unit.type_id == UnitTypeId.MARINE else 20
        if unit.has_buff(buff) or unit.health_percentage < .65 or unit.health <= cost + 10:
            return False
        if frame - self.last_issued.get(unit.tag, -1000) < 32:
            return False
        return any(enemy.is_visible and enemy.can_attack_ground
                   and (unit.type_id == UnitTypeId.MARINE or not enemy.is_flying)
                   and unit.distance_to(enemy) <= unit.ground_range + 2
                   for enemy in list(bot.enemy_units) + list(bot.enemy_structures))

    def issue(self, bot, unit, state, frame, owner):
        if not self.ready(bot, unit, state, frame):
            return False
        if not bot.arbiter.allow(unit.tag, owner):
            return False
        ability = (AbilityId.EFFECT_STIM_MARINE if unit.type_id == UnitTypeId.MARINE
                   else AbilityId.EFFECT_STIM_MARAUDER)
        accepted = unit(ability)
        self.last_issued[unit.tag] = frame
        bot.telemetry.counts["stim_commands"] += 1
        bot.telemetry.event("stim_command", unit_tag=unit.tag, unit_type=unit.type_id.name,
                            game_loop=frame, ability=ability.name,
                            locally_accepted=bool(accepted), owner=owner)
        # Even local rejection consumed this frame's command slot. Do not
        # immediately replace it with move/attack and hide an engine rejection.
        return True
