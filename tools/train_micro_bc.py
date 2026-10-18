"""Small offline BC prototype. NumPy only; never launches SC2 or changes splits."""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

CONTRACT = dict(
    feature_version="marine-16-v1",
    action_version="marine-5-v1",
    decision_game_loops=8,
)
SPLITS = ("train", "validation", "test")


def sha256(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def load_dataset(directory):
    directory = Path(directory)
    data_path, meta_path = directory / "demonstrations.npz", directory / "metadata.json"
    meta = json.loads(meta_path.read_text(encoding="utf-8"))
    if any(meta.get(key) != value for key, value in CONTRACT.items()):
        raise ValueError("Incompatible dataset contract")
    if meta.get("dataset_sha256") != sha256(data_path):
        raise ValueError("Dataset SHA256 mismatch")
    with np.load(data_path, allow_pickle=False) as source:
        data = {
            key: source[key].copy()
            for key in ("obs", "mask", "action", "group", "split")
        }
    obs, mask, action = data["obs"], data["mask"], data["action"]
    count = len(obs)
    if (
        not count
        or obs.shape != (count, 16)
        or obs.dtype != np.float32
        or not np.isfinite(obs).all()
        or (np.abs(obs) > 1).any()
        or mask.shape != (count, 5)
        or mask.dtype != np.bool_
        or not mask[:, 4].all()
        or action.shape != (count,)
        or action.dtype != np.int64
        or ((action < 0) | (action >= 5)).any()
    ):
        raise ValueError("Invalid observation, mask or action arrays")
    if not mask[np.arange(count), action].all():
        raise ValueError("Expert label is masked out")
    groups, splits = data["group"], data["split"]
    if groups.shape != (count,) or splits.shape != (count,):
        raise ValueError("Invalid group/split shape")
    if groups.dtype.kind not in "US" or splits.dtype.kind not in "US":
        raise ValueError("Group/split must be strings")
    if set(splits.tolist()) != set(SPLITS):
        raise ValueError("Expected all three frozen splits")
    if meta.get("samples") != count:
        raise ValueError("Dataset sample count mismatch")
    for split in SPLITS:
        if meta.get("split_counts", {}).get(split) != int(np.sum(splits == split)):
            raise ValueError("Dataset split count mismatch")
    for group in set(groups.tolist()):
        assigned = set(splits[groups == group].tolist())
        if (
            len(assigned) != 1
            or meta.get("group_splits", {}).get(group) not in assigned
        ):
            raise ValueError("Scenario group split leakage or provenance mismatch")
    # Also validate groups with no eligible rows, preserved by the exporter.
    if any(split not in SPLITS for split in meta.get("group_splits", {}).values()):
        raise ValueError("Unknown frozen group split")
    return data, meta


def initialize(seed):
    rng = np.random.default_rng(seed)
    weights = {}
    for index, (inputs, outputs) in enumerate(((16, 64), (64, 64), (64, 5)), 1):
        limit = np.sqrt(6.0 / (inputs + outputs))
        weights[f"w{index}"] = rng.uniform(-limit, limit, (inputs, outputs)).astype(
            np.float32
        )
        weights[f"b{index}"] = np.zeros(outputs, dtype=np.float32)
    return weights


def forward(weights, obs):
    first = np.tanh(obs @ weights["w1"] + weights["b1"])
    second = np.tanh(first @ weights["w2"] + weights["b2"])
    return second @ weights["w3"] + weights["b3"], (first, second)


def loss_gradient(weights, obs, mask, action, gradients=False):
    logits, (first, second) = forward(weights, obs)
    legal = np.where(mask, logits, -np.inf)
    shifted = legal - legal.max(axis=1, keepdims=True)
    exponent = np.exp(shifted)
    probabilities = exponent / exponent.sum(axis=1, keepdims=True)
    rows = np.arange(len(obs))
    loss = float(np.mean(np.log(exponent.sum(axis=1)) - shifted[rows, action]))
    accuracy = float(np.mean(np.argmax(legal, axis=1) == action))
    metrics = dict(samples=len(obs), masked_loss=loss, masked_accuracy=accuracy)
    if not gradients:
        return metrics
    delta = probabilities.copy()
    delta[rows, action] -= 1
    delta /= len(obs)
    result = dict(w3=second.T @ delta, b3=delta.sum(axis=0))
    delta = (delta @ weights["w3"].T) * (1 - second * second)
    result.update(w2=first.T @ delta, b2=delta.sum(axis=0))
    delta = (delta @ weights["w2"].T) * (1 - first * first)
    result.update(w1=obs.T @ delta, b1=delta.sum(axis=0))
    return metrics, result


def train(dataset, output, *, seed=42, epochs=1000, learning_rate=0.003):
    if not isinstance(epochs, int) or epochs < 1:
        raise ValueError("epochs must be positive")
    if not np.isfinite(learning_rate) or learning_rate <= 0:
        raise ValueError("learning_rate must be positive and finite")
    data, source_meta = load_dataset(dataset)
    output = Path(output)
    if output.exists():
        raise FileExistsError(
            "Use a new model output directory; never overwrite models"
        )
    partitions = {
        split: tuple(
            data[key][data["split"] == split] for key in ("obs", "mask", "action")
        )
        for split in SPLITS
    }
    weights = initialize(seed)
    first_moment = {key: np.zeros_like(value) for key, value in weights.items()}
    second_moment = {key: np.zeros_like(value) for key, value in weights.items()}
    initial_train = loss_gradient(weights, *partitions["train"])
    best_loss = loss_gradient(weights, *partitions["validation"])["masked_loss"]
    best = {key: value.copy() for key, value in weights.items()}
    best_epoch, history = 0, []
    for epoch in range(1, epochs + 1):
        _, gradients = loss_gradient(weights, *partitions["train"], gradients=True)
        for key, gradient in gradients.items():
            first_moment[key] = 0.9 * first_moment[key] + 0.1 * gradient
            second_moment[key] = (
                0.999 * second_moment[key] + 0.001 * gradient * gradient
            )
            weights[key] -= (
                learning_rate
                * (first_moment[key] / (1 - 0.9**epoch))
                / (np.sqrt(second_moment[key] / (1 - 0.999**epoch)) + 1e-8)
            )
        if not all(np.isfinite(value).all() for value in weights.values()):
            raise ValueError("Non-finite training weights")
        validation = loss_gradient(weights, *partitions["validation"])
        if validation["masked_loss"] < best_loss:
            best_loss, best_epoch = validation["masked_loss"], epoch
            best = {key: value.copy() for key, value in weights.items()}
        if epoch == 1 or epoch == epochs or epoch % max(1, epochs // 20) == 0:
            history.append(
                dict(
                    epoch=epoch,
                    train=loss_gradient(weights, *partitions["train"]),
                    validation=validation,
                )
            )
    # Test is evaluated only after the validation-selected checkpoint is frozen.
    report = {split: loss_gradient(best, *partitions[split]) for split in SPLITS}
    train_actions = partitions["train"][2]
    majority = int(np.argmax(np.bincount(train_actions, minlength=5)))
    for split, (_, mask, action) in partitions.items():
        baseline = np.where(mask[:, majority], majority, 4)
        report[split]["train_majority_with_hold_fallback_accuracy"] = float(
            np.mean(baseline == action)
        )
        predicted = np.argmax(
            np.where(mask, forward(best, partitions[split][0])[0], -np.inf), axis=1
        )
        report[split]["action_recall"] = {
            str(label): float(np.mean(predicted[action == label] == label))
            if np.any(action == label)
            else None
            for label in range(5)
        }
    output.mkdir(parents=True, exist_ok=False)
    np.savez_compressed(output / "weights.npz", **best)
    metadata = dict(
        format="marine-bc-numpy-v1",
        **CONTRACT,
        architecture=[16, 64, 64, 5],
        activation="tanh",
        normalization="marine-16-v1",
        weights_sha256=sha256(output / "weights.npz"),
        dataset_sha256=source_meta["dataset_sha256"],
        dataset_metadata_sha256=sha256(Path(dataset) / "metadata.json"),
        expert_versions=source_meta.get("expert_versions", []),
        scenario_versions=source_meta.get("scenario_versions", []),
        seed=seed,
        prototype=True,
        training_readiness="not_established",
        sample_counts=source_meta["split_counts"],
        training=dict(
            optimizer="adam",
            learning_rate=learning_rate,
            epochs=epochs,
            batch="full_train_split",
            beta1=0.9,
            beta2=0.999,
            epsilon=1e-8,
            selection="minimum_validation_masked_loss",
            selected_epoch=best_epoch,
        ),
    )
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8"
    )
    training_report = dict(
        initial_train=initial_train,
        selected_epoch=best_epoch,
        metrics=report,
        history=history,
        weights_sha256=metadata["weights_sha256"],
        dataset_sha256=metadata["dataset_sha256"],
        prototype=True,
        training_readiness="not_established",
        interpretation="Offline imitation prototype only; accuracy is label agreement, not combat strength or generalization.",
    )
    (output / "training_report.json").write_text(
        json.dumps(training_report, indent=2, allow_nan=False), encoding="utf-8"
    )
    return training_report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("dataset", type=Path)
    parser.add_argument("output", type=Path)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument("--epochs", type=int, default=1000)
    parser.add_argument("--learning-rate", type=float, default=0.003)
    args = parser.parse_args()
    print(
        json.dumps(
            train(
                args.dataset,
                args.output,
                seed=args.seed,
                epochs=args.epochs,
                learning_rate=args.learning_rate,
            ),
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
