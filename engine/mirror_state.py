"""
mirror_state.py — 3x3 Mirror Cube (Mirror Blocks) geometry and move engine.

Vendored verbatim from ~/cubeblender/mirror_state.py so TWIST stays
self-contained. The cube is a normal 3x3 mechanism with asymmetric cut planes:
every piece keeps its own box dimensions as it travels, which is exactly why a
scrambled mirror cube is lumpy. Solving it means restoring the cube shape, not
matching colours.
"""

import random
import numpy as np

# ── cuts and centers for 3x3 Mirror Cube ──────────────────────────────────
# Solving dimensions: 3.2 x 3.2 x 3.2
# Center of rotation is (0,0,0)
# To prevent collision and coordinate drift, cuts along all axes (X, Y, Z) must
# be identical and the middle slice must be symmetric around the origin.
CUTS = [-1.4, -0.35, 0.35, 1.85]

# Slice thicknesses:
# Slice 0 (Left/Down/Back): 1.05
# Slice 1 (Middle): 0.70
# Slice 2 (Right/Up/Front): 1.50
W = [CUTS[i+1] - CUTS[i] for i in range(3)] 
H = W
D = W

# Solved centers
CX = [(CUTS[i+1] + CUTS[i]) / 2.0 for i in range(3)] # [-0.875, 0.0, 1.1]
CY = CX
CZ = CX

AXES = {
    'U': (0, 1, 0),
    'D': (0, 1, 0),
    'R': (1, 0, 0),
    'L': (1, 0, 0),
    'F': (0, 0, 1),
    'B': (0, 0, 1),
}

BASE_ANGLES = {
    'U': -90,
    'D': 90,
    'R': -90,
    'L': 90,
    'F': -90,
    'B': 90,
}


def get_rotation_matrix(axis, angle_deg):
    """Rodrigues' rotation formula to get 3x3 rotation matrix."""
    angle = np.radians(angle_deg)
    c, s = np.cos(angle), np.sin(angle)
    ax, ay, az = axis
    norm = np.sqrt(ax*ax + ay*ay + az*az)
    ax, ay, az = ax/norm, ay/norm, az/norm
    
    R = np.array([
        [c + ax*ax*(1-c),    ax*ay*(1-c) - az*s, ax*az*(1-c) + ay*s],
        [ay*ax*(1-c) + az*s, c + ay*ay*(1-c),    ay*az*(1-c) - ax*s],
        [az*ax*(1-c) - ay*s, az*ay*(1-c) + ax*s, c + az*az*(1-c)   ]
    ])
    return R


class Cubie:
    def __init__(self, i, j, k):
        self.i = i
        self.j = j
        self.k = k
        self.width = W[i]
        self.height = H[j]
        self.depth = D[k]
        
        center = (CX[i], CY[j], CZ[k])
        self.solved_center = np.array(center, dtype=float)
        
        # State
        self.pos = np.array(center, dtype=float)
        self.rot = np.identity(3, dtype=float)
        
        # External faces mapping:
        # fi=0: -Z (Back), 1: +Z (Front), 2: +Y (Up), 3: -Y (Down), 4: +X (Right), 5: -X (Left)
        self.external_faces = [
            k == 0, # Back (-Z)
            k == 2, # Front (+Z)
            j == 2, # Up (+Y)
            j == 0, # Down (-Y)
            i == 2, # Right (+X)
            i == 0, # Left (-X)
        ]

    def reset(self):
        self.pos = self.solved_center.copy()
        self.rot = np.identity(3, dtype=float)


class MirrorCubeState:
    def __init__(self):
        self.cubies = []
        for i in range(3):
            for j in range(3):
                for k in range(3):
                    self.cubies.append(Cubie(i, j, k))

    def reset(self):
        for c in self.cubies:
            c.reset()

    def get_affected_cubies(self, face):
        """Returns the cubies belonging to the specified face's layer."""
        affected = []
        for c in self.cubies:
            x, y, z = c.pos
            if face == 'U' and y > 0.2:
                affected.append(c)
            elif face == 'D' and y < -0.2:
                affected.append(c)
            elif face == 'R' and x > 0.2:
                affected.append(c)
            elif face == 'L' and x < -0.2:
                affected.append(c)
            elif face == 'F' and z > 0.2:
                affected.append(c)
            elif face == 'B' and z < -0.2:
                affected.append(c)
        return affected

    def apply_move(self, move_str):
        """Apply a 3x3 face move like 'R', 'U2', or 'F''."""
        face = move_str[0]
        suffix = move_str[1:] if len(move_str) > 1 else ""
        
        turns = 1
        if suffix == "'":
            turns = -1
        elif suffix == "2":
            turns = 2
            
        axis = AXES[face]
        angle = BASE_ANGLES[face] * turns
        R_mat = get_rotation_matrix(axis, angle)
        
        affected = self.get_affected_cubies(face)
        for c in affected:
            c.pos = np.dot(R_mat, c.pos)
            c.rot = np.dot(R_mat, c.rot)

    def is_solved(self):
        """Checks if all cubies are back to their original position and orientation."""
        for c in self.cubies:
            if not np.allclose(c.pos, c.solved_center, atol=1e-3):
                return False
            if not np.allclose(c.rot, np.identity(3), atol=1e-3):
                return False
        return True

    def to_kociemba_string(self):
        """Reconstruct the 3x3 color state string for the Kociemba solver."""
        # Map current positions to slot indices (0, 1, 2)
        grid = {}
        for c in self.cubies:
            i = 0 if c.pos[0] < -0.2 else (2 if c.pos[0] > 0.2 else 1)
            j = 0 if c.pos[1] < -0.2 else (2 if c.pos[1] > 0.2 else 1)
            k = 0 if c.pos[2] < -0.2 else (2 if c.pos[2] > 0.2 else 1)
            grid[(i, j, k)] = c

        def get_face_color(cubie, world_dir):
            # Rotate world direction into cubie's local frame
            local_dir = np.dot(cubie.rot.T, world_dir)
            
            # Local face directions:
            # 0=Back(-Z), 1=Front(+Z), 2=Up(+Y), 3=Down(-Y), 4=Right(+X), 5=Left(-X)
            local_axes = [
                (0.0, 0.0, -1.0),
                (0.0, 0.0, 1.0),
                (0.0, 1.0, 0.0),
                (0.0, -1.0, 0.0),
                (1.0, 0.0, 0.0),
                (-1.0, 0.0, 0.0),
            ]
            
            best_fi = 0
            best_dot = -2.0
            for fi, axis in enumerate(local_axes):
                dot = np.dot(local_dir, axis)
                if dot > best_dot:
                    best_dot = dot
                    best_fi = fi
            
            # Map the local face to its solved/home color letter
            if cubie.external_faces[best_fi]:
                if best_fi == 0: return 'B'
                elif best_fi == 1: return 'F'
                elif best_fi == 2: return 'U'
                elif best_fi == 3: return 'D'
                elif best_fi == 4: return 'R'
                elif best_fi == 5: return 'L'
            return '?' # Fallback for internal face query (should not occur)

        res = []
        # U face (Up, world-dir (0, 1, 0)): scan Z from 0 to 2, then X from 0 to 2
        for z in [0, 1, 2]:
            for x in [0, 1, 2]:
                res.append(get_face_color(grid[(x, 2, z)], (0.0, 1.0, 0.0)))
                
        # R face (Right, world-dir (1, 0, 0)): scan Y from 2 to 0, then Z from 2 to 0
        for y in [2, 1, 0]:
            for z in [2, 1, 0]:
                res.append(get_face_color(grid[(2, y, z)], (1.0, 0.0, 0.0)))
                
        # F face (Front, world-dir (0, 0, 1)): scan Y from 2 to 0, then X from 0 to 2
        for y in [2, 1, 0]:
            for x in [0, 1, 2]:
                res.append(get_face_color(grid[(x, y, 2)], (0.0, 0.0, 1.0)))
                
        # D face (Down, world-dir (0, -1, 0)): scan Z from 2 to 0, then X from 0 to 2
        for z in [2, 1, 0]:
            for x in [0, 1, 2]:
                res.append(get_face_color(grid[(x, 0, z)], (0.0, -1.0, 0.0)))
                
        # L face (Left, world-dir (-1, 0, 0)): scan Y from 2 to 0, then Z from 0 to 2
        for y in [2, 1, 0]:
            for z in [0, 1, 2]:
                res.append(get_face_color(grid[(0, y, z)], (-1.0, 0.0, 0.0)))
                
        # B face (Back, world-dir (0, 0, -1)): scan Y from 2 to 0, then X from 2 to 0
        for y in [2, 1, 0]:
            for x in [2, 1, 0]:
                res.append(get_face_color(grid[(x, y, 0)], (0.0, 0.0, -1.0)))
                
        return "".join(res)


def get_random_scramble(length=25):
    faces = ['U', 'D', 'R', 'L', 'F', 'B']
    suffixes = ['', "'", '2']
    seq = []
    last_face = None
    for _ in range(length):
        face = random.choice(faces)
        while face == last_face:
            face = random.choice(faces)
        suffix = random.choice(suffixes)
        seq.append(face + suffix)
        last_face = face
    return seq
