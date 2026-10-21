"""Production ownership gate; independent of PPO observations and action masks."""
import math

ENTRY_BUFFER = 1.0
OWNER_EXIT_BUFFER = 0.5


def engagement_check(unit, enemies, owned_previous=False):
    """Release ready Marines only when every local enemy is safely distant.

    Unit.distance_to is centre distance, so both radii belong in each range.
    Missing/nonfinite data stays on the existing micro path conservatively.
    """
    buffer = ENTRY_BUFFER + (OWNER_EXIT_BUFFER if owned_previous else 0.0)
    result = dict(accepted=True, reason="unknown_geometry", enemy_count=len(enemies),
                  unknown_count=0, owned_previous=owned_previous, buffer=buffer,
                  enemy_tag=None, distance=None, own_threshold=None, threat_threshold=None)
    try:
        cooldown = float(unit.weapon_cooldown)
    except (AttributeError, TypeError, ValueError):
        cooldown = math.nan
    if not math.isfinite(cooldown):
        result.update(reason="unknown_cooldown", unknown_count=1)
        return result
    if cooldown > 0:
        result["reason"] = "cooldown_active"
        return result
    closest_margin = math.inf
    for enemy in enemies:
        try:
            distance = float(unit.distance_to(enemy))
            own_range, enemy_range = float(unit.ground_range), float(enemy.ground_range)
            own_radius, enemy_radius = float(unit.radius), float(enemy.radius)
            values = (distance, own_range, enemy_range, own_radius, enemy_radius)
            if not all(math.isfinite(value) and value >= 0 for value in values):
                raise ValueError("invalid geometry")
        except (AttributeError, TypeError, ValueError, OverflowError):
            result["unknown_count"] += 1
            continue
        own_threshold = own_range + own_radius + enemy_radius + buffer
        threat_threshold = enemy_range + own_radius + enemy_radius + buffer
        margin = distance - max(own_threshold, threat_threshold)
        if margin < closest_margin:
            closest_margin = margin
            result.update(enemy_tag=enemy.tag, distance=distance,
                          own_threshold=own_threshold, threat_threshold=threat_threshold)
    if result["unknown_count"] or not enemies:
        return result
    if closest_margin <= 0:
        result["reason"] = ("own_attack_range" if result["distance"] <= result["own_threshold"]
                            else "enemy_threat_range")
    else:
        result.update(accepted=False, reason="ready_outside_engagement")
    return result
