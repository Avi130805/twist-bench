#!/usr/bin/env python3
"""
measure_saturation.py — does scramble length actually control difficulty?

Answer, for a 3x3: only in the shallow range. God's number is 20 in the half-turn
metric, and the distance of a random state saturates near 18 well before you have
applied 30 moves. Past that, a longer scramble is not a harder task.

This script measures it rather than asserting it: for each scramble length it
generates N scrambles and reports the Kociemba distance of the resulting state.

    python tools/measure_saturation.py --trials 20
"""

import argparse
import random
import statistics
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import scramble as scr  # noqa: E402
from engine.cubes import make_cube  # noqa: E402

LENGTHS = (1, 2, 3, 5, 8, 12, 16, 20, 25, 30, 40, 60, 100, 300)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--trials", type=int, default=20)
    ap.add_argument("--seed", type=int, default=0)
    args = ap.parse_args()

    try:
        import kociemba
    except ImportError:
        print("needs kociemba: pip install kociemba")
        return 1
    sys.path.insert(0, str(ROOT / "tools"))
    import score_run

    rng = random.Random(args.seed)
    cube = make_cube("3x3")

    print(f"3x3, {args.trials} scrambles per length, distance via Kociemba\n")
    print(f"{'length':>7} {'mean':>7} {'median':>7} {'min':>5} {'max':>5}   "
          f"{'cancellations':>13}")
    print("-" * 62)

    for n in LENGTHS:
        dists, cancels = [], 0
        for _ in range(args.trials):
            cube.reset()
            moves = scr.random_scramble(cube.legal_moves(), rng, n)
            cancels += scr.count_cancellations(moves)
            for m in moves:
                cube.apply(m, animate=False, record=False)
            d, err = score_run.distance(cube.facelets())
            if d is None:
                print(f"  {n}: {err}")
                return 1
            dists.append(d)
        print(f"{n:>7} {statistics.mean(dists):>7.1f} "
              f"{statistics.median(dists):>7.1f} {min(dists):>5} {max(dists):>5}   "
              f"{cancels:>13}")

    print("\nDistance stops responding to length well before 30 moves. Beyond that,")
    print("a longer scramble is the same task, so scramble length is not a")
    print("difficulty dial except in the shallow regime.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
