"""
pngwrite.py — minimal, dependency-free PNG writer.

This pygame build has no SDL_image, so `pygame.image.save` can only emit BMP.
Screenshots are the benchmark's whole visual channel and they need to be PNGs a
vision model can read, so we encode them here with nothing but zlib.
"""

import struct
import zlib


def _chunk(tag: bytes, data: bytes) -> bytes:
    return (
        struct.pack(">I", len(data))
        + tag
        + data
        + struct.pack(">I", zlib.crc32(tag + data) & 0xFFFFFFFF)
    )


def write_rgb(path, width: int, height: int, rgb: bytes, level: int = 6):
    """Write 8-bit RGB pixel data (top-to-bottom, no row padding) as a PNG."""
    stride = width * 3
    expected = stride * height
    if len(rgb) < expected:
        raise ValueError(f"expected {expected} bytes of pixel data, got {len(rgb)}")

    # PNG wants a filter byte in front of every scanline; filter 0 = none.
    raw = bytearray()
    for y in range(height):
        raw.append(0)
        raw += rgb[y * stride:(y + 1) * stride]

    out = b"\x89PNG\r\n\x1a\n"
    out += _chunk(b"IHDR", struct.pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0))
    out += _chunk(b"IDAT", zlib.compress(bytes(raw), level))
    out += _chunk(b"IEND", b"")

    with open(path, "wb") as fh:
        fh.write(out)
    return path


def write_gl_readpixels(path, width: int, height: int, buf: bytes, level: int = 6):
    """Same, for a bottom-up buffer straight out of glReadPixels."""
    stride = width * 3
    flipped = b"".join(
        buf[y * stride:(y + 1) * stride] for y in range(height - 1, -1, -1)
    )
    return write_rgb(path, width, height, flipped, level)
