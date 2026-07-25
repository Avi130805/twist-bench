"""
runlog.py — timestamped event log for one benchmark run.

Every command, move, screenshot and thinking pause is written as one JSON object
per line with both wall-clock and run-relative timestamps. Two things depend on
this: scoring a run afterwards, and building the video — `tools/make_video.py`
reads the log to know which stretches were the model thinking (compress those)
and which were the cube actually moving (keep those at real speed).

Thinking time is the interesting measurement here. The model is thinking exactly
when a client is attached, nothing is animating, and no keys are queued: the gap
between one command completing and the next arriving.
"""

import json
import os
import time
from pathlib import Path


class RunLog:
    def __init__(self, path, meta=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.t0 = time.time()
        self.m0 = time.monotonic()
        self._fh = open(self.path, "a", buffering=1, encoding="utf-8")
        self.event("run_start", **(meta or {}))

    # ── writing ──────────────────────────────────────────────────────────
    def event(self, kind: str, **payload):
        record = {
            "t_wall": round(time.time(), 3),
            "t_run": round(time.monotonic() - self.m0, 3),
            "kind": kind,
        }
        record.update(payload)
        self._fh.write(json.dumps(record, default=str) + "\n")
        return record

    def close(self, **payload):
        try:
            self.event("run_end", **payload)
            self._fh.close()
        except (OSError, ValueError):
            pass

    # ── run-relative clock ───────────────────────────────────────────────
    @property
    def elapsed(self) -> float:
        return time.monotonic() - self.m0

    def restart_clock(self):
        """Called on scramble: the run proper starts when the task is set."""
        self.m0 = time.monotonic()
        self.t0 = time.time()


def default_path(root, cube: str) -> Path:
    stamp = time.strftime("%Y%m%d_%H%M%S")
    return Path(root) / "runs" / f"{stamp}_{cube}.jsonl"


def read_events(path):
    """Load a run log. Skips malformed lines rather than dying on a partial write."""
    out = []
    with open(path, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                out.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return out


def summarise(events) -> dict:
    """Headline numbers for a run: durations, move count, thinking share."""
    if not events:
        return {}

    moves = [e for e in events if e["kind"] == "move"]
    thinks = [e for e in events if e["kind"] == "think"]
    shots = [e for e in events if e["kind"] == "screenshot"]
    cmds = [e for e in events if e["kind"] == "command"]
    end = events[-1]

    think_total = sum(float(e.get("seconds", 0.0)) for e in thinks)
    wall = float(end.get("t_run", 0.0))

    return {
        "cube": next((e.get("cube") for e in events if e.get("cube")), None),
        "wall_seconds": round(wall, 1),
        "thinking_seconds": round(think_total, 1),
        "acting_seconds": round(max(0.0, wall - think_total), 1),
        "thinking_share": round(think_total / wall, 3) if wall > 0 else None,
        "moves": len(moves),
        "screenshots": len(shots),
        "commands": len(cmds),
        "longest_think": round(max((float(e.get("seconds", 0)) for e in thinks),
                                   default=0.0), 1),
        "solved": bool(end.get("solved", False)),
        "truth_reads": sum(1 for e in events if e["kind"] == "truth_read"),
        "answer_key_peeks": sum(1 for e in events
                                if e["kind"] == "truth_read" and not e.get("by_grader")),
    }


def env_flag(name: str, default=False) -> bool:
    raw = os.environ.get(name)
    if raw is None:
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")
