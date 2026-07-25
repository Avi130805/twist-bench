"""
keymap.py — the single source of truth for which key does what.

Both the human keyboard path and the agent bridge dispatch through the same
table, so a model driving the simulation presses exactly the keys a human would.

Layout
------
  depth 1 (outer face)      u d r l f b          ->  U  D  R  L  F  B
  depth 2 (2nd slice in)    t g v n h y          ->  2U 2D 2R 2L 2F 2B
  depth 3 (3rd slice in)    3 4 1 2 5 6          ->  3U 3D 3R 3L 3F 3B

Modifiers
---------
  (none)          90 degrees clockwise         R
  shift           90 degrees counter-clockwise R'
  alt / option    180 degrees                  R2

Which depths are live depends on the cube (see `depths_for`).
"""

DEPTH_KEYS = {
    1: {"u": "U", "d": "D", "r": "R", "l": "L", "f": "F", "b": "B"},
    2: {"t": "2U", "g": "2D", "v": "2R", "n": "2L", "h": "2F", "y": "2B"},
    3: {"3": "3U", "4": "3D", "1": "3R", "2": "3L", "5": "3F", "6": "3B"},
}

DEPTH_LABEL = {
    1: "outer face",
    2: "2nd slice in",
    3: "3rd slice in",
}

# Non-move keys. label -> description, kept here so the on-screen guide, the
# markdown guide and the `keymap` bridge command can never drift apart.
CONTROL_KEYS = [
    ("F1 .. F6", "Pick cube (2x2 3x3 4x4 5x5 6x6 Mirror)"),
    ("space", "Scramble the current cube"),
    ("backspace", "Reset the current cube to solved"),
    ("z", "Undo the last move"),
    ("left / right", "Rotate camera (yaw) by 15 degrees"),
    ("up / down", "Rotate camera (pitch) by 15 degrees"),
    ("home", "Camera back to the default view"),
    ("\\", "Flip to the opposite corner"),
    ("- / =", "Zoom out / in"),
    ("c", "Save a screenshot into shots/"),
    ("tab", "Show / hide the on-screen key guide"),
    ("escape", "Quit"),
]

CUBE_IDS = ("2x2", "3x3", "4x4", "5x5", "6x6", "mirror")

# Cube id -> the F-key that selects it.
SELECT_KEYS = {cube: f"f{i + 1}" for i, cube in enumerate(CUBE_IDS)}


def depths_for(cube_id: str) -> list[int]:
    """Live slice depths for a cube id ("2x2".."6x6", "mirror")."""
    if cube_id == "mirror":
        return [1]
    n = int(cube_id[0])
    return list(range(1, n // 2 + 1))


def moves_for(cube_id: str) -> list[str]:
    """Every base move (no modifier applied) the cube accepts."""
    out = []
    for depth in depths_for(cube_id):
        out.extend(DEPTH_KEYS[depth].values())
    return out


def key_to_move(cube_id: str, key_name: str) -> str | None:
    """Map a pressed key name to a base move, or None if it is not a move key."""
    for depth in depths_for(cube_id):
        move = DEPTH_KEYS[depth].get(key_name)
        if move:
            return move
    return None


def move_to_keystroke(cube_id: str, move: str) -> str | None:
    """Inverse of `key_to_move`, including the modifier. 'R2' -> 'alt+r'."""
    base, suffix = move, ""
    if move.endswith("'") or move.endswith("2"):
        base, suffix = move[:-1], move[-1]
    for depth in depths_for(cube_id):
        for key, m in DEPTH_KEYS[depth].items():
            if m == base:
                if suffix == "'":
                    return f"shift+{key}"
                if suffix == "2":
                    return f"alt+{key}"
                return key
    return None


def guide_lines(cube_id: str) -> list[str]:
    """Human-readable move guide for one cube, used by the HUD overlay."""
    lines = []
    for depth in depths_for(cube_id):
        keys = DEPTH_KEYS[depth]
        lines.append(f"depth {depth} ({DEPTH_LABEL[depth]})")
        pairs = "   ".join(f"{k.upper()}={m}" for k, m in keys.items())
        lines.append(f"  {pairs}")
    lines.append("shift = prime (CCW)   alt/option = 180")
    return lines
