# Vendored from the Rubix project (github.com/Avi130805) so this repo runs
# standalone. Unmodified except for this header. The cube size constant is
# retargeted at import time by engine/sizing.py — see that module.

"""
utils.py — Constants, color maps, and move notation for the 6×6 Rubik's Cube.
"""

import re
from enum import IntEnum

# ──────────────────────────────────────────────
# Face indices — the order we store faces in the state array
# ──────────────────────────────────────────────
class Face(IntEnum):
    U = 0  # Up    (White)
    R = 1  # Right (Red)
    F = 2  # Front (Green)
    D = 3  # Down  (Yellow)
    L = 4  # Left  (Orange)
    B = 5  # Back  (Blue)


# ──────────────────────────────────────────────
# Color names for display / debugging
# ──────────────────────────────────────────────
COLOR_NAMES = {
    Face.U: "White",
    Face.R: "Red",
    Face.F: "Green",
    Face.D: "Yellow",
    Face.L: "Orange",
    Face.B: "Blue",
}

# Short color codes (for Kociemba-style string representation)
COLOR_CODES = {
    Face.U: "U",
    Face.R: "R",
    Face.F: "F",
    Face.D: "D",
    Face.L: "L",
    Face.B: "B",
}

# ──────────────────────────────────────────────
# Cube dimensions
# ──────────────────────────────────────────────
CUBE_SIZE = 6

# ──────────────────────────────────────────────
# Move notation
# ──────────────────────────────────────────────
# Face names that can appear in moves
FACE_LETTERS = {"U", "D", "R", "L", "F", "B"}

# Map face letter to Face enum
FACE_MAP = {
    "U": Face.U,
    "R": Face.R,
    "F": Face.F,
    "D": Face.D,
    "L": Face.L,
    "B": Face.B,
}

# Opposite face mapping
OPPOSITE_FACE = {
    Face.U: Face.D,
    Face.D: Face.U,
    Face.R: Face.L,
    Face.L: Face.R,
    Face.F: Face.B,
    Face.B: Face.F,
}

# ──────────────────────────────────────────────
# Move parsing
# ──────────────────────────────────────────────
# Regex to parse move strings like: R, R', R2, 2R, 2R', 2Rw, 3Fw2, etc.
# Groups: (depth)(face)(wide)(direction)
#   depth: optional integer (1-based layer, default 1 = outermost)
#   face:  U/D/R/L/F/B
#   wide:  optional 'w' (rotate from layer 1 through depth)
#   direction: optional ' or 2 (prime = CCW, 2 = 180°)
MOVE_REGEX = re.compile(
    r"^(\d?)([UDRLF B])(w?)(['2]?)$"
)


def parse_move(move_str: str) -> dict:
    """
    Parse a move string into its components.

    Returns dict with:
        face:      Face enum
        depth:     int (1 = outermost layer, 2 = second layer, etc.)
        wide:      bool (if True, rotate layers 1..depth together)
        turns:     int (1 = CW 90°, -1 = CCW 90°, 2 = 180°)

    Examples:
        "R"    → face=R, depth=1, wide=False, turns=1
        "R'"   → face=R, depth=1, wide=False, turns=-1
        "R2"   → face=R, depth=1, wide=False, turns=2
        "2R"   → face=R, depth=2, wide=False, turns=1
        "3Rw'" → face=R, depth=3, wide=True,  turns=-1
        "Uw"   → face=U, depth=2, wide=True,  turns=1  (Uw defaults depth=2)
    """
    move_str = move_str.strip()
    m = MOVE_REGEX.match(move_str)
    if not m:
        raise ValueError(f"Invalid move notation: '{move_str}'")

    depth_str, face_letter, wide_str, dir_str = m.groups()

    face = FACE_MAP[face_letter]
    wide = bool(wide_str)

    # Depth
    if depth_str:
        depth = int(depth_str)
    elif wide:
        depth = 2  # "Uw" means layers 1-2
    else:
        depth = 1

    # Direction / turns
    if dir_str == "'":
        turns = -1
    elif dir_str == "2":
        turns = 2
    else:
        turns = 1

    if depth < 1 or depth > CUBE_SIZE // 2:
        raise ValueError(f"Depth {depth} out of range for {CUBE_SIZE}×{CUBE_SIZE} cube")

    return {
        "face": face,
        "depth": depth,
        "wide": wide,
        "turns": turns,
    }


def move_to_string(face: Face, depth: int = 1, wide: bool = False, turns: int = 1) -> str:
    """Convert move components back to standard notation string."""
    s = ""
    if depth > 1 or (depth == 1 and not wide):
        if depth > 1:
            s += str(depth)
    s += face.name
    if wide:
        s += "w"
    if turns == -1:
        s += "'"
    elif turns == 2:
        s += "2"
    return s


def invert_move(move_str: str) -> str:
    """Return the inverse of a move. R → R', R' → R, R2 → R2."""
    parsed = parse_move(move_str)
    if parsed["turns"] == 1:
        parsed["turns"] = -1
    elif parsed["turns"] == -1:
        parsed["turns"] = 1
    # turns == 2 stays the same (180° is self-inverse)
    return move_to_string(**parsed)


def invert_sequence(moves: list[str]) -> list[str]:
    """Return the inverse of a move sequence (reversed, each move inverted)."""
    return [invert_move(m) for m in reversed(moves)]
