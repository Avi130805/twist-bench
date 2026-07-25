"""
sizing.py — makes the fixed 6x6 Rubix engine work at any cube size 2..6.

The Rubix modules (`utils`, `cube_state`, `cube_renderer`) were written against a
module-level `CUBE_SIZE = 6` constant. Every function reads that constant at call
time through its module globals, so re-binding the module attribute is enough to
retarget the whole engine at a different N — no forking of the engine required.

`activate(n)` must be called before touching any CubeState / renderer function for
a cube of size n. Only one size is live at a time, which is all the app needs.
"""

import sys
from pathlib import Path

# The engine lives in engine/vendor/ (copied from the Rubix project, see the
# README there). Appended rather than prepended so it can never shadow a
# same-named module from the host application.
VENDOR_DIR = Path(__file__).resolve().parent / "vendor"
if str(VENDOR_DIR) not in sys.path:
    sys.path.append(str(VENDOR_DIR))

import utils            # noqa: E402  (vendored)
import cube_state       # noqa: E402  (vendored)

SUPPORTED_SIZES = (2, 3, 4, 5, 6)

_current = None
_renderer = None


def _renderer_module():
    """Import cube_renderer lazily — it pulls in PyOpenGL."""
    global _renderer
    if _renderer is None:
        import cube_renderer  # noqa: E402  (vendored)
        _renderer = cube_renderer
    return _renderer


def activate(n: int):
    """Retarget the Rubix engine at an n x n x n cube."""
    global _current
    if n not in SUPPORTED_SIZES:
        raise ValueError(f"Unsupported cube size: {n}")
    if _current == n:
        return
    utils.CUBE_SIZE = n
    cube_state.CUBE_SIZE = n
    rend = _renderer_module()
    rend.N = n
    rend.OFF = (n - 1) / 2.0
    _current = n


def current() -> int | None:
    return _current


def max_depth(n: int) -> int:
    """Deepest addressable slice for an n x n cube.

    Layers 1..n//2 from each of the six faces cover every slice that matters:
    on an odd cube the untouched middle slice is only reachable as a whole-cube
    rotation of the other layers, which never changes solvedness.
    """
    return n // 2
