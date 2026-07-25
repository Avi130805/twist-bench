#!/usr/bin/env python3
"""
gen_keymap.py — regenerate KEYMAP.md from engine/keymap.py.

The on-screen guide, the `keymap` bridge command and the markdown guide all read
the same tables, so run this after touching engine/keymap.py:

    python tools/gen_keymap.py
"""

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from engine import keymap  # noqa: E402

CUBE_TITLE = {
    "2x2": "2x2x2 (Pocket Cube)",
    "3x3": "3x3x3",
    "4x4": "4x4x4 (Rubik's Revenge)",
    "5x5": "5x5x5 (Professor's Cube)",
    "6x6": "6x6x6 (V-Cube 6)",
    "mirror": "3x3 Mirror Cube (Mirror Blocks)",
}

NOTES = {
    "2x2": "Two layers only, so every slice is an outer face. Depth-1 keys are the whole move set.",
    "3x3": "Depth-1 keys are the whole move set; the middle slice is just the other two layers turned the other way.",
    "4x4": "Four layers: depth 1 and depth 2 from each of the six faces reach all of them.",
    "5x5": "Five layers. Depths 1-2 from each face reach layers 1,2,4,5; the centre slice only differs by a whole-cube rotation, which never changes solvedness.",
    "6x6": "Six layers: depths 1-3 from each face reach every one of them.",
    "mirror": "A 3x3 mechanism with asymmetric cut planes. One colour, so it is solved by restoring the cube SHAPE, not by matching colours.",
}


def render() -> str:
    out = []
    w = out.append

    w("# TWIST — Key Guide")
    w("")
    w("> Generated from `engine/keymap.py` by `tools/gen_keymap.py`. Do not hand-edit.")
    w("")
    w("Every cube is driven by the same layout. A key names a **slice**, a modifier")
    w("names the **direction**. Press `Tab` in the app to overlay this guide on screen.")
    w("")

    w("## Modifiers")
    w("")
    w("| Modifier | Turn | Notation | Example |")
    w("|---|---|---|---|")
    w("| *(none)* | 90 degrees clockwise | `R` | `R` = press `R` |")
    w("| `shift` | 90 degrees counter-clockwise | `R'` | `R'` = press `Shift+R` |")
    w("| `alt` / `option` | 180 degrees | `R2` | `R2` = press `Alt+R` |")
    w("")
    w("\"Clockwise\" is always judged looking **at** the named face from outside the cube.")
    w("")

    w("## Slice keys")
    w("")
    for depth in sorted(keymap.DEPTH_KEYS):
        w(f"**Depth {depth} — {keymap.DEPTH_LABEL[depth]}**")
        w("")
        w("| Key | Move | Turns |")
        w("|---|---|---|")
        for key, move in keymap.DEPTH_KEYS[depth].items():
            face = move[-1]
            names = {"U": "Up", "D": "Down", "R": "Right", "L": "Left",
                     "F": "Front", "B": "Back"}
            w(f"| `{key.upper()}` | `{move}` | {names[face]} face, slice {depth} |")
        w("")

    w("## Which keys are live on which cube")
    w("")
    w("| Cube | Select key | Live depths | Move keys | Legal moves |")
    w("|---|---|---|---|---|")
    for cube in keymap.CUBE_IDS:
        depths = keymap.depths_for(cube)
        keys = []
        for d in depths:
            keys.extend(k.upper() for k in keymap.DEPTH_KEYS[d])
        w(f"| {CUBE_TITLE[cube]} | `{keymap.SELECT_KEYS[cube].upper()}` | "
          f"{', '.join(str(d) for d in depths)} | `{' '.join(keys)}` | "
          f"{len(keymap.moves_for(cube)) * 3} |")
    w("")
    w("Legal-move counts include all three directions per slice.")
    w("Pressing a key that is not live on the current cube does nothing.")
    w("")

    w("## Per-cube detail")
    w("")
    for cube in keymap.CUBE_IDS:
        w(f"### {CUBE_TITLE[cube]}  —  select with `{keymap.SELECT_KEYS[cube].upper()}`")
        w("")
        w(NOTES[cube])
        w("")
        for depth in keymap.depths_for(cube):
            pairs = "  ".join(
                f"`{k.upper()}`->`{m}`" for k, m in keymap.DEPTH_KEYS[depth].items()
            )
            w(f"- depth {depth} ({keymap.DEPTH_LABEL[depth]}): {pairs}")
        w("")
        example = keymap.moves_for(cube)[0]
        w(f"Example: `{example}` `{example}'` `{example}2` = "
          f"`{keymap.move_to_keystroke(cube, example)}` "
          f"`{keymap.move_to_keystroke(cube, example + chr(39))}` "
          f"`{keymap.move_to_keystroke(cube, example + '2')}`")
        w("")

    w("## Everything else")
    w("")
    w("| Key | Action |")
    w("|---|---|")
    for key, desc in keymap.CONTROL_KEYS:
        w(f"| `{key}` | {desc} |")
    w("")
    w("Mouse: drag to orbit the camera, scroll to zoom, click the top-bar buttons to")
    w("switch cube / scramble / reset / undo / screenshot / toggle this guide.")
    w("")
    return "\n".join(out)


if __name__ == "__main__":
    target = ROOT / "KEYMAP.md"
    target.write_text(render(), encoding="utf-8")
    print(f"wrote {target}")
