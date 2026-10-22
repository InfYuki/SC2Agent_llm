"""Focused offline fixture: heldout registry, observations, frozen metrics, overlap."""
import json
from pathlib import Path
import sys
import tempfile
from unittest.mock import patch

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bot.micro_bc import SHAPES
from tools import evaluate_micro as runner
from tools import evaluate_frozen_micro_bc as frozen
from tools import train_micro_bc as training
from tools.check_expert_subset import fixtures


def write_dataset(path, data):
    path.mkdir()
    np.savez_compressed(path / "demonstrations.npz", **data)
    meta = dict(training.CONTRACT, samples=len(data["obs"]),
        dataset_sha256=training.sha256(path / "demonstrations.npz"),
        split_counts={s: int(np.sum(data["split"] == s)) for s in training.SPLITS},
        group_splits={g: str(data["split"][data["group"] == g][0]) for g in set(data["group"])})
    (path / "metadata.json").write_text(json.dumps(meta), encoding="utf-8")


def expect_error(call):
    try:
        call()
    except ValueError:
        return
    raise AssertionError("Expected strict rejection")


def main():
    cases, experts = runner.select_cases()
    assert len(cases) == 12 and experts == ["amove", "kite"]
    assert sum(len(experts) for c in cases) == 24
    train = runner.select_cases(["dual_zergling_train"], ["kite"])[0][0]
    assert (train["distance"], train["second_distance"], train["second_health"], train["seed"], train["split"]) == (6, 8, .5, 101, "train")
    selected = runner.select_cases(list(frozen.NEW_CASES), ["kite"])[0]
    assert [(c["distance"], c["second_distance"], c["seed"], c["split"], c["limit"]) for c in selected] == [(6, 10, 111, "validation", 12), (9, 10, 121, "test", 12)]
    with tempfile.TemporaryDirectory(prefix="frozen_bc_check_") as temp:
        root = Path(temp)
        scene = root / "scene"
        fixtures(scene)
        initial = json.loads((scene / "initial_scene_observation.json").read_text())
        initial.update(friendly_position=[0, 0], friendly_ground_range=5, friendly_radius=.375,
                       weapon_cooldown=0, mask=[False, False, True, False, True], expert_action=2)
        for e, distance in zip(initial["enemies"], (7.2, 10.2)):
            e.update(distance=distance, position=[distance, 0], radius=.375)
        (scene / "initial_scene_observation.json").write_text(json.dumps(initial))
        for case in selected:
            observed = runner.observed_case_check(scene, case, "kite")
            assert observed["passed"] and observed["coverage_diagnostics"]["both_out_of_range"]
            assert not observed["coverage_diagnostics"]["nearest_shootable_weakest_not"]
            assert observed["actual_observation"]["enemies"][0]["distance"] == 7.2
        # Existing Marine checks retain nearest/weakest priority requirements.
        initial["enemies"][0]["in_range"] = True
        initial["mask"][0] = True
        initial["expert_action"] = 0
        (scene / "initial_scene_observation.json").write_text(json.dumps(initial))
        assert runner.observed_case_check(scene, cases[8], "amove")["passed"]
        initial["expert_action"] = 2
        (scene / "initial_scene_observation.json").write_text(json.dumps(initial))
        assert not runner.observed_case_check(scene, cases[8], "amove")["passed"]
        # 93 historical rows; old cross-split collisions are deliberate.
        old = dict(obs=np.zeros((93, 16), dtype=np.float32), mask=np.ones((93, 5), dtype=bool),
                   action=np.full(93, 4, dtype=np.int64), game_loop=np.arange(93, dtype=np.int64),
                   group=np.array(["old_" + training.SPLITS[i % 3] for i in range(93)]),
                   split=np.array([training.SPLITS[i % 3] for i in range(93)]))
        new = {k: v.copy() for k, v in old.items()}
        for key in new:
            added = {"obs": np.zeros((2, 16), dtype=np.float32), "mask": np.ones((2, 5), dtype=bool),
                     "action": np.array([4, 4], dtype=np.int64), "game_loop": np.array([100, 101], dtype=np.int64),
                     "group": np.array(list(frozen.NEW_CASES)), "split": np.array(["validation", "test"])}[key]
            new[key] = np.concatenate([new[key], added])
        new["obs"][93, 0] = -0.0
        write_dataset(root / "old", old)
        write_dataset(root / "new", new)
        models = [root / "model_a", root / "model_b"]
        for model in models:
            model.mkdir()
            np.savez_compressed(model / "weights.npz", **{k: np.zeros(shape, dtype=np.float32) for k, shape in SHAPES.items()})
            metadata = dict(training.CONTRACT, format="marine-bc-numpy-v1", architecture=[16,64,64,5],
                            activation="tanh", normalization="marine-16-v1", weights_sha256=training.sha256(model / "weights.npz"))
            (model / "metadata.json").write_text(json.dumps(metadata))
        def evaluate(directory=root / "new"):
            return frozen.evaluate(directory, root / "old", models, ["before", "after"], list(frozen.NEW_CASES))
        with patch.object(training, "train", side_effect=AssertionError("Training forbidden")), patch.object(training, "initialize", side_effect=AssertionError("Initialization forbidden")):
            report = evaluate()
        assert report["training_updates"] == 0 and all(m["files_unchanged"] for m in report["models"])
        assert not report["qualification"]["independent_heldout"]
        for mode in ("obs", "obs_plus_mask"):
            audit = report["duplicate_audit"][mode]
            assert all(x["matching_pairs"] for x in audit["historical_cross_split"].values())
            assert all(x["matching_pairs"] for x in audit["new_vs_history_and_each_other"].values())
        metric = report["cases"]["dual_zergling_validation"]["models"]["before"]
        assert metric["action_recall"]["0"] is None and metric["action_recall"]["4"] == 0
        assert metric["action_confusion_true_rows_predicted_columns"][4][0] == 1
        assert report["cases"]["dual_zergling_test"]["two_model_agreement"] == 1
        # Adjacent float32 values must not be rounded into an overlap.
        unique = {k: v.copy() for k, v in new.items()}
        unique["obs"][93, 0] = np.nextafter(np.float32(0), np.float32(1))
        unique["obs"][94, 0] = .125
        write_dataset(root / "unique", unique)
        assert evaluate(root / "unique")["qualification"]["independent_heldout"]
        missing = {k: v[:94].copy() for k, v in new.items()}
        write_dataset(root / "missing", missing)
        missing_report = evaluate(root / "missing")
        assert not missing_report["qualification"]["independent_heldout"]
        assert missing_report["qualification"]["missing_eligible_cases"] == ["dual_zergling_test"]
        assert missing_report["cases"]["dual_zergling_test"]["status"] == "missing_eligible_samples"
        changed = {k: v.copy() for k, v in new.items()}
        changed["game_loop"][1] = 999
        write_dataset(root / "changed", changed)
        expect_error(lambda: evaluate(root / "changed"))
        for name, key, value in (("nonfinite", "obs", float("nan")), ("illegal_mask", "mask", False)):
            bad = {k: v.copy() for k, v in new.items()}
            bad[key][93, 4] = value
            write_dataset(root / name, bad)
            expect_error(lambda directory=root / name: evaluate(directory))
        json.dumps(report, allow_nan=False)
    print("PASS: default24, new explicit splits, observed range diagnostics, historical93 prefix, two frozen models, null recall, exact signed-zero overlap, independence refusal, zero training, SHA unchanged")


if __name__ == "__main__":
    main()
