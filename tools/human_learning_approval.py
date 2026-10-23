"""Explicit post-match consent shared by launcher and all human learning paths."""
import json
from datetime import datetime, timezone
from pathlib import Path


def learning_block(run_dir):
    run_dir = Path(run_dir)
    metadata = json.loads((run_dir / "human_training.json").read_text(encoding="utf-8")) if (run_dir / "human_training.json").is_file() else {}
    if (run_dir / "learning_excluded.json").exists() or metadata.get("learning_exclusion"):
        return "permanently_excluded"
    path = run_dir / "learning_decision.json"
    decision = json.loads(path.read_text(encoding="utf-8")) if path.is_file() else {}
    if decision.get("format") != "human-learning-decision-v1" or decision.get("run_id") != run_dir.name or decision.get("status") != "approved":
        return "learning_not_approved"
    return None


def decide(run_dir, mode="ask", *, input_fn=input, interactive=None):
    run_dir = Path(run_dir)
    # A yes cannot clear an exclusion. Validate before writing any decision.
    if learning_block(run_dir) == "permanently_excluded":
        raise ValueError("This match is permanently excluded from learning")
    if mode == "ask":
        import sys
        interactive = sys.stdin.isatty() if interactive is None else interactive
        answer = ""
        if interactive:
            try:
                answer = input_fn("Learn from this match (LLM + PPO + replay)? [y/N; Enter=pending]: ").strip().lower()
            except (EOFError, KeyboardInterrupt):
                pass
        status = "approved" if answer in ("y", "yes") else "skipped" if answer in ("n", "no") else "pending"
    else:
        status = "approved" if mode == "yes" else "skipped"
    run_dir.mkdir(parents=True, exist_ok=True)
    path = run_dir / "learning_decision.json"
    payload = dict(format="human-learning-decision-v1", run_id=run_dir.name, status=status,
                   decided_at_utc=datetime.now(timezone.utc).isoformat(), source="explicit_user_yes" if status == "approved" else "user_or_no_input")
    temporary = path.with_suffix(".tmp")
    temporary.write_text(json.dumps(payload, indent=2), encoding="utf-8")
    temporary.replace(path)
    return status
