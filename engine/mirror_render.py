"""
mirror_render.py — OpenGL drawing for the silver 3x3 mirror cube.

Drawing code lifted from ~/cubeblender/mirror_main.py; the easing is swapped for
the same smootherstep curve cube_renderer.Animation uses so both cube families
animate identically.
"""

from math import cos, pi, sin

from OpenGL.GL import *

from .mirror_state import MirrorCubeState, AXES, BASE_ANGLES, CUTS

# The mechanism turns about the origin, but the solved block is not centred on
# it (the cut planes are asymmetric). Shift the whole model for display only so
# the cube sits in the middle of the frame; layer rotations stay about the origin.
MODEL_CENTER = (CUTS[0] + CUTS[-1]) / 2.0

QUADS = [
    (0, 1, 2, 3), (4, 5, 6, 7),   # Back (-Z), Front (+Z)
    (3, 2, 6, 7), (0, 1, 5, 4),   # Up (+Y), Down (-Y)
    (1, 2, 6, 5), (0, 3, 7, 4),   # Right (+X), Left (-X)
]

NORMALS = [
    (0, 0, -1), (0, 0, 1),
    (0, 1, 0), (0, -1, 0),
    (1, 0, 0), (-1, 0, 0),
]

EDGES = [
    (0, 1), (1, 2), (2, 3), (3, 0),
    (4, 5), (5, 6), (6, 7), (7, 4),
    (0, 4), (1, 5), (2, 6), (3, 7),
]

GAP = 0.03


def _vertices(w, h, d):
    hw, hh, hd = w / 2.0, h / 2.0, d / 2.0
    return [
        (-hw, -hh, -hd), (hw, -hh, -hd), (hw, hh, -hd), (-hw, hh, -hd),
        (-hw, -hh, hd), (hw, -hh, hd), (hw, hh, hd), (-hw, hh, hd),
    ]


def configure_lighting():
    """Brushed-metal rig — brighter and shinier than the sticker-cube rig."""
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    glLightfv(GL_LIGHT0, GL_POSITION, (5.0, 7.0, 9.0, 0.0))
    glLightfv(GL_LIGHT0, GL_AMBIENT, (0.35, 0.35, 0.38, 1.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.85, 0.88, 0.95, 1.0))
    glLightfv(GL_LIGHT0, GL_SPECULAR, (0.95, 0.95, 1.0, 1.0))

    glLightfv(GL_LIGHT1, GL_POSITION, (-6.0, -4.0, 4.0, 0.0))
    glLightfv(GL_LIGHT1, GL_DIFFUSE, (0.20, 0.20, 0.18, 1.0))
    glLightfv(GL_LIGHT1, GL_SPECULAR, (0.10, 0.10, 0.10, 1.0))

    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (1.0, 1.0, 1.0, 1.0))
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 64.0)


def _draw_background():
    viewport = glGetIntegerv(GL_VIEWPORT)
    w, h = int(viewport[2]), int(viewport[3])
    if w <= 0 or h <= 0:
        return

    glDisable(GL_DEPTH_TEST)
    glDisable(GL_LIGHTING)

    glMatrixMode(GL_PROJECTION)
    glPushMatrix()
    glLoadIdentity()
    glOrtho(0, w, 0, h, -1, 1)
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    glLoadIdentity()

    glBegin(GL_QUADS)
    glColor3f(0.55, 0.58, 0.62)
    glVertex2f(0, 0)
    glVertex2f(w, 0)
    glColor3f(0.78, 0.80, 0.82)
    glVertex2f(w, h)
    glVertex2f(0, h)
    glEnd()

    cx, cy = w * 0.50, h * 0.35
    rx, ry = min(w, h) * 0.32, min(w, h) * 0.11
    glBegin(GL_TRIANGLE_FAN)
    glColor4f(0.18, 0.20, 0.22, 0.32)
    glVertex2f(cx, cy)
    glColor4f(0.18, 0.20, 0.22, 0.0)
    for i in range(49):
        a = 2.0 * pi * i / 48
        glVertex2f(cx + cos(a) * rx, cy + sin(a) * ry)
    glEnd()

    glPopMatrix()
    glMatrixMode(GL_PROJECTION)
    glPopMatrix()
    glMatrixMode(GL_MODELVIEW)
    glEnable(GL_DEPTH_TEST)


def _cubie_matrix(cubie):
    r = cubie.rot
    return [
        float(r[0, 0]), float(r[1, 0]), float(r[2, 0]), 0.0,
        float(r[0, 1]), float(r[1, 1]), float(r[2, 1]), 0.0,
        float(r[0, 2]), float(r[1, 2]), float(r[2, 2]), 0.0,
        0.0, 0.0, 0.0, 1.0,
    ]


def _draw_faces(cubie, active):
    verts = _vertices(cubie.width - GAP, cubie.height - GAP, cubie.depth - GAP)
    glBegin(GL_QUADS)
    for fi, quad in enumerate(QUADS):
        glNormal3fv(NORMALS[fi])
        if cubie.external_faces[fi]:
            glColor3fv((0.86, 0.88, 0.92) if active else (0.75, 0.77, 0.80))
        else:
            glColor3fv((0.12, 0.13, 0.15))
        for vi in quad:
            glVertex3fv(verts[vi])
    glEnd()


def _draw_lines(cubie):
    verts = _vertices(cubie.width - GAP, cubie.height - GAP, cubie.depth - GAP)
    glBegin(GL_LINES)
    for a, b in EDGES:
        glVertex3fv(verts[a])
        glVertex3fv(verts[b])
    glEnd()


class MirrorAnimation:
    """Reverse-style animation: state is applied first, the layer swings to rest."""

    def __init__(self):
        self.active = False
        self.affected = []
        self.axis = (0, 1, 0)
        self.current = 0.0
        self.start_angle = 0.0
        self.progress = 1.0
        self.speed = 6.0

    def start(self, face: str, turns: int, affected):
        target = BASE_ANGLES[face] * turns
        self.axis = AXES[face]
        self.affected = affected
        self.start_angle = -target
        self.current = self.start_angle
        self.progress = 0.0
        self.speed = 6.0 if abs(turns) <= 1 else 9.0
        self.active = target != 0

    def update(self, dt=None):
        if not self.active:
            return False
        if dt is None:
            dt = 1.0 / 60.0
        dt = max(0.0, min(float(dt), 1.0 / 15.0))

        angle = max(abs(self.start_angle), 1e-6)
        self.progress = min(1.0, self.progress + (max(self.speed, 0.1) * 60.0 * dt) / angle)
        t = self.progress
        eased = t * t * t * (t * (t * 6.0 - 15.0) + 10.0)
        self.current = self.start_angle * (1.0 - eased)

        if self.progress >= 1.0:
            self.current = 0.0
            self.active = False
            self.affected = []
            return True
        return False


def draw_mirror_cube(state: MirrorCubeState, rot_x, rot_y, zoom, anim: MirrorAnimation):
    glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
    _draw_background()
    glClear(GL_DEPTH_BUFFER_BIT)

    glLoadIdentity()
    glTranslatef(0, 0, zoom)
    glRotatef(rot_x, 1, 0, 0)
    glRotatef(rot_y, 0, 1, 0)
    glTranslatef(-MODEL_CENTER, -MODEL_CENTER, -MODEL_CENTER)

    glEnable(GL_DEPTH_TEST)
    glEnable(GL_LIGHTING)

    animating = anim.active
    affected = anim.affected if animating else ()

    for c in state.cubies:
        glPushMatrix()
        active = animating and c in affected
        if active:
            glRotatef(anim.current, float(anim.axis[0]), float(anim.axis[1]), float(anim.axis[2]))
        glTranslatef(float(c.pos[0]), float(c.pos[1]), float(c.pos[2]))
        glMultMatrixf(_cubie_matrix(c))
        _draw_faces(c, active)
        glPopMatrix()

    glDisable(GL_LIGHTING)
    glEnable(GL_POLYGON_OFFSET_LINE)
    glPolygonOffset(-2, -2)
    glLineWidth(1.4)
    glColor4f(0.02, 0.02, 0.03, 0.80)

    for c in state.cubies:
        glPushMatrix()
        if animating and c in affected:
            glRotatef(anim.current, float(anim.axis[0]), float(anim.axis[1]), float(anim.axis[2]))
        glTranslatef(float(c.pos[0]), float(c.pos[1]), float(c.pos[2]))
        glMultMatrixf(_cubie_matrix(c))
        _draw_lines(c)
        glPopMatrix()

    glDisable(GL_POLYGON_OFFSET_LINE)
    glDisable(GL_LIGHTING)
