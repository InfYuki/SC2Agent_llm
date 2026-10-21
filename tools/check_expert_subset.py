"""One focused offline check for resumable expert subsets; never launches SC2."""
import copy
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from tools import evaluate_micro as runner
from tools import export_micro_dataset as exporter


def expect_error(call):
    try:
        call()
    except (ValueError, RuntimeError, OSError):
        return
    raise AssertionError("Expected refusal")


def fixtures(directory):
    directory.mkdir(parents=True)
    summary = dict(status="completed", result=None, error=None, counters={})
    (directory / "summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (directory / "game.SC2Replay").write_bytes(b"test replay")
    (directory / "scenario_result.json").write_text(json.dumps(dict(outcome="game_time_limit")), encoding="utf-8")
    initial = dict(initialization_confirmed=True, friendly_type_id=48, health=45,
                   visible_enemy_count=2, nearest_tag=1, weakest_tag=2,
                   enemies=[dict(tag=1, type_id=105, role=0, health=35, health_max=35, in_range=False),
                            dict(tag=2, type_id=105, role=1, health=17.5, health_max=35, in_range=False)])
    (directory / "initial_scene_observation.json").write_text(json.dumps(initial), encoding="utf-8")
    rows = []
    for start, interval, truncated in ((0, 8, False), (8, 2, True)):
        rows.append(dict(engagement_id="fixture", game_loop=start, next_game_loop=start + interval,
            actual_game_loops=interval, obs=[0.0]*16, next_obs=None if truncated else [0.0]*16,
            mask=[True]*5, requested_action=4, executed_action=4, command_result="hold",
            terminated=False, truncated=truncated, bc_eligible=not truncated,
            next_observation_valid=not truncated, split="train",
            versions=dict(feature="marine-16-v1", action="marine-5-v1", expert="marine-kite-v1",
                          scenario="fixture-v1", decision_game_loops=8)))
    (directory / "micro_transitions.jsonl").write_text("".join(json.dumps(r)+"\n" for r in rows), encoding="utf-8")


def main():
    cases, experts = runner.select_cases()
    assert len(cases) == 12 and experts == ["amove", "kite"]
    assert len(runner.make_plan("default", cases, experts, dict(python=sys.executable, game_path="fixture"), False)["runs"]) == 24
    cases, experts = runner.select_cases(["dual_zergling_train", "dual_zergling_train"], ["kite", "kite"])
    assert len(cases) == 1 and experts == ["kite"] and cases[0] not in runner.CASES
    assert (cases[0]["distance"], cases[0]["second_distance"], cases[0]["second_health"], cases[0]["limit"]) == (6, 8, .5, 12)
    expect_error(lambda: runner.select_cases(["unknown"]))
    with tempfile.TemporaryDirectory(prefix="expert_subset_check_") as temp:
        root = Path(temp)
        environment = dict(python=sys.executable, game_path="fixture", source_hashes={}, map_sha256="fixture")
        called = []
        with patch.object(runner, "ROOT", root), patch.object(exporter, "ROOT", root), patch.object(runner, "frozen_environment", return_value=environment):
            def setup(name, run_experts=("kite",)):
                output = root / "artifacts/micro_suites" / name
                output.mkdir(parents=True)
                plan = runner.make_plan(name, cases, list(run_experts), environment, True)
                runner.write_json(output / "plan.json", plan)
                suite = dict(status="pending", scope=plan["scope"], selected=plan["selected"],
                    runs=[dict(r, status="pending", passed=False) for r in plan["runs"]])
                return output, plan, suite

            def finish(output, run, case):
                called.append(run["run_id"])
                directory = root / "artifacts/runs" / run["run_id"]
                fixtures(directory)
                checked = runner.audit(directory)
                observed = runner.observed_case_check(directory, case, run["expert"])
                assert checked["status"] == "passed" and observed["passed"]
                return dict(passed=True, audit=checked, observed_case_check=observed, result=dict(outcome="game_time_limit"))

            output, plan, suite = setup("subset")
            with runner.execution_lock(output / "execution.lock"):
                expect_error(lambda: _take_lock(output / "execution.lock"))
                with patch.object(runner, "run_case", side_effect=finish):
                    assert runner.execute(output, plan, suite) == 0
            assert suite["scope"] == "subset" and suite["selected"]["run_count"] == 1
            assert suite["runs"][0]["raw_sha256"]["micro_transitions.jsonl"]
            before = list(called)
            with patch.object(runner, "run_case", side_effect=AssertionError("Completed run relaunched")):
                assert runner.execute(output, plan, suite) == 0
            assert called == before
            meta = exporter.export(output / "summary.json", root / "dataset")
            assert meta["samples"] == 1 and meta["split_counts"] == {"train": 1}
            directory = root / "artifacts/runs" / suite["runs"][0]["run_id"]
            digest = runner.sha(directory / "micro_transitions.jsonl")
            sidecar = directory / "learning_exclusion.json"
            sidecar.write_text(json.dumps(dict(excluded_from_future_training=True,
                run_id=directory.name, raw_sha256={"micro_transitions.jsonl": digest})), encoding="utf-8")
            expect_error(lambda: exporter.export(output / "summary.json", root / "excluded"))
            sidecar.write_text(json.dumps(dict(excluded_from_future_training=False,
                raw_sha256={"micro_transitions.jsonl": "changed"})), encoding="utf-8")
            expect_error(lambda: exporter.export(output / "summary.json", root / "badsha"))
            sidecar.write_text("[]", encoding="utf-8")
            expect_error(lambda: exporter.export(output / "summary.json", root / "badsidecar"))
            sidecar.unlink()
            (directory / "micro_transitions.jsonl").write_text("changed", encoding="utf-8")
            expect_error(lambda: runner.resume_state(plan, suite))

            output, plan, suite = setup("failure", ("amove", "kite"))
            with patch.object(runner, "run_case", return_value=dict(passed=False)):
                assert runner.execute(output, plan, suite) == 1
            assert len(suite["runs"]) == 2 and [r["status"] for r in suite["runs"]] == ["failed", "pending"]
            expect_error(lambda: exporter.export(output / "summary.json", root / "partial"))
            with patch.object(runner, "run_case", side_effect=finish):
                assert runner.execute(output, plan, suite) == 1
            assert [r["status"] for r in suite["runs"]] == ["failed", "passed"]
            assert called[-1] == "failure_dual_zergling_train_kite"
            expect_error(lambda: exporter.export(output / "summary.json", root / "stillfailed"))

            output, plan, suite = setup("interrupt", ("amove", "kite"))
            suite["runs"][0]["status"] = "running"
            with patch.object(runner, "run_case", side_effect=finish):
                assert runner.execute(output, plan, suite) == 1
            assert [r["status"] for r in suite["runs"]] == ["interrupted", "passed"]
            output, plan, suite = setup("changed")
            with patch.object(runner, "frozen_environment", return_value=dict(environment, map_sha256="changed")):
                expect_error(lambda: runner.execute(output, plan, suite))
            assert suite["runs"][0]["status"] == "pending"
            with patch.object(runner, "frozen_environment", return_value=dict(environment, source_hashes={"changed": "hash"})):
                expect_error(lambda: runner.execute(output, plan, suite))
            assert suite["runs"][0]["status"] == "pending"
            mutated = copy.deepcopy(suite)
            mutated["runs"][0]["command"].append("changed")
            expect_error(lambda: runner.resume_state(plan, mutated))
    print("PASS: default24/explicit subset, lock, pending-only resume, failure/interruption denominator, source/map/raw identity, subset NPZ, exclusion")


def _take_lock(path):
    with runner.execution_lock(path):
        pass


if __name__ == "__main__":
    main()
