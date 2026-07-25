"""
textfont.py — text rendering that survives a pygame build without SDL_ttf.

The venv's pygame has no compiled `font` module, so `pygame.font` falls back to a
pure-python shim that trips over a circular import with `pygame.sysfont`
(`pygame.freetype` fails the same way). The underlying `pygame._freetype` C
extension is fine, so this module wraps it in the small slice of the classic
`pygame.font.Font` API the HUD actually uses, and falls back to the real
`pygame.font` on a healthy install.
"""

import os

import pygame

_MONO_CANDIDATES = (
    "/System/Library/Fonts/Menlo.ttc",
    "/System/Library/Fonts/SFNSMono.ttf",
    "/System/Library/Fonts/Monaco.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSansMono.ttf",
)

_backend = None
_font_path = None


def _init():
    global _backend, _font_path
    if _backend:
        return _backend

    try:
        pygame.font.init()
        pygame.font.Font(None, 14)
        _backend = "pygame.font"
        return _backend
    except Exception:
        pass

    import pygame._freetype as freetype
    freetype.init()
    for path in _MONO_CANDIDATES:
        if os.path.exists(path):
            _font_path = path
            break
    else:
        _font_path = os.path.join(os.path.dirname(pygame.__file__), "freesansbold.ttf")
    _backend = "freetype"
    return _backend


class _FreetypeFont:
    """The subset of pygame.font.Font the HUD needs, on top of _freetype."""

    def __init__(self, size: int, bold: bool = False):
        import pygame._freetype as freetype
        self._font = freetype.Font(_font_path, size)
        self._font.antialiased = True
        self._font.strong = bold
        self._font.pad = True
        self._size = size
        self._linesize = max(int(self._font.get_sized_height(size)), size + 2)

    def render(self, text, antialias=True, color=(255, 255, 255)):
        self._font.antialiased = bool(antialias)
        surf, _ = self._font.render(text or " ", fgcolor=tuple(color)[:3], size=self._size)
        return surf

    def get_linesize(self):
        return self._linesize

    def size(self, text):
        rect = self._font.get_rect(text or " ", size=self._size)
        return rect.width, self._linesize


def mono(size: int, bold: bool = False):
    """Return a monospace font object with a pygame.font.Font-compatible API."""
    if _init() == "pygame.font":
        name = pygame.font.match_font("menlo,dejavusansmono,couriernew,monospace")
        return pygame.font.Font(name, size) if name else pygame.font.Font(None, size)
    return _FreetypeFont(size, bold)


def backend() -> str:
    return _init()
