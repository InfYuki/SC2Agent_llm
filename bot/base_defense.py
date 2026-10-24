"""Bounded static defense, orbital economy and garrisons outside policy actions."""
from ares.behaviors.macro import BuildStructure, UpgradeCCs
from sc2.ids.ability_id import AbilityId as A
from sc2.ids.unit_typeid import UnitTypeId as U


class OrbitalResearch:
    """One upgrade at a time; at most eight seconds of saving per 45 seconds."""
    def __init__(self):
        self.reserve_until = -1.
        self.retry_at = 0.

    def execute(self, ai, config, mediator):
        if not ai.orbital_enabled() or ai.supply_workers < 16:
            return False
        if ai.tech_requirement_progress(U.ORBITALCOMMAND) < 1:
            return False
        if any(any(o.ability.id == A.UPGRADETOORBITAL_ORBITALCOMMAND for o in th.orders)
               for th in ai.townhalls):
            return False
        idle = [th for th in ai.townhalls if th.type_id == U.COMMANDCENTER
                and th.is_ready and th.is_idle and not th.is_flying]
        if not idle:
            return False
        if ai.can_afford(U.ORBITALCOMMAND):
            issued = UpgradeCCs(U.ORBITALCOMMAND).execute(ai, config, mediator)
            if issued:
                ai.telemetry.counts['orbital_upgrade_commands'] += 1
            return issued
        if ai.time >= self.retry_at:
            self.reserve_until, self.retry_at = ai.time + 8, ai.time + 45
        return ai.time < self.reserve_until


class BaseDefenses:
    def execute(self, ai, config, mediator):
        policy = ai.defense_policy()
        if policy == 'none' or ai._saving_expansion:
            return False
        bases = [b for b in ai.ready_townhalls if not b.is_flying]
        if not bases or ai.supply_workers < 18:
            return False
        visible = [e for e in ai.enemy_units if e.is_visible]
        ground = any(e.can_attack_ground and any(e.distance_to(b) < 25 for b in bases)
                     for e in visible)
        air = any(e.is_flying and e.can_attack_ground for e in visible)
        if ai.time >= 180 or ground:
            if ai.tech_requirement_progress(U.BUNKER) >= 1 and not ai.structure_pending(U.BUNKER):
                fronts = sorted(bases, key=lambda b: b.distance_to(ai.start_location), reverse=True)
                for base in fronts[:2 if policy == 'fortified' else 1]:
                    if not any(s.distance_to(base) < 18 for s in ai.structures(U.BUNKER)):
                        if ai.can_afford(U.BUNKER):
                            return BuildStructure(base.position, U.BUNKER, bunker=True,
                                production=False, closest_to=base.position.towards(ai.game_info.map_center, 7),
                                to_count_per_base=1, max_on_route=1, find_alternative=False,
                                tech_progress_check=1.).execute(ai, config, mediator)
        if ai.time < 240 or (not air and ai.time < 420 and policy != 'fortified'):
            return False
        if ai.tech_requirement_progress(U.MISSILETURRET) < 1:
            if not ai.structure_present_or_pending(U.ENGINEERINGBAY) and ai.can_afford(U.ENGINEERINGBAY):
                return BuildStructure(ai.start_location, U.ENGINEERINGBAY,
                    to_count=1, upgrade_structure=True, production=False).execute(ai, config, mediator)
            return False
        if ai.structure_pending(U.MISSILETURRET):
            return False
        for base in bases:
            local = [t for t in ai.structures(U.MISSILETURRET) if t.distance_to(base) < 14]
            if len(local) < (2 if policy == 'fortified' else 1) and ai.can_afford(U.MISSILETURRET):
                patches = [p for p in ai.mineral_field if p.mineral_contents > 0 and p.distance_to(base) < 10]
                towards = patches[0].position if patches else base.position
                return BuildStructure(base.position, U.MISSILETURRET,
                    missile_turret=True, production=False, closest_to=towards,
                    to_count_per_base=2 if policy == 'fortified' else 1,
                    max_on_route=1, find_alternative=False,
                    tech_progress_check=1.).execute(ai, config, mediator)
        return False


class BaseController:
    def __init__(self):
        self.load_targets = {}
        self.last_scan = -1000
        self.last_orbital = {}
        self.last_load = {}
        self.quiet_since = {}
        self.hidden_seen_until = -1

    def orbital_step(self, ai, frame):
        orbitals = [b for b in ai.townhalls if b.type_id == U.ORBITALCOMMAND
                    and b.is_ready and not b.is_flying and b.energy >= 50]
        hidden = [e for e in ai.enemy_units if e.is_visible
                  and (e.is_cloaked or e.is_burrowed) and not e.is_revealed
                  and any(e.distance_to(b) < 25 for b in ai.townhalls)]
        detectors = [s for s in ai.structures(U.MISSILETURRET) if s.is_ready]
        hidden = [e for e in hidden if not any(d.distance_to(e) <= 10 for d in detectors)]
        if hidden:
            self.hidden_seen_until = frame + 672  # Keep one scan for 30s after evidence.
        for orbital in orbitals:
            if frame - self.last_orbital.get(orbital.tag, -1000) < 32:
                continue
            if hidden and frame - self.last_scan >= 224:
                accepted = orbital(A.SCANNERSWEEP_SCAN, hidden[0].position)
                self.last_scan = frame
                ai.telemetry.counts['orbital_scan_commands'] += 1
                ai.telemetry.event('orbital_ability', ability='scan', game_loop=frame,
                                   unit_tag=orbital.tag, locally_accepted=bool(accepted))
            else:
                # Retain one scan once cloaked/burrowed enemies have actually been seen.
                if frame < self.hidden_seen_until and orbital.energy < 100:
                    continue
                patches = [p for p in ai.mineral_field if p.mineral_contents >= 50
                           and any(b.is_ready and not b.is_flying and p.distance_to(b) < 10
                                   for b in ai.townhalls)
                           and not any(e.is_visible and e.can_attack_ground and e.distance_to(p) < 15
                                       for e in ai.enemy_units)]
                if not patches:
                    continue
                patch = max(patches, key=lambda p: p.mineral_contents)
                accepted = orbital(A.CALLDOWNMULE_CALLDOWNMULE, patch)
                ai.telemetry.counts['orbital_mule_commands'] += 1
                ai.telemetry.event('orbital_ability', ability='mule', game_loop=frame,
                                   unit_tag=orbital.tag, locally_accepted=bool(accepted))
            self.last_orbital[orbital.tag] = frame

    def prepare(self, ai, army, state, frame):
        self.load_targets = {}
        bunkers = [b for b in ai.structures(U.BUNKER) if b.is_ready]
        for bunker in bunkers:
            enemies = [e for e in ai.enemy_units if e.is_visible and e.distance_to(bunker) < 18]
            if enemies:
                self.quiet_since[bunker.tag] = frame
            if (state in {'attack', 'retreat'} and not enemies
                    and frame - self.quiet_since.get(bunker.tag, 0) >= 224
                    and bunker.cargo_used):
                if ai.arbiter.allow(bunker.tag, 'rule_bunker'):
                    bunker(A.UNLOADALL_BUNKER)
                    ai.telemetry.counts['bunker_unload_commands'] += 1
                continue
            if state in {'attack', 'retreat'} and not enemies:
                continue
            slots = int(bunker.cargo_left)
            marines = sorted([m for m in army if m.type_id == U.MARINE
                              and m.health_percentage > .3 and m.distance_to(bunker) < 12
                              and m.tag not in self.load_targets],
                             key=lambda m: m.distance_to(bunker))
            for marine in marines[:slots]:
                self.load_targets[marine.tag] = bunker

    def issue_load(self, ai, unit, frame):
        bunker = self.load_targets.get(unit.tag)
        if bunker is None:
            return False
        if frame - self.last_load.get(unit.tag, -1000) < 32:
            return True  # Preserve the approach/load order, outside PPO sampling.
        if ai.arbiter.allow(unit.tag, 'rule_combat'):
            accepted = unit(A.SMART, bunker)
            self.last_load[unit.tag] = frame
            ai.telemetry.counts['bunker_load_commands'] += 1
            ai.telemetry.event('bunker_load', game_loop=frame, unit_tag=unit.tag,
                               bunker_tag=bunker.tag, locally_accepted=bool(accepted))
        return True
