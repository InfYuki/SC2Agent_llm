"""Offline, post-match opponent evidence; never produces PPO training samples.

Uses Blizzard s2protocol and mpyq. Install the optional parser into
.local-setup/replay-analysis without changing the game environment. A different
protocol build is accepted only when explicitly requested/configured and recorded.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path
import sys

ROOT = Path(__file__).resolve().parents[1]
OPTIONAL = ROOT / ".local-setup" / "replay-analysis"

# Bounded Terran army vocabulary, including the air threat from the recent games.
# Tracker morph names are retained as evidence, not counted as extra births.
ARMY_TYPES = {"Marine", "Marauder", "Reaper", "Ghost", "SiegeTank", "SiegeTankSieged",
              "Hellion", "HellionTank", "WidowMine", "WidowMineBurrowed", "Cyclone",
              "Thor", "ThorAP", "Medivac", "VikingFighter", "VikingAssault", "Banshee",
              "Raven", "Liberator", "LiberatorAG", "Battlecruiser"}


def read(path):
    return json.loads(Path(path).read_text(encoding="utf-8-sig"))


def write(path, value):
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, ensure_ascii=False, indent=2,
                                    allow_nan=False), encoding="utf-8")
    temporary.replace(path)


def decoded(value):
    return value.decode("utf-8", errors="replace") if isinstance(value, bytes) else value


def analyze(run_dir, *, protocol_build=None, human_name="HumanTerran", memory_dir=None):
    run_dir = Path(run_dir).resolve()
    summary = read(run_dir / "summary.json")
    manifest = read(run_dir / "manifest.json")
    if (summary.get("status") != "completed" or summary.get("error")
            or summary.get("stop_reason") or not manifest["config"].get("human_training")):
        raise ValueError("Only naturally completed human-training games may be analyzed")
    sys.path.insert(0, str(OPTIONAL))
    import mpyq
    from s2protocol import versions
    replay = run_dir / "game.SC2Replay"
    archive = mpyq.MPQArchive(str(replay))
    header = versions.latest().decode_replay_header(archive.header["user_data_header"]["content"])
    actual_build = header["m_version"]["m_baseBuild"]
    requested_build = actual_build if protocol_build is None else protocol_build
    selection = "exact_schema" if protocol_build is None else "explicit_cli_override"
    try:
        protocol = versions.build(requested_build)
    except ImportError as error:
        config_path = Path(memory_dir) / "replay_protocol.json" if memory_dir else None
        config = read(config_path) if config_path and config_path.is_file() else {}
        # This is a deliberately explicit, locally validated pair, not a
        # nearest-version heuristic. A future exact schema always wins.
        permitted = (protocol_build is None and actual_build == 98370
                     and config.get("format") == "human-replay-protocol-v1"
                     and config.get("compatibility_overrides") == {"98370": 98310})
        if not permitted:
            raise ValueError(f"No exact replay schema for build {requested_build}; "
                             "install a matching s2protocol or explicitly select --protocol-build") from error
        requested_build = 98310
        selection = "persisted_explicit_compatibility_pair"
        protocol = versions.build(requested_build)
    details = protocol.decode_replay_details(archive.read_file("replay.details"))
    players = details["m_playerList"]
    human_slots = [i + 1 for i, player in enumerate(players) if decoded(player["m_name"]) == human_name]
    if len(players) != 2 or len(human_slots) != 1:
        raise ValueError("Replay must have two players and one exact human name match")
    human_id = human_slots[0]
    agent_id = 3 - human_id
    agent_result = {1: "Result.Victory", 2: "Result.Defeat", 3: "Result.Tie"}.get(players[agent_id - 1]["m_result"])
    if agent_result != summary["result"]:
        raise ValueError("Replay/summary outcome mismatch")
    events = list(protocol.decode_replay_tracker_events(archive.read_file("replay.tracker.events")))
    final_loop = header["m_elapsedGameLoops"]
    if (not events or any(e["_gameloop"] > final_loop for e in events)
            or abs(final_loop / 22.4 - summary["game_span_seconds"]) > 2):
        raise ValueError("Replay tracker/header/summary timing mismatch")
    known, timeline, stats, born = {}, [], [], Counter()
    for event in events:
        name = event["_event"].split(".")[-1]
        time = round(event["_gameloop"] / 22.4, 3)
        tag = (event.get("m_unitTagIndex"), event.get("m_unitTagRecycle"))
        if name in {"SUnitInitEvent", "SUnitBornEvent"}:
            kind = decoded(event["m_unitTypeName"])
            known[tag] = (kind, event.get("m_controlPlayerId"))
            if event.get("m_controlPlayerId") == human_id and not kind.startswith("Beacon"):
                if name == "SUnitBornEvent":
                    born[kind] += 1
                timeline.append(dict(seconds=time, loop=event["_gameloop"],
                                     event="construction_started" if name == "SUnitInitEvent" else "created",
                                     unit=kind, x=event.get("m_x"), y=event.get("m_y")))
        elif name == "SUnitDoneEvent" and known.get(tag, (None, None))[1] == human_id:
            timeline.append(dict(seconds=time, loop=event["_gameloop"],
                                 event="construction_completed", unit=known[tag][0]))
        elif name == "SUnitTypeChangeEvent" and known.get(tag, (None, None))[1] == human_id:
            kind = decoded(event["m_unitTypeName"])
            timeline.append(dict(seconds=time, loop=event["_gameloop"], event="morphed", unit=kind))
            known[tag] = (kind, human_id)
        elif name == "SUpgradeEvent" and event["m_playerId"] == human_id:
            kind = decoded(event["m_upgradeTypeName"])
            if not kind.startswith("Spray"):
                timeline.append(dict(seconds=time, loop=event["_gameloop"], event="upgrade_completed", unit=kind))
        elif name == "SPlayerStatsEvent" and event["m_playerId"] == human_id:
            values = event["m_stats"]
            stats.append(dict(seconds=time, workers=values["m_scoreValueWorkersActiveCount"],
                              supply_used=values["m_scoreValueFoodUsed"] / 4096,
                              minerals=values["m_scoreValueMineralsCurrent"],
                              gas=values["m_scoreValueVespeneCurrent"],
                              mineral_rate=values["m_scoreValueMineralsCollectionRate"],
                              gas_rate=values["m_scoreValueVespeneCollectionRate"]))
    key_types = {"SupplyDepot", "Barracks", "Refinery", "CommandCenter", "OrbitalCommand",
                 "Factory", "FactoryTechLab", "Starport", "StarportReactor", "Bunker",
                 "EngineeringBay", "Armory", "FusionCore"} | ARMY_TYPES
    milestones = []
    seen = Counter()
    for row in timeline:
        kind, event = row["unit"], row["event"]
        if kind not in key_types or event == "construction_completed":
            continue
        seen[kind, event] += 1
        if seen[kind, event] <= (3 if kind in {"CommandCenter", "SiegeTank", "Medivac"} else 1):
            milestones.append(dict(row, ordinal=seen[kind, event]))
    profile = dict(format="human-replay-profile-v1", source_run_id=run_dir.name,
                   evidence_scope="post-match full-information replay; NOT current live vision; one game only",
                   replay_sha256=hashlib.sha256(replay.read_bytes()).hexdigest(),
                   actual_replay_build=actual_build, decoder_schema_build=requested_build,
                   compatibility_override=requested_build != actual_build,
                   decoder_selection=selection,
                   integrity_checks=["two named player slots", "agent outcome equals summary",
                                     "tracker loops bounded by replay header", "duration agrees within 2 game seconds"],
                   parser_reference="https://github.com/Blizzard/s2protocol",
                   human_name=human_name, human_player_id=human_id,
                   duration_seconds=round(final_loop / 22.4, 3),
                   human_result="Victory" if agent_result == "Result.Defeat" else "Defeat" if agent_result == "Result.Victory" else "Tie",
                   milestones=milestones, cumulative_units_created=dict(born),
                   peak_workers=max(s["workers"] for s in stats),
                   peak_supply=max(s["supply_used"] for s in stats),
                   final_economy=stats[-1])
    result_dir = run_dir / "replay_analysis"
    write(result_dir / "human_build_timeline.json", dict(profile=profile, timeline=timeline, economy_samples=stats))
    write(result_dir / "opponent_profile.json", profile)
    if memory_dir is not None:
        update_memory(Path(memory_dir), profile)
    return profile


def update_memory(memory_dir, profile):
    # Offline inspection may remain available; publishing lessons requires consent.
    if str(ROOT) not in sys.path:
        sys.path.insert(0, str(ROOT))
    from tools.human_learning_approval import learning_block
    run_id = profile.get("source_run_id", "")
    if not run_id or Path(run_id).name != run_id or run_id in {".", ".."}:
        raise ValueError("Invalid replay source run identity")
    blocked = learning_block(ROOT / "artifacts" / "runs" / run_id)
    if blocked:
        raise ValueError("Replay memory update blocked: " + blocked)
    path = memory_dir / "strategy_memory.json"
    memory = read(path) if path.is_file() else dict(format="human-strategy-memory-v1", matches_seen=0, recent_matches=[], lessons=[])
    if memory.get("format") != "human-strategy-memory-v1":
        raise ValueError("Unsupported strategy memory")
    # This is a compact post-game study, explicitly not a live-state estimate.
    brief = {key: profile[key] for key in ("format", "source_run_id", "evidence_scope", "replay_sha256",
             "actual_replay_build", "decoder_schema_build", "compatibility_override", "peak_workers")}
    selected = [r for r in profile["milestones"] if r["unit"] in
                {"CommandCenter", "Factory", "Starport", "FusionCore", "Armory"} | ARMY_TYPES]
    # Preserve first Battlecruiser/Factory unit timings before repeated macro events
    # fill the prompt budget. Chronology remains explicit in each row's seconds.
    first_army = [r for r in selected if r["unit"] in ARMY_TYPES and r["event"] == "created"
                  and r.get("ordinal") == 1]
    chosen = first_army + [r for r in selected if r not in first_army]
    brief["milestones"] = sorted([{k: r[k] for k in ("seconds", "event", "unit", "ordinal")}
                                  for r in chosen[:18]], key=lambda r: r["seconds"])
    brief["army_created"] = {k: v for k, v in profile["cumulative_units_created"].items()
                             if k in ARMY_TYPES}
    records = memory.setdefault("recent_matches", [])
    record = next((r for r in records if r.get("run_id") == profile["source_run_id"]), None)
    if record is None:
        record = dict(run_id=profile["source_run_id"], evidence_scope="post-match replay only")
        records.append(record)
    record["postmatch_replay_profile"] = brief
    observed_army = ", ".join(f"{v} {k}" for k, v in brief["army_created"].items())
    lessons = [
        "Post-match replay study of one human game is historical training knowledge, not current enemy vision or a fixed opponent habit; scout before adapting.",
        "Human cumulative units created in the studied game: " + observed_army + ". These are production totals, not simultaneous army size; past timing evidence is in postmatch_replay_profile.",
        "The human reached " + str(profile["peak_workers"]) + " active workers in the studied game; do not stop economic growth at 20-36 workers when safe expansion and supported production are available.",
    ]
    if brief["army_created"].get("SiegeTank"):
        lessons.append("The studied human used Siege Tanks. Prepare supported combined arms and avoid blindly sending Marines into a currently observed siege line; this is a planning hypothesis, not proof of a fixed opponent build.")
    if brief["army_created"].get("Battlecruiser"):
        lessons.append("The studied human produced Battlecruisers. Scout current air threats and choose supported anti-air production rather than relying on ground-only damage; past replay evidence does not prove the next build or any counter's effectiveness.")
    # Shared old lessons had no per-line provenance. Rebuild from retained match
    # evidence instead of keeping stale army summaries that omitted air units.
    prior = []
    for previous in reversed(records):
        prior.extend(previous.get("notes", []))
        evidence = previous.get("postmatch_replay_profile", {})
        army = evidence.get("army_created", {})
        if army and previous is not record:
            prior.append("Historical replay " + str(previous.get("run_id")) +
                         " cumulative army: " + ", ".join(f"{v} {k}" for k, v in army.items()) +
                         ". Production totals, not current enemy vision.")
    memory["lessons"] = list(dict.fromkeys(lessons + prior))[:8]
    memory["recent_matches"] = records[-8:]
    memory["updated_at_utc"] = datetime.now(timezone.utc).isoformat()
    write(path, memory)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", required=True, type=Path)
    parser.add_argument("--protocol-build", type=int)
    parser.add_argument("--memory-dir", type=Path)
    args = parser.parse_args()
    profile = analyze(args.run_dir, protocol_build=args.protocol_build, memory_dir=args.memory_dir)
    print(json.dumps(profile, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
