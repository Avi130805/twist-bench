"""
launcher.py — make sure the simulation window is up before an agent talks to it.

An agent should never have to ask a human to start the app first, and the window
has to be genuinely on screen so a person can watch the solve happen live. This
module checks the loopback port, starts `app.py` detached if nothing answers, and
waits for the bridge to come up.

The interpreter matters: `agent_cli.py` only needs the stdlib, so an agent may
well be running it under a bare system python. The app itself needs the venv with
pygame and PyOpenGL, so we resolve that explicitly rather than trusting
`sys.executable`.
"""

import os
import socket
import subprocess
import sys
import time
from pathlib import Path

APP_DIR = Path(__file__).resolve().parents[1]
APP_PATH = APP_DIR / "app.py"
LOG_PATH = APP_DIR / "shots" / "app.log"

# Interpreters that can actually run the simulation, best first. A repo-local
# venv wins; the Rubix one is kept as a fallback for the original layout this
# grew out of. Failing both we use whatever is running us, which is correct when
# the dependencies are installed globally.
_VENV_CANDIDATES = (
    APP_DIR / ".venv" / "bin" / "python",
    APP_DIR / "venv" / "bin" / "python",
    APP_DIR.parent / "Rubix" / "venv" / "bin" / "python",
)


def port_is_live(host: str, port: int, timeout=0.4) -> bool:
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except OSError:
        return False


def resolve_python() -> str:
    for candidate in _VENV_CANDIDATES:
        if candidate.exists():
            return str(candidate)
    return sys.executable


def ensure_running(host="127.0.0.1", port=8181, cube=None, seed=None,
                   pace=None, timeout=40.0, log=None) -> dict:
    """Return once the simulation is answering on (host, port).

    Reports what it did: {"started": bool, "pid": int|None, "python": str}.
    """
    if port_is_live(host, port):
        return {"ok": True, "started": False, "pid": None, "python": None,
                "detail": "simulation already running"}

    if host not in ("127.0.0.1", "localhost", "::1"):
        raise RuntimeError(f"refusing to launch a simulation for remote host {host}")
    if not APP_PATH.exists():
        raise RuntimeError(f"cannot find {APP_PATH}")

    python = resolve_python()
    cmd = [python, str(APP_PATH), "--host", host, "--port", str(port)]
    if cube:
        cmd += ["--cube", cube]
    if seed is not None:
        cmd += ["--seed", str(seed)]
    if pace is not None:
        cmd += ["--pace", str(pace)]

    LOG_PATH.parent.mkdir(parents=True, exist_ok=True)
    handle = open(LOG_PATH, "ab", buffering=0)
    handle.write(f"\n=== launched {time.strftime('%Y-%m-%d %H:%M:%S')} ===\n".encode())

    # start_new_session keeps the window alive if the agent's shell goes away.
    proc = subprocess.Popen(
        cmd,
        cwd=str(APP_DIR),
        stdout=handle,
        stderr=subprocess.STDOUT,
        stdin=subprocess.DEVNULL,
        start_new_session=True,
        env={**os.environ, "PYTHONUNBUFFERED": "1"},
    )

    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if port_is_live(host, port):
            if log:
                log(f"[launcher] simulation up on {host}:{port} (pid {proc.pid})")
            return {"ok": True, "started": True, "pid": proc.pid, "python": python,
                    "detail": f"launched {APP_PATH.name}"}
        if proc.poll() is not None:
            tail = ""
            try:
                tail = LOG_PATH.read_text(errors="replace")[-1200:]
            except OSError:
                pass
            raise RuntimeError(
                f"simulation exited immediately (code {proc.returncode}).\n"
                f"Interpreter: {python}\nLog tail:\n{tail}"
            )
        time.sleep(0.25)

    raise TimeoutError(
        f"simulation did not open its bridge on {host}:{port} within {timeout:.0f}s. "
        f"See {LOG_PATH}"
    )
