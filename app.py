#!/usr/bin/env python3
"""
app.py — TWIST: airgapped Rubik's cube simulation for visual AI benchmarks.

Six cubes in one window (2x2, 3x3, 4x4, 5x5, 6x6 and the 3x3 silver mirror cube),
switchable with a button click or an F-key. Every cube is driven by the same
keyboard layout, and an AI model drives it through the same keyboard layout over
a loopback socket — see agent_bridge.py and agent_client.py.

Run:
    python app.py
"""

import argparse
import atexit
import random
import signal
import sys
import time
import warnings
from collections import deque
from pathlib import Path

import pygame
from pygame.locals import *
from OpenGL.GL import *

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from agent_bridge import DEFAULT_HOST, DEFAULT_PORT, AgentBridge  # noqa: E402
from engine import keymap, pngwrite, recorder, runlog, textfont  # noqa: E402
# engine.cubes must come first: importing it puts engine/vendor/ on sys.path.
from engine.cubes import make_cube  # noqa: E402
from cube_renderer import init_gl, resize_gl  # noqa: E402  (vendored)

SHOTS_DIR = APP_DIR / "shots"

# pygame 2.6 renamed tostring/tobytes; keep working on either spelling. These two
# are pygame core, unlike load/save, so they work without SDL_image.
_surface_to_bytes = getattr(pygame.image, "tobytes", None) or pygame.image.tostring
_surface_from_bytes = getattr(pygame.image, "frombytes", None) or pygame.image.fromstring

# Camera presets: (pitch, yaw) in degrees.
VIEWS = {
    "iso": (25.0, -35.0),
    "iso_back": (-25.0, 145.0),
    "front": (0.0, 0.0),
    "back": (0.0, 180.0),
    "right": (0.0, -90.0),
    "left": (0.0, 90.0),
    "top": (89.0, 0.0),
    "bottom": (-89.0, 0.0),
}

KEY_ALIASES = {
    "esc": K_ESCAPE,
    "enter": K_RETURN,
    "return": K_RETURN,
    "spacebar": K_SPACE,
    "plus": K_EQUALS,
    "minus": K_MINUS,
    "backslash": K_BACKSLASH,
}

# ── HUD palette ──────────────────────────────────────────────────────────
BG_BAR = (18, 21, 26, 235)
BTN = (44, 50, 60, 245)
BTN_HOT = (72, 82, 98, 250)
BTN_ON = (32, 122, 92, 252)
TEXT = (226, 231, 238)
TEXT_DIM = (150, 160, 174)
GOOD = (86, 220, 150)
BAD = (255, 138, 120)
PANEL = (14, 17, 22, 232)


def _mmss(seconds: float) -> str:
    seconds = max(0.0, float(seconds))
    if seconds < 60:
        return f"{seconds:04.1f}s"
    m, s = divmod(int(seconds), 60)
    if m < 60:
        return f"{m}:{s:02d}"
    h, m = divmod(m, 60)
    return f"{h}:{m:02d}:{s:02d}"


def parse_keystroke(text: str):
    """'shift+r' -> (pygame key constant, modifier mask). None if unknown."""
    parts = [p for p in str(text).strip().lower().replace(" ", "").split("+") if p]
    if not parts:
        return None
    mods = 0
    for part in parts[:-1]:
        if part == "shift":
            mods |= KMOD_SHIFT
        elif part in ("alt", "option", "opt"):
            mods |= KMOD_ALT
        elif part in ("ctrl", "control"):
            mods |= KMOD_CTRL
        else:
            return None
    name = parts[-1]
    key = KEY_ALIASES.get(name)
    if key is None:
        try:
            key = pygame.key.key_code(name)
        except ValueError:
            return None
    return key, mods


class Button:
    __slots__ = ("rect", "label", "action", "group")

    def __init__(self, rect, label, action, group=""):
        self.rect = pygame.Rect(rect)
        self.label = label
        self.action = action
        self.group = group


class TwistApp:
    def __init__(self, args):
        self.args = args
        self.win = [args.width, args.height]
        self.rng = random.Random(args.seed) if args.seed is not None else random.Random()

        pygame.init()
        pygame.display.gl_set_attribute(GL_MULTISAMPLEBUFFERS, 1)
        pygame.display.gl_set_attribute(GL_MULTISAMPLESAMPLES, 8)
        pygame.display.set_mode(self.win, DOUBLEBUF | OPENGL | RESIZABLE)
        pygame.display.set_caption("TWIST — airgapped cube simulation")
        init_gl(*self.win)

        self._init_fonts()
        self.hud_tex = glGenTextures(1)
        self.hud_surface = None
        self.hud_dirty = True
        self._alloc_hud()

        self.cubes = {cid: None for cid in keymap.CUBE_IDS}
        self.cube = None
        self.cube_id = None

        self.pitch = self.target_pitch = VIEWS["iso"][0]
        self.yaw = self.target_yaw = VIEWS["iso"][1]
        self.zoom = self.target_zoom = -14.0
        self.dragging = False

        self.show_guide = not args.no_guide
        self.status_msg = ""
        self.status_until = 0.0
        # A task is "armed" once a scramble has been applied. Without this a
        # model can autostart the window itself and be handed a solved cube,
        # which looks like a successful run but measures nothing.
        self.task_armed = False
        self.task_depth = 0
        self.buttons: list[Button] = []
        self.hover = None
        self.shot_index = 0

        self.key_queue = deque()
        self.pending = []

        # Live agent trace, so a human can watch a solve happen.
        self.activity = deque(maxlen=14)
        self.agent_seen = 0.0
        self.agent_commands = 0
        self.pace = max(0.0, float(args.pace))
        self._pace_until = 0.0

        # Run recording. "Thinking" is the gap between one agent command
        # finishing and the next arriving — that is the model reasoning.
        self.log = None
        if not args.no_log:
            path = args.log or runlog.default_path(APP_DIR, args.cube)
            self.log = runlog.RunLog(path, meta={"cube": args.cube, "seed": args.seed,
                                                 "pace": self.pace})
            self._log_path = Path(path)
            self._log(f"[log] recording run to {path}")
        self.last_cmd_at = None
        self.total_think = 0.0
        self.longest_think = 0.0

        self.recorder = None
        if args.record:
            try:
                self.recorder = recorder.Recorder(
                    args.record, self.win[0], self.win[1],
                    active_fps=args.record_fps, idle_fps=args.record_idle_fps,
                    log=self._log)
                self.recorder.start()
            except RuntimeError as exc:
                self._log(f"[record] disabled: {exc}")
                self.recorder = None

        self.bridge = None
        if not args.no_bridge:
            self.bridge = AgentBridge(args.host, args.port, log=self._log)
            try:
                self.bridge.start()
            except OSError as exc:
                self._log(f"[bridge] could not bind {args.host}:{args.port} — {exc}")
                self.bridge = None

        SHOTS_DIR.mkdir(exist_ok=True)
        self.select_cube(args.cube)
        self._layout_buttons()

    # ── setup helpers ────────────────────────────────────────────────────
    def _log(self, msg):
        print(msg, flush=True)

    def _init_fonts(self):
        with warnings.catch_warnings():
            warnings.filterwarnings("ignore", category=RuntimeWarning)
            self.font_sm = textfont.mono(14)
            self.font_md = textfont.mono(15, bold=True)
            self.font_lg = textfont.mono(19, bold=True)
        self._log(f"[font] backend: {textfont.backend()}")

    def _alloc_hud(self):
        w, h = self.win
        self.hud_surface = pygame.Surface((w, h), pygame.SRCALPHA)
        glBindTexture(GL_TEXTURE_2D, self.hud_tex)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MIN_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_MAG_FILTER, GL_NEAREST)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_S, GL_CLAMP_TO_EDGE)
        glTexParameteri(GL_TEXTURE_2D, GL_TEXTURE_WRAP_T, GL_CLAMP_TO_EDGE)
        glTexImage2D(GL_TEXTURE_2D, 0, GL_RGBA, w, h, 0, GL_RGBA, GL_UNSIGNED_BYTE, None)
        glBindTexture(GL_TEXTURE_2D, 0)
        self.hud_dirty = True

    def _layout_buttons(self):
        self.buttons = []
        x, y, h, pad = 14, 12, 30, 6
        for cid in keymap.CUBE_IDS:
            label = "Mirror" if cid == "mirror" else cid
            w = 78 if cid == "mirror" else 56
            self.buttons.append(Button((x, y, w, h), label, ("select", cid), "cube"))
            x += w + pad

        x += 18
        for label, action, w in (
            ("Scramble", ("scramble", None), 92),
            ("Reset", ("reset", None), 66),
            ("Undo", ("undo", None), 62),
            ("Shot", ("shot", None), 58),
            ("Guide", ("guide", None), 66),
        ):
            self.buttons.append(Button((x, y, w, h), label, action, "cmd"))
            x += w + pad
        self.hud_dirty = True

    # ── cube switching ───────────────────────────────────────────────────
    def select_cube(self, cube_id: str):
        if cube_id not in keymap.CUBE_IDS:
            return False
        if self.cube_id != cube_id:
            # Switching cube abandons whatever task was armed on the old one.
            self.task_armed, self.task_depth = False, 0
        if self.cubes[cube_id] is None:
            self.cubes[cube_id] = make_cube(cube_id)
        self.cube = self.cubes[cube_id]
        self.cube_id = cube_id
        self.cube.activate()
        self.cube.configure_lighting()
        self.target_zoom = self.cube.default_zoom
        self.zoom = self.target_zoom
        # Deliberately do NOT clear key_queue: a queued "f4 space" must still
        # scramble the cube the f4 just selected.
        self.set_status(f"{self.cube.label} selected")
        self.hud_dirty = True
        return True

    def set_status(self, msg, seconds=2.6):
        self.status_msg = msg
        self.status_until = time.monotonic() + seconds
        self.hud_dirty = True

    def run_seconds(self) -> float:
        return self.log.elapsed if self.log else 0.0

    def log_activity(self, label: str, detail: str = "", source: str = "agent"):
        self.activity.append((label, detail, source))
        if source == "agent":
            self.agent_seen = time.monotonic()
        self.hud_dirty = True

    # ── input ────────────────────────────────────────────────────────────
    def handle_key(self, key, mods, source="human") -> bool:
        name = pygame.key.name(key)
        shift = bool(mods & KMOD_SHIFT)
        alt = bool(mods & KMOD_ALT)
        stroke = ("shift+" if shift else "") + ("alt+" if alt else "") + name

        for cube_id, sel in keymap.SELECT_KEYS.items():
            if name == sel:
                ok = self.select_cube(cube_id)
                if ok:
                    self.log_activity(cube_id, stroke, source)
                return ok

        base = keymap.key_to_move(self.cube_id, name)
        if base:
            if self.cube.busy:
                return False
            move = base + ("'" if shift else ("2" if alt else ""))
            self.cube.apply(move)
            self.set_status(f"move {move}")
            self.log_activity(move, stroke, source)
            if self.log:
                self.log.event("move", move=move, key=stroke, source=source,
                               cube=self.cube_id, move_count=self.cube.move_count,
                               solved=self.cube.is_solved())
            if source == "agent" and self.pace:
                self._pace_until = time.monotonic() + self.pace
            return True

        if key == K_SPACE:
            moves = self.cube.scramble(rng=self.rng)
            self.task_armed, self.task_depth = True, len(moves)
            self.set_status(f"scrambled ({len(moves)} moves)")
            self.log_activity("scramble", f"{len(moves)} moves", source)
        elif key == K_BACKSPACE:
            self.cube.reset()
            self.task_armed, self.task_depth = False, 0
            self.set_status("reset to solved")
            self.log_activity("reset", stroke, source)
        elif key == K_z:
            if self.cube.busy:
                return False
            undone = self.cube.undo()
            self.set_status(f"undo {undone}" if undone else "nothing to undo")
            self.log_activity("undo", undone or "-", source)
        elif key == K_LEFT:
            self.target_yaw -= 15.0
        elif key == K_RIGHT:
            self.target_yaw += 15.0
        elif key == K_UP:
            self.target_pitch = max(-89.0, self.target_pitch - 15.0)
        elif key == K_DOWN:
            self.target_pitch = min(89.0, self.target_pitch + 15.0)
        elif key == K_HOME:
            self.set_view("iso")
        elif key == K_BACKSLASH:
            self.target_yaw += 180.0
            self.target_pitch = -self.target_pitch
        elif key in (K_EQUALS, K_PLUS):
            self.target_zoom = min(self.target_zoom + 1.2, -4.0)
        elif key == K_MINUS:
            self.target_zoom = max(self.target_zoom - 1.2, -45.0)
        elif key == K_c:
            path = self.capture(self.next_shot_path("manual"))
            self.set_status(f"saved {path.name}")
        elif key == K_TAB:
            self.show_guide = not self.show_guide
        elif key == K_ESCAPE:
            self.quit()
        else:
            return False

        self.hud_dirty = True
        return True

    def handle_click(self, pos):
        for btn in self.buttons:
            if btn.rect.collidepoint(pos):
                kind, value = btn.action
                if kind == "select":
                    self.select_cube(value)
                elif kind == "scramble":
                    moves = self.cube.scramble(rng=self.rng)
                    self.set_status(f"scrambled ({len(moves)} moves)")
                elif kind == "reset":
                    self.cube.reset()
                    self.set_status("reset to solved")
                elif kind == "undo":
                    if not self.cube.busy:
                        undone = self.cube.undo()
                        self.set_status(f"undo {undone}" if undone else "nothing to undo")
                elif kind == "shot":
                    path = self.capture(self.next_shot_path("manual"))
                    self.set_status(f"saved {path.name}")
                elif kind == "guide":
                    self.show_guide = not self.show_guide
                self.hud_dirty = True
                return True
        return False

    def set_view(self, view: str):
        if view not in VIEWS:
            return False
        self.target_pitch, self.target_yaw = VIEWS[view]
        return True

    # ── screenshots ──────────────────────────────────────────────────────
    def next_shot_path(self, tag="shot") -> Path:
        self.shot_index += 1
        return SHOTS_DIR / f"{tag}_{self.cube_id}_{self.shot_index:04d}.png"

    def grab(self, view=None, hud=False):
        """Render one view and return (width, height, top-down RGB bytes)."""
        if view:
            pitch, yaw = VIEWS[view]
        else:
            pitch, yaw = self.pitch, self.yaw
        self.render(pitch, yaw, self.zoom, with_hud=hud)
        glFinish()
        w, h = self.win
        glPixelStorei(GL_PACK_ALIGNMENT, 1)
        raw = glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE)
        buf = raw.tobytes() if hasattr(raw, "tobytes") else bytes(raw)
        stride = w * 3
        flipped = b"".join(buf[y * stride:(y + 1) * stride] for y in range(h - 1, -1, -1))
        return w, h, flipped

    def capture(self, path: Path, view=None, hud=False) -> Path:
        w, h, rgb = self.grab(view=view, hud=hud)
        path.parent.mkdir(parents=True, exist_ok=True)
        pngwrite.write_rgb(str(path), w, h, rgb)
        return path

    def build_sheet(self, paths, views, tag="sheet"):
        """Join captured views into one labelled contact sheet.

        Each view keeps its full pixel resolution — the sheet gets wider rather
        than the views getting smaller — because misreading stickers is the
        dominant failure mode and downscaling makes it worse. Whether one wide
        image beats several separate ones is an open question this flag exists
        to let you measure.
        """
        tiles = [_surface_from_bytes(rgb, (w, h), "RGB") for w, h, rgb in paths]
        label_h = self.font_lg.get_linesize() + 14
        tw = sum(t.get_width() for t in tiles)
        th = max(t.get_height() for t in tiles) + label_h

        sheet = pygame.Surface((tw, th))
        sheet.fill((236, 238, 241))
        x = 0
        for tile, view in zip(tiles, views):
            sheet.blit(tile, (x, label_h))
            name = (view or "current").replace("_", " ")
            faces = {"iso": "shows Up, Front, Right",
                     "iso_back": "shows Down, Back, Left"}.get(view or "", "")
            img = self.font_lg.render(f"{name}   {faces}", True, (24, 27, 32))
            sheet.blit(img, (x + 18, 8))
            if x:
                pygame.draw.line(sheet, (150, 156, 164), (x, 0), (x, th), 2)
            x += tile.get_width()

        path = self.next_shot_path(f"{tag}_sheet")
        raw = _surface_to_bytes(sheet, "RGB", False)
        pngwrite.write_rgb(str(path), tw, th, raw)
        return path

    # ── agent bridge ─────────────────────────────────────────────────────
    def status_payload(self, ok=True, **extra):
        payload = {
            "ok": ok,
            "cube": self.cube_id,
            "family": self.cube.family,
            "size": self.cube.n,
            "solved": bool(self.cube.is_solved()),
            "move_count": self.cube.move_count,
            "busy": bool(self.cube.busy),
            "pending_keys": len(self.key_queue),
            "task_armed": self.task_armed,
            "task_moves": self.task_depth,
            "task_depth": self.task_depth,  # deprecated alias
            "camera": {
                "pitch": round(self.target_pitch, 2),
                "yaw": round(self.target_yaw, 2),
                "zoom": round(self.target_zoom, 2),
            },
            "legal_moves": self.cube.legal_moves(),
        }
        payload.update(extra)
        return payload

    def keymap_payload(self):
        depths = keymap.depths_for(self.cube_id)
        return {
            "ok": True,
            "cube": self.cube_id,
            "modifiers": {"none": "90 CW", "shift": "90 CCW (prime)", "alt": "180"},
            "move_keys": {
                f"depth{d}": keymap.DEPTH_KEYS[d] for d in depths
            },
            "controls": dict(keymap.CONTROL_KEYS),
            "select_keys": keymap.SELECT_KEYS,
            "views": sorted(VIEWS),
        }

    def enqueue_keystrokes(self, items) -> tuple[int, list]:
        if isinstance(items, str):
            items = items.split()
        bad = []
        parsed = []
        for item in items:
            combo = parse_keystroke(item)
            if combo is None:
                bad.append(item)
            else:
                parsed.append(combo)
        if bad:
            return 0, bad
        self.key_queue.extend(parsed)
        return len(parsed), []

    def think_seconds(self) -> float:
        """How long the model has been thinking since its last command.

        Deliberately not conditioned on an open socket: the CLI opens a fresh
        connection per command, so between commands there is nobody connected —
        which is exactly when the model is thinking hardest.
        """
        if self.last_cmd_at is None:
            return 0.0
        if self.cube.busy or self.key_queue or self.pending:
            return 0.0
        return max(0.0, time.monotonic() - self.last_cmd_at)

    def _close_think_gap(self):
        """Bank the pause that just ended, so the video knows to compress it."""
        gap = self.think_seconds()
        if gap < 0.35:
            return
        self.total_think += gap
        self.longest_think = max(self.longest_think, gap)
        if self.log:
            self.log.event("think", seconds=round(gap, 3),
                           total=round(self.total_think, 3))

    def handle_request(self, req):
        cmd = req.cmd
        self._close_think_gap()
        self.agent_seen = self.last_cmd_at = time.monotonic()
        if self.log:
            self.log.event("command", cmd=cmd, cube=self.cube_id,
                           payload={k: v for k, v in req.payload.items() if k != "cmd"})
        if cmd not in ("ping", "status", "keymap"):
            self.agent_commands += 1
            self.hud_dirty = True

        if cmd in ("ping", "status"):
            req.complete(self.status_payload())

        elif cmd == "keymap":
            req.complete(self.keymap_payload())

        elif cmd == "keys":
            keys = req.get("keys", req.get("value", []))
            count, bad = self.enqueue_keystrokes(keys)
            if bad:
                req.fail(f"unknown key(s): {bad}")
            elif req.get("wait", True):
                self._defer(req, self._idle, lambda r: r.complete(
                    self.status_payload(dispatched=count)))
            else:
                req.complete(self.status_payload(queued=count))

        elif cmd == "moves":
            moves = req.get("moves", req.get("value", []))
            if isinstance(moves, str):
                moves = moves.split()
            strokes, bad = [], []
            for move in moves:
                stroke = keymap.move_to_keystroke(self.cube_id, move)
                (strokes if stroke else bad).append(stroke or move)
            if bad:
                req.fail(f"illegal move(s) for {self.cube_id}: {bad}")
                return
            count, _ = self.enqueue_keystrokes(strokes)
            if req.get("wait", True):
                self._defer(req, self._idle, lambda r: r.complete(
                    self.status_payload(dispatched=count)))
            else:
                req.complete(self.status_payload(queued=count))

        elif cmd == "select":
            cube_id = str(req.get("cube", req.get("value", "")))
            if self.select_cube(cube_id):
                self.log_activity(cube_id, "select")
                req.complete(self.status_payload())
            else:
                req.fail(f"unknown cube '{cube_id}'; choose from {list(keymap.CUBE_IDS)}")

        elif cmd == "scramble":
            count = req.get("moves")
            seed = req.get("seed")
            rng = random.Random(seed) if seed is not None else self.rng
            self.key_queue.clear()
            applied = self.cube.scramble(count=count, rng=rng)
            self.task_armed, self.task_depth = True, len(applied)
            self.set_status(f"scrambled ({len(applied)} moves)")
            self.log_activity("scramble", f"{len(applied)} moves")
            if self.log:
                # The run proper starts here: this is when the task is set.
                self.log.restart_clock()
                self.total_think = 0.0
                self.longest_think = 0.0
                self.log.event("scramble", cube=self.cube_id, moves=applied,
                               depth=len(applied), seed=seed)
            req.complete(self.status_payload(scramble=applied))

        elif cmd == "reset":
            self.key_queue.clear()
            self.cube.reset()
            self.task_armed, self.task_depth = False, 0
            self.set_status("reset to solved")
            self.log_activity("reset", "solved")
            req.complete(self.status_payload())

        elif cmd == "undo":
            def do_undo(r):
                undone = self.cube.undo()
                r.complete(self.status_payload(undone=undone))
            self._defer(req, self._idle, do_undo)

        elif cmd == "camera":
            view = req.get("view")
            if view:
                if not self.set_view(view):
                    req.fail(f"unknown view '{view}'; choose from {sorted(VIEWS)}")
                    return
            if req.get("yaw") is not None:
                self.target_yaw = float(req.get("yaw"))
            if req.get("pitch") is not None:
                self.target_pitch = max(-89.0, min(89.0, float(req.get("pitch"))))
            if req.get("zoom") is not None:
                self.target_zoom = max(-45.0, min(-4.0, float(req.get("zoom"))))
            if req.get("snap", True):
                self.pitch, self.yaw, self.zoom = (
                    self.target_pitch, self.target_yaw, self.target_zoom)
            self.hud_dirty = True
            req.complete(self.status_payload())

        elif cmd == "screenshot":
            views = req.get("views") or ([req.get("view")] if req.get("view") else [None])
            tag = str(req.get("tag", "agent"))
            hud = bool(req.get("hud", False))
            sheet = bool(req.get("sheet", False))
            ready = (lambda: True) if req.get("force") else self._idle

            def finish(r):
                for view in views:
                    if view is not None and view not in VIEWS:
                        r.fail(f"unknown view '{view}'; choose from {sorted(VIEWS)}")
                        return
                if sheet and len(views) > 1:
                    grabs = [self.grab(view=v, hud=hud) for v in views]
                    paths = [str(self.build_sheet(grabs, views, tag))]
                else:
                    paths = [str(self.capture(self.next_shot_path(tag), view=v, hud=hud))
                             for v in views]
                self.log_activity("look", ", ".join(v or "current" for v in views))
                if self.log:
                    self.log.event("screenshot", images=paths, cube=self.cube_id,
                                   views=[v or "current" for v in views])
                r.complete(self.status_payload(images=paths, views=[v or "current" for v in views]))

            self._defer(req, ready, finish)

        elif cmd == "pace":
            value = req.get("seconds", req.get("value"))
            if value is None:
                req.complete(self.status_payload(pace=self.pace))
                return
            self.pace = max(0.0, min(5.0, float(value)))
            self._pace_until = 0.0
            self.set_status(f"pace {self.pace:.2f}s")
            req.complete(self.status_payload(pace=self.pace))

        elif cmd == "state":
            # Logged loudly: this is the answer key, and a grader needs to see
            # in the trace if the model under test ever reached for it.
            # The grader is entitled to read this; the model under test is not.
            # Tagging the difference stops repeated scoring from looking like
            # the model peeked.
            by_grader = bool(req.get("grader", False))
            self.log_activity("TRUTH", "grader read" if by_grader else "answer key read")
            self.set_status("ground-truth state read", 4.0)
            if self.log:
                self.log.event("truth_read", cube=self.cube_id, by_grader=by_grader)
            req.complete(self.status_payload(facelets=self.cube.facelets(),
                                             history=list(self.cube.history)))

        elif cmd == "quit":
            req.complete({"ok": True, "bye": True})
            self.quit()

        else:
            req.fail(f"unknown command '{cmd}'")

    def _idle(self):
        return not self.key_queue and not self.cube.busy

    def _defer(self, req, ready, finish):
        self.pending.append((req, ready, finish))

    def _resolve_pending(self):
        if not self.pending:
            return
        still = []
        for req, ready, finish in self.pending:
            if ready():
                finish(req)
            else:
                still.append((req, ready, finish))
        self.pending = still

    # ── HUD ──────────────────────────────────────────────────────────────
    def _text(self, surf, text, x, y, font=None, color=TEXT):
        img = (font or self.font_sm).render(text, True, color)
        surf.blit(img, (x, y))
        return img.get_height()

    def redraw_hud(self):
        surf = self.hud_surface
        surf.fill((0, 0, 0, 0))
        w, h = self.win

        pygame.draw.rect(surf, BG_BAR, (0, 0, w, 54))
        for btn in self.buttons:
            kind, value = btn.action
            on = (kind == "select" and value == self.cube_id) or (kind == "guide" and self.show_guide)
            color = BTN_ON if on else (BTN_HOT if btn is self.hover else BTN)
            pygame.draw.rect(surf, color, btn.rect, border_radius=6)
            pygame.draw.rect(surf, (0, 0, 0, 90), btn.rect, width=1, border_radius=6)
            label = self.font_md.render(btn.label, True, TEXT)
            surf.blit(label, label.get_rect(center=btn.rect.center))

        solved = self.cube.is_solved()
        status_bits = [
            f"{self.cube.label}",
            "SOLVED" if solved else "SCRAMBLED",
            f"moves {self.cube.move_count}",
            f"yaw {self.target_yaw:+.0f}  pitch {self.target_pitch:+.0f}",
        ]
        if self.bridge:
            status_bits.append(f"agent {self.args.host}:{self.args.port} ({self.bridge.clients})")
        else:
            status_bits.append("agent off")
        if self.key_queue:
            status_bits.append(f"queued {len(self.key_queue)}")

        y = h - 30
        pygame.draw.rect(surf, BG_BAR, (0, h - 34, w, 34))
        x = 14
        for i, bit in enumerate(status_bits):
            color = TEXT
            if i == 1:
                color = GOOD if solved else BAD
            elif i > 1:
                color = TEXT_DIM
            img = self.font_md.render(bit, True, color)
            surf.blit(img, (x, y))
            x += img.get_width() + 22

        if self.status_msg and time.monotonic() < self.status_until:
            img = self.font_md.render(self.status_msg, True, (255, 205, 120))
            surf.blit(img, (14, h - 62))

        self._draw_activity(surf)

        if self.show_guide:
            self._draw_guide(surf)

    def _draw_activity(self, surf):
        """Left-hand live trace: who is driving, and what they just pressed."""
        w, h = self.win
        pad = 14
        pw = 306
        px, py = 14, 68

        live = (time.monotonic() - self.agent_seen) < 3.0
        connected = bool(self.bridge and self.bridge.clients)
        thinking = self.think_seconds()

        line_h = self.font_sm.get_linesize() + 2
        rows = list(self.activity)[-12:]
        clock_h = self.font_lg.get_linesize() + 10
        ph = (pad * 2 + self.font_md.get_linesize() + 8 + clock_h
              + max(1, len(rows)) * line_h)
        ph = min(ph, h - py - 80)

        pygame.draw.rect(surf, PANEL, (px, py, pw, ph), border_radius=10)
        pygame.draw.rect(surf, (255, 255, 255, 26), (px, py, pw, ph), width=1, border_radius=10)

        if self.cube.busy or self.key_queue:
            head, head_color, dot = "AGENT ACTING", (120, 240, 170), (90, 230, 150)
        elif thinking >= 0.6:
            head, head_color, dot = "AGENT THINKING", (255, 196, 96), (240, 176, 70)
        elif live or connected:
            head, head_color, dot = "AGENT CONNECTED", (150, 200, 255), (110, 160, 220)
        else:
            head, head_color, dot = "WAITING FOR AGENT", (150, 160, 174), (95, 105, 120)
        pygame.draw.circle(surf, dot, (px + pad + 4, py + pad + 6), 5)
        self._text(surf, head, px + pad + 18, py + pad - 2, self.font_md, head_color)
        if self.agent_commands:
            count = f"{self.agent_commands}"
            img = self.font_sm.render(count, True, TEXT_DIM)
            surf.blit(img, (px + pw - pad - img.get_width(), py + pad))

        # Big clock: how long the model has been thinking, or the run total.
        y = py + pad + self.font_md.get_linesize() + 4
        if thinking >= 0.6:
            label, value, colour = "thinking", _mmss(thinking), (255, 196, 96)
        elif self.cube.busy or self.key_queue:
            label, value, colour = "moving", _mmss(self.run_seconds()), (120, 240, 170)
        else:
            label, value, colour = "run", _mmss(self.run_seconds()), (170, 182, 198)
        self._text(surf, label, px + pad, y + 5, self.font_sm, TEXT_DIM)
        img = self.font_lg.render(value, True, colour)
        surf.blit(img, (px + pad + 78, y))
        think_total = self.total_think + (thinking if thinking >= 0.35 else 0.0)
        if think_total >= 1.0:
            tot = self.font_sm.render(f"think {_mmss(think_total)}", True, (150, 160, 174))
            surf.blit(tot, (px + pw - pad - tot.get_width(), y + 6))
        y += clock_h

        if not rows:
            self._text(surf, "no activity yet", px + pad, y, self.font_sm, (110, 120, 134))
            return

        limit = py + ph - pad
        for i, (label, detail, source) in enumerate(rows):
            if y > limit - line_h:
                break
            newest = i == len(rows) - 1
            key_color = (255, 226, 150) if newest else (200, 170, 110)
            if source == "human":
                key_color = (170, 210, 255) if newest else (130, 160, 195)
            self._text(surf, label, px + pad, y, self.font_sm, key_color)
            self._text(surf, str(detail), px + pad + 104, y, self.font_sm,
                       TEXT if newest else TEXT_DIM)
            y += line_h

    def _draw_guide(self, surf):
        w, h = self.win
        pad = 16
        pw = 448
        px = w - pw - 14
        py = 68
        lines = []
        lines.append(("title", f"{self.cube.label} — key guide"))
        lines.append(("dim", "-" * 42))
        for depth in keymap.depths_for(self.cube_id):
            lines.append(("head", f"depth {depth} ({keymap.DEPTH_LABEL[depth]})"))
            for key, move in keymap.DEPTH_KEYS[depth].items():
                lines.append(("row", (key.upper(), move)))
        lines.append(("head", "modifiers"))
        lines.append(("row", ("shift", "prime / counter-clockwise  (R')")))
        lines.append(("row", ("alt", "180 degrees  (R2)")))
        lines.append(("head", "controls"))
        for key, desc in keymap.CONTROL_KEYS:
            lines.append(("row", (key, desc)))

        line_h = self.font_sm.get_linesize() + 2
        ph = pad * 2 + 6
        for kind, _ in lines:
            ph += self.font_md.get_linesize() + 4 if kind in ("title", "head") else line_h
        ph = min(ph, h - py - 46)

        pygame.draw.rect(surf, PANEL, (px, py, pw, ph), border_radius=10)
        pygame.draw.rect(surf, (255, 255, 255, 26), (px, py, pw, ph), width=1, border_radius=10)

        y = py + pad
        limit = py + ph - pad
        for kind, payload in lines:
            if y > limit - line_h:
                break
            if kind == "title":
                self._text(surf, payload, px + pad, y, self.font_lg, TEXT)
                y += self.font_lg.get_linesize() + 4
            elif kind == "head":
                y += 4
                self._text(surf, payload.upper(), px + pad, y, self.font_md, (140, 205, 255))
                y += self.font_md.get_linesize() + 2
            elif kind == "dim":
                self._text(surf, payload, px + pad, y, self.font_sm, (70, 80, 95))
                y += line_h
            else:
                key, desc = payload
                self._text(surf, key, px + pad, y, self.font_sm, (255, 214, 140))
                self._text(surf, str(desc), px + pad + 112, y, self.font_sm, TEXT_DIM)
                y += line_h

    def upload_hud(self):
        w, h = self.win
        data = _surface_to_bytes(self.hud_surface, "RGBA", False)
        glBindTexture(GL_TEXTURE_2D, self.hud_tex)
        glTexSubImage2D(GL_TEXTURE_2D, 0, 0, 0, w, h, GL_RGBA, GL_UNSIGNED_BYTE, data)
        glBindTexture(GL_TEXTURE_2D, 0)

    def blit_hud(self):
        w, h = self.win
        glDisable(GL_DEPTH_TEST)
        glDisable(GL_LIGHTING)
        glEnable(GL_BLEND)
        glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
        glEnable(GL_TEXTURE_2D)
        glBindTexture(GL_TEXTURE_2D, self.hud_tex)
        glColor4f(1, 1, 1, 1)

        glMatrixMode(GL_PROJECTION)
        glPushMatrix()
        glLoadIdentity()
        glOrtho(0, w, h, 0, -1, 1)
        glMatrixMode(GL_MODELVIEW)
        glPushMatrix()
        glLoadIdentity()

        glBegin(GL_QUADS)
        glTexCoord2f(0, 0); glVertex2f(0, 0)
        glTexCoord2f(1, 0); glVertex2f(w, 0)
        glTexCoord2f(1, 1); glVertex2f(w, h)
        glTexCoord2f(0, 1); glVertex2f(0, h)
        glEnd()

        glPopMatrix()
        glMatrixMode(GL_PROJECTION)
        glPopMatrix()
        glMatrixMode(GL_MODELVIEW)

        glBindTexture(GL_TEXTURE_2D, 0)
        glDisable(GL_TEXTURE_2D)
        glEnable(GL_DEPTH_TEST)

    # ── frame ────────────────────────────────────────────────────────────
    def render(self, pitch, yaw, zoom, with_hud=True):
        self.cube.draw(pitch, yaw, zoom)
        if with_hud:
            if self.hud_dirty:
                self.redraw_hud()
                self.upload_hud()
                self.hud_dirty = False
            self.blit_hud()

    def shutdown(self):
        """Finalise the recording and log. Safe to call more than once."""
        if getattr(self, "_shut_down", False):
            return
        self._shut_down = True
        if self.recorder:
            self.recorder.stop()
            self.recorder = None
        if self.log:
            self.log.close(cube=self.cube_id, solved=bool(self.cube.is_solved()),
                           move_count=self.cube.move_count,
                           thinking_seconds=round(self.total_think, 2),
                           longest_think=round(self.longest_think, 2))
            self.log = None
        if self.bridge:
            self.bridge.stop()
            self.bridge = None

    def quit(self):
        self.shutdown()
        pygame.quit()
        sys.exit(0)

    def install_signal_handlers(self):
        """A killed or Ctrl-C'd run must still leave a playable mp4 behind."""
        def handler(signum, _frame):
            self._log(f"[app] signal {signum}, shutting down cleanly")
            self.shutdown()
            pygame.quit()
            sys.exit(0)

        for sig in (signal.SIGTERM, signal.SIGINT, signal.SIGHUP):
            try:
                signal.signal(sig, handler)
            except (ValueError, OSError):
                pass
        atexit.register(self.shutdown)

    def run(self):
        clock = pygame.time.Clock()
        last_status = None

        while True:
            dt = clock.tick(60) / 1000.0

            for e in pygame.event.get():
                if e.type == QUIT:
                    self.quit()
                elif e.type == VIDEORESIZE:
                    self.win = [max(640, e.w), max(480, e.h)]
                    resize_gl(*self.win)
                    self._alloc_hud()
                    self._layout_buttons()
                elif e.type == MOUSEBUTTONDOWN:
                    if e.button == 1 and self.handle_click(e.pos):
                        pass
                    elif e.button in (1, 3):
                        self.dragging = True
                    elif e.button == 4:
                        self.target_zoom = min(self.target_zoom + 1.0, -4.0)
                        self.hud_dirty = True
                    elif e.button == 5:
                        self.target_zoom = max(self.target_zoom - 1.0, -45.0)
                        self.hud_dirty = True
                elif e.type == MOUSEBUTTONUP:
                    if e.button in (1, 3):
                        self.dragging = False
                elif e.type == MOUSEMOTION:
                    if self.dragging:
                        dx, dy = e.rel
                        self.target_yaw += dx * 0.48
                        self.target_pitch = max(-89.0, min(89.0, self.target_pitch + dy * 0.48))
                    else:
                        hover = next((b for b in self.buttons if b.rect.collidepoint(e.pos)), None)
                        if hover is not self.hover:
                            self.hover = hover
                            self.hud_dirty = True
                elif e.type == KEYDOWN:
                    self.handle_key(e.key, e.mod)

            if self.bridge:
                for req in self.bridge.poll():
                    try:
                        self.handle_request(req)
                    except Exception as exc:  # never let a bad command kill the app
                        req.fail(f"{type(exc).__name__}: {exc}")

            if (self.key_queue and not self.cube.busy
                    and time.monotonic() >= self._pace_until):
                key, mods = self.key_queue.popleft()
                self.handle_key(key, mods, source="agent")

            self._resolve_pending()

            # While anything is in flight the model is not thinking, so keep the
            # thinking clock parked at "now".
            if self.key_queue or self.cube.busy or self.pending:
                self.last_cmd_at = time.monotonic()

            self.pitch += (self.target_pitch - self.pitch) * 0.20
            self.yaw += (self.target_yaw - self.yaw) * 0.20
            self.zoom += (self.target_zoom - self.zoom) * 0.20

            self.cube.tick(dt)

            snapshot = (self.cube_id, self.cube.move_count, self.cube.busy,
                        len(self.key_queue),
                        bool(self.status_msg and time.monotonic() < self.status_until),
                        (time.monotonic() - self.agent_seen) < 3.0,
                        self.bridge.clients if self.bridge else 0,
                        round(self.think_seconds(), 1),
                        round(self.run_seconds(), 1))
            if snapshot != last_status:
                last_status = snapshot
                self.hud_dirty = True

            self.render(self.pitch, self.yaw, self.zoom)

            if self.recorder:
                now = time.monotonic()
                idle = self.think_seconds() >= 1.0
                if self.recorder.due(now, idle):
                    glFinish()
                    w, h = self.win
                    glPixelStorei(GL_PACK_ALIGNMENT, 1)
                    raw = glReadPixels(0, 0, w, h, GL_RGB, GL_UNSIGNED_BYTE)
                    buf = raw.tobytes() if hasattr(raw, "tobytes") else bytes(raw)
                    stride = w * 3
                    self.recorder.write(b"".join(
                        buf[y * stride:(y + 1) * stride] for y in range(h - 1, -1, -1)))

            pygame.display.flip()


def build_parser():
    p = argparse.ArgumentParser(description="TWIST — airgapped cube simulation")
    p.add_argument("--cube", default="3x3", choices=list(keymap.CUBE_IDS),
                   help="cube shown at startup")
    p.add_argument("--width", type=int, default=1280)
    p.add_argument("--height", type=int, default=860)
    p.add_argument("--host", default=DEFAULT_HOST, help="agent bridge bind address (loopback)")
    p.add_argument("--port", type=int, default=DEFAULT_PORT)
    p.add_argument("--no-bridge", action="store_true", help="run without the agent socket")
    p.add_argument("--no-guide", action="store_true", help="start with the key guide hidden")
    p.add_argument("--seed", type=int, default=None, help="seed scrambles for reproducible runs")
    p.add_argument("--record", default=None, metavar="OUT.mp4",
                   help="record the window to mp4 (needs ffmpeg); thinking pauses "
                        "are sampled slowly so they self-compress on playback")
    p.add_argument("--record-fps", type=float, default=24.0,
                   help="frames captured per second while the cube is moving")
    p.add_argument("--record-idle-fps", type=float, default=2.0,
                   help="frames captured per second while the model is thinking; "
                        "0 drops thinking entirely so the clip is moves only")
    p.add_argument("--log", default=None, metavar="PATH",
                   help="run log to append to (default: runs/<timestamp>_<cube>.jsonl)")
    p.add_argument("--no-log", action="store_true", help="do not record a run log")
    p.add_argument("--pace", type=float, default=0.0, metavar="SECONDS",
                   help="minimum interval between agent moves, so a human can follow "
                        "along (0 = as fast as the animation allows)")
    return p


def main():
    args = build_parser().parse_args()
    if args.host not in ("127.0.0.1", "localhost", "::1"):
        print(f"[warn] binding the agent bridge to {args.host} is not loopback-only")
    app = TwistApp(args)
    app.install_signal_handlers()
    app.run()


if __name__ == "__main__":
    main()
