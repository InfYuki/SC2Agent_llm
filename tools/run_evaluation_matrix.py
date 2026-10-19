"""Frozen, sequential E0--E4 engineering batches (stdlib only).

Default invocation writes a plan and starts NO game. Example, zero HTTP calls:
  python -s tools/run_evaluation_matrix.py --modes E0 E2
  python -s tools/run_evaluation_matrix.py --resume artifacts/evaluation_batches/ID --execute

One attempt per selected arm, ordered E0..E4. --llm-max-calls is a TOTAL
reservation across E1/E4 (0 by default, at most 20); unused calls are never
reassigned. LLM arms still load their normal local settings when executed.
Resume only runs pending attempts; failed/unknown/interrupted attempts stay final.
A stale execution.lock requires manual PID inspection and removal after its owner
has exited. Never remove a live owner's lock. No active latest_state is read.
An additional repository execution lock prevents concurrent games from this
runner across batches; it does not coordinate other SC2 launchers.
"""
import argparse
from collections import Counter
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import subprocess
import sys
import time
import uuid

ROOT = Path(__file__).resolve().parents[1]
MODES = {"E0": "rule", "E1": "llm", "E2": "rule_bc",
         "E3": "rule_ppo", "E4": "llm_ppo"}
COMMON = dict(map="Ancient Cistern LE", opponent="Zerg", difficulty="Easy",
              realtime=False, game_step=8, seed=20261020, max_game_seconds=1200,
              micro_max_units=4, wall_timeout=600)
SOURCE_SUFFIXES = {".py", ".yml", ".yaml", ".toml", ".lock", ".SC2Map"}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True).encode()).hexdigest()


def save(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2, ensure_ascii=True) + "\n", encoding="utf-8")
    os.replace(temporary, path)


def git(root, *args):
    return subprocess.check_output(["git", *args], cwd=root, text=True).strip()


def source_identity(root):
    # Explicit extensions exclude credentials, logs, datasets and model outputs.
    # Include untracked source too: an uncommitted implementation is still frozen.
    hashes = {}
    for prefix in (Path("."), Path("ares-sc2")):
        base = root / prefix
        names = git(base, "ls-files", "--cached", "--others", "--exclude-standard", "-z")
        for name in names.split("\0"):
            path = base / name
            if name and path.suffix in SOURCE_SUFFIXES and path.is_file():
                hashes[(prefix / name).as_posix()] = sha(path)
    return dict(project_commit=git(root, "rev-parse", "HEAD"),
                ares_commit=git(root / "ares-sc2", "rev-parse", "HEAD"),
                source_hashes=hashes, python=str(Path(sys.executable).resolve()),
                python_version=sys.version)


def model_identity(path, kind):
    path = path.resolve()
    hashes = {name: sha(path / name) for name in ("metadata.json", "weights.npz")}
    metadata = json.loads((path / "metadata.json").read_text(encoding="utf-8"))
    contract = dict(format=f"marine-{kind}-numpy-v1", feature_version="marine-16-v1",
                    action_version="marine-5-v1", decision_game_loops=8,
                    architecture=[16, 64, 64, 5], activation="tanh", normalization="marine-16-v1")
    if any(metadata.get(k) != v for k, v in contract.items()):
        raise ValueError(f"{kind} metadata contract mismatch")
    if metadata.get("weights_sha256") != hashes["weights.npz"]:
        raise ValueError(f"{kind} weights hash mismatch")
    return dict(path=str(path), sha256=hashes)


def map_identity(game_path, name):
    # Mirrors installed sc2.maps.get: exact stem/suffix, Maps + one subfolder.
    # Refuse duplicates instead of depending on filesystem iteration order.
    base = Path(game_path) / "Maps"
    candidates = []
    for entry in base.iterdir():
        for path in entry.iterdir() if entry.is_dir() else (entry,):
            if path.is_file() and path.suffix == ".SC2Map" and path.stem == name:
                candidates.append(path.resolve())
    if len(candidates) != 1:
        raise ValueError("selected installed map must have exactly one match")
    return dict(path=str(candidates[0]), sha256=sha(candidates[0]))


def make_plan(root, args, batch_id):
    selected = [e for e in MODES if e in args.modes]
    models = {}
    if "E2" in selected:
        models["bc"] = model_identity(Path(args.bc_model), "bc")
    if any(e in selected for e in ("E3", "E4")):
        models["ppo"] = model_identity(Path(args.ppo_model), "ppo")
    llm = [e for e in selected if e in ("E1", "E4")]
    if args.llm_max_calls and not llm:
        raise ValueError("LLM budget requires E1 or E4")
    attempts = []
    for e in selected:
        index = llm.index(e) if e in llm else None
        cap = (args.llm_max_calls // len(llm) + (index < args.llm_max_calls % len(llm))) if index is not None else 0
        attempts.append(dict(experiment=e, mode=MODES[e], run_id=f"{batch_id}_{e}", llm_max_calls=int(cap)))
    return dict(schema=1, batch_id=batch_id, scope="engineering only; no strength inference",
                created_utc=datetime.now(timezone.utc).isoformat(), common=COMMON.copy(),
                game_path=str(Path(args.game_path).resolve()), models=models,
                installed_map=map_identity(args.game_path, COMMON["map"]),
                llm_total_call_cap=args.llm_max_calls, max_games=len(attempts),
                inputs=source_identity(root), attempts=attempts,
                limitations=["game build and remote provider behavior are not frozen",
                            "NPZ content is hash-checked; actor runtime performs tensor validation",
                            "missing raw manifests remain unmapped in the offline report"])


def validate(root, plan, state):
    if digest(plan) != state["plan_sha256"]:
        raise ValueError("frozen plan changed")
    if source_identity(root) != plan["inputs"]:
        raise ValueError("source/interpreter identity changed; create a new batch")
    if map_identity(plan["game_path"], plan["common"]["map"]) != plan["installed_map"]:
        raise ValueError("installed map changed; create a new batch")
    for kind, model in plan["models"].items():
        if model_identity(Path(model["path"]), kind) != model:
            raise ValueError("model identity changed; create a new batch")
    expected = [a["run_id"] for a in plan["attempts"]]
    if [a["run_id"] for a in state["attempts"]] != expected:
        raise ValueError("attempt inventory changed")
    if sum(a["llm_max_calls"] for a in plan["attempts"]) != plan["llm_total_call_cap"]:
        raise ValueError("invalid total LLM reservation")


def command(root, plan, attempt):
    result = [plan["inputs"]["python"], "-s", "-u", str(root / "run_local.py"),
              "--mode", attempt["mode"], "--run-id", attempt["run_id"],
              "--game-path", plan["game_path"], "--llm-max-calls", str(attempt["llm_max_calls"])]
    for key, value in plan["common"].items():
        if key == "wall_timeout":
            continue
        if key == "realtime":
            result.append("--realtime" if value else "--no-realtime")
        else:
            result.extend(["--" + key.replace("_", "-"), str(value)])
    for kind in ("bc", "ppo"):
        if kind in plan["models"] and ((kind == "bc" and attempt["experiment"] == "E2") or
                                        (kind == "ppo" and attempt["experiment"] in ("E3", "E4"))):
            result.extend([f"--{kind}-model", plan["models"][kind]["path"]])
    return result


def kill_owned(process):
    """Same PID-scoped Windows tree watchdog as tools/probe.py."""
    if process.poll() is None:
        subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True, check=False)
        process.wait(timeout=30)


def report(root, folder, plan, state):
    # All selected attempts remain in batch state, including ones with no raw run.
    state["counts"] = dict(Counter(a["status"] for a in state["attempts"]))
    try:
        from tools.report_evaluation_matrix import build_report, markdown
        paths = [root / "artifacts" / "runs" / a["run_id"] for a in state["attempts"]
                 if a["status"] not in ("pending", "collision")]
        result = build_report(paths)
        save(folder / "report.json", result)
        (folder / "report.md").write_text(markdown(result), encoding="utf-8")
        state["report_status"] = "written; collision/foreign raw excluded; use state.json for complete selected denominator and mode mapping"
    except Exception as exc:
        state["report_status"] = "failed:" + type(exc).__name__
    save(folder / "state.json", state)


def execute(root, folder, plan, state):
    validate(root, plan, state)
    if os.name != "nt":
        raise ValueError("execution watchdog currently supports Windows only")
    for row in state["attempts"]:
        if row["status"] == "running":
            row.update(status="interrupted", outcome="unknown", reason="prior owner exited; not rerun")
    save(folder / "state.json", state)
    try:
        for attempt, row in zip(plan["attempts"], state["attempts"]):
            if row["status"] != "pending":
                continue
            validate(root, plan, state)
            run = root / "artifacts" / "runs" / attempt["run_id"]
            if run.exists():
                row.update(status="collision", outcome="unknown", reason="run path already exists; never overwritten")
                save(folder / "state.json", state)
                continue
            row.update(status="running", started_utc=datetime.now(timezone.utc).isoformat())
            save(folder / "state.json", state)  # Reserve before Popen; ambiguous crashes never rerun.
            process = None
            started = time.monotonic()
            try:
                with (folder / f"{attempt['experiment']}.log").open("x", encoding="utf-8") as log:
                    process = subprocess.Popen(command(root, plan, attempt), cwd=root,
                        env=dict(os.environ, PYTHONIOENCODING="utf-8", PYTHONNOUSERSITE="1", PYTHONUNBUFFERED="1"),
                        stdout=log, stderr=subprocess.STDOUT)
                    row["pid"] = process.pid
                    save(folder / "state.json", state)
                    try:
                        code = process.wait(timeout=plan["common"]["wall_timeout"])
                        row.update(status="exited" if code == 0 else "failed", exit_code=code)
                    except subprocess.TimeoutExpired:
                        kill_owned(process)
                        row.update(status="timeout", outcome="unknown")
            except KeyboardInterrupt:
                if process is not None:
                    kill_owned(process)
                row.update(status="interrupted", outcome="unknown")
                raise
            except Exception as exc:
                if process is not None:
                    kill_owned(process)
                row.update(status="failed", outcome="unknown", reason=type(exc).__name__)
            finally:
                row["wall_seconds"] = time.monotonic() - started
                row["ended_utc"] = datetime.now(timezone.utc).isoformat()
                # Raw evidence is authoritative for a known outcome, never exit code.
                try:
                    from tools.report_evaluation_matrix import load_attempt
                    evidence = load_attempt(run)
                    row["evidence_category"] = evidence["category"]
                    row["outcome"] = evidence["outcome"]
                    if row["status"] == "exited":
                        row["status"] = evidence["category"]
                except Exception:
                    row.setdefault("outcome", "unknown")
                    if row["status"] == "exited":
                        row["status"] = "unknown"
                save(folder / "state.json", state)
    finally:
        report(root, folder, plan, state)
    return 0 if all(a["status"] == "completed" for a in state["attempts"]) else 1


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--execute", action="store_true", help="Launch games; without this, NO games or API calls")
    parser.add_argument("--resume", type=Path, help="Existing batch directory; only --execute may accompany it")
    parser.add_argument("--batch-dir", type=Path, help="New batch directory (must not exist)")
    parser.add_argument("--modes", choices=list(MODES), nargs="+", default=list(MODES))
    parser.add_argument("--llm-max-calls", type=int, default=0, help="TOTAL HTTP call reservation, split across E1/E4; 0..20")
    parser.add_argument("--bc-model", default=str(ROOT / "artifacts/models/marine_bc_mvp_20261018_seed42"))
    parser.add_argument("--ppo-model", default=str(ROOT / "artifacts/models/marine_ppo_curriculum256_20261019"))
    parser.add_argument("--game-path", default=os.getenv("SC2PATH", r"C:\Program Files (x86)\StarCraft II"))
    raw = list(sys.argv[1:] if argv is None else argv)
    args = parser.parse_args(raw)
    if not 0 <= args.llm_max_calls <= 20:
        parser.error("LLM total cap must be 0..20")
    if args.resume and any(token.split("=")[0] not in ("--resume", "--execute") for token in raw if token.startswith("--")):
        parser.error("resume freezes configuration; only --resume and --execute are accepted")
    try:
        if args.resume:
            folder = args.resume.resolve()
        else:
            folder = (args.batch_dir or ROOT / "artifacts/evaluation_batches" /
                      ("matrix_" + datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_") + uuid.uuid4().hex[:8])).resolve()
            plan = make_plan(ROOT, args, folder.name)
            folder.mkdir(parents=True, exist_ok=False)
            save(folder / "plan.json", plan)
            save(folder / "state.json", dict(plan_sha256=digest(plan), attempts=[
                dict(run_id=a["run_id"], experiment=a["experiment"], mode=a["mode"], status="pending", outcome="unknown")
                for a in plan["attempts"]]))
        # Same exclusive lock protects dry-run reads and every resume mutation.
        lock = folder / "execution.lock"
        with lock.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(dict(pid=os.getpid(), started_utc=datetime.now(timezone.utc).isoformat())))
        global_lock = None
        try:
            if args.execute:
                global_path = ROOT / "artifacts/evaluation_runner_execution.lock"
                global_path.parent.mkdir(parents=True, exist_ok=True)
                with global_path.open("x", encoding="utf-8") as stream:
                    stream.write(json.dumps(dict(pid=os.getpid(), batch=str(folder))))
                global_lock = global_path
            plan = json.loads((folder / "plan.json").read_text(encoding="utf-8"))
            state = json.loads((folder / "state.json").read_text(encoding="utf-8"))
            validate(ROOT, plan, state)
            print(json.dumps(dict(batch=str(folder), games_started=0 if not args.execute else "explicit execution",
                                  selected=[a["experiment"] for a in plan["attempts"]],
                                  max_games=plan["max_games"], llm_total_call_cap=plan["llm_total_call_cap"])), flush=True)
            return execute(ROOT, folder, plan, state) if args.execute else 0
        finally:
            if global_lock is not None:
                global_lock.unlink()
            lock.unlink()
    except (OSError, ValueError, KeyError, subprocess.SubprocessError) as exc:
        print("Batch refused: " + type(exc).__name__ + ": " + str(exc), file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.path.insert(0, str(ROOT))
    raise SystemExit(main())
