#!/usr/bin/env python3
"""
score_run.py — grade a benchmark attempt.

Pass/fail is a bad benchmark metric: on a task this hard almost every model
scores zero and you learn nothing about which is closer. So this reports a
gradient instead.

Metrics
-------
solved            did every face end up uniform (the headline)
faces_uniform     0..6, partial credit that moves early
sticker_score     0..1, fraction of stickers matching their face's modal colour
distance          3x3 only: optimal-ish solution length from here, via Kociemba.
                  This is the good one. Scramble depth 20 -> distance 18; if the
                  model works for 60 moves and distance is now 14, it made real
                  progress. If distance went UP it was thrashing.
distance_reduced  distance at scramble minus distance now. Negative is bad.

Usage
-----
    python tools/score_run.py                        # score the live cube
    python tools/score_run.py --log runs/x.jsonl     # add timing from a run log
    python tools/score_run.py --selftest             # verify the facelet mapping
"""

import argparse
import json
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from agent_client import Twist  # noqa: E402
from engine import runlog  # noqa: E402

FACE_ORDER = ("U", "R", "F", "D", "L", "B")


def kociemba_string(facelets: dict) -> str:
    """Flatten a facelet dump into the 54-character URFDLB string Kociemba wants.

    Our row/column convention already matches the standard one (row 0 is the top
    row seen looking at that face, column 0 the left), so this is a straight
    concatenation. `--selftest` proves it rather than trusting it.
    """
    out = []
    for face in FACE_ORDER:
        rows = facelets[face]
        if len(rows) != 3 or any(len(r) != 3 for r in rows):
            raise ValueError("Kociemba scoring only applies to a 3x3")
        out.append("".join(rows))
    return "".join(out)


SOLVED_STRING = "".join(f * 9 for f in FACE_ORDER)


def distance(facelets: dict):
    """Optimal-ish solution length from this state, or None if unavailable."""
    try:
        import kociemba
    except ImportError:
        return None, "kociemba not installed"
    try:
        state = kociemba_string(facelets)
    except ValueError as exc:
        return None, str(exc)
    # Handed an already-solved cube, kociemba returns a 13-move identity
    # sequence rather than an empty one. Left unhandled that reports a solved
    # cube as 13 moves from solved, which is exactly the sort of wrong number
    # that ends up in a chart.
    if state == SOLVED_STRING:
        return 0, None
    try:
        return len(kociemba.solve(state).split()), None
    except Exception as exc:
        return None, str(exc)


def partial_credit(facelets: dict) -> dict:
    """Face-level partial credit, works for every cube size."""
    uniform = 0
    matched = total = 0
    per_face = {}
    for face, rows in facelets.items():
        stickers = "".join(rows)
        counts = Counter(stickers)
        modal, modal_n = counts.most_common(1)[0]
        per_face[face] = round(modal_n / len(stickers), 3)
        if modal_n == len(stickers):
            uniform += 1
        matched += modal_n
        total += len(stickers)
    return {
        "faces_uniform": uniform,
        "faces_total": len(facelets),
        "sticker_score": round(matched / total, 4) if total else 0.0,
        "per_face": per_face,
    }


def score_live(host, port, log_path=None) -> dict:
    with Twist(host, port) as cb:
        truth = cb.ground_truth(grader=True)

    facelets = truth.get("facelets", {})
    result = {
        "cube": truth["cube"],
        "solved": truth["solved"],
        "move_count": truth["move_count"],
        "task_armed": truth.get("task_armed"),
        "scramble_depth": truth.get("task_depth"),
    }
    if not truth.get("task_armed"):
        # No scramble was ever applied, so the model was handed a solved cube.
        # Scoring this would record a fake success.
        result["VOID"] = ("no task was armed — the cube was never scrambled. "
                          "Run tools/new_task.py before handing the model the "
                          "prompt. This run measures nothing.")

    if truth["family"] == "mirror":
        # No colours to score. Shape is restored or it is not; the only partial
        # signal worth having would be per-piece placement, which the kociemba
        # string cannot express.
        result["scoring"] = "shape-only; solved is the whole metric"
        result["faces_uniform"] = 6 if truth["solved"] else 0
    else:
        result.update(partial_credit(facelets))

    if truth["cube"] == "3x3":
        dist, err = distance(facelets)
        result["distance"] = dist
        if err:
            result["distance_error"] = err

    if log_path:
        events = runlog.read_events(log_path)
        result["timing"] = runlog.summarise(events)
        scramble = next((e for e in events if e["kind"] == "scramble"), None)
        if scramble:
            result["scramble_depth"] = scramble.get("depth")
            result["scramble"] = scramble.get("moves")
        # Only untagged reads are suspicious: the scorer tags its own.
        peeks = sum(1 for e in events
                    if e["kind"] == "truth_read" and not e.get("by_grader"))
        result["answer_key_peeks"] = peeks
        if peeks:
            result["INTEGRITY"] = (
                f"the answer key was read {peeks} time(s) by something other than "
                f"the grader during this run. Treat this run as void.")
    return result


def selftest(host, port) -> int:
    """Prove the facelet mapping by solving a scramble through the real key path.

    Mutates the live cube. If the mapping were wrong, Kociemba would either
    reject the string or return moves that do not solve it.
    """
    print("selftest: scrambling, solving via Kociemba, replaying through keys...")
    with Twist(host, port) as cb:
        cb.select("3x3")
        cb.scramble(moves=25, seed=4242)
        facelets = cb.ground_truth()["facelets"]
        dist, err = distance(facelets)
        if dist is None:
            print(f"FAIL: {err}")
            return 1
        import kociemba
        solution = kociemba.solve(kociemba_string(facelets)).split()
        print(f"  Kociemba returned {len(solution)} moves: {' '.join(solution)}")
        cb.move(*solution)
        state = cb.status()
        print(f"  solved after replay: {state['solved']}  (moves {state['move_count']})")
        if state["solved"]:
            print("PASS — facelet mapping and move engine agree with Kociemba.")
            return 0
        print("FAIL — the mapping or the move engine is wrong.")
        return 1


def main():
    ap = argparse.ArgumentParser(description="Score a TWIST attempt")
    ap.add_argument("--host", default="127.0.0.1")
    ap.add_argument("--port", type=int, default=8181)
    ap.add_argument("--log", default=None, help="run log to fold timing into")
    ap.add_argument("--selftest", action="store_true",
                    help="verify scoring against Kociemba (mutates the live cube)")
    args = ap.parse_args()

    if args.selftest:
        sys.exit(selftest(args.host, args.port))

    log = args.log
    if log is None:
        runs = sorted((ROOT / "runs").glob("*.jsonl"),
                      key=lambda p: p.stat().st_mtime, reverse=True)
        log = str(runs[0]) if runs else None

    print(json.dumps(score_live(args.host, args.port, log), indent=2))


if __name__ == "__main__":
    main()
