"""
cubes.py — one interface over both cube families.

`NxNCube` wraps the Rubix engine (cube_state + cube_renderer + its Animation)
retargeted to any size 2..6 by `sizing.activate`. `MirrorCube` wraps the vendored
mirror-blocks engine. The app and the agent bridge only ever talk to the
`Cube` protocol below, so neither has to care which family is on screen.
"""

import random

from . import keymap, scramble, sizing
from .mirror_render import MirrorAnimation, draw_mirror_cube
from .mirror_state import MirrorCubeState, get_random_scramble

sizing.activate(6)  # bind the Rubix globals before importing anything from them

from cube_renderer import Animation, build_color_map, draw_cube  # noqa: E402
from cube_state import CubeState  # noqa: E402
from utils import invert_move, parse_move  # noqa: E402

# One default for every cube. 300 well-formed moves is far past the point where
# the state distribution stops changing, so the number is about being safely
# randomised, not about tuning difficulty — see engine/scramble.py.
DEFAULT_SCRAMBLE_LENGTH = scramble.DEFAULT_LENGTH


class NxNCube:
    """A 2x2 .. 6x6 sticker cube."""

    family = "nxn"

    def __init__(self, n: int):
        self.n = n
        self.cube_id = f"{n}x{n}"
        self.label = f"{n}x{n}"
        self.default_zoom = -(n * 2.9 + 3.0)
        self.history: list[str] = []
        self.activate()
        self.cs = CubeState()
        self.anim = Animation()
        self.cmap = build_color_map(self.cs)

    # ── lifecycle ────────────────────────────────────────────────────────
    def activate(self):
        sizing.activate(self.n)

    def configure_lighting(self):
        from .lighting import sticker_lighting
        sticker_lighting()

    # ── moves ────────────────────────────────────────────────────────────
    @property
    def busy(self) -> bool:
        return self.anim.active

    @property
    def move_count(self) -> int:
        return len(self.history)

    def legal_moves(self) -> list[str]:
        return keymap.moves_for(self.cube_id)

    def apply(self, move: str, animate=True, record=True):
        self.activate()
        p = parse_move(move)
        self.cs.apply_move(move)
        self.cmap = build_color_map(self.cs)
        if record:
            self.history.append(move)
        if animate:
            self.anim.start(p["face"], p["depth"], p["wide"], p["turns"])

    def undo(self):
        if not self.history:
            return None
        move = self.history.pop()
        self.apply(invert_move(move), animate=True, record=False)
        return move

    def reset(self):
        self.activate()
        self.cs = CubeState()
        self.cmap = build_color_map(self.cs)
        self.anim.active = False
        self.history.clear()

    def scramble(self, count=None, rng=None):
        rng = rng or random
        count = count or DEFAULT_SCRAMBLE_LENGTH
        self.reset()
        moves = scramble.random_scramble(self.legal_moves(), rng, count)
        self.activate()
        for m in moves:
            self.cs.apply_move(m)
        self.cmap = build_color_map(self.cs)
        return moves

    def is_solved(self) -> bool:
        self.activate()
        return self.cs.is_solved()

    def facelets(self) -> dict:
        """Sticker grids per face, letters U/R/F/D/L/B — a ground-truth dump."""
        self.activate()
        from utils import COLOR_CODES, Face
        out = {}
        for face in Face:
            grid = self.cs.faces[face]
            out[face.name] = [
                "".join(COLOR_CODES[Face(int(v))] for v in row) for row in grid
            ]
        return out

    # ── frame ────────────────────────────────────────────────────────────
    def tick(self, dt):
        self.activate()
        if self.anim.active:
            self.anim.update(dt)

    def draw(self, rot_x, rot_y, zoom):
        self.activate()
        draw_cube(self.cmap, rot_x, rot_y, zoom, self.anim)


class MirrorCube:
    """The silver 3x3 mirror cube — one colour, solved by shape."""

    family = "mirror"
    cube_id = "mirror"
    label = "Mirror"
    n = 3

    def __init__(self):
        self.default_zoom = -11.5
        self.state = MirrorCubeState()
        self.anim = MirrorAnimation()
        self.history: list[str] = []

    def activate(self):
        pass

    def configure_lighting(self):
        from .lighting import mirror_lighting
        mirror_lighting()

    @property
    def busy(self) -> bool:
        return self.anim.active

    @property
    def move_count(self) -> int:
        return len(self.history)

    def legal_moves(self) -> list[str]:
        return keymap.moves_for(self.cube_id)

    def apply(self, move: str, animate=True, record=True):
        face = move[0]
        suffix = move[1:]
        turns = -1 if suffix == "'" else (2 if suffix == "2" else 1)
        self.state.apply_move(move)
        if record:
            self.history.append(move)
        if animate:
            # Affected cubies are read after the state moves — the animation
            # swings them from displaced back to rest.
            self.anim.start(face, turns, self.state.get_affected_cubies(face))

    def undo(self):
        if not self.history:
            return None
        move = self.history.pop()
        if move.endswith("2"):
            inverse = move
        elif move.endswith("'"):
            inverse = move[:-1]
        else:
            inverse = move + "'"
        self.apply(inverse, animate=True, record=False)
        return move

    def reset(self):
        self.state.reset()
        self.anim.active = False
        self.anim.affected = []
        self.history.clear()

    def scramble(self, count=None, rng=None):
        count = count or DEFAULT_SCRAMBLE_LENGTH
        self.reset()
        moves = scramble.random_scramble(self.legal_moves(), rng or random, count)
        for m in moves:
            self.state.apply_move(m)
        return moves

    def is_solved(self) -> bool:
        return self.state.is_solved()

    def facelets(self) -> dict:
        return {"kociemba": self.state.to_kociemba_string()}

    def tick(self, dt):
        if self.anim.active:
            self.anim.update(dt)

    def draw(self, rot_x, rot_y, zoom):
        draw_mirror_cube(self.state, rot_x, rot_y, zoom, self.anim)


def make_cube(cube_id: str):
    if cube_id == "mirror":
        return MirrorCube()
    return NxNCube(int(cube_id[0]))
