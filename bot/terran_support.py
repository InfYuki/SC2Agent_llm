"""Rule controlled Tank/Medivac support, outside the Marine PPO contract."""
from sc2.ids.ability_id import AbilityId
from sc2.ids.unit_typeid import UnitTypeId
from ares.behaviors.macro import MacroBehavior


TANK_TYPES = {UnitTypeId.SIEGETANK, UnitTypeId.SIEGETANKSIEGED}
SUPPORT_TYPES = TANK_TYPES | {UnitTypeId.MEDIVAC}


def composition(profile):
    if profile == "marine_basic":
        return {UnitTypeId.MARINE: {"proportion": 1.0, "priority": 0}}
    return {
        UnitTypeId.MARINE: {"proportion": 0.80, "priority": 2},
        UnitTypeId.SIEGETANK: {"proportion": 0.12, "priority": 0},
        UnitTypeId.MEDIVAC: {"proportion": 0.08, "priority": 1},
    }


class FirstSupportReserve(MacroBehavior):
    """Pause lower-priority Marine spending until the first tech/support is funded.

    Supply, workers, gas buildings and expansion remain above this behavior.
    TechUp and SpawnController still validate actual build prerequisites/queues.
    """
    def execute(self, ai, config, mediator):
        factories = ai.structures(UnitTypeId.FACTORY).ready
        starports = ai.structures(UnitTypeId.STARPORT).ready
        cost = None
        if not ai.structure_present_or_pending(UnitTypeId.FACTORY):
            cost = (150, 100)
        elif factories and not any(f.has_techlab for f in factories):
            cost = (50, 25)
        elif factories and not ai.structure_present_or_pending(UnitTypeId.STARPORT):
            cost = (150, 100)
        elif any(f.has_techlab for f in factories) and not (
            ai.units.of_type(TANK_TYPES) or ai.already_pending(UnitTypeId.SIEGETANK)
        ):
            cost = (150, 125)
        elif starports and not (
            ai.units(UnitTypeId.MEDIVAC) or ai.already_pending(UnitTypeId.MEDIVAC)
        ):
            cost = (100, 100)
        waiting = cost is not None and (ai.minerals < cost[0] or ai.vespene < cost[1])
        if waiting:
            ai.telemetry.counts["support_resource_reservation_steps"] += 1
        return waiting


class SupportController:
    def __init__(self):
        self.last_contact = {}
        self.last_order = {}

    def command(self, bot, unit, action, target, frame):
        signature = (action, getattr(target, "tag", None),
                     round(getattr(target, "x", 0), 1), round(getattr(target, "y", 0), 1))
        old = self.last_order.get(unit.tag)
        if old and old[0] == signature and frame - old[1] < 32 and not unit.is_idle:
            return
        if not bot.arbiter.allow(unit.tag, "rule_support"):
            return
        if action == "siege":
            accepted = unit(AbilityId.SIEGEMODE_SIEGEMODE)
        elif action == "unsiege":
            accepted = unit(AbilityId.UNSIEGE_UNSIEGE)
        elif action == "heal":
            accepted = unit(AbilityId.MEDIVACHEAL_HEAL, target)
        elif action == "attack":
            accepted = unit.attack(target)
        else:
            accepted = unit.move(target)
        self.last_order[unit.tag] = (signature, frame)
        bot.telemetry.counts["support_" + action + "_commands"] += 1
        bot.telemetry.event("support_command", unit_tag=unit.tag, unit_type=unit.type_id.name,
                            action=action, game_loop=frame, locally_accepted=bool(accepted))

    def step(self, bot, ground_army, state, target, frame):
        support = list(bot.units.of_type(SUPPORT_TYPES))
        # Marine micro replaces the arbiter's owner map; extend it without
        # clearing issued Marine commands or changing their ownership.
        bot.arbiter.owners.update({u.tag: "rule_support" for u in support})
        alive = {u.tag for u in support}
        self.last_contact = {k: v for k, v in self.last_contact.items() if k in alive}
        self.last_order = {k: v for k, v in self.last_order.items() if k in alive}
        visible = [u for u in list(bot.enemy_units) + list(bot.enemy_structures)
                   if u.is_visible and not u.is_flying]
        for tank in (u for u in support if u.type_id in TANK_TYPES):
            nearby = [e for e in visible if tank.distance_to(e) <= 14]
            firing = [e for e in nearby if 3 <= tank.distance_to(e) <= 12.5]
            if nearby:
                self.last_contact[tank.tag] = frame
            # Never cancel an in-progress siege/unsiege animation.
            if tank.orders and tank.orders[0].ability.id in {
                AbilityId.SIEGEMODE_SIEGEMODE, AbilityId.UNSIEGE_UNSIEGE,
            }:
                continue
            if tank.type_id == UnitTypeId.SIEGETANKSIEGED:
                quiet = frame - self.last_contact.get(tank.tag, -1000) >= 67
                overrun = bool(nearby) and not firing and all(tank.distance_to(e) < 3 for e in nearby)
                if state == "retreat" or overrun or (quiet and tank.distance_to(target) > 5):
                    self.command(bot, tank, "unsiege", None, frame)
            elif state != "retreat" and firing:
                self.command(bot, tank, "siege", None, frame)
            else:
                self.command(bot, tank, "move" if state in {"rally", "retreat"} else "attack", target, frame)

        biological = [u for u in bot.units if u.is_biological
                      and u.type_id not in {UnitTypeId.SCV, UnitTypeId.PROBE, UnitTypeId.DRONE}]
        for medivac in (u for u in support if u.type_id == UnitTypeId.MEDIVAC):
            anti_air = [e for e in list(bot.enemy_units) + list(bot.enemy_structures)
                        if e.is_visible and e.can_attack_air
                        and medivac.distance_to(e) < float(e.air_range) + 3]
            if anti_air:
                enemy = min(anti_air, key=medivac.distance_to)
                destination = medivac.position.towards(enemy.position, -5)
                self.command(bot, medivac, "move", destination, frame)
                continue
            injured = [u for u in biological if u.health < u.health_max
                       and medivac.distance_to(u) <= 10]
            if injured and medivac.energy >= 5 and state != "retreat":
                patient = min(injured, key=lambda u: (u.health_percentage, medivac.distance_to(u)))
                self.command(bot, medivac, "heal", patient, frame)
            else:
                destination = (ground_army.center.towards(bot.start_location, 4)
                               if ground_army else bot.start_location)
                if state == "retreat":
                    destination = target
                self.command(bot, medivac, "move", destination, frame)
