"""
lighting.py — light rig tuned for machine vision rather than for looks.

The stock Rubix rig lights the cube from the front-top-right, which leaves the
`iso_back` view sitting in shadow. A model reading stickers from a screenshot
should see the same six colours from every angle, so this rig lifts the ambient
term and adds a rear fill light: less dramatic, far more legible.
"""

from OpenGL.GL import *


def sticker_lighting():
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)
    glEnable(GL_LIGHT2)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    # Key light — front / top / right.
    glLightfv(GL_LIGHT0, GL_POSITION, (4.0, 6.0, 9.0, 0.0))
    glLightfv(GL_LIGHT0, GL_AMBIENT, (0.42, 0.43, 0.45, 1.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.58, 0.60, 0.64, 1.0))
    glLightfv(GL_LIGHT0, GL_SPECULAR, (0.10, 0.11, 0.13, 1.0))

    # Side fill — keeps the left flank off the floor.
    glLightfv(GL_LIGHT1, GL_POSITION, (-7.0, -2.0, 5.0, 0.0))
    glLightfv(GL_LIGHT1, GL_AMBIENT, (0.0, 0.0, 0.0, 1.0))
    glLightfv(GL_LIGHT1, GL_DIFFUSE, (0.24, 0.25, 0.27, 1.0))
    glLightfv(GL_LIGHT1, GL_SPECULAR, (0.02, 0.02, 0.03, 1.0))

    # Under-light on the viewer's side. Lights are set in eye space, so this one
    # follows the camera and rescues downward-facing stickers in `iso_back`.
    glLightfv(GL_LIGHT2, GL_POSITION, (-1.5, -6.0, 6.0, 0.0))
    glLightfv(GL_LIGHT2, GL_AMBIENT, (0.0, 0.0, 0.0, 1.0))
    glLightfv(GL_LIGHT2, GL_DIFFUSE, (0.36, 0.37, 0.39, 1.0))
    glLightfv(GL_LIGHT2, GL_SPECULAR, (0.0, 0.0, 0.0, 1.0))

    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (0.10, 0.11, 0.13, 1.0))
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 30.0)


def mirror_lighting():
    """Brushed metal, but with the same rear fill so shape reads from any angle."""
    glEnable(GL_LIGHTING)
    glEnable(GL_LIGHT0)
    glEnable(GL_LIGHT1)
    glEnable(GL_LIGHT2)
    glEnable(GL_COLOR_MATERIAL)
    glColorMaterial(GL_FRONT_AND_BACK, GL_AMBIENT_AND_DIFFUSE)

    glLightfv(GL_LIGHT0, GL_POSITION, (5.0, 7.0, 9.0, 0.0))
    glLightfv(GL_LIGHT0, GL_AMBIENT, (0.34, 0.34, 0.37, 1.0))
    glLightfv(GL_LIGHT0, GL_DIFFUSE, (0.72, 0.75, 0.82, 1.0))
    glLightfv(GL_LIGHT0, GL_SPECULAR, (0.85, 0.85, 0.92, 1.0))

    glLightfv(GL_LIGHT1, GL_POSITION, (-6.0, -4.0, 4.0, 0.0))
    glLightfv(GL_LIGHT1, GL_AMBIENT, (0.0, 0.0, 0.0, 1.0))
    glLightfv(GL_LIGHT1, GL_DIFFUSE, (0.22, 0.22, 0.20, 1.0))
    glLightfv(GL_LIGHT1, GL_SPECULAR, (0.10, 0.10, 0.10, 1.0))

    glLightfv(GL_LIGHT2, GL_POSITION, (-1.5, -6.0, 6.0, 0.0))
    glLightfv(GL_LIGHT2, GL_AMBIENT, (0.0, 0.0, 0.0, 1.0))
    glLightfv(GL_LIGHT2, GL_DIFFUSE, (0.30, 0.30, 0.33, 1.0))
    glLightfv(GL_LIGHT2, GL_SPECULAR, (0.10, 0.10, 0.12, 1.0))

    glMaterialfv(GL_FRONT_AND_BACK, GL_SPECULAR, (0.9, 0.9, 0.95, 1.0))
    glMaterialf(GL_FRONT_AND_BACK, GL_SHININESS, 56.0)
