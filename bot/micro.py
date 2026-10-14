"""Shared, deterministic marine-16-v1 observation/action contract (no ML stack)."""
from dataclasses import dataclass
from enum import IntEnum
import math

from sc2.ids.unit_typeid import UnitTypeId
from sc2.position import Point2

FEATURE_VERSION = "marine-16-v1"
ACTION_VERSION = "marine-5-v1"
EXPERT_VERSION = "marine-kite-v1"
SCENARIO_VERSION = "visible-ground-skirmish-v1"
DECISION_LOOPS = 8
RADIUS = 12.0
MOVE_DISTANCE = 2.0
SUPPORTED = {
    UnitTypeId.MARINE,
    UnitTypeId.ZERGLING,
    UnitTypeId.ROACH,
    UnitTypeId.HYDRALISK,
    UnitTypeId.ZEALOT,
    UnitTypeId.STALKER,
}


class Action(IntEnum):
    NEAREST = 0
    WEAKEST = 1
    RETREAT = 2
    APPROACH = 3
    HOLD = 4  # keep the current order; never hold_position()


def clip(value):
    if not math.isfinite(value):
        raise ValueError("Non-finite micro feature")
    return max(-1.0, min(1.0, float(value)))


def fraction(value, maximum):
    return clip(value / maximum) if maximum > 0 else 0.0


def visible(unit):
    return unit.is_visible and not unit.is_memory and not unit.is_snapshot


def effective_health(unit):
    return unit.health + unit.shield


def relative(origin, target, scale):
    return [clip((target.x - origin.x) / scale), clip((target.y - origin.y) / scale)]


def clear_segment(bot, unit, destination):
    """Conservative local movement; terrain footprint and known building collisions."""
    origin = unit.position
    distance = origin.distance_to(destination)
    if distance < 0.25:
        return False
    structures = list(bot.structures) + [s for s in bot.enemy_structures if visible(s)]
    structures += list(getattr(bot, "destructables", ()))
    structures += list(getattr(bot, "mineral_field", ()))
    structures += list(getattr(bot, "vespene_geyser", ()))
    structures = [
        s
        for s in structures
        if origin.distance_to(s.position) < distance + unit.radius + s.radius
    ]
    mediator = getattr(bot, "mediator", None)
    clean_grid = mediator.get_cached_ground_grid if mediator is not None else None
    for step in range(1, math.ceil(distance / 0.5) + 1):
        point = origin.towards(destination, min(distance, step * 0.5))
        radius = unit.radius
        for dx, dy in ((0, 0), (radius, 0), (-radius, 0), (0, radius), (0, -radius)):
            try:
                footprint = Point2((float(point.x + dx), float(point.y + dy)))
                if not bot.in_pathing_grid(footprint):
                    return False
                if clean_grid is not None:
                    x, y = int(footprint.x), int(footprint.y)
                    if not (
                        0 <= x < clean_grid.shape[0] and 0 <= y < clean_grid.shape[1]
                    ):
                        return False
                    if not math.isfinite(float(clean_grid[x, y])):
                        return False
            except (IndexError, AssertionError):
                return False
        if any(point.distance_to(s.position) < radius + s.radius for s in structures):
            return False
    return True


@dataclass(frozen=True)
class Context:
    obs: tuple
    mask: tuple
    nearest: object = None
    weakest: object = None
    retreat: object = None
    approach: object = None
    enemies: tuple = ()
    supported: bool = False
    reason: str = "no_enemy"


def context(bot, unit, army, goal):
    nearby = tuple(
        e
        for e in bot.enemy_units
        if visible(e)
        and unit.distance_to(e) <= RADIUS
        and (e.can_attack_ground or e.type_id in SUPPORTED)
    )
    enemies = tuple(e for e in nearby if e.type_id in SUPPORTED and not e.is_flying)
    supported = bool(enemies) and len(nearby) <= 8 and len(enemies) == len(nearby)
    # Visible static defenses are outside this first contract.
    static_threat = any(
        visible(e) and e.can_attack_ground and unit.distance_to(e) <= RADIUS
        for e in bot.enemy_structures
    )
    supported = supported and not static_threat
    nearest = min(enemies, key=lambda e: (unit.distance_to(e), e.tag), default=None)
    weakest = min(
        enemies,
        key=lambda e: (effective_health(e), unit.distance_to(e), e.tag),
        default=None,
    )
    own = [
        fraction(unit.health, unit.health_max),
        fraction(unit.shield, unit.shield_max),
        fraction(unit.weapon_cooldown, 15.0),
    ]
    nearest_features = (
        [
            *relative(unit.position, nearest.position, RADIUS),
            fraction(unit.distance_to(nearest), RADIUS),
            fraction(nearest.health, nearest.health_max),
            fraction(nearest.shield, nearest.shield_max),
            fraction(nearest.weapon_cooldown, 30.0),
        ]
        if nearest
        else [0.0] * 6
    )
    weakest_features = (
        [
            *relative(unit.position, weakest.position, RADIUS),
            fraction(
                effective_health(weakest), weakest.health_max + weakest.shield_max
            ),
        ]
        if weakest
        else [0.0] * 3
    )
    friends = sum(u.tag != unit.tag and unit.distance_to(u) <= RADIUS for u in army)
    obs = tuple(
        own
        + nearest_features
        + weakest_features
        + [fraction(friends, 16), fraction(len(enemies), 16)]
        + relative(unit.position, goal, 64.0)
    )
    retreat = approach = None
    if supported and nearest:
        distance = unit.distance_to(nearest)
        if distance > 0.01:
            retreat = unit.position.towards(nearest.position, -MOVE_DISTANCE)
            approach = unit.position.towards(
                nearest.position, min(MOVE_DISTANCE, max(0.0, distance - 1.0))
            )
    ready = unit.weapon_cooldown <= 0
    mask = (
        bool(supported and ready and unit.target_in_range(nearest)),
        bool(supported and ready and unit.target_in_range(weakest)),
        bool(retreat is not None and clear_segment(bot, unit, retreat)),
        bool(approach is not None and clear_segment(bot, unit, approach)),
        True,
    )
    return Context(
        obs,
        mask,
        nearest,
        weakest,
        retreat,
        approach,
        enemies,
        supported,
        "supported"
        if supported
        else "unsupported"
        if nearby or static_threat
        else "no_enemy",
    )


def expert(unit, ctx):
    """Shoot weakest in range; kite during cooldown; approach only out of range."""
    if ctx.mask[Action.WEAKEST]:
        return Action.WEAKEST
    if ctx.mask[Action.NEAREST]:
        return Action.NEAREST
    if (
        unit.weapon_cooldown > 0
        and ctx.nearest
        and not (
            ctx.nearest.ground_range > unit.ground_range
            and (
                ctx.nearest.real_speed >= unit.real_speed
                or ctx.nearest.real_speed < 0.5
            )
        )
        and unit.distance_to(ctx.nearest)
        < unit.ground_range + unit.radius + ctx.nearest.radius + 1.0
        and ctx.mask[Action.RETREAT]
    ):
        return Action.RETREAT
    if (
        ctx.nearest
        and not unit.target_in_range(ctx.nearest)
        and ctx.mask[Action.APPROACH]
    ):
        return Action.APPROACH
    return Action.HOLD


def action_target(ctx, action):
    return (ctx.nearest, ctx.weakest, ctx.retreat, ctx.approach, None)[action]


def repeated_order(unit, action, target):
    if not unit.orders:
        return False
    order = unit.orders[0]
    name = order.ability.id.name
    if action in (Action.NEAREST, Action.WEAKEST):
        return "ATTACK" in name and order.target == target.tag
    if action in (Action.RETREAT, Action.APPROACH):
        return (
            "MOVE" in name
            and isinstance(order.target, Point2)
            and order.target.distance_to(target) < 0.25
        )
    return False
