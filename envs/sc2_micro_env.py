"""Real SC2 reset/step bridge; custom Gym-style API, not a Gymnasium Env.

Every reset cold-starts an owned worker. Death/system failure may return obs=None;
system failures always carry rollout_discard=True and must not train a policy.
"""
from multiprocessing.connection import Listener
import numbers
import math
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

from envs.micro_ipc import HOLD_MASK, PROTOCOL, message, validate_state

ROOT = Path(__file__).resolve().parents[1]
SCENARIOS = ("marine-vs-marine", "marine-vs-zergling")


class MicroEnvCloseError(RuntimeError):
    """The owned worker was cleaned up without a confirmed graceful close."""


def training_task(*, scenario="marine-vs-marine", distance=6.0,
                  max_game_seconds=8.0, map_name="Ancient Cistern LE",
                  own_health_fraction=1.0, enemy_health_fraction=1.0,
                  enemy_count=1, second_distance=None, second_enemy_health_fraction=None):
    """Serializable task contract; HP deltas use real unit HP, divided by 45."""
    if isinstance(enemy_count, bool) or not isinstance(enemy_count, numbers.Integral) or enemy_count not in (1, 2):
        raise ValueError("enemy_count must be an integer: 1 or 2")
    enemy_count = int(enemy_count)
    if enemy_count == 1 and (second_distance is not None or second_enemy_health_fraction is not None):
        raise ValueError("Second enemy fields require enemy_count=2")
    distance, max_game_seconds = float(distance), float(max_game_seconds)
    own_health_fraction, enemy_health_fraction = float(own_health_fraction), float(enemy_health_fraction)
    if scenario not in SCENARIOS:
        raise ValueError("Unsupported training scenario")
    if not math.isfinite(distance) or not 0 < distance <= 10:
        raise ValueError("distance must be finite and in (0,10]")
    if not math.isfinite(max_game_seconds) or not 0 < max_game_seconds <= 120:
        raise ValueError("max-game-seconds must be finite and in (0,120]")
    if not (math.isfinite(own_health_fraction) and 0.2 < own_health_fraction <= 1
            and math.isfinite(enemy_health_fraction) and 0 < enemy_health_fraction <= 1):
        raise ValueError("Health fractions require own in (0.2,1], enemy in (0,1]")
    task = dict(scenario=scenario, scenario_version=scenario + "-v6", distance=distance,
                max_game_seconds=max_game_seconds, map_name=map_name,
                friendly_count=1, enemy_count=enemy_count, health_fraction=own_health_fraction,
                enemy_health_fraction=enemy_health_fraction, enemy_hidden=False,
                decision_game_loops=8, reward_scale=45.0,
                reward_version="effective-hp-delta-45-terminal-1-v1")
    if enemy_count == 2:
        second_distance = 8.0 if second_distance is None else float(second_distance)
        second_enemy_health_fraction = (0.5 if second_enemy_health_fraction is None
                                        else float(second_enemy_health_fraction))
        if not (math.isfinite(second_distance) and distance + 1 <= second_distance <= 10
                and math.isfinite(second_enemy_health_fraction) and 0 < second_enemy_health_fraction <= 1):
            raise ValueError("Second target distance must be near distance + 1 through 10; health in (0,1]")
        task.update(scenario_version=scenario + "-1v2-v1", second_distance=second_distance,
                    second_enemy_health_fraction=second_enemy_health_fraction)
    return task


def normalize_training_task(task):
    """Validate a full stored contract, including legacy full-health tasks."""
    friendly_count = task.get("friendly_count")
    if isinstance(friendly_count, bool) or not isinstance(friendly_count, numbers.Integral) or friendly_count != 1:
        raise ValueError("friendly_count must be the integer 1")
    normalized = training_task(**{key: task[key] for key in
        ("scenario", "distance", "max_game_seconds", "map_name")},
        own_health_fraction=task.get("health_fraction", 1.0),
        enemy_health_fraction=task.get("enemy_health_fraction", 1.0),
        enemy_count=task.get("enemy_count", 1), second_distance=task.get("second_distance"),
        second_enemy_health_fraction=task.get("second_enemy_health_fraction"))
    stored = dict(task)
    stored.setdefault("enemy_count", 1)
    if stored != normalized:
        raise ValueError("Incompatible resume task metadata")
    return normalized


def normalize_curriculum(value):
    if (not isinstance(value, dict) or set(value) != {"format", "selection", "tasks"}
            or value["format"] != "marine-micro-curriculum-v1"
            or value["selection"] != "round-robin"
            or not isinstance(value["tasks"], list) or not value["tasks"]):
        raise ValueError("Invalid frozen curriculum")
    return dict(format=value["format"], selection=value["selection"],
                tasks=[normalize_training_task(task) for task in value["tasks"]])


class SC2MicroEnv:
    def __init__(self, *, game_path=r"C:\Program Files (x86)\StarCraft II",
                 map_name="Ancient Cistern LE", max_game_seconds=20,
                 startup_timeout=90, step_timeout=30, output_root=None, worker_python=None,
                 scenario="marine-vs-marine", distance=6.0,
                 own_health_fraction=1.0, enemy_health_fraction=1.0,
                 enemy_count=1, second_distance=None, second_enemy_health_fraction=None):
        self.game_path = str(game_path)
        self.worker_python = str(worker_python or sys.executable)
        self.map_name = map_name
        self.max_game_seconds = float(max_game_seconds)
        self.task = training_task(scenario=scenario, distance=distance,
                                  max_game_seconds=max_game_seconds, map_name=map_name,
                                  own_health_fraction=own_health_fraction,
                                  enemy_health_fraction=enemy_health_fraction, enemy_count=enemy_count,
                                  second_distance=second_distance,
                                  second_enemy_health_fraction=second_enemy_health_fraction)
        self.startup_timeout = float(startup_timeout)
        self.step_timeout = float(step_timeout)
        if min(self.max_game_seconds, self.startup_timeout, self.step_timeout) <= 0:
            raise ValueError("Time limits must be positive")
        self.output_root = Path(output_root or ROOT / "artifacts" / "micro_env")
        self._process = self._listener = self._connection = self._log = None
        self._state = None
        self._done = True
        self._close_confirmed = False
        self.close_info = None

    def reset(self, *, seed=42, options=None):
        self.close()
        self._close_confirmed = False
        self.close_info = None
        if options:
            raise ValueError("Training task is fixed at construction; reset options are unsupported")
        self.episode_id = uuid.uuid4().hex
        self.output_dir = self.output_root / self.episode_id
        self.output_dir.mkdir(parents=True, exist_ok=False)
        key = secrets.token_bytes(32)
        self._listener = Listener(("127.0.0.1", 0), family="AF_INET", authkey=key)
        host, port = self._listener.address
        self._listener._listener._socket.settimeout(self.startup_timeout)
        env = dict(os.environ, SC2_MICRO_HOST=host, SC2_MICRO_PORT=str(port),
                   SC2_MICRO_AUTHKEY=key.hex(), PYTHONNOUSERSITE="1", PYTHONUNBUFFERED="1")
        command = [self.worker_python, "-s", "-u", str(ROOT / "tools" / "sc2_micro_worker.py"),
                   "--episode-id", self.episode_id, "--seed", str(int(seed)),
                   "--output-dir", str(self.output_dir), "--game-path", self.game_path,
                   "--max-game-seconds", str(self.max_game_seconds), "--map", self.map_name,
                   "--scenario", self.task["scenario"], "--distance", str(self.task["distance"]),
                   "--health-fraction", str(self.task["health_fraction"]),
                   "--enemy-health-fraction", str(self.task["enemy_health_fraction"])]
        command += ["--enemy-count", str(self.task["enemy_count"])]
        if self.task["enemy_count"] == 2:
            command += ["--second-distance", str(self.task["second_distance"]),
                        "--second-enemy-health-fraction", str(self.task["second_enemy_health_fraction"])]
        self._log = (self.output_dir / "worker.log").open("w", encoding="utf-8")
        started = time.monotonic()
        try:
            self._process = subprocess.Popen(command, cwd=ROOT, env=env, stdout=self._log,
                                             stderr=subprocess.STDOUT,
                                             creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            self._connection = self._listener.accept()
            self._listener.close()
            self._listener = None
            packet = self._receive(max(0.01, self.startup_timeout - (time.monotonic() - started)))
            self._state = validate_state(packet, episode_id=self.episode_id, decision_id=0, kind="ready")
            if self._state["terminated"] or self._state["truncated"]:
                raise ValueError("Reset did not produce a live initial state")
            self._done = False
            info = self._info(packet)
            info["reset_wall_seconds"] = time.monotonic() - started
            return tuple(packet["obs"]), info
        except Exception as exc:
            self._cleanup()
            raise RuntimeError(f"SC2 reset failed ({type(exc).__name__}: {exc}); log: {self.output_dir / 'worker.log'}") from exc

    def _receive(self, timeout):
        if not self._connection.poll(timeout):
            reason = "worker_exit" if self._process.poll() is not None else "ipc_timeout"
            raise TimeoutError(reason)
        packet = self._connection.recv()
        if isinstance(packet, dict) and packet.get("type") == "error":
            raise RuntimeError(str(packet.get("info", {}).get("reason", "worker_error")))
        return packet

    def _info(self, packet):
        if packet["info"].get("task") != self.task:
            raise ValueError("Worker task does not match the requested training task")
        return dict(packet["info"], episode_id=self.episode_id, decision_id=packet["decision_id"],
                    frame=packet["frame"], unit_slot=0, action_mask=tuple(packet["mask"]),
                    output_dir=str(self.output_dir))

    def action_masks(self):
        return tuple(self._state["mask"]) if self._state is not None else HOLD_MASK

    def step(self, action):
        if self._done:
            raise RuntimeError("Call reset() before stepping a completed environment")
        if isinstance(action, bool) or not isinstance(action, numbers.Integral) or not 0 <= action < 5:
            raise ValueError("Action must be an integer in Discrete(5)")
        if not self.action_masks()[action]:
            raise ValueError("Action is masked at the current state")
        state = self._state
        started = time.monotonic()
        try:
            self._connection.send(message("action", self.episode_id, state["decision_id"],
                                          state["frame"], action=int(action)))
            packet = validate_state(self._receive(self.step_timeout), episode_id=self.episode_id,
                                    decision_id=state["decision_id"] + 1, kind="transition",
                                    previous_frame=state["frame"])
            self._state = packet
            self._done = packet["terminated"] or packet["truncated"]
            info = self._info(packet)
            if self._done:
                closed = self._receive(self.step_timeout)
                expected = dict(protocol=PROTOCOL, type="closed", episode_id=self.episode_id,
                                decision_id=packet["decision_id"], frame=packet["frame"], unit_slot=0)
                if any(closed.get(key) != value for key, value in expected.items()):
                    raise ValueError("Missing official episode close confirmation")
                info["worker_close"] = closed.get("info", {})
                info["official_close_confirmed"] = True
                if self._process.wait(timeout=5) != 0:
                    raise RuntimeError("Worker exited nonzero after close confirmation")
                self._close_confirmed = True
                self.close_info = dict(closed["info"], worker_exit_code=0)
            info["step_wall_seconds"] = time.monotonic() - started
            obs = None if packet["obs"] is None else tuple(packet["obs"])
            return obs, float(packet["reward"]), packet["terminated"], packet["truncated"], info
        except Exception as exc:
            info = dict(system_failure=True, rollout_discard=True, reason=str(exc),
                        error_type=type(exc).__name__, episode_id=self.episode_id,
                        decision_id=state["decision_id"], frame=state["frame"],
                        observation_source="unavailable", action_mask=HOLD_MASK,
                        output_dir=str(self.output_dir))
            self._cleanup()
            return None, 0.0, False, True, info

    def close(self):
        try:
            if self._process is None or self._close_confirmed:
                return
            if self._state is None or self._done:
                raise MicroEnvCloseError("Worker has no live state for graceful close")
            state = self._state
            started = time.monotonic()
            self._connection.send(message("close", self.episode_id, state["decision_id"],
                                          state["frame"]))
            closed = self._receive(self.step_timeout)
            expected = message("closed", self.episode_id, state["decision_id"], state["frame"])
            if (not isinstance(closed, dict)
                    or any(closed.get(key) != value for key, value in expected.items())
                    or closed.get("info", {}).get("reason") != "training_budget_close"):
                raise ValueError("Missing training budget close confirmation")
            remaining = max(0.01, self.step_timeout - (time.monotonic() - started))
            if self._process.wait(timeout=remaining) != 0:
                raise RuntimeError("Worker exited nonzero after close confirmation")
            self._close_confirmed = True
            self.close_info = dict(closed["info"], worker_exit_code=0)
        except Exception as exc:
            raise MicroEnvCloseError(f"SC2 graceful close failed: {exc}") from exc
        finally:
            self._cleanup()

    def _cleanup(self):
        """Release IPC and, on failure, force only this worker's process tree."""
        self._done = True
        self._state = None
        if self._connection is not None:
            self._connection.close()
            self._connection = None
        if self._listener is not None:
            self._listener.close()
            self._listener = None
        if self._process is not None:
            if self._process.poll() is None:
                if os.name == "nt":
                    try:
                        subprocess.run(["taskkill", "/PID", str(self._process.pid), "/T", "/F"],
                                       capture_output=True, timeout=10,
                                       creationflags=subprocess.CREATE_NO_WINDOW)
                    except subprocess.TimeoutExpired:
                        self._process.kill()
                else:
                    self._process.kill()
                try:
                    self._process.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    self._process.kill()
            self._process = None
        if self._log is not None:
            self._log.close()
            self._log = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        try:
            self.close()
        except MicroEnvCloseError as close_error:
            if exc is None:
                raise
            exc.add_note(str(close_error))
