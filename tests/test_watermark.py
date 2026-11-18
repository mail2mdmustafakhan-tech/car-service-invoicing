"""The watermark, and the contrast it is allowed to cost.

The mark behind the pages is the workshop's own logo. It started as a picture
drawn faintly in the margins, which went wrong in a way that looked like a
styling bug and was not: the logo Mohammed installed is the white variant of
the ARC roundel, an RGB PNG with no alpha channel, so its white background is
as much a part of the file as the roundel is. Painted over a dark page it was
a grey rectangle with hard edges.

It is a mask now -- the logo's shape, in the page's own ink -- which needs a
logo that has a shape to mask. These tests are about that distinction, and
about the ceiling on how strong the mark may be, which is set by the faintest
text it passes over rather than by how it looks.
"""

from __future__ import annotations

import re
from pathlib import Path

import pytest

from app import images
from app import repository as repo

BRANDING = Path(__file__).resolve().parent.parent / "branding"
CSS = Path(__file__).resolve().parent.parent / "app" / "static" / "css" / "app.css"


# ---------------------------------------------------------------------------
# Telling one kind of logo from the other
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("name,expected", [
    ("arc-logo-512.png", True),
    ("arc-logo-1024.png", True),
    ("arc-logo-512-white.png", False),      # RGB, no alpha -- the one that broke it
    ("arc-logo.svg", True),
])
def test_transparency_is_read_from_the_file_itself(name, expected):
    assert images.has_transparency((BRANDING / name).read_bytes()) is expected


def test_a_jpeg_never_has_transparency():
    assert images.has_transparency(b"\xff\xd8\xff\xe0" + b"\x00" * 40) is False


def test_an_unreadable_file_is_not_treated_as_a_logo():
    assert images.has_transparency(b"") is False


def test_an_unknown_format_is_given_the_benefit_of_the_doubt():
    """A watermark that does not appear is a puzzle somebody has to solve; one
    that appears as a faint rectangle is a fault anybody can report. The
    second kind gets fixed, so lean that way."""
    assert images.has_transparency(b"GIF89a" + b"\x00" * 40) is True


# ---------------------------------------------------------------------------
# What the page does with the answer
# ---------------------------------------------------------------------------

def _install(conn, name):
    repo.set_logo(conn, (BRANDING / name).read_bytes(), filename=name)
    conn.commit()


def test_a_transparent_logo_gets_a_watermark(shop, web_db):
    from app import db

    with db.session(web_db) as conn:
        _install(conn, "arc-logo-1024.png")

    assert "--watermark" in shop.get("/settings").text


def test_a_solid_logo_gets_no_watermark_and_is_told_why(shop, web_db):
    """The grey box in dark mode, and the reason it was a mystery."""
    from app import db

    with db.session(web_db) as conn:
        _install(conn, "arc-logo-512-white.png")

    page = shop.get("/settings").text
    assert "--watermark" not in page, "the rectangle is back"
    assert "solid background" in page, "and nothing on the page says why"


def test_a_solid_logo_still_appears_everywhere_else(shop, web_db):
    """Only the watermark is refused. The top bar and the printed documents
    carry the logo as it is -- on white paper a white background is invisible,
    which is what that file was made for."""
    from app import db

    with db.session(web_db) as conn:
        _install(conn, "arc-logo-512-white.png")

    assert "/logo?v=" in shop.get("/settings").text
    assert shop.get("/logo").status_code == 200


def test_an_existing_logo_is_examined_once_and_remembered(shop, web_db):
    """An install that had a logo before the column existed must not have to
    re-upload it, and must not be re-read on every page load either -- the
    whole reason branding is its own table is to keep the bytes out of the
    render path.
    """
    from app import db

    with db.session(web_db) as conn:
        _install(conn, "arc-logo-1024.png")
        conn.execute("UPDATE branding SET logo_has_alpha = NULL")
        conn.commit()

    assert "--watermark" in shop.get("/settings").text

    with db.session(web_db) as conn:
        answer = conn.execute("SELECT logo_has_alpha FROM branding").fetchone()[0]
    assert answer == 1, "the answer was not written back, so it will be worked out again"


def test_removing_the_logo_forgets_the_answer(shop, web_db):
    from app import db

    with db.session(web_db) as conn:
        _install(conn, "arc-logo-1024.png")
        repo.clear_logo(conn)
        conn.commit()
        assert conn.execute("SELECT logo_has_alpha FROM branding").fetchone()[0] is None

    assert "--watermark" not in shop.get("/settings").text


# ---------------------------------------------------------------------------
# The ceiling, which is set by contrast and not by taste
# ---------------------------------------------------------------------------

def _hex(value: str) -> tuple[int, int, int]:
    value = value.lstrip("#")
    return tuple(int(value[i:i + 2], 16) for i in (0, 2, 4))  # type: ignore[return-value]


def _relative_luminance(colour: tuple[int, int, int]) -> float:
    def channel(v: float) -> float:
        v /= 255
        return v / 12.92 if v <= 0.03928 else ((v + 0.055) / 1.055) ** 2.4
    r, g, b = colour
    return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b)


def _contrast(a: tuple[int, int, int], b: tuple[int, int, int]) -> float:
    la, lb = _relative_luminance(a), _relative_luminance(b)
    hi, lo = max(la, lb), min(la, lb)
    return (hi + 0.05) / (lo + 0.05)


def _over(fg: tuple[int, int, int], bg: tuple[int, int, int], alpha: float):
    return tuple(
        round(f * alpha + b * (1 - alpha)) for f, b in zip(fg, bg, strict=True)
    )


def _tokens(block: str) -> dict[str, str]:
    return dict(re.findall(r"--([a-z-]+):\s*(#[0-9a-fA-F]{6});", block))


def _theme_blocks() -> dict[str, dict[str, str]]:
    """The light and dark token blocks, read out of the stylesheet."""
    css = CSS.read_text()
    light = css[css.index(":root {"):]
    light = light[:light.index("\n}")]
    dark = css[css.index('[data-theme="dark"] {'):]
    dark = dark[:dark.index("\n}")]
    return {"light": _tokens(light), "dark": _tokens(dark)}


def _watermark_rule() -> str:
    """The rule that draws the mark.

    Found by the declaration that only it has, not by its selector: the print
    block switches `body::before` off and sits earlier in the file, so
    searching for the selector finds the wrong rule. The first version of
    this helper did exactly that and the tests failed on the stylesheet
    rather than on the application.
    """
    css = CSS.read_text()
    at = css.index("mask-image: var(--watermark)")
    start = css.rindex("body::before", 0, at)
    return css[start:css.index("\n}", at)]


def _opacities() -> dict[str, float]:
    css = CSS.read_text()
    mark = _watermark_rule()
    base = float(re.search(r"opacity:\s*([\d.]+);", mark).group(1))
    dark = float(re.search(
        r'\[data-theme="dark"\] body::before \{ opacity: ([\d.]+); \}', css
    ).group(1))
    return {"light": base, "dark": dark}


def test_the_watermark_keeps_out_of_the_content_column():
    """It lives in the empty space beside the form and never over it.

    The mark was briefly centred over the whole page, which is what a
    watermark is on paper but not what was wanted here -- and it cost
    contrast on every line of text it lay under. In the margins it costs
    none, so the rule is simply that it stays there: sized and placed from
    the same 1140px the container is, and behind the content in any case.
    """
    rule = _watermark_rule()
    assert "z-index: 0;" in rule, "the mark must sit behind the content"
    assert "--edge: calc(50% - 570px" in rule, (
        "the mark's position is no longer derived from the content width, so "
        "the two can now drift apart"
    )
    assert "aspect-ratio: 1;" in rule, (
        "a height taken from --edge resolves against the viewport's height "
        "and collapses to zero -- see the comment in the stylesheet"
    )


def test_the_watermark_is_square():
    """Guarding one specific way it broke: `--edge` holds a percentage, and a
    percentage resolves against whichever property consumes it -- the window's
    width in `width` and its *height* in `height`. Used for both, the mark
    came out 200px wide and 0px tall, correctly positioned and invisible.
    The measurement that checked its width said everything was fine.
    """
    rule = _watermark_rule()
    assert "height:" not in rule, (
        "height must come from aspect-ratio, not from a percentage"
    )


@pytest.mark.parametrize("theme", ["light", "dark"])
def test_the_faintest_text_passes_even_with_no_watermark(theme):
    """The floor, independent of the mark. Worth its own test because this is
    what was actually broken: in the light theme --ink-faint was 3.53:1 --
    below AA on hints, the secondary column of every table and the whole
    footer -- before any watermark existed."""
    tokens = _theme_blocks()[theme]
    assert _contrast(_hex(tokens["ink-faint"]), _hex(tokens["surface"])) >= 4.5


def test_the_watermark_is_painted_as_a_mask_not_as_a_picture():
    """A picture is whatever the file contains, background included. A mask is
    only its shape."""
    mark = _watermark_rule()
    assert "mask-image: var(--watermark)" in mark
    assert "background-image: var(--watermark)" not in mark


def test_the_watermark_never_prints():
    """The customer's copy carries the logo in its letterhead; a second faint
    one in the margins is ink spent on nothing.

    Searched for the declaration rather than for "@media print", of which
    there is now more than one -- the pager hides its buttons the same way.
    """
    css = CSS.read_text()
    assert "body::before, body::after { display: none; }" in css


# ---------------------------------------------------------------------------
# Two smaller things on the same page
# ---------------------------------------------------------------------------

def test_the_marque_ribbon_is_centred():
    css = CSS.read_text()
    foot = css[css.index(".pagefoot-inner {"):]
    foot = foot[:foot.index("\n}")]
    assert "justify-content: center;" in foot


def test_applying_a_chart_filter_returns_to_the_charts(shop):
    """Applying a filter reloads the dashboard, and a reload starts at the
    top -- so the charts somebody was looking at when they pressed Apply
    ended up a screen and a half above them and the filter appeared to have
    done nothing. The form submits to the panel's own anchor.

    A GET form keeps the fragment of its action and replaces only the query,
    which is what makes this work at all.
    """
    page = shop.get("/").text
    assert 'id="analytics"' in page, "the panel has nothing to come back to"
    assert 'action="/#analytics"' in page


def test_clearing_a_chart_filter_returns_there_too(shop, web_db):
    from app import db

    with db.session(web_db) as conn:
        conn.execute(
            "INSERT INTO vehicles (customer_id, plate_no, make) VALUES (1, 'A', 'BMW')"
        )
        conn.commit()

    page = shop.get("/?make=BMW").text
    assert 'href="/#analytics"' in page
