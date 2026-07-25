#!/usr/bin/env python3
"""
new_task.py — arm one graded task. Run this BEFORE you hand a model the prompt.

Pasting the prompt into a model is not enough on its own. The model's first
command will happily autostart the simulation, and a freshly started simulation
holds a SOLVED cube — so the model reports "already solved" and the run silently
measures nothing. This script is the missing step: it opens the window, selects
the cube, scrambles it to a chosen depth from a chosen seed, and prints the task
record you need in order to score and reproduce the run.

    python tools/new_task.py                                  # 3x3, depth 20
    python tools/new_task.py --cube 4x4 --depth 12 --seed 7
    python tools/new_task.py --depth 3 --pace 0.3 --record videos/run.mp4
    python tools/new_task.py --print-prompt                   # also emit the prompt
"""

import argparse
import json
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_client import Twist, TwistError  # noqa: E402
from engine import keymap  # noqa: E402
from engine.launcher import port_is_live, resolve_python  # noqa: E402


def main():
    ap = argparse.ArgumentParser(description="Arm one TWIST task")
    ap.add_argument("--cube", default="3x3", choices=list(keymap.CUBE_IDS))
    ap.add_argument("--depth", type=int, default=20,
                    help="scramble depth — the difficulty dial. Sweep it.")
    ap.add_argument("--seed", type=int, default=None,
                    help="scramble seed; same seed + same cube = same task")
    ap.add_argument("--pace", type=float, default=None,
                    help="minimum seconds between agent moves, for watchability")
    ap.add_argument("--record", default=None, metavar="OUT.mp4",
                    help="record this run (only applies if the window is not up yet)")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8181)
    ap.add_argument("--print-prompt", action="store_true",
                    help="also print the standalone prompt for this cube")
    args = ap.parse_args()

    already_up = port_is_live(args.host, args.port)
    if already_up and args.record:
        print("note: the window is already running, so --record was NOT applied.\n"
              "      Stop it first (python3 agent_cli.py stop) to record this run.",
              file=sys.stderr)

    if not already_up:
        # Launch here rather than via the client so --record/--pace get through.
        cmd = [resolve_python(), str(ROOT / "app.py"),
               "--host", args.host, "--port", str(args.port), "--cube", args.cube]
        if args.pace is not None:
            cmd += ["--pace", str(args.pace)]
        if args.record:
            cmd += ["--record", args.record]
        log = open(ROOT / "shots" / "app.log", "ab", buffering=0)
        subprocess.Popen(cmd, cwd=str(ROOT), stdout=log, stderr=subprocess.STDOUT,
                         stdin=subprocess.DEVNULL, start_new_session=True)
        deadline = time.monotonic() + 40
        while time.monotonic() < deadline and not port_is_live(args.host, args.port):
            time.sleep(0.25)
        if not port_is_live(args.host, args.port):
            print("failed to start the simulation; see shots/app.log", file=sys.stderr)
            return 1

    with Twist(args.host, args.port, autostart=False) as cb:
        cb.select(args.cube)
        if args.pace is not None and already_up:
            cb.pace(args.pace)
        result = cb.scramble(moves=args.depth, seed=args.seed)
        state = cb.status()

    if state["solved"]:
        print("ERROR: the cube came out solved — the scramble did nothing.\n"
              "       Check --depth is greater than zero.", file=sys.stderr)
        return 1

    task = {
        "cube": args.cube,
        "scramble_depth": args.depth,
        "seed": args.seed,
        "scramble": result["scramble"],
        "task_armed": state["task_armed"],
        "solved_at_start": state["solved"],
    }
    print(json.dumps(task, indent=2))
    print("\nTask armed. Keep the scramble above — it is the answer key; do not "
          "show it to the model.", file=sys.stderr)

    if args.print_prompt:
        gen = ROOT / "tools" / "gen_prompt.py"
        print("\n" + "=" * 70 + "\nPROMPT — paste everything below into the model\n"
              + "=" * 70 + "\n", file=sys.stderr)
        subprocess.run([sys.executable, str(gen), "--cube", args.cube, "--standalone"])
    return 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except (TwistError, OSError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        sys.exit(1)
