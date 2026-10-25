"""Optional game chat; no strategy objects, training data or HTTP on the game loop."""
from collections import Counter, deque
import json
from pathlib import Path
import random
import re
import time


GREETING = "载入《聊天流》战术，真正的比赛在比赛开始前就已经开始了。——F91.孙一峰"
CHAT_BYTES = 200


def chat_text(value, *, limit=120):
    text = re.sub(r"sk-[A-Za-z0-9_-]{12,}", "[redacted]", str(value))
    return " ".join(text.split())[:limit]


def chunks(text, max_bytes=CHAT_BYTES):
    """Split on characters rather than cutting UTF-8 bytes."""
    result, part = [], ""
    for character in text:
        if len((part + character).encode("utf-8")) > max_bytes:
            result.append(part)
            part = ""
        part += character
    if part:
        result.append(part)
    return result


class BanterRuntime:
    def __init__(self, ai, worker, *, rng=None, clock=None):
        self.ai, self.worker = ai, worker
        self.rng = rng or random.Random()
        self.clock = clock or time.monotonic
        self._closed = False
        self._greeted = False
        self._next_comment = 0.0
        self._last_sent = -100.0
        self._last_submit_wall = -100.0
        self._inflight = None
        self._previous_chat = []
        self._pending_human = deque(maxlen=4)
        self._history = deque(maxlen=12)
        self._log = None
        try:
            self._log = (Path(ai.telemetry.output) / "banter_events.jsonl").open("a", encoding="utf-8")
        except OSError:
            pass  # Chat diagnostics never make gameplay fail.
        self._event("started", interval_game_seconds=[60, 120])

    def _event(self, event, **fields):
        if self._log is None:
            return
        try:
            self._log.write(json.dumps(dict(event=event, game_seconds=round(float(self.ai.time), 2), **fields), ensure_ascii=False) + "\n")
            self._log.flush()
        except (OSError, ValueError):
            pass

    def _incoming(self, now):
        current = [(int(item.player_id), chat_text(item.message, limit=300))
                   for item in getattr(self.ai.state, "chat", [])]
        # SDK observations may include the previous frame's chat. Remove only
        # the overlapping suffix/prefix; allow the same words again later.
        overlap = 0
        for size in range(min(len(current), len(self._previous_chat)), 0, -1):
            if self._previous_chat[-size:] == current[:size]:
                overlap = size
                break
        self._previous_chat = current[-32:]
        own_id = int(getattr(self.ai, "player_id", 2))
        if not getattr(self.ai.options, "human_training", False):
            return
        for player, message in current[overlap:]:
            if player == 1 and player != own_id and message:
                self._pending_human.append(dict(player_id=player, text=message, game_seconds=now))
                self._event("human_chat", text=message)

    def _snapshot(self):
        ai = self.ai
        visible = [u for u in ai.enemy_units if u.is_visible]
        visible += [u for u in ai.enemy_structures if u.is_visible]
        own = Counter(u.type_id.name for u in ai.units)
        enemy = Counter(u.type_id.name for u in visible)
        return dict(
            information_scope="Current own state and currently visible enemies only; no replay or hidden enemy information.",
            own_units=dict(own.most_common(20)), enemy_visible=dict(enemy.most_common(20)),
            minerals=int(ai.minerals), vespene=int(ai.vespene),
            supply_used=float(ai.supply_used), supply_cap=float(ai.supply_cap),
            own_bases=len(ai.townhalls),
            base_under_attack=any(
                (u.can_attack_ground or u.can_attack_air) and u.distance_to(base) < 25
                for u in visible for base in ai.townhalls),
            chat_mood=self._chat_mood([u for u in ai.enemy_units if u.is_visible]),
        )

    def _chat_mood(self, enemies):
        """Conservative local tone cue, not a commander score or global win claim."""
        ai = self.ai

        def combat(unit):
            return (not getattr(unit, "is_worker", False)
                    and not getattr(unit, "is_structure", False)
                    and (getattr(unit, "can_attack_ground", False)
                         or getattr(unit, "can_attack_air", False)))

        def close(unit, others, distance):
            return any(unit.distance_to(other) <= distance for other in others)

        def weighted_supply(units):
            total = 0.0
            for unit in units:
                try:
                    weight = float(ai.calculate_supply_cost(unit.type_id))
                    maximum = float(unit.health_max + unit.shield_max)
                    current = float(unit.health + unit.shield)
                except (AttributeError, KeyError, TypeError, ValueError):
                    return None  # Unknown unit data must not become free enemy strength.
                if weight <= 0 or maximum <= 0:
                    return None
                total += weight * max(0.0, min(1.0, current / maximum))
            return total

        own = [u for u in ai.units if combat(u)]
        enemies = [u for u in enemies if combat(u)]
        local_enemies = [u for u in enemies
                         if close(u, own, 18) or close(u, ai.townhalls, 25)]
        local_own = [u for u in own if close(u, local_enemies, 18)]
        local_defences = [u for u in getattr(ai, "structures", [])
                          if getattr(u, "is_ready", True)
                          and (getattr(u, "can_attack_ground", False)
                              or getattr(u, "can_attack_air", False))
                          and close(u, local_enemies, 18)]
        cue = dict(stance="uncertain", emotion="谨慎、嘴硬、试探",
                   scope="Visible local engagement only; hidden forces and global advantage unknown.",
                   evidence=[])
        if not local_enemies:
            cue["evidence"].append("no_current_visible_local_engagement")
            return cue
        # Detect a concrete local mismatch before any supply estimate: many
        # ground-only tanks cannot justify boasting at an airborne opponent.
        air = any(getattr(u, "is_flying", False) for u in local_enemies)
        ground = any(not getattr(u, "is_flying", False) for u in local_enemies)
        defenders = local_own + local_defences
        missing_air = air and not any(getattr(u, "can_attack_air", False) for u in defenders)
        missing_ground = ground and not any(getattr(u, "can_attack_ground", False) for u in defenders)
        damaged_base = any(
            getattr(base, "health_percentage", 1.0) < 0.4
            and close(base, local_enemies, 25) for base in ai.townhalls)
        if missing_air or missing_ground or damaged_base:
            cue.update(stance="disadvantage", emotion="慌张、紧张、强装镇定")
            if missing_air:
                cue["evidence"].append("visible_local_air_threat_without_nearby_anti_air")
            if missing_ground:
                cue["evidence"].append("visible_local_ground_threat_without_nearby_ground_defence")
            if damaged_base:
                cue["evidence"].append("own_low_health_base_under_visible_attack")
            return cue
        if local_defences:
            # Building supply is zero and is not a fair army-strength proxy.
            cue["evidence"].append("own_static_defences_present_strength_not_compared")
            return cue
        ours, theirs = weighted_supply(local_own), weighted_supply(local_enemies)
        if ours is None or theirs is None:
            cue["evidence"].append("unknown_local_unit_strength")
            return cue
        cue.update(own_local_health_weighted_supply=round(ours, 2),
                   visible_enemy_local_health_weighted_supply=round(theirs, 2))
        if theirs >= 1.8 * max(ours, 1.0):
            cue.update(stance="disadvantage", emotion="慌张、紧张、强装镇定")
            cue["evidence"].append("visible_local_combat_force_is_much_larger_than_mine")
        elif ours >= 1.8 * max(theirs, 1.0):
            cue.update(stance="advantage", emotion="得意、自信、轻度挑衅")
            cue["evidence"].append("my_local_combat_force_is_much_larger_than_visible_opponent")
        else:
            cue["evidence"].append("visible_local_forces_not_clearly_one_sided")
        return cue

    async def _send(self, text, kind):
        # Only the mandated greeting may span messages. Generated replies are
        # one short bubble, even if the model ignores the requested length.
        messages = chunks(text) if kind == "greeting" else chunks(chat_text(text))[:1]
        for message in messages:
            if message:
                await self.ai.chat_send(message, team_only=False)
                self._event("sent", kind=kind, text=message)
        if messages:
            self._history.append("".join(messages))
            self._last_sent = float(self.ai.time)
            self._next_comment = self._last_sent + self.rng.uniform(60, 120)

    async def step(self):
        if self._closed:
            return
        now, wall = float(self.ai.time), self.clock()
        self._incoming(now)
        if not self._greeted:
            self._greeted = True
            await self._send(GREETING, "greeting")
            return
        result = self.worker.poll()
        if result is not None:
            pending, self._inflight = self._inflight, None
            if pending and result.get("ok") and wall - pending["wall"] <= 30 and now - pending["game"] <= 45:
                content = chat_text(result.get("content", ""))
                if content:
                    await self._send(content, pending["kind"])
            elif pending:
                self._event("response_skipped", reason="failed_or_stale")
        if self.worker.busy or self._inflight is not None:
            return
        while self._pending_human and now - self._pending_human[0]["game_seconds"] > 120:
            self._pending_human.popleft()
        reply = bool(self._pending_human) and now - self._last_sent >= 15
        if not reply and now < self._next_comment:
            return
        if wall - self._last_submit_wall < 10:
            return
        kind = "reply" if reply else "comment"
        messages = list(self._pending_human) if reply else []
        payload = dict(kind=kind, game_seconds=round(now, 2),
                       speaker=dict(identity="小鲸鱼，当前Terran参赛Agent", perspective="first_person",
                                    me="the agent's own army and bases", opponent="the human Terran player"),
                       battlefield=self._snapshot(),
                       human_messages=messages, recent_bot_messages=list(self._history)[-6:])
        if self.worker.submit(payload):
            self._last_submit_wall = wall
            self._inflight = dict(kind=kind, wall=wall, game=now)
            if kind == "comment":
                # A provider failure is not permission to retry each game step.
                self._next_comment = now + self.rng.uniform(60, 120)
            if reply:
                self._pending_human.clear()
            self._event("requested", kind=kind)

    def close(self):
        if self._closed:
            return
        self._closed = True
        try:
            self.worker.close()
        except Exception:
            pass
        self._event("closed")
        if self._log is not None:
            try:
                self._log.close()
            except OSError:
                pass


def start_banter(ai):
    if not getattr(ai.options, "chat", False):
        return None
    worker = None
    try:
        from bot.banter_client import BanterSettings, Worker
        settings = BanterSettings.load(Path(__file__).resolve().parents[1] / ".env.chat.local")
        worker = Worker(settings)
        return BanterRuntime(ai, worker)
    except Exception:
        # Never serialize exceptions: provider errors and configuration parsers
        # may include credentials. No fallback to the strategic API key.
        print("Game chat unavailable; continuing gameplay without chat.", flush=True)
        if worker is not None:
            try:
                worker.close()
            except Exception:
                pass
        return None
