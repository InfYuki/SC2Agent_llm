"""Exclude a human match without deleting evidence or undoing valid PPO successors.

Automatic cleanup is deliberately restricted to matches with no PPO update.
An updated PPO model cannot be unlearned by subtracting its gradients later.
"""
import argparse
from datetime import datetime, timezone
import hashlib
import json
from pathlib import Path


def read(path, default=None):
    return json.loads(path.read_text(encoding="utf-8-sig")) if path.is_file() else default


def write(path, value):
    path.parent.mkdir(parents=True, exist_ok=True)
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(value, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def rebuild_lessons(records):
    """Rebuild only from retained records: old shared lessons have no provenance."""
    lessons = []
    for record in records:
        additions = list(record.get("notes", []))
        profile = record.get("postmatch_replay_profile", {})
        if profile:
            army = profile.get("army_created", {})
            additions += [
                "Post-match replay study of one human game is historical training knowledge, not current enemy vision or a fixed opponent habit; scout before adapting.",
                "Human cumulative units created in the studied game: " + ", ".join(f"{v} {k}" for k, v in army.items()) + ". These are production totals, not simultaneous army size; past timing evidence is in postmatch_replay_profile.",
                "The human reached " + str(profile.get("peak_workers")) + " active workers in the studied game; do not stop economic growth at 20-36 workers when safe expansion and supported production are available.",
            ]
            if army.get("SiegeTank"):
                additions.append("The studied human used Siege Tanks. Prepare supported combined arms and avoid blindly sending Marines into a currently observed siege line; this is a planning hypothesis, not proof of a fixed opponent build.")
        lessons = list(dict.fromkeys(additions + lessons))[:8]
    return lessons


def exclude(run_dir, memory_dir, reason):
    run_dir, memory_dir = Path(run_dir).resolve(), Path(memory_dir).resolve()
    if not (run_dir / "human_training.json").is_file():
        raise ValueError("Not a human training run")
    learning = read(run_dir / "learning_report.json", {})
    if learning.get("ppo", {}).get("status") == "updated":
        raise ValueError("PPO already updated: inspect successor model lineage before choosing a rollback; automatic exclusion cleanup refused")
    marker = run_dir / "learning_excluded.json"
    memory_path = memory_dir / "strategy_memory.json"
    memory = read(memory_path, {})
    records = memory.get("recent_matches", [])
    retained = [r for r in records if r.get("run_id") != run_dir.name]
    removed = len(records) - len(retained)
    if marker.exists():
        # Recover an interruption between the permanent block and memory write.
        if removed:
            memory.update(recent_matches=retained,
                          matches_seen=max(0, memory.get("matches_seen", len(records)) - removed),
                          lessons=rebuild_lessons(retained))
            write(memory_path, memory)
        return read(marker)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%S%fZ")
    backup = run_dir / "learning_exclusion_backup" / stamp
    backup.mkdir(parents=True)
    if memory_path.exists():
        (backup / "strategy_memory.json").write_bytes(memory_path.read_bytes())
    pointer = memory_dir / "ppo_latest.json"
    pointer_hash = hashlib.sha256(pointer.read_bytes()).hexdigest() if pointer.exists() else None
    audit = dict(format="human-learning-exclusion-v1", source_run_id=run_dir.name,
                 excluded=True, reason=reason, timestamp_utc=stamp, backup=str(backup),
                 removed_memory_records=removed, ppo_action="unchanged_no_update_from_excluded_match",
                 ppo_latest_sha256=pointer_hash,
                 caveat="Later matches may already have read this historical LLM memory; past decisions cannot be undone. Raw evidence and original learning report retained.")
    # Write permanent block before removing memory. It blocks accidental relearning.
    write(marker, audit)
    if removed:
        memory.update(recent_matches=retained,
                      matches_seen=max(0, memory.get("matches_seen", len(records)) - removed),
                      lessons=rebuild_lessons(retained), updated_at_utc=stamp)
        write(memory_path, memory)
    return audit


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--run-dir", type=Path, required=True)
    parser.add_argument("--memory-dir", type=Path, required=True)
    parser.add_argument("--reason", required=True)
    args = parser.parse_args()
    print(json.dumps(exclude(args.run_dir, args.memory_dir, args.reason), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
