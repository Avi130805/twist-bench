# Vendored from the Rubix project (github.com/Avi130805) so this repo runs
# standalone. Unmodified except for this header. The cube size constant is
# retargeted at import time by engine/sizing.py — see that module.

"""
cube_state.py — 6×6 Rubik's Cube state model and move engine.

State representation:
    6 faces, each a 6×6 numpy array of ints (0–5 representing colors).
    Face indices follow the Face enum in utils.py:
        0=U (Up/White), 1=R (Right/Red), 2=F (Front/Green),
        3=D (Down/Yellow), 4=L (Left/Orange), 5=B (Back/Blue)

    For each face, row 0 is the "top" row as seen when looking directly at
    that face, and column 0 is the "left" column.

Coordinate conventions (when looking at each face):
    U face: top-left is U[0][0], top-right is U[0][5]
            viewed from above, "top" row borders Back face
    D face: viewed from below, "top" row borders Front face
    F face: viewed head-on, "top" row borders Up face
    B face: viewed from behind (looking at the back), "top" row borders Up face
    R face: viewed from the right side, "top" row borders Up face
    L face: viewed from the left side, "top" row borders Up face
"""

import json
import numpy as np
from utils import (
    Face, CUBE_SIZE, COLOR_CODES, FACE_MAP, OPPOSITE_FACE,
    parse_move, invert_sequence
)


class CubeState:
    """
    Represents the full state of a 6×6×6 Rubik's Cube.

    The state is stored as a dict of 6 numpy arrays, keyed by Face enum.
    Each array is shape (6, 6) with integer values 0–5 representing colors.
    """

    def __init__(self):
        """Initialize to the solved state."""
        self.faces = {}
        for face in Face:
            self.faces[face] = np.full((CUBE_SIZE, CUBE_SIZE), face.value, dtype=np.int8)
        self.sticker_ids = self._solved_sticker_ids()

    # ──────────────────────────────────────────────
    # Basic accessors
    # ──────────────────────────────────────────────

    def get_face(self, face: Face) -> np.ndarray:
        """Return a copy of the 6×6 array for the given face."""
        return self.faces[face].copy()

    def get_sticker(self, face: Face, row: int, col: int) -> int:
        """Return the color value at a specific sticker position."""
        return int(self.faces[face][row, col])

    def set_sticker(self, face: Face, row: int, col: int, color: int):
        """Set the color value at a specific sticker position."""
        if not (0 <= color <= 5):
            raise ValueError(f"Color must be 0–5, got {color}")
        self.faces[face][row, col] = color
        self.sticker_ids = None

    def is_solved(self) -> bool:
        """Check if every face has a uniform color (any valid solved permutation)."""
        for face in Face:
            grid = self.faces[face]
            if not np.all(grid == grid[0, 0]):
                return False
        return True

    def copy(self) -> "CubeState":
        """Return an independent deep copy of this state."""
        new = CubeState.__new__(CubeState)
        new.faces = {f: arr.copy() for f, arr in self.faces.items()}
        sticker_ids = getattr(self, "sticker_ids", None)
        new.sticker_ids = (
            {f: arr.copy() for f, arr in sticker_ids.items()}
            if sticker_ids is not None
            else None
        )
        return new

    @staticmethod
    def _solved_sticker_ids() -> dict[Face, np.ndarray]:
        """Return stable physical sticker identities for a solved cube."""
        ids: dict[Face, np.ndarray] = {}
        face_area = CUBE_SIZE * CUBE_SIZE
        for face in Face:
            start = face.value * face_area
            ids[face] = np.arange(start, start + face_area, dtype=np.int16).reshape(
                (CUBE_SIZE, CUBE_SIZE)
            )
        return ids

    # ──────────────────────────────────────────────
    # Serialization
    # ──────────────────────────────────────────────

    def export_state(self) -> dict:
        """Serialize the cube state to a JSON-compatible dict."""
        return {
            face.name: self.faces[face].tolist()
            for face in Face
        }

    def import_state(self, data: dict):
        """Load cube state from a dict (as produced by export_state)."""
        for name, grid in data.items():
            face = Face[name]
            arr = np.array(grid, dtype=np.int8)
            if arr.shape != (CUBE_SIZE, CUBE_SIZE):
                raise ValueError(f"Face {name} has wrong shape: {arr.shape}")
            self.faces[face] = arr
        self.sticker_ids = None

    def to_json(self) -> str:
        """Serialize to a JSON string."""
        return json.dumps(self.export_state())

    @classmethod
    def from_json(cls, json_str: str) -> "CubeState":
        """Create a CubeState from a JSON string."""
        state = cls.__new__(cls)
        state.faces = {}
        state.sticker_ids = None
        for face in Face:
            state.faces[face] = np.zeros((CUBE_SIZE, CUBE_SIZE), dtype=np.int8)
        state.import_state(json.loads(json_str))
        return state

    # ──────────────────────────────────────────────
    # Kociemba 3×3 string (for after reduction)
    # ──────────────────────────────────────────────

    def to_3x3_string(self) -> str:
        """
        Convert the (reduced) cube state to a 54-character Kociemba string.

        Assumes the cube has been reduced: all 4×4 centers on each face are
        the same color, and all 4 edge wings per edge are paired.

        Maps each 6×6 face to a 3×3 face by sampling:
            3×3 position (r, c) maps to 6×6 position:
                (0,0)→(0,0)  (0,1)→(0,2)  (0,2)→(0,5)
                (1,0)→(2,0)  (1,1)→(2,2)  (1,2)→(2,5)
                (2,0)→(5,0)  (2,1)→(5,2)  (2,2)→(5,5)

        Face order for Kociemba: U R F D L B
        """
        # Mapping from 3×3 (r,c) to 6×6 (r,c) — corners and edges
        sample_map = [
            (0, 0), (0, 2), (0, 5),
            (2, 0), (2, 2), (2, 5),
            (5, 0), (5, 2), (5, 5),
        ]

        result = []
        for face in Face:
            grid = self.faces[face]
            for r6, c6 in sample_map:
                color_val = int(grid[r6, c6])
                result.append(COLOR_CODES[Face(color_val)])

        return "".join(result)

    # ──────────────────────────────────────────────
    # Face rotation (rotate a face grid in place)
    # ──────────────────────────────────────────────

    def _rotate_face_cw(self, face: Face):
        """Rotate a face grid 90° clockwise (as seen looking at that face)."""
        self.faces[face] = np.rot90(self.faces[face], k=-1)

    def _rotate_face_ccw(self, face: Face):
        """Rotate a face grid 90° counter-clockwise."""
        self.faces[face] = np.rot90(self.faces[face], k=1)

    def _rotate_face_180(self, face: Face):
        """Rotate a face grid 180°."""
        self.faces[face] = np.rot90(self.faces[face], k=2)

    # ──────────────────────────────────────────────
    # Layer rotation — the core move engine
    # ──────────────────────────────────────────────

    def _rotate_layer(self, face: Face, layer: int, turns: int):
        """
        Rotate a single layer of the cube.

        Args:
            face:  Which face this layer belongs to.
            layer: 0 = the face itself (outermost), 1 = one layer in, etc.
                   Range: 0 to CUBE_SIZE-1.
            turns: 1 = CW 90°, -1 = CCW 90°, 2 = 180° (from the perspective
                   of looking at `face`).
        """
        n = CUBE_SIZE  # 6

        # If it's the outermost layer (layer == 0), also rotate the face grid
        if layer == 0:
            if turns == 1:
                self._rotate_face_cw(face)
            elif turns == -1:
                self._rotate_face_ccw(face)
            elif turns == 2:
                self._rotate_face_180(face)

        # If it's the furthest layer, also rotate the opposite face
        if layer == n - 1:
            opp = OPPOSITE_FACE[face]
            if turns == 1:
                self._rotate_face_ccw(opp)  # CW on one side = CCW on the other
            elif turns == -1:
                self._rotate_face_cw(opp)
            elif turns == 2:
                self._rotate_face_180(opp)

        # Now cycle the 4 strips of stickers on adjacent faces.
        # The strip positions depend on which face and which layer.
        self._cycle_strips(face, layer, turns)

    def _cycle_strips(self, face: Face, layer: int, turns: int):
        """
        Cycle the 4 edge strips around the axis defined by `face` at `layer`.

        Each face rotation moves strips of 6 stickers between 4 adjacent faces.
        The layer index (0 = closest to `face`) determines which row/column
        of each adjacent face is affected.
        """
        n = CUBE_SIZE  # 6
        idx = layer  # distance from the face

        # Get the 4 strips in CW order (as seen looking at `face`)
        strips = self._get_strips(face, idx)

        # Read current values
        values = [self._read_strip(s) for s in strips]

        # Cycle them
        if turns == 1:  # CW
            # Each strip gets the value of the previous one
            # 0←3, 1←0, 2←1, 3←2
            new_values = [values[-1]] + values[:-1]
        elif turns == -1:  # CCW
            # 0←1, 1←2, 2←3, 3←0
            new_values = values[1:] + [values[0]]
        elif turns == 2:  # 180°
            # 0←2, 1←3, 2←0, 3←1
            new_values = [values[2], values[3], values[0], values[1]]
        else:
            raise ValueError(f"Invalid turns: {turns}")

        # Write back
        for s, v in zip(strips, new_values):
            self._write_strip(s, v)

    def _get_strips(self, face: Face, idx: int) -> list:
        """
        Return 4 strip descriptors in CW order for the given face and layer.

        Each strip is a tuple: (face, positions) where positions is a list of
        (row, col) tuples describing which stickers form the strip, ordered
        so that strip[0] is adjacent to the "next" face in CW order.

        The ordering convention ensures that when we cycle strips, the
        sticker orientations are preserved correctly.
        """
        n = CUBE_SIZE  # 6

        if face == Face.U:
            # U layer at depth `idx` — the strip is row `idx` on F/R/B/L
            # CW order looking down at U: F → R → B → L
            # F: row idx, left-to-right
            # R: row idx, left-to-right
            # B: row idx, left-to-right
            # L: row idx, left-to-right
            # BUT: B face is "mirrored" when looking from U.
            # Actually, let's think about this systematically.
            #
            # Looking down at U face, CW order:
            # F top row → R top row → B bottom row (reversed) → L top row
            # Wait, this needs careful analysis per face.
            #
            # Standard cube strip cycles for U layer at depth d:
            # F[d, 0..5] → R[d, 0..5] → B[5-d, 5..0] → L[d, 0..5]
            # BUT this depends on orientation convention. Let me use the
            # standard convention consistent with WCA orientation.

            # For U at depth idx:
            # CW rotation moves:
            #   F row idx  →  L row idx (reversed? no)
            # Let me just hard-code the correct cycles.

            # F row `idx` (L-to-R) → R col `idx` from opposite face perspective...
            # Actually the cleanest approach: define cycles explicitly.

            # When U rotates CW (looking from top):
            # F[idx, :] → R[:, n-1-idx] (bottom-to-top reading becomes left-to-right)
            # But we need to be careful about direction.

            # Let me use a cleaner formulation.
            # For a U-axis rotation at depth `idx`:
            return [
                (Face.F, [(idx, c) for c in range(n)]),          # F row idx, L→R
                (Face.R, [(idx, c) for c in range(n)]),          # R row idx, L→R -- WRONG
                (Face.B, [(n-1-idx, c) for c in range(n-1, -1, -1)]),  # B row n-1-idx, R→L
                (Face.L, [(idx, c) for c in range(n)]),          # L row idx, L→R -- WRONG
            ]
            # Hmm, this doesn't seem right either. Let me think more carefully.

        # I need to redo this systematically. Let me define the adjacency
        # strips for each face axis properly.

        # Actually, I'll implement this with a well-known correct approach:
        # define the 4 adjacent strips for each face's CW rotation directly.

        if face == Face.U:
            # U CW (looking from top): F→L, R→F, B→R, L→B
            # Strips: row `idx` on F, col `n-1-idx` on R (top→bottom),
            #         row `n-1-idx` on B (R→L), col `idx` on L (bottom→top)
            return [
                (Face.F, [(idx, c) for c in range(n)]),                       # F row
                (Face.R, [(idx, c) for c in range(n)]),                       # corrected below
                (Face.B, [(n-1-idx, c) for c in range(n-1, -1, -1)]),        # B row reversed
                (Face.L, [(idx, c) for c in range(n)]),                       # L row
            ]
            # No — I keep going in circles. Let me use THE definitive approach.

        # I'll abandon this tangled approach and use a rotation-matrix-based
        # method instead. See _apply_face_move() below.
        raise NotImplementedError("Use _apply_face_move instead")

    def _read_strip(self, strip) -> np.ndarray:
        face, positions = strip
        return np.array([self.faces[face][r, c] for r, c in positions], dtype=np.int8)

    def _write_strip(self, strip, values: np.ndarray):
        face, positions = strip
        for (r, c), v in zip(positions, values):
            self.faces[face][r, c] = v

    # ──────────────────────────────────────────────
    # Definitive move implementation
    # ──────────────────────────────────────────────
    # Instead of the generic strip-cycling approach above (which gets
    # confusing with orientation), I'll define the 4-strip cycles
    # explicitly for each of the 6 face axes. This is more code but
    # 100% correct and easy to verify.

    def _apply_single_layer(self, face: Face, layer: int, turns: int):
        """
        Apply a single-layer rotation.

        face:  The face axis (U/D/R/L/F/B)
        layer: 0 = outermost (touching `face`), up to n-1
        turns: 1=CW, -1=CCW, 2=180  (looking at `face`)
        """
        self._apply_physical_single_layer(face, layer, turns)

    def _extract_four_strips(self, face: Face, idx: int):
        """
        Extract 4 strips of length n in CW order for the given face axis.

        Returns 4 numpy arrays of length n (the sticker colors).
        The strips are ordered CW when looking at `face`.

        CRITICAL: The strips must be aligned so that sticker i in strip k
        maps to sticker i in strip k+1 after a CW rotation.
        """
        n = CUBE_SIZE

        if face == Face.U:
            # Looking down at U. CW = F→R→B→L (i.e., what's on F goes to R)
            # Wait, no. CW looking from top: front goes to LEFT.
            # Standard: U CW looking from top: F→L→B→R→F
            # Hmm, actually standard notation:
            # U CW: the top row of F goes where the top row of R was,
            #        top row of R goes where the bottom row (reversed) of B was, etc.
            #
            # Let me just use the KNOWN correct cycle:
            # U CW moves: F[idx]→R[idx], R[idx]→B_reversed[n-1-idx], B[n-1-idx]→L_reversed[idx], L[idx]→F[idx]
            #
            # No wait. Let me think super carefully.
            #
            # Physical U CW rotation (looking from above, turning the top layer clockwise):
            # - The stickers that were on the FRONT face's top row move to the RIGHT face's top row
            # - RIGHT top → BACK bottom (reversed)
            # - BACK bottom → LEFT top (reversed)  - wait, this reversal is wrong too...
            #
            # OK definitive source (verified many times in cubing implementations):
            # U CW:
            #   temp = F[idx, :]
            #   F[idx, :] = R[idx, :]
            #   R[idx, :] = B[idx, :]
            #   B[idx, :] = L[idx, :]
            #   L[idx, :] = temp
            # WAIT — this would be U' (counter-clockwise)!
            #
            # U CW (standard): Front moves to RIGHT, Left moves to FRONT,
            #   Back moves to LEFT, Right moves to BACK.
            #   Hmm, that's also wrong for many conventions.
            #
            # Let me use a physical model:
            # Stand in front of the cube, looking at F.
            # U = top face. CW = when viewed from ABOVE, turn clockwise.
            # So the front row of stickers (which is F's top row) goes to RIGHT.
            # No! Clockwise from above: Front → Right → Back → Left → Front.
            # So what WAS at Front goes to Right.
            #
            # F[idx, :] goes to become R[:, n-1-idx]? No — it stays as a row.
            #
            # Actually, if we're just rotating the U layer:
            # All four faces F, R, B, L have a horizontal row at depth idx from the top.
            # When U is rotated CW (from above): F→R, R→B, B→L, L→F
            # But B's row is "backwards" relative to the other three — when you go
            # around the cube, B is faced the opposite way.
            #
            # NO. The convention I defined in the docstring says:
            # "For each face, row 0 is the 'top' row as seen when looking directly at
            #  that face"
            # So the B face, when looked at directly, has its own row 0 at top.
            # When looking at the cube from above, B's row idx is at the BOTTOM of
            # the back face (because B is flipped horizontally relative to F when
            # viewed from above).
            #
            # SIMPLEST CORRECT APPROACH:
            # When we rotate U CW:
            #   F row idx (left to right) → R row idx (left to right)
            #   R row idx (left to right) → B row idx, but REVERSED (right to left)
            #     Wait no... I need to think about this with actual stickers.
            #
            # Let me label the stickers on the top ring:
            # F face, row 0: F00 F01 F02 F03 F04 F05
            # R face, row 0: R00 R01 R02 R03 R04 R05
            # B face, row 0: B00 B01 B02 B03 B04 B05
            # L face, row 0: L00 L01 L02 L03 L04 L05
            #
            # When U is turned CW (looking from top), going around the cube:
            # F00 is at front-left → goes to R00 (right-front)?
            #
            # No. Let's use 3D coordinates.
            # F face, row 0, col 0 = front-top-left corner of front face
            # After U CW, this sticker moves to...
            # CW from top: front-left corner goes to... right-front.
            # That means F[0,0] → R[0,0]
            # And F[0,5] → R[0,5]? No, F[0,5] is front-top-right,
            # which goes to right-top-back, which is R[0,5]. Yes!
            # So F row 0 → R row 0, same order.
            #
            # R[0,0] = right-top-front → goes to back-top-right.
            # B face row 0, with our convention "looking directly at B face"...
            # Looking at B face, left = the cube's right side (since we're looking
            # from behind). So back-top-right = B[0,0] when looking at B face.
            # And R[0,5] = right-top-back → back-top-left = B[0,5].
            # So R row 0 → B row 0, but REVERSED!
            # R[0,0]→B[0,5], R[0,1]→B[0,4], ..., R[0,5]→B[0,0]
            #
            # B[0,0] = back-top-right (looking at B) → goes to left-top-back
            # L face: looking at L, left = front, right = back
            # left-top-back = L[0,5]
            # B[0,5] = back-top-left → left-top-front = L[0,0]
            # So B row 0 → L row 0, but REVERSED!
            # B[0,0]→L[0,5], B[0,1]→L[0,4], ..., B[0,5]→L[0,0]
            #
            # L[0,0] = left-top-front → front-top-left = F[0,0]
            # L[0,5] = left-top-back → front-top... wait, that doesn't work.
            # L[0,0] goes to front. CW from top: left moves to front.
            # left-top-front → front-top-left = F[0,0]
            # left-top-back → front-top-right = F[0,5]? No!
            # CW from top: left-top-back should go to front-top... hmm.
            # left-top-front (L[0,0]) goes to front-top-LEFT.
            # Wait, no. If L is the left face, L[0,0] is looking at L face:
            # top-left of L = left-top-front of cube.
            # CW from top: front moves to right, left moves to front.
            # So left-top-front → front-top-left = F[0,0]. Yes!
            # left-top-back = L[0,5] → where? CW from top: left-back goes to front-left.
            # Hmm, no. CW from top: going clockwise, left→front→right→back→left.
            # So left-top-front → front-top-right? No...
            #
            # I'm overcomplicating this. Let me just use the x,y,z physical coords.
            #
            # Physical coordinates: x=left-to-right, y=bottom-to-top, z=back-to-front
            # U CW from top = rotation around Y axis, CW when viewed from +Y:
            #   x' = z, z' = -x  (or equivalently: x'=z, z'=n-1-x for discrete)
            #   Wait: CW from above in right-hand rule is actually rotation of
            #   (x,z) → (z, -x), so x' = z, z' = -x
            #   In our 0-indexed: x' = z, z' = n-1-x
            #
            # So sticker at position (x, y, z) goes to (z, y, n-1-x)
            # Now map this to face stickers:
            #
            # F face (z = n-1): sticker at row r (from top = n-1-r in y), col c (= x)
            #   So F[r, c] has physical coords: x=c, y=n-1-r (wait, row 0 is top which
            #   is max y)... Actually let me define:
            #   F face, viewed looking at it (-z direction):
            #     row 0 = top = y=n-1, row n-1 = bottom = y=0
            #     col 0 = left = x=0, col n-1 = right = x=n-1
            #   So F[r,c] → physical (x=c, y=n-1-r, z=n-1)
            #
            # R face (x = n-1): viewed looking at it (-x direction):
            #     row 0 = top = y=n-1, row n-1 = bottom = y=0
            #     col 0 = left = z=n-1 (front), col n-1 = right = z=0 (back)
            #   So R[r,c] → physical (x=n-1, y=n-1-r, z=n-1-c)
            #
            # B face (z = 0): viewed looking at it (+z direction, from behind):
            #     row 0 = top = y=n-1, row n-1 = bottom = y=0
            #     col 0 = left = x=n-1 (cube's right), col n-1 = right = x=0 (cube's left)
            #   So B[r,c] → physical (x=n-1-c, y=n-1-r, z=0)
            #
            # L face (x = 0): viewed looking at it (+x direction):
            #     row 0 = top = y=n-1, row n-1 = bottom = y=0
            #     col 0 = left = z=0 (back), col n-1 = right = z=n-1 (front)
            #   So L[r,c] → physical (x=0, y=n-1-r, z=c)
            #
            # U face (y = n-1): viewed looking at it (-y direction, from above):
            #     row 0 = top = z=0 (back), row n-1 = bottom = z=n-1 (front)
            #     col 0 = left = x=0, col n-1 = right = x=n-1
            #   So U[r,c] → physical (x=c, y=n-1, z=r)   ... Wait:
            #     row 0 = "top" when looking down = back (z=0)
            #     So U[r,c] → (x=c, y=n-1, z=r)
            #
            # D face (y = 0): viewed looking at it (+y direction, from below):
            #     row 0 = top when looking up = front (z=n-1)
            #     col 0 = left when looking up = x=0? Actually when looking up from
            #     below, left and right are flipped... let me think.
            #     Looking up at the bottom, with front still towards you:
            #     row 0 = front (z=n-1), row n-1 = back (z=0)
            #     col 0 = left = x=0, col n-1 = right = x=n-1
            #     Hmm, but that would make D a mirror of U, which is actually wrong
            #     for standard cubing. Let me re-check.
            #     Actually, convention varies. Let me use:
            #     D[r,c] → (x=c, y=0, z=n-1-r)
            #     This means row 0 = z=n-1 (front), which makes sense when looking
            #     at D from below with front towards you.
            #
            # Now let's verify U CW (rotation: x'=z, z'=n-1-x):
            # F[idx,c]: physical (c, n-1-idx, n-1)
            #   After rotation: (n-1, n-1-idx, n-1-c) → that's on R face (x=n-1)
            #   R[r',c']: (n-1, n-1-r', n-1-c'). So n-1-r'=n-1-idx → r'=idx,
            #   n-1-c'=n-1-c → c'=c.
            #   So F[idx,c] → R[idx,c]. ✓ Direct copy, no reversal!
            #
            # R[idx,c]: physical (n-1, n-1-idx, n-1-c)
            #   After rotation: (n-1-c, n-1-idx, n-1-(n-1)) = (n-1-c, n-1-idx, 0)
            #   That's on B face (z=0). B[r',c']: (n-1-c', n-1-r', 0)
            #   n-1-c'=n-1-c → c'=c. n-1-r'=n-1-idx → r'=idx.
            #   So R[idx,c] → B[idx,c]. ✓ Direct copy, no reversal!
            #
            # B[idx,c]: physical (n-1-c, n-1-idx, 0)
            #   After rotation: (0, n-1-idx, n-1-(n-1-c)) = (0, n-1-idx, c)
            #   That's on L face (x=0). L[r',c']: (0, n-1-r', c')
            #   n-1-r'=n-1-idx → r'=idx. c'=c.
            #   So B[idx,c] → L[idx,c]. ✓ Direct copy!
            #
            # L[idx,c]: physical (0, n-1-idx, c)
            #   After rotation: (c, n-1-idx, n-1-0) = (c, n-1-idx, n-1)
            #   That's on F face (z=n-1). F[r',c']: (c', n-1-r', n-1)
            #   c'=c. n-1-r'=n-1-idx → r'=idx.
            #   So L[idx,c] → F[idx,c]. ✓ Direct copy!
            #
            # BEAUTIFUL! For U CW: F→R→B→L→F, all row `idx`, all same column order!

            s0 = self.faces[Face.F][idx, :].copy()  # F row idx
            s1 = self.faces[Face.R][idx, :].copy()  # R row idx
            s2 = self.faces[Face.B][idx, :].copy()  # B row idx
            s3 = self.faces[Face.L][idx, :].copy()  # L row idx
            return s0, s1, s2, s3

        elif face == Face.D:
            # D CW (looking from below): physically it's rotation around Y,
            # but in the opposite sense (CW from below = CCW from above).
            # Rotation: x' = n-1-z, z' = x  (opposite of U)
            #
            # D governs layer at y = idx (0=D face, layer 0 = closest to D)
            # Physical y = idx for this layer.
            # But for the adjacent faces F/R/B/L, the row affected is:
            # On F face, y=idx means n-1-r=idx → r=n-1-idx
            # Similarly for R, B, L: r = n-1-idx
            #
            # D CW: rotation x'=n-1-z, z'=x
            # F[n-1-idx, c]: physical (c, idx, n-1)
            #   After: (n-1-(n-1), idx, c) = (0, idx, c) → L face (x=0)
            #   L[r', c']: (0, n-1-r', c'). n-1-r'=idx → r'=n-1-idx. c'=c.
            #   F[n-1-idx, c] → L[n-1-idx, c] ✓
            #
            # L[n-1-idx, c]: physical (0, idx, c)
            #   After: (n-1-c, idx, 0) → B face (z=0)
            #   B[r', c']: (n-1-c', n-1-r', 0). n-1-c'=n-1-c → c'=c.
            #   n-1-r'=idx → r'=n-1-idx.
            #   L[n-1-idx, c] → B[n-1-idx, c] ✓
            #
            # B[n-1-idx, c]: physical (n-1-c, idx, 0)
            #   After: (n-1-0, idx, n-1-c) = (n-1, idx, n-1-c) → R face (x=n-1)
            #   R[r', c']: (n-1, n-1-r', n-1-c'). n-1-r'=idx → r'=n-1-idx.
            #   n-1-c'=n-1-c → c'=c.
            #   B[n-1-idx, c] → R[n-1-idx, c] ✓
            #
            # R[n-1-idx, c]: physical (n-1, idx, n-1-c)
            #   After: (n-1-(n-1-c), idx, n-1) = (c, idx, n-1) → F face
            #   F[r', c']: (c', n-1-r', n-1). c'=c, n-1-r'=idx → r'=n-1-idx.
            #   R[n-1-idx, c] → F[n-1-idx, c] ✓
            #
            # So D CW: F→L→B→R→F, row n-1-idx, all same order!

            r = n - 1 - idx
            s0 = self.faces[Face.F][r, :].copy()
            s1 = self.faces[Face.L][r, :].copy()
            s2 = self.faces[Face.B][r, :].copy()
            s3 = self.faces[Face.R][r, :].copy()
            return s0, s1, s2, s3

        elif face == Face.R:
            # R CW (looking from right side): rotation around X axis
            # CW from +X: y' = z, z' = n-1-y  (or y' = z, z' = -y)
            #
            # R layer at depth idx: x = n-1-idx
            #
            # Affected stickers on U, F, D, B:
            # U face: U[r,c] → (c, n-1, r). x=c, so we need c=n-1-idx. → col n-1-idx
            # F face: F[r,c] → (c, n-1-r, n-1). x=c, need c=n-1-idx. → col n-1-idx
            # D face: D[r,c] → (c, 0, n-1-r). x=c, need c=n-1-idx. → col n-1-idx
            # B face: B[r,c] → (n-1-c, n-1-r, 0). x=n-1-c, need n-1-c=n-1-idx → c=idx. → col idx
            #
            # R CW: y'=z, z'=n-1-y
            # F[r, n-1-idx]: physical (n-1-idx, n-1-r, n-1)
            #   After: y'=n-1, z'=n-1-(n-1-r)=r. → (n-1-idx, n-1, r)
            #   That's on U face: U[r',c'] → (c', n-1, r'). c'=n-1-idx, r'=r.
            #   F[r, n-1-idx] → U[r, n-1-idx]... wait let me check.
            #   U[r,c] → physical (c, n-1, r). So (n-1-idx, n-1, r) → c=n-1-idx, r(U)=r.
            #   Hmm, but U[r,c] physical is (x=c, y=n-1, z=r). So for (n-1-idx, n-1, r):
            #   c=n-1-idx, z=r → r(U value)=r. Yes! F[r, n-1-idx] → U[r, n-1-idx] ✓
            #
            # U[r, n-1-idx]: physical (n-1-idx, n-1, r)
            #   After: y'=r, z'=n-1-(n-1)=0. → (n-1-idx, r, 0)
            #   B face (z=0): B[r',c'] → (n-1-c', n-1-r', 0). n-1-c'=n-1-idx → c'=idx.
            #   n-1-r'=r → r'=n-1-r.
            #   U[r, n-1-idx] → B[n-1-r, idx] ✓
            #
            # B[n-1-r, idx]: physical (n-1-idx, n-1-(n-1-r), 0) = (n-1-idx, r, 0)
            #   After: y'=0, z'=n-1-r → (n-1-idx, 0, n-1-r)
            #   D face (y=0): D[r',c'] → (c', 0, n-1-r'). c'=n-1-idx, n-1-r'=n-1-r → r'=r.
            #   B[n-1-r, idx] → D[r, n-1-idx] ✓... wait
            #   Actually for D: D[r,c] → physical (c, 0, n-1-r). So (n-1-idx, 0, n-1-r'):
            #   c=n-1-idx, n-1-r'= actual z = n-1-r, so r'=r.
            #   B[n-1-r, idx] → D[r, n-1-idx] ✓
            #
            # D[r, n-1-idx]: physical (n-1-idx, 0, n-1-r)
            #   After: y'=n-1-r, z'=n-1-0=n-1. → (n-1-idx, n-1-r, n-1)
            #   F face: F[r',c'] → (c', n-1-r', n-1). c'=n-1-idx, n-1-r'=n-1-r → r'=r.
            #   D[r, n-1-idx] → F[r, n-1-idx] ✓
            #
            # R CW cycle: F→U→B(reversed)→D→F
            # F[:, n-1-idx] → U[:, n-1-idx] (same order)
            # U[:, n-1-idx] → B[:, idx] (reversed: U[r]→B[n-1-r])
            # B[:, idx] → D[:, n-1-idx] (reversed: B[n-1-r]→D[r], i.e. B[s]→D[n-1-s])
            # D[:, n-1-idx] → F[:, n-1-idx] (same order)
            #
            # Strip 0 (s0) = F col n-1-idx top-to-bottom
            # Strip 1 (s1) = U col n-1-idx top-to-bottom
            # Strip 2 (s2) = B col idx BOTTOM-to-top (reversed)
            # Strip 3 (s3) = D col n-1-idx top-to-bottom
            # CW cycle: s0→s1, s1→s2, s2→s3, s3→s0
            # But s2 is reversed relative to others.
            # To handle: store them all in aligned order.

            c = n - 1 - idx
            s0 = self.faces[Face.F][:, c].copy()           # F col, top→bottom
            s1 = self.faces[Face.U][:, c].copy()            # U col, top→bottom
            s2 = self.faces[Face.B][:, idx][::-1].copy()    # B col idx, reversed
            s3 = self.faces[Face.D][:, c].copy()            # D col, top→bottom
            return s0, s1, s2, s3

        elif face == Face.L:
            # L CW (looking from left): rotation around X, opposite to R
            # CW from -X: y'=n-1-z, z'=y
            #
            # L at depth idx: x = idx
            #
            # Similar analysis yields:
            # L CW cycle: F→D→B(rev)→U→F  on cols
            # F col idx, U col idx, B col n-1-idx (reversed), D col idx

            c = idx
            bc = n - 1 - idx
            s0 = self.faces[Face.F][:, c].copy()
            s1 = self.faces[Face.D][:, c].copy()
            s2 = self.faces[Face.B][:, bc][::-1].copy()
            s3 = self.faces[Face.U][:, c].copy()
            return s0, s1, s2, s3

        elif face == Face.F:
            # F CW (looking at front): rotation around Z axis
            # CW from +Z: x'=y, y'=n-1-x  (or x'=y, y'=-x)
            #
            # F at depth idx: z = n-1-idx
            #
            # Affected faces: U, R, D, L
            # U face: U[r,c] → (c, n-1, r). z=r, need r=n-1-idx. → U row n-1-idx
            # R face: R[r,c] → (n-1, n-1-r, n-1-c). z=n-1-c, need n-1-c=n-1-idx → c=idx. → R col idx
            # D face: D[r,c] → (c, 0, n-1-r). z=n-1-r, need n-1-r=n-1-idx → r=idx. → D row idx
            # L face: L[r,c] → (0, n-1-r, c). z=c, need c=n-1-idx. → L col n-1-idx
            #
            # F CW: x'=y, y'=n-1-x
            # U[n-1-idx, c]: physical (c, n-1, n-1-idx)
            #   After: x'=n-1, y'=n-1-c → (n-1, n-1-c, n-1-idx)
            #   R face: (n-1, n-1-r', n-1-c'). n-1-r'=n-1-c → r'=c. n-1-c'=n-1-idx → c'=idx.
            #   U[n-1-idx, c] → R[c, idx] ✓
            #
            # R[r, idx]: physical (n-1, n-1-r, n-1-idx)
            #   After: x'=n-1-r, y'=n-1-(n-1)=0 → (n-1-r, 0, n-1-idx)
            #   D face: (c', 0, n-1-r'). c'=n-1-r, n-1-r'=n-1-idx → r'=idx.
            #   R[r, idx] → D[idx, n-1-r] ✓
            #
            # D[idx, c]: physical (c, 0, n-1-idx)
            #   After: x'=0, y'=n-1-c → (0, n-1-c, n-1-idx)
            #   L face: (0, n-1-r', c'). n-1-r'=n-1-c → r'=c. c'=n-1-idx.
            #   D[idx, c] → L[c, n-1-idx] ✓
            #
            # L[r, n-1-idx]: physical (0, n-1-r, n-1-idx)
            #   After: x'=n-1-r, y'=n-1-0=n-1 → (n-1-r, n-1, n-1-idx)
            #   U face: (c', n-1, r'). c'=n-1-r, r'=n-1-idx.
            #   L[r, n-1-idx] → U[n-1-idx, n-1-r] ✓
            #
            # Summary:
            # U[n-1-idx, c] → R[c, idx]        (U row → R col, aligned)
            # R[r, idx]      → D[idx, n-1-r]   (R col → D row, reversed)
            # D[idx, c]      → L[c, n-1-idx]   (D row → L col, aligned)
            # L[r, n-1-idx]  → U[n-1-idx, n-1-r] (L col → U row, reversed)
            #
            # So we have aligned strips:
            # s0 = U row n-1-idx, left→right
            # s1 = R col idx, top→bottom
            # s2 = D row idx, right→left (reversed)
            # s3 = L col n-1-idx, bottom→top (reversed)

            ur = n - 1 - idx
            s0 = self.faces[Face.U][ur, :].copy()                   # U row, L→R
            s1 = self.faces[Face.R][:, idx].copy()                  # R col, T→B
            s2 = self.faces[Face.D][idx, :][::-1].copy()            # D row, reversed
            s3 = self.faces[Face.L][:, n - 1 - idx][::-1].copy()    # L col, reversed
            return s0, s1, s2, s3

        elif face == Face.B:
            # B CW (looking from behind, i.e., looking in +z direction):
            # CW from -Z: x'=n-1-y, y'=x
            #
            # B at depth idx: z = idx
            #
            # Affected: U row idx, L col idx, D row n-1-idx, R col n-1-idx
            #
            # B CW analysis:
            # U[idx, c] → L[n-1-c, idx]    (U row → L col, reversed)
            # L[r, idx] → D[n-1-idx, r]    (L col → D row, aligned)
            # D[n-1-idx, c] → R[n-1-c, n-1-idx]  (D row → R col, reversed)
            # R[r, n-1-idx] → U[idx, r]    (R col → U row, aligned)
            #
            # Aligned strips:
            # s0 = U row idx, L→R
            # s1 = L col idx, bottom→top (reversed)
            # s2 = D row n-1-idx, R→L (reversed)
            # s3 = R col n-1-idx, T→B

            dr = n - 1 - idx
            s0 = self.faces[Face.U][idx, :].copy()
            s1 = self.faces[Face.L][:, idx][::-1].copy()
            s2 = self.faces[Face.D][dr, :][::-1].copy()
            s3 = self.faces[Face.R][:, dr].copy()
            return s0, s1, s2, s3

        raise ValueError(f"Unknown face: {face}")

    def _write_four_strips(self, face: Face, idx: int,
                           new_s0, new_s1, new_s2, new_s3):
        """Write 4 strips back to the cube after cycling."""
        n = CUBE_SIZE

        if face == Face.U:
            self.faces[Face.F][idx, :] = new_s0
            self.faces[Face.R][idx, :] = new_s1
            self.faces[Face.B][idx, :] = new_s2
            self.faces[Face.L][idx, :] = new_s3

        elif face == Face.D:
            r = n - 1 - idx
            self.faces[Face.F][r, :] = new_s0
            self.faces[Face.L][r, :] = new_s1
            self.faces[Face.B][r, :] = new_s2
            self.faces[Face.R][r, :] = new_s3

        elif face == Face.R:
            c = n - 1 - idx
            self.faces[Face.F][:, c] = new_s0
            self.faces[Face.U][:, c] = new_s1
            self.faces[Face.B][:, idx] = new_s2[::-1]      # reverse back
            self.faces[Face.D][:, c] = new_s3

        elif face == Face.L:
            c = idx
            bc = n - 1 - idx
            self.faces[Face.F][:, c] = new_s0
            self.faces[Face.D][:, c] = new_s1
            self.faces[Face.B][:, bc] = new_s2[::-1]       # reverse back
            self.faces[Face.U][:, c] = new_s3

        elif face == Face.F:
            ur = n - 1 - idx
            self.faces[Face.U][ur, :] = new_s0
            self.faces[Face.R][:, idx] = new_s1
            self.faces[Face.D][idx, :] = new_s2[::-1]      # reverse back
            self.faces[Face.L][:, n - 1 - idx] = new_s3[::-1]  # reverse back

        elif face == Face.B:
            dr = n - 1 - idx
            self.faces[Face.U][idx, :] = new_s0
            self.faces[Face.L][:, idx] = new_s1[::-1]      # reverse back
            self.faces[Face.D][dr, :] = new_s2[::-1]       # reverse back
            self.faces[Face.R][:, dr] = new_s3

    # ──────────────────────────────────────────────
    # Physical coordinate move implementation
    # ──────────────────────────────────────────────

    def _apply_physical_single_layer(self, face: Face, layer: int, turns: int):
        """
        Rotate one physical slice by moving each affected sticker by its 3D
        position and outward normal. This preserves cubie constraints.
        """
        if turns not in (-1, 1, 2):
            raise ValueError(f"Invalid turns: {turns}")

        axis, coord, cw_dir = self._layer_axis_coord_direction(face, layer)
        direction = cw_dir if turns in (1, 2) else -cw_dir
        reps = 2 if turns == 2 else 1

        source = {f: arr.copy() for f, arr in self.faces.items()}
        target = {f: arr.copy() for f, arr in self.faces.items()}
        source_ids = None
        target_ids = None
        if getattr(self, "sticker_ids", None) is not None:
            source_ids = {f: arr.copy() for f, arr in self.sticker_ids.items()}
            target_ids = {f: arr.copy() for f, arr in self.sticker_ids.items()}

        for src_face in Face:
            for row in range(CUBE_SIZE):
                for col in range(CUBE_SIZE):
                    pos, normal = self._sticker_to_physical(src_face, row, col)
                    if pos[axis] != coord:
                        continue

                    new_pos = pos
                    new_normal = normal
                    for _ in range(reps):
                        new_pos = self._rotate_coord_quarter(new_pos, axis, direction)
                        new_normal = self._rotate_normal_quarter(new_normal, axis, direction)

                    dst_face, dst_row, dst_col = self._physical_to_sticker(new_pos, new_normal)
                    target[dst_face][dst_row, dst_col] = source[src_face][row, col]
                    if source_ids is not None and target_ids is not None:
                        target_ids[dst_face][dst_row, dst_col] = source_ids[src_face][row, col]

        self.faces = target
        if target_ids is not None:
            self.sticker_ids = target_ids

    @staticmethod
    def _layer_axis_coord_direction(face: Face, layer: int):
        """Return (axis_index, layer_coordinate, cw_quarter_direction)."""
        n = CUBE_SIZE - 1
        if face == Face.U:
            return 1, n - layer, -1
        if face == Face.D:
            return 1, layer, 1
        if face == Face.R:
            return 0, n - layer, -1
        if face == Face.L:
            return 0, layer, 1
        if face == Face.F:
            return 2, n - layer, -1
        if face == Face.B:
            return 2, layer, 1
        raise ValueError(f"Unknown face: {face}")

    @staticmethod
    def _sticker_to_physical(face: Face, row: int, col: int):
        """Map a sticker to ((x,y,z), outward_normal)."""
        n = CUBE_SIZE - 1
        if face == Face.U:
            return (col, n, row), (0, 1, 0)
        if face == Face.D:
            return (col, 0, n - row), (0, -1, 0)
        if face == Face.R:
            return (n, n - row, n - col), (1, 0, 0)
        if face == Face.L:
            return (0, n - row, col), (-1, 0, 0)
        if face == Face.F:
            return (col, n - row, n), (0, 0, 1)
        if face == Face.B:
            return (n - col, n - row, 0), (0, 0, -1)
        raise ValueError(f"Unknown face: {face}")

    @staticmethod
    def _physical_to_sticker(pos, normal):
        """Map a physical sticker coordinate and normal back to face indices."""
        x, y, z = pos
        n = CUBE_SIZE - 1
        if normal == (0, 1, 0):
            return Face.U, z, x
        if normal == (0, -1, 0):
            return Face.D, n - z, x
        if normal == (1, 0, 0):
            return Face.R, n - y, n - z
        if normal == (-1, 0, 0):
            return Face.L, n - y, z
        if normal == (0, 0, 1):
            return Face.F, n - y, x
        if normal == (0, 0, -1):
            return Face.B, n - y, n - x
        raise ValueError(f"Invalid sticker normal: {normal}")

    @staticmethod
    def _rotate_coord_quarter(pos, axis: int, direction: int):
        """Rotate a coordinate one quarter turn around a global axis."""
        x, y, z = pos
        n = CUBE_SIZE - 1
        if axis == 0:
            return (x, n - z, y) if direction > 0 else (x, z, n - y)
        if axis == 1:
            return (z, y, n - x) if direction > 0 else (n - z, y, x)
        if axis == 2:
            return (n - y, x, z) if direction > 0 else (y, n - x, z)
        raise ValueError(f"Invalid axis: {axis}")

    @staticmethod
    def _rotate_normal_quarter(normal, axis: int, direction: int):
        """Rotate an outward normal one quarter turn around a global axis."""
        x, y, z = normal
        if axis == 0:
            return (x, -z, y) if direction > 0 else (x, z, -y)
        if axis == 1:
            return (z, y, -x) if direction > 0 else (-z, y, x)
        if axis == 2:
            return (-y, x, z) if direction > 0 else (y, -x, z)
        raise ValueError(f"Invalid axis: {axis}")

    # ──────────────────────────────────────────────
    # Public move interface
    # ──────────────────────────────────────────────

    def apply_move(self, move_str: str):
        """
        Apply a single move in standard notation.

        Examples: "R", "R'", "R2", "2U", "3Fw'", "Uw2"
        """
        parsed = parse_move(move_str)
        face = parsed["face"]
        depth = parsed["depth"]
        wide = parsed["wide"]
        turns = parsed["turns"]

        if wide:
            # Wide move: rotate layers 0 through depth-1
            for layer in range(depth):
                self._apply_single_layer(face, layer, turns)
        else:
            # Single layer at the given depth (depth is 1-based, layer is 0-based)
            layer = depth - 1
            self._apply_single_layer(face, layer, turns)

    def apply_sequence(self, moves: list[str]):
        """Apply a sequence of moves."""
        for move in moves:
            self.apply_move(move)

    # ──────────────────────────────────────────────
    # Display / debugging
    # ──────────────────────────────────────────────

    def __str__(self) -> str:
        """Pretty-print the cube state as an unfolded net."""
        n = CUBE_SIZE
        color_chars = "WRGOBY"  # Indices 0-5 → U(White), R(Red), F(Green), D(yell-O-w wait)
        # Let me use the Face enum values properly
        char_map = {
            0: "W",  # U = White
            1: "R",  # R = Red
            2: "G",  # F = Green
            3: "Y",  # D = Yellow
            4: "O",  # L = Orange
            5: "B",  # B = Blue
        }

        def face_row_str(face: Face, row: int) -> str:
            return " ".join(char_map[int(v)] for v in self.faces[face][row])

        lines = []

        # U face (indented)
        indent = " " * (n * 2 + 1)
        for r in range(n):
            lines.append(indent + face_row_str(Face.U, r))

        lines.append("")

        # L, F, R, B in a row
        for r in range(n):
            row = (
                face_row_str(Face.L, r) + "  " +
                face_row_str(Face.F, r) + "  " +
                face_row_str(Face.R, r) + "  " +
                face_row_str(Face.B, r)
            )
            lines.append(row)

        lines.append("")

        # D face (indented)
        for r in range(n):
            lines.append(indent + face_row_str(Face.D, r))

        return "\n".join(lines)

    def __repr__(self) -> str:
        return f"CubeState(solved={self.is_solved()})"

    # ──────────────────────────────────────────────
    # Validation (for color editor)
    # ──────────────────────────────────────────────

    def validate_sticker_counts(self) -> tuple[bool, str]:
        """
        Check that there are exactly 36 stickers of each color.

        Returns (is_valid, error_message).
        """
        counts = np.zeros(6, dtype=int)
        for face in Face:
            for val in self.faces[face].flat:
                counts[val] += 1

        expected = CUBE_SIZE * CUBE_SIZE  # 36
        for i in range(6):
            if counts[i] != expected:
                return False, (
                    f"Color {i} ({Face(i).name}) has {counts[i]} stickers, "
                    f"expected {expected}"
                )
        return True, "Valid"
