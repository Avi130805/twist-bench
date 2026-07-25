"""
agent_client.py — Python client for driving the live TWIST simulation.

    from agent_client import Twist

    with Twist() as cb:
        cb.select("4x4")
        cb.scramble(seed=7)
        shots = cb.look()              # two isometric views -> PNG paths
        cb.press("r", "shift+u", "alt+f")
        print(cb.status()["solved"])

Every call blocks until the simulation has actually finished the work, so a
screenshot taken right after a key press always shows the settled cube.
"""

import json
import socket
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from engine.launcher import ensure_running, port_is_live  # noqa: E402

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8181


class TwistError(RuntimeError):
    pass


class Twist:
    def __init__(self, host=DEFAULT_HOST, port=DEFAULT_PORT, timeout=180.0,
                 autostart=True, cube=None, seed=None, pace=None):
        self.host = host
        self.port = port
        self.timeout = timeout
        self.autostart = autostart
        self.launch_cube = cube
        self.launch_seed = seed
        self.launch_pace = pace
        self.launch_info = None
        self._sock = None
        self._stream = None

    # ── connection ───────────────────────────────────────────────────────
    def connect(self):
        """Connect, opening the simulation window first if it is not up yet."""
        if self._sock is not None:
            return self
        if self.autostart and not port_is_live(self.host, self.port):
            self.launch_info = ensure_running(
                self.host, self.port, cube=self.launch_cube,
                seed=self.launch_seed, pace=self.launch_pace)
        self._sock = socket.create_connection((self.host, self.port), timeout=self.timeout)
        self._stream = self._sock.makefile("rwb")
        return self

    def close(self):
        for obj in (self._stream, self._sock):
            try:
                if obj:
                    obj.close()
            except OSError:
                pass
        self._stream = self._sock = None

    def __enter__(self):
        return self.connect()

    def __exit__(self, *exc):
        self.close()

    # ── raw protocol ─────────────────────────────────────────────────────
    def send(self, cmd: str, **payload) -> dict:
        if self._sock is None:
            self.connect()
        payload["cmd"] = cmd
        line = json.dumps(payload) + "\n"

        try:
            raw = self._exchange(line)
        except (OSError, ConnectionError) as exc:
            # The window went away mid-run. Bring it back and try once more,
            # rather than stranding a long agent session.
            if not self.autostart:
                raise TwistError(f"lost the simulation: {exc}") from exc
            self.close()
            self.connect()
            raw = self._exchange(line)

        result = json.loads(raw)
        if not result.get("ok", False):
            raise TwistError(result.get("error", "unknown error"))
        return result

    def _exchange(self, line: str) -> bytes:
        self._stream.write(line.encode("utf-8"))
        self._stream.flush()
        raw = self._stream.readline()
        if not raw:
            raise ConnectionError("simulation closed the connection")
        return raw

    def ensure(self) -> dict:
        """Open the simulation window if it is not already up."""
        if port_is_live(self.host, self.port):
            return {"ok": True, "started": False, "detail": "simulation already running"}
        info = ensure_running(self.host, self.port, cube=self.launch_cube,
                              seed=self.launch_seed, pace=self.launch_pace)
        self.launch_info = info
        return info

    # ── commands ─────────────────────────────────────────────────────────
    def status(self) -> dict:
        return self.send("status")

    def keymap(self) -> dict:
        return self.send("keymap")

    def press(self, *keys, wait=True) -> dict:
        """Press keys exactly as a human would: press('r', 'shift+u', 'alt+f')."""
        flat = []
        for key in keys:
            flat.extend(key.split() if isinstance(key, str) else key)
        return self.send("keys", keys=flat, wait=wait)

    def move(self, *moves, wait=True) -> dict:
        """Sugar over press(): move('R', "U'", 'F2') translates to keystrokes."""
        flat = []
        for m in moves:
            flat.extend(m.split() if isinstance(m, str) else m)
        return self.send("moves", moves=flat, wait=wait)

    def select(self, cube: str) -> dict:
        """cube is one of 2x2, 3x3, 4x4, 5x5, 6x6, mirror."""
        return self.send("select", cube=cube)

    def scramble(self, moves=None, seed=None) -> dict:
        return self.send("scramble", moves=moves, seed=seed)

    def reset(self) -> dict:
        return self.send("reset")

    def undo(self) -> dict:
        return self.send("undo")

    def camera(self, view=None, yaw=None, pitch=None, zoom=None) -> dict:
        return self.send("camera", view=view, yaw=yaw, pitch=pitch, zoom=zoom)

    def pace(self, seconds=None) -> dict:
        """Minimum wall-clock interval between agent moves, so a human can watch."""
        return self.send("pace", seconds=seconds)

    def screenshot(self, views=None, tag="agent", hud=False, sheet=False) -> list:
        result = self.send("screenshot", views=views, tag=tag, hud=hud, sheet=sheet)
        return result["images"]

    def look(self, tag="look", sheet=False) -> list:
        """Two opposite isometric shots — together they show all six faces."""
        return self.screenshot(views=["iso", "iso_back"], tag=tag, sheet=sheet)

    def ground_truth(self, grader=False) -> dict:
        """Sticker dump + move history. For scoring, not for the model.

        Pass grader=True when this is the operator scoring a run, so the read is
        tagged as legitimate and does not count against the model's integrity.
        """
        return self.send("state", grader=grader)

    def stop_simulation(self) -> dict:
        """Close the window cleanly so the run log and video are finalised."""
        was = self.autostart
        self.autostart = False       # never relaunch what we just asked to close
        try:
            return self.send("quit")
        finally:
            self.autostart = was


# Aliases. `Twist` is the real name; the others keep older callers and the
# all-caps project name working.
TWIST = Twist
CubeBench = Twist
CubeBenchError = TwistError
