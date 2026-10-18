"""Shared wire contract for the single-Marine SC2 bridge (trusted local IPC)."""
import math

PROTOCOL = "sc2-micro-v1"
FEATURE_VERSION = "marine-16-v1"
ACTION_VERSION = "marine-5-v1"
DECISION_LOOPS = 8
HOLD_MASK = (False, False, False, False, True)


def message(kind, episode_id, decision_id, frame, **fields):
    return dict(protocol=PROTOCOL, type=kind, episode_id=episode_id,
                decision_id=decision_id, unit_slot=0, frame=frame, **fields)


def validate_state(packet, *, episode_id, decision_id, kind, previous_frame=None):
    if not isinstance(packet, dict):
        raise ValueError("IPC reply must be a mapping")
    for key, value in dict(protocol=PROTOCOL, type=kind, episode_id=episode_id,
                           decision_id=decision_id, unit_slot=0).items():
        if packet.get(key) != value:
            raise ValueError(f"IPC {key} mismatch")
    frame = packet.get("frame")
    if type(frame) is not int or frame < 0:
        raise ValueError("Invalid game frame")
    terminated, truncated = packet.get("terminated"), packet.get("truncated")
    if type(terminated) is not bool or type(truncated) is not bool:
        raise ValueError("Missing episode boundary flags")
    if previous_frame is not None:
        delta = frame - previous_frame
        if delta != DECISION_LOOPS and not ((terminated or truncated) and 0 <= delta <= DECISION_LOOPS):
            raise ValueError(f"Expected 8 game loops, received {delta}")
    obs = packet.get("obs")
    if obs is None:
        if not (terminated or truncated):
            raise ValueError("Missing live observation")
    elif len(obs) != 16 or not all(math.isfinite(float(x)) and -1 <= x <= 1 for x in obs):
        raise ValueError("Invalid marine-16-v1 observation")
    mask = packet.get("mask")
    if mask is None or len(mask) != 5 or not all(type(x) is bool for x in mask) or not mask[4]:
        raise ValueError("Invalid marine-5-v1 action mask")
    if not math.isfinite(float(packet.get("reward", float("nan")))):
        raise ValueError("Non-finite reward")
    if not isinstance(packet.get("info"), dict):
        raise ValueError("Missing transition info")
    return packet
