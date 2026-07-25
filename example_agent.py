#!/usr/bin/env python3
"""
example_agent.py — end-to-end smoke test of the agent channel.

Not a solver: it scrambles each cube, photographs it, then presses the inverse
sequence back through the key path and photographs it again. If this script
prints SOLVED for all six cubes, the whole loop a benchmark model depends on —
keys in, pixels out — is working.

    python example_agent.py
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

from agent_client import Twist, TwistError  # noqa: E402

CUBES = ["2x2", "3x3", "4x4", "5x5", "6x6", "mirror"]


def invert(move: str) -> str:
    if move.endswith("2"):
        return move
    return move[:-1] if move.endswith("'") else move + "'"


def main():
    try:
        cb = Twist().connect()
    except OSError as exc:
        print(f"cannot reach the simulation ({exc}).\n"
              f"Start it first:  python app.py")
        return 1

    failures = 0
    with cb:
        for cube in CUBES:
            cb.select(cube)
            scrambled = cb.scramble(moves=18, seed=2024)
            before = cb.screenshot(views=["iso", "iso_back"], tag=f"before_{cube}")

            # Drive the cube purely through keystrokes, one move at a time.
            for move in reversed(scrambled["scramble"]):
                cb.move(invert(move))

            state = cb.status()
            after = cb.screenshot(views=["iso"], tag=f"after_{cube}")
            flag = "SOLVED" if state["solved"] else "NOT SOLVED"
            if not state["solved"]:
                failures += 1
            print(f"{cube:>6}  {flag:<10} moves={state['move_count']:<3} "
                  f"before={Path(before[0]).name} after={Path(after[0]).name}")

    print("\nall cubes solved" if not failures else f"\n{failures} cube(s) failed")
    return 0 if not failures else 1


if __name__ == "__main__":
    try:
        sys.exit(main())
    except TwistError as exc:
        print(f"bridge error: {exc}")
        sys.exit(1)
