"""What can be told about an uploaded image from its own bytes.

Small and deliberately dependency-free: this project ships no image library,
because every one of them wants a compiler and this has to install on a
Windows PC at a service centre without one.

Only one question is asked here so far, and it is asked because of a bug that
looked like a styling problem and was not. The watermark in the page margins
is the workshop's own logo. The file Mohammed installed is the white variant
of the ARC roundel -- an RGB PNG with no alpha channel at all -- so its white
background is as much a part of the picture as the roundel is. Painted faintly
over a dark page it became a grey rectangle with hard edges, which is exactly
what a watermark must never be.

A logo with a transparent background is now masked rather than drawn (see
`app.css`), so only its shape is painted and in one flat colour that suits
whichever theme is on. A logo without one cannot be masked -- the mask would
be the whole rectangle -- so the watermark is simply not drawn, and Settings
says why.
"""

from __future__ import annotations

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"

#: PNG colour types that carry an alpha channel: 4 is greyscale+alpha,
#: 6 is truecolour+alpha. Type 3 is a palette, which can carry transparency
#: in a separate tRNS chunk instead.
PNG_ALPHA_TYPES = frozenset({4, 6})
PNG_PALETTE = 3


def has_transparency(data: bytes, mime: str = "") -> bool:
    """Whether *data* can be used as a mask -- that is, whether it has a
    transparent background rather than a solid one.

    Errs towards "yes" for formats that cannot be checked cheaply, because the
    cost of being wrong is asymmetric: a watermark that does not appear is a
    puzzle somebody has to solve, while one that appears as a faint rectangle
    is a visible fault anybody can report. The second kind gets fixed.
    """
    if not data:
        return False

    if data.startswith(PNG_MAGIC):
        return _png_has_alpha(data)

    # JPEG has no alpha channel. There is no variant of it that does.
    if data[:3] == b"\xff\xd8\xff":
        return False

    # SVG is shapes on nothing unless it paints its own background, and a
    # logo that paints its own background is unusual enough to let through.
    # GIF and WebP both carry transparency and are rare enough here not to
    # be worth a parser.
    return True


def _png_has_alpha(data: bytes) -> bool:
    """Read the colour type out of a PNG's header.

    The IHDR chunk is always first and always at the same offset: 8 bytes of
    signature, 4 of length, 4 of type, then width, height, bit depth, and at
    byte 25 the colour type.
    """
    if len(data) < 26:
        return False
    colour_type = data[25]
    if colour_type in PNG_ALPHA_TYPES:
        return True
    if colour_type == PNG_PALETTE:
        # A palette image is transparent only if it carries a tRNS chunk.
        # It appears before the image data, so there is no need to walk the
        # whole file -- but the file is small and correctness is cheaper than
        # a chunk parser here.
        return b"tRNS" in data
    return False
