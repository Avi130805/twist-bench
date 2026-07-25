# Vendored from the Rubix project (github.com/Avi130805) so this repo runs
# standalone. Unmodified except for this header. The cube size constant is
# retargeted at import time by engine/sizing.py — see that module.

"""
cube_renderer.py — OpenGL rendering for the 6×6 Rubik's Cube.

Adapted from proven PyOpenGL code. Each cubie is drawn as GL_QUADS
with full colored faces, lit plastic side geometry, and crisp black edges.
Supports smooth layer rotation animation.
"""

from math import cos, pi, sin

from OpenGL.GL import *
from OpenGL.GLU import *
from cube_state import CubeState
from utils import Face, CUBE_SIZE

# ── Cubie geometry ───────────────────────────────────────────────────────
CUBIE = 0.985
HALF = CUBIE / 2.0
GAP = 1.0

VERTS = [
    (-HALF, -HALF, -HALF), ( HALF, -HALF, -HALF),
    ( HALF,  HALF, -HALF), (-HALF,  HALF, -HALF),
    (-HALF, -HALF,  HALF), ( HALF, -HALF,  HALF),
    ( HALF,  HALF,  HALF), (-HALF,  HALF,  HALF),
]

# fi=0: -Z (Back), 1: +Z (Front), 2: +Y (Up), 3: -Y (Down),
# 4: +X (Right), 5: -X (Left)
QUADS = [
    (0,1,2,3), (4,5,6,7),
    (3,2,6,7), (0,1,5,4),
    (1,2,6,5), (0,3,7,4),
]

NORMALS = [
    (0, 0,-1), (0, 0, 1),
    (0, 1, 0), (0,-1, 0),
    (1, 0, 0), (-1,0, 0),
]

EDGES = [
    (0,1),(1,2),(2,3),(3,0),
    (4,5),(5,6),(6,7),(7,4),
    (0,4),(1,5),(2,6),(3,7),
]

# ── Colors ───────────────────────────────────────────────────────────────
GL_COLORS = {
    0: (0.96, 0.97, 0.94),   # White  (U)
    1: (0.86, 0.04, 0.06),   # Red    (R)
    2: (0.02, 0.64, 0.32),   # Green  (F)
    3: (1.0,  0.84, 0.05),   # Yellow (D)
    4: (1.0,  0.45, 0.05),   # Orange (L)
    5: (0.04, 0.28, 0.86),   # Blue   (B)
}

BODY = (0.018, 0.020, 0.026)
INTERNAL = (0.050, 0.054, 0.064)
EDGE = (0.0, 0.0, 0.0)

N   = CUBE_SIZE          # 6
OFF = (N - 1) / 2.0      # 2.5

# CW rotation: (axis, angle) for glRotatef — mathematically correct values.
CW_ROT = {
    Face.U: ((0,1,0), -90),
    Face.D: ((0,1,0),  90),
    Face.R: ((1,0,0), -90),
    Face.L: ((1,0,0),  90),
    Face.F: ((0,0,1), -90),
    Face.B: ((0,0,1),  90),
}


# ── Sticker-to-CubeState mapping ────────────────────────────────────────

def _sticker_color(cs, gx, gy, gz, fi):
    n = N - 1
    val = None
    if   fi == 0 and gz == 0: val = cs.get_sticker(Face.B, n-gy, n-gx)
    elif fi == 1 and gz == n: val = cs.get_sticker(Face.F, n-gy, gx)
    elif fi == 2 and gy == n: val = cs.get_sticker(Face.U, gz, gx)
    elif fi == 3 and gy == 0: val = cs.get_sticker(Face.D, n-gz, gx)
    elif fi == 4 and gx == n: val = cs.get_sticker(Face.R, n-gy, n-gz)
    elif fi == 5 and gx == 0: val = cs.get_sticker(Face.L, n-gy, gz)
    return GL_COLORS[val] if val is not None else INTERNAL


def build_color_map(cs):
    """Build {(gx,gy,gz): [6 RGB tuples]} from CubeState."""
    cmap = {}
    for gx in range(N):
        for gy in range(N):
            for gz in range(N):
                if (0 < gx < N-1) and (0 < gy < N-1) and (0 < gz < N-1):
                    continue
                cmap[(gx,gy,gz)] = [
                    _sticker_color(cs, gx, gy, gz, fi) for fi in range(6)
                ]
    return cmap


# ── OpenGL init ──────────────────────────────────────────────────────────

def init_gl(w, h):
    glEnable(GL_MULTISAMPLE)
    glEnable(GL_LINE_SMOOTH)
    glHint(GL_LINE_SMOOTH_HINT, GL_NICEST)
    glEnable(GL_BLEND)
    glBlendFunc(GL_SRC_ALPHA, GL_ONE_MINUS_SRC_ALPHA)
    glShadeModel(GL_SMOOTH)
    glEnable(GL_NORMALIZE)
    glViewport(0, 0, w, h)
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(45.0, w / float(h), 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW)
    glLoadIdentity()
    glEnable(GL_DEPTH_TEST)
    glDepthFunc(GL_LEQUAL)
    glClearColor(0.70, 0.72, 0.74, 1.0)
    _configure_lighting()


def resize_gl(w, h):
    glViewport(0, 0, w, h)
    glMatrixMode(GL_PROJECTION); glLoadIdentity()
    gluPerspective(45.0, w / max(h, 1), 0.1, 100.0)
    glMatrixMode(GL_MODELVIEW)


def _configure_lighting():
    """Set up a soft two-light rig for the fixed-function OpenGL pipeline."""
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    glLightfv(GL_LIGHT0, GL_POSITION, (4.0, 6.0, 9.0, 0.0))
    glLightfv(GL_LIGHT0, GL_AMBIENT,  (0.25, 0.27, 0.30, 1.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE,  (0.86, 0.90, 0.98, 1.0))
    glLightfv(GL_LIGHT0, GL_SPECULAR, (0.24, 0.28, 0.36, 1.0))

    glLightfv(GL_LIGHT1, GL_POSITION, (-6.0, -3.0, 5.0, 0.0))
    glLightfv(GL_LIGHT1, GL_DIFFUSE,  (0.20, 0.22, 0.26, 1.0))
    glLightfv(GL_LIGHT1, GL_SPECULAR, (0.05, 0.06, 0.08, 1.0))

    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (0.18, 0.20, 0.24, 1.0))
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 38.0)


def _draw_scene_background():
    """Draw a neutral grey screen-space gradient and contact shadow."""
    viewport = glGetIntegerv(GL_VIEWPORT)
    w, h = int(viewport[2]), int(viewport[3])
    if w <= 0 or h <= 0:
        return

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)
    glDisable(GL_TEXTURE_2D)

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, w, 0, h, -1, 1)

    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glBegin(GL_QUADS)
    glColor3f(0.62, 0.64, 0.67)
    glVertex2f(0, 0)
    glVertex2f(w, 0)
    glColor3f(0.82, 0.83, 0.85)
    glVertex2f(w, h)
    glVertex2f(0, h)
    glEnd()

    cx = w * 0.50
    cy = h * 0.36
    rx = min(w, h) * 0.34
    ry = min(w, h) * 0.12

    glBegin(GL_TRIANGLE_FAN)
    glColor4f(0.28, 0.30, 0.32, 0.24)
    glVertex2f(cx, cy)
    glColor4f(0.28, 0.30, 0.32, 0.0)
    for i in range(49):
        a = 2.0 * pi * i / 48
        glVertex2f(cx + cos(a) * rx, cy + sin(a) * ry)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)


def _display_face_color(color, active=False):
    """Slightly brighten external face colors, with a small lift while moving."""
    lift = 0.060 if active else 0.020
    return tuple(min(1.0, c + (1.0 - c) * lift) for c in color)


def _has_sticker(color):
    return color != INTERNAL


def _apply_animation_transform(gx, gy, gz, anim):
    if anim and anim.active and (gx, gy, gz) in anim.affected:
        glRotatef(anim.current, *anim.axis)
        return True
    return False


def _draw_cubie_faces(fc, active):
    glBegin(GL_QUADS)
    for fi, quad in enumerate(QUADS):
        glNormal3fv(NORMALS[fi])
        if _has_sticker(fc[fi]):
            glColor3fv(_display_face_color(fc[fi], active))
        else:
            glColor3fv(BODY)
        for vi in quad:
            glVertex3fv(VERTS[vi])
    glEnd()


def _draw_cubie_lines(fc):
    glLineWidth(1.15)
    glBegin(GL_LINES)
    for a, b in EDGES:
        glVertex3fv(VERTS[a])
        glVertex3fv(VERTS[b])
    glEnd()


# ── Drawing ──────────────────────────────────────────────────────────────

def draw_cube(cmap, rot_x, rot_y, zoom, anim=None):
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    _draw_scene_background()
    glClear(GL_DEPTH_BUFFER_BIT)

    glLoadIdentity()
    glTranslatef(0, 0, zoom)
    glRotatef(rot_x, 1, 0, 0)
    glRotatef(rot_y, 0, 1, 0)

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)

    # ── Plastic body + full colored faces ──
    for (gx, gy, gz), fc in cmap.items():
        wx = (gx - OFF) * GAP
        wy = (gy - OFF) * GAP
        wz = (gz - OFF) * GAP

        glPushMatrix()
        active = _apply_animation_transform(gx, gy, gz, anim)
        glTranslatef(wx, wy, wz)
        _draw_cubie_faces(fc, active)
        glPopMatrix()

    # ── Crisp cubie seams and sticker bevel outlines ──
    glDisable(GL_LIGHTING)
    glEnable(GL_POLYGON_OFFSET_LINE)
    glPolygonOffset(-4, -4)
    glLineWidth(1.15)
    glColor4f(*EDGE, 0.72)

    for (gx, gy, gz), fc in cmap.items():
        wx = (gx - OFF) * GAP
        wy = (gy - OFF) * GAP
        wz = (gz - OFF) * GAP

        glPushMatrix()
        _apply_animation_transform(gx, gy, gz, anim)
        glTranslatef(wx, wy, wz)
        _draw_cubie_lines(fc)
        glPopMatrix()

    glDisable(GL_POLYGON_OFFSET_LINE)
    glDisable(GL_LIGHTING)


# ── Animation ────────────────────────────────────────────────────────────
# REVERSE approach: CubeState is applied BEFORE animation starts.
# The animation starts at -angle (displaced) and animates toward 0 (rest).
# This means the layer visually rotates INTO its final position — no snap.

class Animation:
    def __init__(self):
        self.active   = False
        self.affected = set()
        self.axis     = (0, 1, 0)
        self.current  = 0.0     # starts at -target, animates toward 0
        self.start_angle = 0.0
        self.progress = 1.0
        self.speed    = 6.0
        self.move_str = ""

    def start(self, face, depth, wide, turns):
        self.affected = set()
        layers = list(range(depth)) if wide else [depth - 1]

        for layer in layers:
            for gx in range(N):
                for gy in range(N):
                    for gz in range(N):
                        if (0 < gx < N-1) and (0 < gy < N-1) and (0 < gz < N-1):
                            continue
                        ok = False
                        if   face == Face.U: ok = (gy == N-1-layer)
                        elif face == Face.D: ok = (gy == layer)
                        elif face == Face.R: ok = (gx == N-1-layer)
                        elif face == Face.L: ok = (gx == layer)
                        elif face == Face.F: ok = (gz == N-1-layer)
                        elif face == Face.B: ok = (gz == layer)
                        if ok:
                            self.affected.add((gx, gy, gz))

        axis, cw = CW_ROT[face]
        self.axis = axis
        if   turns ==  1: target = cw
        elif turns == -1: target = -cw
        elif turns ==  2: target = cw * 2
        else:             target = 0

        # Start at NEGATIVE of target (displaced), animate toward 0 (rest).
        self.start_angle = -target
        self.current = self.start_angle
        self.progress = 0.0
        self.speed = 6.0 if abs(turns) <= 1 else 9.0
        self.active = target != 0

    def update(self, dt=None):
        """Advance toward 0 using delta time and smootherstep easing."""
        if not self.active:
            return False

        if dt is None:
            dt = 1.0 / 60.0
        dt = max(0.0, min(float(dt), 1.0 / 15.0))

        angle = max(abs(self.start_angle), 1e-6)
        self.progress = min(1.0, self.progress + (max(self.speed, 0.1) * 60.0 * dt) / angle)
        eased = _smootherstep(self.progress)
        self.current = self.start_angle * (1.0 - eased)

        if self.progress >= 1.0:
            self.current = 0.0
            self.progress = 1.0
            self.active = False
            return True
        return False


def _smootherstep(t):
    t = max(0.0, min(1.0, t))
    return t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
