"""Bounded, shared Terran production profiles (unit-number proportions)."""
PRODUCTION_PROFILES = {
    "marine_basic": (("MARINE", 1.0, 0),),
    "marine_tank_medivac": (("MARINE", .80, 2), ("SIEGETANK", .12, 0), ("MEDIVAC", .08, 1)),
    "marine_marauder_medivac": (("MARINE", .65, 2), ("MARAUDER", .25, 0), ("MEDIVAC", .10, 1)),
    "reaper_pressure": (("MARINE", .35, 1), ("REAPER", .65, 0)),
    "ghost_support": (("MARINE", .65, 3), ("MARAUDER", .15, 1), ("GHOST", .10, 0), ("MEDIVAC", .10, 2)),
}


def needs_gas(profile):
    return any(name != "MARINE" for name, _, _ in PRODUCTION_PROFILES[profile])


def tech_units(profile):
    # Explicit dependencies are delegated to pinned Ares TechUp. Marine needs
    # only the first Barracks which is always in the high-priority macro plan.
    return tuple(name for name, _, _ in PRODUCTION_PROFILES[profile] if name != "MARINE")
