# TWIST — Key Guide

> Generated from `engine/keymap.py` by `tools/gen_keymap.py`. Do not hand-edit.

Every cube is driven by the same layout. A key names a **slice**, a modifier
names the **direction**. Press `Tab` in the app to overlay this guide on screen.

## Modifiers

| Modifier | Turn | Notation | Example |
|---|---|---|---|
| *(none)* | 90 degrees clockwise | `R` | `R` = press `R` |
| `shift` | 90 degrees counter-clockwise | `R'` | `R'` = press `Shift+R` |
| `alt` / `option` | 180 degrees | `R2` | `R2` = press `Alt+R` |

"Clockwise" is always judged looking **at** the named face from outside the cube.

## Slice keys

**Depth 1 — outer face**

| Key | Move | Turns |
|---|---|---|
| `U` | `U` | Up face, slice 1 |
| `D` | `D` | Down face, slice 1 |
| `R` | `R` | Right face, slice 1 |
| `L` | `L` | Left face, slice 1 |
| `F` | `F` | Front face, slice 1 |
| `B` | `B` | Back face, slice 1 |

**Depth 2 — 2nd slice in**

| Key | Move | Turns |
|---|---|---|
| `T` | `2U` | Up face, slice 2 |
| `G` | `2D` | Down face, slice 2 |
| `V` | `2R` | Right face, slice 2 |
| `N` | `2L` | Left face, slice 2 |
| `H` | `2F` | Front face, slice 2 |
| `Y` | `2B` | Back face, slice 2 |

**Depth 3 — 3rd slice in**

| Key | Move | Turns |
|---|---|---|
| `3` | `3U` | Up face, slice 3 |
| `4` | `3D` | Down face, slice 3 |
| `1` | `3R` | Right face, slice 3 |
| `2` | `3L` | Left face, slice 3 |
| `5` | `3F` | Front face, slice 3 |
| `6` | `3B` | Back face, slice 3 |

## Which keys are live on which cube

| Cube | Select key | Live depths | Move keys | Legal moves |
|---|---|---|---|---|
| 2x2x2 (Pocket Cube) | `F1` | 1 | `U D R L F B` | 18 |
| 3x3x3 | `F2` | 1 | `U D R L F B` | 18 |
| 4x4x4 (Rubik's Revenge) | `F3` | 1, 2 | `U D R L F B T G V N H Y` | 36 |
| 5x5x5 (Professor's Cube) | `F4` | 1, 2 | `U D R L F B T G V N H Y` | 36 |
| 6x6x6 (V-Cube 6) | `F5` | 1, 2, 3 | `U D R L F B T G V N H Y 3 4 1 2 5 6` | 54 |
| 3x3 Mirror Cube (Mirror Blocks) | `F6` | 1 | `U D R L F B` | 18 |

Legal-move counts include all three directions per slice.
Pressing a key that is not live on the current cube does nothing.

## Per-cube detail

### 2x2x2 (Pocket Cube)  —  select with `F1`

Two layers only, so every slice is an outer face. Depth-1 keys are the whole move set.

- depth 1 (outer face): `U`->`U`  `D`->`D`  `R`->`R`  `L`->`L`  `F`->`F`  `B`->`B`

Example: `U` `U'` `U2` = `u` `shift+u` `alt+u`

### 3x3x3  —  select with `F2`

Depth-1 keys are the whole move set; the middle slice is just the other two layers turned the other way.

- depth 1 (outer face): `U`->`U`  `D`->`D`  `R`->`R`  `L`->`L`  `F`->`F`  `B`->`B`

Example: `U` `U'` `U2` = `u` `shift+u` `alt+u`

### 4x4x4 (Rubik's Revenge)  —  select with `F3`

Four layers: depth 1 and depth 2 from each of the six faces reach all of them.

- depth 1 (outer face): `U`->`U`  `D`->`D`  `R`->`R`  `L`->`L`  `F`->`F`  `B`->`B`
- depth 2 (2nd slice in): `T`->`2U`  `G`->`2D`  `V`->`2R`  `N`->`2L`  `H`->`2F`  `Y`->`2B`

Example: `U` `U'` `U2` = `u` `shift+u` `alt+u`

### 5x5x5 (Professor's Cube)  —  select with `F4`

Five layers. Depths 1-2 from each face reach layers 1,2,4,5; the centre slice only differs by a whole-cube rotation, which never changes solvedness.

- depth 1 (outer face): `U`->`U`  `D`->`D`  `R`->`R`  `L`->`L`  `F`->`F`  `B`->`B`
- depth 2 (2nd slice in): `T`->`2U`  `G`->`2D`  `V`->`2R`  `N`->`2L`  `H`->`2F`  `Y`->`2B`

Example: `U` `U'` `U2` = `u` `shift+u` `alt+u`

### 6x6x6 (V-Cube 6)  —  select with `F5`

Six layers: depths 1-3 from each face reach every one of them.

- depth 1 (outer face): `U`->`U`  `D`->`D`  `R`->`R`  `L`->`L`  `F`->`F`  `B`->`B`
- depth 2 (2nd slice in): `T`->`2U`  `G`->`2D`  `V`->`2R`  `N`->`2L`  `H`->`2F`  `Y`->`2B`
- depth 3 (3rd slice in): `3`->`3U`  `4`->`3D`  `1`->`3R`  `2`->`3L`  `5`->`3F`  `6`->`3B`

Example: `U` `U'` `U2` = `u` `shift+u` `alt+u`

### 3x3 Mirror Cube (Mirror Blocks)  —  select with `F6`

A 3x3 mechanism with asymmetric cut planes. One colour, so it is solved by restoring the cube SHAPE, not by matching colours.

- depth 1 (outer face): `U`->`U`  `D`->`D`  `R`->`R`  `L`->`L`  `F`->`F`  `B`->`B`

Example: `U` `U'` `U2` = `u` `shift+u` `alt+u`

## Everything else

| Key | Action |
|---|---|
| `F1 .. F6` | Pick cube (2x2 3x3 4x4 5x5 6x6 Mirror) |
| `space` | Scramble the current cube |
| `backspace` | Reset the current cube to solved |
| `z` | Undo the last move |
| `left / right` | Rotate camera (yaw) by 15 degrees |
| `up / down` | Rotate camera (pitch) by 15 degrees |
| `home` | Camera back to the default view |
| `\` | Flip to the opposite corner |
| `- / =` | Zoom out / in |
| `c` | Save a screenshot into shots/ |
| `tab` | Show / hide the on-screen key guide |
| `escape` | Quit |

Mouse: drag to orbit the camera, scroll to zoom, click the top-bar buttons to
switch cube / scramble / reset / undo / screenshot / toggle this guide.
