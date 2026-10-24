"""One background request, bounded result queue, no credentials in diagnostics."""
from dataclasses import dataclass, field
import json
import os
from pathlib import Path
import queue
import threading
import time

import requests


def private_values(path):
    values = {}
    if Path(path).is_file():
        for line in Path(path).read_text(encoding="utf-8-sig").splitlines():
            name, sep, value = line.strip().partition("=")
            if sep and name.startswith("DEEPSEEK_"):
                values[name] = value.strip().strip("\"'")
    return values


@dataclass(frozen=True)
class Settings:
    api_key: str = field(repr=False)
    base_url: str = "https://api.deepseek.com"
    model: str = "deepseek-flash"

    @classmethod
    def load(cls, path):
        values = private_values(path)

        def get(name, default=""):
            return os.environ.get(name, values.get(name, default))

        key = get("DEEPSEEK_API_KEY")
        if not key:
            raise ValueError("Missing DEEPSEEK_API_KEY in environment or .env.local")
        base = get("DEEPSEEK_BASE_URL", "https://api.deepseek.com").rstrip("/")
        # This adapter is deliberately limited to the already authorized provider.
        if base not in ("https://api.deepseek.com", "https://api.deepseek.com/v1"):
            raise ValueError("DeepSeek base URL must use the official HTTPS endpoint")
        model = get("DEEPSEEK_MODEL", "deepseek-flash")
        if model != "deepseek-flash":
            raise ValueError("This validated adapter uses deepseek-flash")
        return cls(key, base, model)


EXAMPLE = {
    "schema_version": "strategy-v1",
    "request_id": "COPY_FROM_SNAPSHOT",
    "snapshot_seq": 1,
    "stance": "defend_then_expand",
    "economy": {"worker_target": 72, "base_target": 4},
    "production_profile": "marine_tank_medivac",
    "research_priority": [],
    "squad_tasks": [{"squad_id": "main", "task": "rally", "target_id": "own_natural"}],
    "attack_gate": {"min_army_supply": 20},
    "reason_summary": "Build a stable economy",
}
SYSTEM = """You are the strategic commander of a local StarCraft II Terran bot.
Return only a JSON object matching the example exactly, copying request_id and snapshot_seq.
You control goals; Ares handles execution. Choose production_profile:
marine_tank_medivac (Marine80%/Tank12%/Medivac8%),
marine_basic (all Marines), marine_marauder_medivac (Marine65%/Marauder25%/Medivac10%),
reaper_pressure (Marine35%/Reaper65%), or ghost_support
(Marine65%/Marauder15%/Ghost10%/Medivac10%). Fractions are unit counts, not supply.
Marauders require Barracks TechLab; Reapers need Barracks and gas; Ghosts need
Barracks TechLab and Ghost Academy. Local Ares builds prerequisites/refineries.
Use Marauders versus armored ground units; they cannot attack air. Reapers have
basic ground attack only, no harassment or grenade controller. Ghosts have basic
attack only; no EMP, Snipe, cloak or nuke controller yet. These infantry use rules,
only Marines use PPO. Medivacs heal/follow, no drops; Tanks siege/unsiege by rules.
Prefer suitable mixed production against visible evidence rather than always
choosing advanced tech. No research, coordinates, raw actions or extra
keys. Never assume hidden enemy units. A requested tech profile takes time and resources.
stance: develop|defend_then_expand|pressure. worker_target integer16..80, base_target1..4.
Only squad main. task attack targets enemy_main; defend/rally/retreat target own_main or
own_natural. own_natural falls back to own_main until ready. min_army_supply integer6..60.
reason_summary at most160 characters, concise rationale only. Local emergency defense
always overrides you. Plans expire45 game seconds from snapshot; changes commit30 seconds.
previous_human_match_experience, when present, contains bounded lessons from previous
human matches. Use them to adjust your goals; they are experience, not current enemy facts.
Local economy starts expanding after120 seconds with20 workers, unlocks third at360
and fourth at540 seconds; visible threats and Ares location safety gate construction.
economy_policy shows effective saturation goals and gas staffing. Local mineral depletion
or saturation can raise your requested goals; do not treat two bases/44 workers as final.
Prioritize replacement workers and mineral income; surplus gas reduces refinery staffing
with hysteresis, restoring three when gas runs low. Retain sensible goals over
successive snapshots. Avoid indefinite rally/defense when no threat. Marine attack size
20..30 is an initial target; opponent difficulty follows the run configuration (default CheatInsane), so adjust to visible evidence. Snapshot
enemy_memory lists last-seen facts, not current visibility. Attack enemy_main execution
automatically seeks observed buildings then searches expansions. Budget is at most4 bases and80 workers.
Example JSON: """ + json.dumps(
    EXAMPLE, separators=(",", ":")
)


def request(settings, snapshot_json):
    """No SDK retry; the game scheduler owns retries and backoff."""
    started = time.monotonic()
    result = {"ok": False}
    try:
        with requests.post(
            settings.base_url + "/chat/completions",
            headers={"Authorization": "Bearer " + settings.api_key},
            json={
                "model": settings.model,
                "messages": [
                    {"role": "system", "content": SYSTEM},
                    {"role": "user", "content": snapshot_json},
                ],
                "response_format": {"type": "json_object"},
                "max_tokens": 768,
                "thinking": {"type": "disabled"},
            },
            timeout=(5, 15),
        ) as response:
            result["http_status"] = response.status_code
            if response.status_code != 200:
                result["error"] = "http_status"
            else:
                data = response.json()
                content = data["choices"][0]["message"]["content"]
                if not isinstance(content, str) or len(content) > 10000:
                    raise ValueError("content")
                # Discard reasoning and provider error bodies; only this contract is used.
                content = content.replace(settings.api_key, "[REDACTED]")
                result.update(
                    ok=True,
                    content=content,
                    usage={
                        k: v
                        for k, v in data.get("usage", {}).items()
                        if k in ("prompt_tokens", "completion_tokens", "total_tokens")
                        and type(v) is int
                    },
                )
    except requests.Timeout:
        result["error"] = "network_timeout"
    except requests.RequestException:
        result["error"] = "network_error"
    except (ValueError, KeyError, IndexError, TypeError):
        result["error"] = "response_format"
    result["latency_seconds"] = time.monotonic() - started
    return result


class Worker:
    def __init__(self, settings, transport=request):
        self.settings, self.transport = settings, transport
        self.results = queue.Queue(maxsize=1)
        self.thread = None
        self.closed = False

    @property
    def busy(self):
        return self.thread is not None and self.thread.is_alive()

    def submit(self, snapshot_json):
        if self.closed or self.busy or not self.results.empty():
            return False

        def run():
            try:
                result = self.transport(self.settings, snapshot_json)
            except Exception:
                result = {"ok": False, "error": "worker_error"}
            self.results.put_nowait(result)

        self.thread = threading.Thread(target=run, name="strategy-http", daemon=True)
        self.thread.start()
        return True

    def poll(self):
        try:
            return self.results.get_nowait()
        except queue.Empty:
            return None

    def close(self):
        self.closed = True
        # Never wait for HTTP in the SC2 event loop. Daemon dies on process exit.
