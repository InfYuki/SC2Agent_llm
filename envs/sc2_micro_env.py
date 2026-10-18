"""Real SC2 reset/step bridge; custom Gym-style API, not a Gymnasium Env.

Every reset cold-starts an owned worker. Death/system failure may return obs=None;
system failures always carry rollout_discard=True and must not train a policy.
"""
from multiprocessing.connection import Listener
import numbers
import os
from pathlib import Path
import secrets
import subprocess
import sys
import time
import uuid

from envs.micro_ipc import HOLD_MASK, PROTOCOL, message, validate_state

ROOT = Path(__file__).resolve().parents[1]


class SC2MicroEnv:
    def __init__(self, *, game_path=r"C:\Program Files (x86)\StarCraft II",
                 map_name="Ancient Cistern LE", max_game_seconds=20,
                 startup_timeout=90, step_timeout=30, output_root=None):
        self.game_path = str(game_path)
        self.map_name = map_name
        self.max_game_seconds = float(max_game_seconds)
        self.startup_timeout = float(startup_timeout)
        self.step_timeout = float(step_timeout)
        if min(self.max_game_seconds, self.startup_timeout, self.step_timeout) <= 0:
            raise ValueError("Time limits must be positive")
        self.output_root = Path(output_root or ROOT / "artifacts" / "micro_env")
        self._process = self._listener = self._connection = self._log = None
        self._state = None
        self._done = True

    def reset(self, *, seed=42, options=None):
        self.close()
        if options:
            raise ValueError("MVP uses one fixed 1v1 Marine scenario; options are unsupported")
        self.episode_id = uuid.uuid4().hex
        self.output_dir = self.output_root / self.episode_id
        self.output_dir.mkdir(parents=True, exist_ok=False)
        key = secrets.token_bytes(32)
        self._listener = Listener(("127.0.0.1", 0), family="AF_INET", authkey=key)
        host, port = self._listener.address
        self._listener._listener._socket.settimeout(self.startup_timeout)
        env = dict(os.environ, SC2_MICRO_HOST=host, SC2_MICRO_PORT=str(port),
                   SC2_MICRO_AUTHKEY=key.hex(), PYTHONNOUSERSITE="1", PYTHONUNBUFFERED="1")
        command = [sys.executable, "-s", "-u", str(ROOT / "tools" / "sc2_micro_worker.py"),
                   "--episode-id", self.episode_id, "--seed", str(int(seed)),
                   "--output-dir", str(self.output_dir), "--game-path", self.game_path,
                   "--max-game-seconds", str(self.max_game_seconds), "--map", self.map_name]
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
            self.close()
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
                self._process.wait(timeout=5)
            info["step_wall_seconds"] = time.monotonic() - started
            obs = None if packet["obs"] is None else tuple(packet["obs"])
            return obs, float(packet["reward"]), packet["terminated"], packet["truncated"], info
        except Exception as exc:
            info = dict(system_failure=True, rollout_discard=True, reason=str(exc),
                        error_type=type(exc).__name__, episode_id=self.episode_id,
                        decision_id=state["decision_id"], frame=state["frame"],
                        observation_source="unavailable", action_mask=HOLD_MASK,
                        output_dir=str(self.output_dir))
            self.close()
            return None, 0.0, False, True, info

    def close(self):
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

    def __exit__(self, *_):
        self.close()
