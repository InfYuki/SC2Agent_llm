"""Export the supported SB3 MaskablePPO actor; run in the training environment."""
import argparse
import hashlib
from importlib.metadata import version
import json
from pathlib import Path
import sys

import numpy as np

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from bot.micro_ppo import NumpyPPOPolicy, POLICY_VERSION


def export_actor(model, checkpoint, output):
    """Export model's actor, tying it to its saved source checkpoint."""
    import torch
    from sb3_contrib import MaskablePPO

    checkpoint, output = Path(checkpoint), Path(output)
    if not isinstance(model, MaskablePPO):
        raise ValueError("Only MaskablePPO can be exported")
    policy = model.policy
    layers = list(policy.mlp_extractor.policy_net)
    if (len(layers) != 4
            or not isinstance(layers[0], torch.nn.Linear)
            or not isinstance(layers[1], torch.nn.Tanh)
            or not isinstance(layers[2], torch.nn.Linear)
            or not isinstance(layers[3], torch.nn.Tanh)
            or policy.normalize_images is not True
            or policy.features_extractor.__class__.__name__ != "FlattenExtractor"):
        raise ValueError("Unsupported PPO actor architecture or preprocessing")
    if model.observation_space.shape != (16,) or model.action_space.n != 5:
        raise ValueError("Unsupported PPO observation/action spaces")
    from bot.micro_bc import SHAPES
    weights = {}
    for index, layer in enumerate((layers[0], layers[2], policy.action_net), 1):
        weights[f"w{index}"] = layer.weight.detach().cpu().numpy().T.copy()
        weights[f"b{index}"] = layer.bias.detach().cpu().numpy().copy()
    for key, shape in SHAPES.items():
        if (weights[key].shape != shape or weights[key].dtype != np.float32
                or not np.isfinite(weights[key]).all()):
            raise ValueError("Unsupported PPO weights: " + key)
    checkpoint_hash = hashlib.sha256(checkpoint.read_bytes()).hexdigest()
    provenance = {}
    source_metadata = checkpoint.parent / "metadata.json"
    if source_metadata.is_file():
        source = json.loads(source_metadata.read_text(encoding="utf-8"))
        if source.get("checkpoint_sha256") != checkpoint_hash:
            raise ValueError("Source metadata checkpoint hash mismatch")
        provenance = {key: source[key] for key in
                      ("initialization", "bc_weights_used", "bc_initialization", "dataset", "task")
                      if key in source}
    # Refuse provenance that attributes a different in-memory actor to the zip.
    saved = MaskablePPO.load(checkpoint, device="cpu")
    for key, tensor in policy.state_dict().items():
        if not torch.equal(tensor.cpu(), saved.policy.state_dict()[key].cpu()):
            raise ValueError("Model differs from source checkpoint: " + key)
    output.mkdir(parents=True, exist_ok=False)
    np.savez(output / "weights.npz", **weights)
    metadata = dict(
        format=POLICY_VERSION, feature_version="marine-16-v1",
        action_version="marine-5-v1", decision_game_loops=8,
        architecture=[16, 64, 64, 5], activation="tanh",
        normalization="marine-16-v1", prototype=True,
        weights_sha256=hashlib.sha256((output / "weights.npz").read_bytes()).hexdigest(),
        producer=dict(algorithm="MaskablePPO", source_checkpoint=str(checkpoint.resolve()),
                      source_checkpoint_sha256=checkpoint_hash,
                      **provenance,
                      versions={name: version(name) for name in
                                ("torch", "stable-baselines3", "sb3-contrib", "numpy")}),
    )
    (output / "metadata.json").write_text(
        json.dumps(metadata, indent=2, allow_nan=False), encoding="utf-8")
    NumpyPPOPolicy.load(output)
    return metadata


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("checkpoint", type=Path)
    parser.add_argument("output", type=Path)
    args = parser.parse_args()
    from sb3_contrib import MaskablePPO
    metadata = export_actor(MaskablePPO.load(args.checkpoint, device="cpu"),
                            args.checkpoint, args.output)
    print(json.dumps(metadata, indent=2))


if __name__ == "__main__":
    main()
