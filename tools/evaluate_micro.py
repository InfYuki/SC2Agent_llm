"""Frozen paired local scene coverage; all games run serially, without LLM."""
import argparse
from collections import Counter
from datetime import datetime
import hashlib
import json
import os
from contextlib import contextmanager
from pathlib import Path
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools.report_micro import audit

CASES = [
    dict(
        id="zerg_close",
        scenario="marine-vs-zergling",
        distance=3,
        health=1,
        seed=42,
        split="train",
        limit=45,
    ),
    dict(
        id="zerg_medium",
        scenario="marine-vs-zergling",
        distance=6,
        health=1,
        seed=11,
        split="validation",
        limit=45,
    ),
    dict(
        id="marine_close",
        scenario="marine-vs-marine",
        distance=3,
        health=1,
        seed=42,
        split="train",
        limit=45,
    ),
    dict(
        id="marine_hurt",
        scenario="marine-vs-marine",
        distance=6,
        health=0.5,
        seed=11,
        split="test",
        limit=45,
    ),
    dict(
        id="zerg_hurt",
        scenario="marine-vs-zergling",
        distance=3,
        health=0.5,
        seed=21,
        split="validation",
        limit=45,
    ),
    dict(
        id="marine_medium",
        scenario="marine-vs-marine",
        distance=6,
        health=1,
        seed=31,
        split="test",
        limit=45,
    ),
    dict(
        id="unseen",
        scenario="marine-vs-zergling",
        distance=6,
        hidden=True,
        health=1,
        seed=41,
        split="test",
        limit=3,
    ),
    dict(
        id="time_limit",
        scenario="marine-vs-zergling",
        distance=6,
        health=1,
        seed=51,
        split="train",
        # The first engine callback can be at loop 17 (~0.76 seconds).
        # Include per-tag initialization and complete 8-loop observations.
        limit=3,
        expected_outcome="game_time_limit",
    ),
]
CASES += [
    dict(
        id=f"dual_nearest_{split}",
        scenario="marine-vs-marine",
        distance=3,
        health=1,
        seed=seed,
        split=split,
        limit=45,
        enemy_count=2,
        second_distance=8,
        second_health=0.5,
        expected_priority=0,
    )
    for split, seed in (("train", 61), ("validation", 71), ("test", 81))
]
CASES += [
    dict(
        id="dual_weakest_in_range",
        scenario="marine-vs-marine",
        distance=3,
        health=1,
        seed=91,
        split="test",
        limit=45,
        enemy_count=2,
        second_distance=5,
        second_health=0.5,
        expected_priority=1,
    )
]


# Explicit opt-in only: the historical 12-case suite stays frozen.
EXTRA_CASES = [dict(id="dual_zergling_train", scenario="marine-vs-zergling",
    distance=6, health=1, seed=101, split="train", limit=12,
    enemy_count=2, second_distance=8, second_health=0.5,
    observed_contract="dual_zergling")]


def select_cases(case_ids=None, experts=None):
    registry = {c["id"]: c for c in CASES + EXTRA_CASES}
    ids = list(dict.fromkeys(case_ids)) if case_ids else [c["id"] for c in CASES]
    selected_experts = list(dict.fromkeys(experts or ("amove", "kite")))
    if any(i not in registry for i in ids) or any(e not in ("amove", "kite") for e in selected_experts):
        raise ValueError("Unknown case or expert")
    return [registry[i].copy() for i in ids], selected_experts


def observed_case_check(directory, case, expert):
    """Check the engine observation, never infer validity from spawn requests."""
    if case.get("expected_outcome") == "game_time_limit":
        initial_path = directory / "initial_scene_observation.json"
        initialized = initial_path.exists() and json.loads(
            initial_path.read_text(encoding="utf-8")
        ).get("initialization_confirmed", False)
        result = json.loads(
            (directory / "scenario_result.json").read_text(encoding="utf-8")
        )
        actual_timeout = (
            result["outcome"] == "game_time_limit"
            and result["truncated"]
            and not result["terminated"]
            and result["game_loop"] / 22.4 >= case["limit"]
        )
        rows = [
            json.loads(line)
            for line in (directory / "micro_transitions.jsonl")
            .read_text(encoding="utf-8")
            .splitlines()
        ]
        complete = sum(
            row["actual_game_loops"] == 8 and not row["truncated"] for row in rows
        )
        return dict(
            passed=bool(
                initialized and actual_timeout and (expert == "amove" or complete > 0)
            ),
            required=True,
            initialization_confirmed=bool(initialized),
            actual_game_time_limit=actual_timeout,
            complete_eight_loop_samples=complete,
        )
    if case.get("enemy_count", 1) != 2:
        return dict(passed=True, required=False)
    path = directory / "initial_scene_observation.json"
    if not path.exists():
        return dict(
            passed=False, required=True, reason="no_confirmed_initial_observation"
        )
    initial = json.loads(path.read_text(encoding="utf-8"))
    enemies = {e["tag"]: e for e in initial["enemies"]}
    near = enemies.get(initial["nearest_tag"])
    weak = enemies.get(initial["weakest_tag"])
    if case.get("observed_contract") == "dual_zergling":
        geometry = bool(initial.get("initialization_confirmed")
            and initial.get("friendly_type_id") == 48
            and initial.get("visible_enemy_count") == 2 and len(enemies) == 2
            and abs(initial["health"] - 45) <= 0.6
            and all(e.get("type_id") == 105 and abs(e["health_max"] - 35) <= 0.6
                    for e in enemies.values())
            and sorted(e.get("role", -1) for e in enemies.values()) == [0, 1]
            and all(abs(e["health"] - e["health_max"] * (1 if e["role"] == 0 else 0.5)) <= 0.6
                    for e in enemies.values()))
        rows = [json.loads(line) for line in (directory / "micro_transitions.jsonl").read_text(encoding="utf-8").splitlines()]
        complete = sum(r["actual_game_loops"] == 8 and not r["truncated"]
                       and r["bc_eligible"] and r["mask"][r["executed_action"]]
                       and r["command_result"] in {"engine_confirmed", "hold"} for r in rows)
        return dict(passed=geometry and (expert == "amove" or complete > 0),
                    required=True, geometry_valid=geometry, complete_legal_samples=complete)
    priority = case["expected_priority"]
    geometry = bool(
        initial["initialization_confirmed"]
        and len(enemies) == 2
        and near
        and weak
        and near["tag"] != weak["tag"]
        and near["health"] > weak["health"]
        and near["in_range"]
        and weak["in_range"] == (priority == 1)
    )
    ready_priority = initial["weapon_cooldown"] > 0 or (
        initial["mask"][priority] and initial["expert_action"] == priority
    )
    rows = [
        json.loads(line)
        for line in (directory / "micro_transitions.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    ]
    confirmed = sum(
        r["requested_action"] == priority
        and r["executed_action"] == priority
        and r["command_result"] == "engine_confirmed"
        and r["actual_game_loops"] == 8
        and r["bc_eligible"]
        for r in rows
    )
    return dict(
        passed=geometry and ready_priority and (expert == "amove" or confirmed > 0),
        required=True,
        geometry_valid=geometry,
        ready_priority_valid=ready_priority,
        expected_priority=priority,
        initial_cooldown=initial["weapon_cooldown"],
        bc_eligible_confirmed_priority=confirmed,
    )



def sha(path):
    return hashlib.sha256(Path(path).read_bytes()).hexdigest()


def write_json(path, value):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(value, indent=2), encoding="utf-8")
    temporary.replace(path)


@contextmanager
def execution_lock(path):
    # OS locks release after a crash. Keep the inode/file: never unlink another owner's lock.
    with path.open("a+b") as handle:
        if path.stat().st_size == 0:
            handle.write(b"0")
            handle.flush()
        handle.seek(0)
        try:
            if os.name == "nt":
                import msvcrt
                msvcrt.locking(handle.fileno(), msvcrt.LK_NBLCK, 1)
            else:
                import fcntl
                fcntl.flock(handle.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError as error:
            raise RuntimeError("Suite is already executing") from error
        try:
            yield
        finally:
            handle.seek(0)
            if os.name == "nt":
                msvcrt.locking(handle.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def frozen_environment():
    import run_local  # same fixed SC2 import paths and map resolver as the runner
    from sc2 import maps
    game_path = str(Path(os.environ.get("SC2PATH", r"C:\Program Files (x86)\StarCraft II")).resolve())
    os.environ["SC2PATH"] = game_path
    map_path = Path(maps.get("Ancient Cistern LE").path).resolve()
    files = [*(ROOT / "bot").glob("*.py"), ROOT / "run_local.py",
             ROOT / "tools/run_micro_scenario.py", Path(__file__),
             ROOT / "tools/report_micro.py", ROOT / "tools/export_micro_dataset.py",
             ROOT / "poetry.lock"]
    return dict(source_hashes={str(p.relative_to(ROOT)): sha(p) for p in files},
                map_path=str(map_path), map_sha256=sha(map_path), game_path=game_path,
                python=sys.executable)


def command_for(case, expert, run_id, environment):
    command = [environment["python"], "-s", "-u", str(ROOT / "tools/run_micro_scenario.py"),
               "--game-path", environment["game_path"], "--map", "Ancient Cistern LE",
               "--scenario", case["scenario"], "--expert", expert,
               "--distance", str(case["distance"]), "--health-fraction", str(case["health"]),
               "--seed", str(case["seed"]), "--data-split", case["split"],
               "--max-game-seconds", str(case["limit"]), "--run-id", run_id]
    if case.get("hidden"):
        command.append("--enemy-hidden")
    if case.get("enemy_count") == 2:
        command += ["--enemy-count", "2", "--second-distance", str(case["second_distance"]),
                    "--second-enemy-health-fraction", str(case["second_health"])]
    return command


def make_plan(suite_id, cases, experts, environment, subset):
    runs = []
    for case in cases:
        for expert in experts:
            run_id = f"{suite_id}_{case['id']}_{expert}"
            runs.append(dict(case=case["id"], expert=expert, split=case["split"], run_id=run_id,
                             command=command_for(case, expert, run_id, environment)))
    return dict(version="marine-coverage-subset-v1", scope="subset" if subset else "full",
                selected=dict(cases=[c["id"] for c in cases], experts=experts,
                              case_count=len(cases), run_count=len(runs)),
                cases=cases, environment=environment, runs=runs)


RAW_FILES = ("micro_transitions.jsonl", "scenario_result.json", "initial_scene_observation.json",
             "manifest.json", "scenario.json", "summary.json", "game.SC2Replay")


def raw_hashes(directory):
    return {name: sha(directory / name) for name in RAW_FILES if (directory / name).exists()}


def resume_state(plan, suite):
    if len(suite["runs"]) != len(plan["runs"]):
        raise ValueError("Frozen run denominator changed")
    for expected, run in zip(plan["runs"], suite["runs"]):
        if any(run.get(key) != value for key, value in expected.items()):
            raise ValueError("Frozen run identity changed")
        directory = ROOT / "artifacts/runs" / run["run_id"]
        if run["status"] not in {"pending", "running", "passed", "failed", "interrupted"}:
            raise ValueError("Invalid run state")
        if run["status"] not in {"pending", "running"} and raw_hashes(directory) != run.get("raw_sha256"):
            raise ValueError("Finished raw input changed: " + run["run_id"])
        if run["status"] == "running":
            run.update(status="interrupted", passed=False, raw_sha256=raw_hashes(directory),
                       error="Previous executor stopped while running; use a new suite to retry")
        if run["status"] == "pending" and directory.exists():
            raise ValueError("Pending run directory already exists: " + run["run_id"])


def run_case(output, run, case):
    directory = ROOT / "artifacts/runs" / run["run_id"]
    with (output / (run["run_id"] + ".log")).open("w", encoding="utf-8") as log:
        process = subprocess.Popen(run["command"], cwd=ROOT, stdout=log, stderr=subprocess.STDOUT)
        try:
            code = process.wait(timeout=120)
        except (subprocess.TimeoutExpired, KeyboardInterrupt):
            # Only the process tree launched for this run is owned by this watchdog.
            subprocess.run(["taskkill", "/PID", str(process.pid), "/T", "/F"], capture_output=True)
            process.wait(timeout=15)
            raise
    summary = json.loads((directory / "summary.json").read_text(encoding="utf-8"))
    result = json.loads((directory / "scenario_result.json").read_text(encoding="utf-8"))
    checked = audit(directory)
    observed = observed_case_check(directory, case, run["expert"])
    expected_empty = run["expert"] == "amove" or case["id"] == "unseen"
    passed = (code == 0 and summary["error"] is None
              and summary["counters"].get("command_conflicts", 0) == 0
              and checked["status"] == ("no_data" if expected_empty else "passed")
              and (directory / "game.SC2Replay").stat().st_size > 0 and observed["passed"])
    return dict(passed=bool(passed), result=result, audit=checked, observed_case_check=observed)


def execute(output, plan, suite):
    def save():
        write_json(output / "summary.json", suite)
    resume_state(plan, suite)
    save()
    for run in suite["runs"]:
        if run["status"] != "pending":
            continue
        if frozen_environment() != plan["environment"]:
            raise ValueError("Frozen source/map/config changed")
        run["status"] = "running"
        suite["status"] = "running"
        save()  # durable identity and state before launching SC2
        print(f"Running {run['case']} / {run['expert']}", flush=True)
        try:
            run.update(run_case(output, run, next(c for c in plan["cases"] if c["id"] == run["case"])))
            run["status"] = "passed" if run["passed"] else "failed"
        except BaseException as error:
            run.update(status="interrupted" if isinstance(error, KeyboardInterrupt) else "failed",
                       passed=False, error=f"{type(error).__name__}: {error}")
            run["raw_sha256"] = raw_hashes(ROOT / "artifacts/runs" / run["run_id"])
            suite["status"] = "failed"
            save()
            raise
        run["raw_sha256"] = raw_hashes(ROOT / "artifacts/runs" / run["run_id"])
        if not run["passed"]:
            suite["status"] = "failed"
            save()
            return 1
        save()
    suite["status"] = "passed" if all(r["status"] == "passed" for r in suite["runs"]) else "failed"
    suite["outcomes"] = {e: dict(Counter(r["result"]["outcome"] for r in suite["runs"]
        if r["expert"] == e and "result" in r)) for e in plan["selected"]["experts"]}
    save()
    return 0 if suite["status"] == "passed" else 1


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--suite-id", default=datetime.now().strftime("micro_%Y%m%d_%H%M%S"))
    parser.add_argument("--case", action="append", dest="case_ids", choices=[c["id"] for c in CASES + EXTRA_CASES])
    parser.add_argument("--expert", action="append", choices=["amove", "kite"])
    parser.add_argument("--resume", action="store_true", help="Continue only pending entries from an existing frozen suite")
    args = parser.parse_args()
    base = ROOT / "artifacts/micro_suites"
    output = (base / args.suite_id).resolve()
    if not output.is_relative_to(base.resolve()) or output == base.resolve():
        parser.error("suite-id must stay inside artifacts/micro_suites")
    if args.resume:
        if not output.is_dir():
            parser.error("Cannot resume missing suite")
    else:
        output.mkdir(parents=True, exist_ok=False)
    with execution_lock(output / "execution.lock"):
        environment = frozen_environment()
        if args.resume:
            plan = json.loads((output / "plan.json").read_text(encoding="utf-8"))
            suite = json.loads((output / "summary.json").read_text(encoding="utf-8"))
            if sha(output / "plan.json") != suite["plan_sha256"] or environment != plan["environment"]:
                raise ValueError("Frozen plan/source/map/config changed")
            if args.case_ids or args.expert:
                cases, experts = select_cases(args.case_ids or plan["selected"]["cases"], args.expert or plan["selected"]["experts"])
                if cases != plan["cases"] or experts != plan["selected"]["experts"]:
                    raise ValueError("Resume selection differs from frozen plan")
        else:
            cases, experts = select_cases(args.case_ids, args.expert)
            plan = make_plan(args.suite_id, cases, experts, environment, bool(args.case_ids or args.expert))
            if any((ROOT / "artifacts/runs" / r["run_id"]).exists() for r in plan["runs"]):
                raise ValueError("Preallocated run directory already exists")
            write_json(output / "plan.json", plan)
            suite = dict(version=plan["version"], scope=plan["scope"], selected=plan["selected"],
                cases=plan["cases"], source_hashes=environment["source_hashes"],
                plan_sha256=sha(output / "plan.json"), status="pending",
                runs=[dict(r, status="pending", passed=False) for r in plan["runs"]])
            write_json(output / "summary.json", suite)
        code = execute(output, plan, suite)
    print(json.dumps(dict(status=suite["status"], scope=suite["scope"], selected=suite["selected"],
                          summary=str(output / "summary.json")), indent=2))
    return code


if __name__ == "__main__":
    raise SystemExit(main())
