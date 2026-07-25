#!/usr/bin/env python3
"""
agent_cli.py — shell front-end to the live simulation, for tool-using models.

    python agent_cli.py status
    python agent_cli.py keymap
    python agent_cli.py select 4x4
    python agent_cli.py scramble --moves 30 --seed 7
    python agent_cli.py press r shift+u alt+f
    python agent_cli.py move R U2 "F'"
    python agent_cli.py look
    python agent_cli.py shot --views iso iso_back front
    python agent_cli.py camera --view top
    python agent_cli.py reset

Every subcommand prints one JSON object on stdout and exits non-zero on error,
so it drops straight into an agent tool loop.
"""

import argparse
import json
import sys

from agent_client import DEFAULT_HOST, DEFAULT_PORT, Twist, TwistError


def build_parser():
    p = argparse.ArgumentParser(description="Drive the TWIST simulation")
    p.add_argument("--host", default=DEFAULT_HOST)
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--no-autostart", action="store_true",
                   help="fail instead of opening the simulation window if it is down")
    sub = p.add_subparsers(dest="cmd", required=True)

    ens = sub.add_parser("ensure", help="open the simulation window if it is not running")
    ens.add_argument("--cube", default=None)
    ens.add_argument("--seed", type=int, default=None)
    ens.add_argument("--pace", type=float, default=None,
                     help="pause between agent moves, in seconds, so a human can watch")

    sub.add_parser("status", help="cube, solved flag, move count, camera")
    sub.add_parser("keymap", help="key layout for the cube currently on screen")
    sub.add_parser("reset", help="restore the current cube to solved")
    sub.add_parser("undo", help="undo the last move")
    lk = sub.add_parser("look", help="two opposite isometric screenshots")
    lk.add_argument("--sheet", action="store_true",
                    help="return one labelled contact sheet instead of two images")
    sub.add_parser("truth", help="ground-truth sticker dump (for scoring)")
    sub.add_parser("stop", help="close the simulation window and finalise the recording")

    sel = sub.add_parser("select", help="switch cube")
    sel.add_argument("cube", choices=["2x2", "3x3", "4x4", "5x5", "6x6", "mirror"])

    scr = sub.add_parser("scramble", help="scramble the current cube")
    scr.add_argument("--moves", type=int, default=None)
    scr.add_argument("--seed", type=int, default=None)

    pr = sub.add_parser("press", help="press keys, e.g. press r shift+u alt+f")
    pr.add_argument("keys", nargs="+")
    pr.add_argument("--no-wait", action="store_true")

    mv = sub.add_parser("move", help="apply moves in cube notation, e.g. move R U2 \"F'\"")
    mv.add_argument("moves", nargs="+")
    mv.add_argument("--no-wait", action="store_true")

    shot = sub.add_parser("shot", help="screenshot one or more views")
    shot.add_argument("--views", nargs="*", default=None,
                      help="iso iso_back front back left right top bottom")
    shot.add_argument("--tag", default="agent")
    shot.add_argument("--hud", action="store_true")
    shot.add_argument("--sheet", action="store_true",
                      help="join the views into one labelled contact sheet")

    pac = sub.add_parser("pace", help="set the minimum interval between agent moves")
    pac.add_argument("seconds", nargs="?", type=float, default=None,
                     help="omit to read the current value")

    cam = sub.add_parser("camera", help="move the camera")
    cam.add_argument("--view")
    cam.add_argument("--yaw", type=float)
    cam.add_argument("--pitch", type=float)
    cam.add_argument("--zoom", type=float)
    return p


def run(args) -> dict:
    client = Twist(
        args.host, args.port,
        autostart=not args.no_autostart,
        cube=getattr(args, "cube", None) if args.cmd == "ensure" else None,
        seed=getattr(args, "seed", None) if args.cmd == "ensure" else None,
        pace=getattr(args, "pace", None) if args.cmd == "ensure" else None,
    )
    if args.cmd == "ensure":
        return client.ensure()

    with client as cb:
        if args.cmd == "status":
            return cb.status()
        if args.cmd == "keymap":
            return cb.keymap()
        if args.cmd == "reset":
            return cb.reset()
        if args.cmd == "undo":
            return cb.undo()
        if args.cmd == "truth":
            return cb.ground_truth()
        if args.cmd == "stop":
            return cb.stop_simulation()
        if args.cmd == "look":
            return {"images": cb.look(sheet=args.sheet)}
        if args.cmd == "select":
            return cb.select(args.cube)
        if args.cmd == "scramble":
            return cb.scramble(moves=args.moves, seed=args.seed)
        if args.cmd == "press":
            return cb.press(*args.keys, wait=not args.no_wait)
        if args.cmd == "move":
            return cb.move(*args.moves, wait=not args.no_wait)
        if args.cmd == "shot":
            return {"images": cb.screenshot(views=args.views, tag=args.tag,
                                            hud=args.hud, sheet=args.sheet)}
        if args.cmd == "pace":
            return cb.pace(args.seconds)
        if args.cmd == "camera":
            return cb.camera(view=args.view, yaw=args.yaw, pitch=args.pitch, zoom=args.zoom)
    raise SystemExit(f"unhandled command {args.cmd}")


def main():
    args = build_parser().parse_args()
    try:
        print(json.dumps(run(args), indent=2))
    except (TwistError, OSError) as exc:
        print(json.dumps({"ok": False, "error": str(exc)}), file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
