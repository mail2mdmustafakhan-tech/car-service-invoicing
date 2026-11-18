"""The page as a column: bar, content, ribbon.

The ribbon used to land at a different height on every screen, because it
simply followed the content. Moving between a full list and an empty one
made the whole page look like it was jumping. The content now takes up the
slack, so on a short page the ribbon sits at the bottom of the window and on
a long one it follows the content as before.

These are structural assertions rather than pixel ones -- the browser does
the arithmetic, and what matters is that the three rules that make it work
are all still present.
"""

from __future__ import annotations

from pathlib import Path

CSS = Path("app/static/css/app.css")


def _block(selector: str) -> str:
    """The declarations of one rule.

    Anchored to the start of a line, because ".pagefoot {" is also a
    substring of the print rule ".topbar, .pagefoot {" and an unanchored
    search finds that one first -- which is how this helper lied the first
    time it was written.
    """
    css = CSS.read_text()
    start = css.index("\n" + selector) + 1
    return css[start:css.index("}", start)]


def test_the_page_is_a_full_height_column():
    body = _block("body {")
    assert "min-height: 100vh" in body
    assert "flex-direction: column" in body


def test_the_content_takes_up_the_slack():
    """Without this the column is full height and the ribbon still floats."""
    assert "flex: 1 0 auto" in _block("main.container {")


def test_the_ribbon_is_never_squashed():
    """A tall page would otherwise compress it rather than scrolling."""
    assert "flex: none" in _block(".pagefoot {")


def test_the_ribbon_comes_after_the_content(shop):
    """Order in the document is what puts it at the bottom of the column."""
    page = shop.get("/").text
    assert page.index("<main") < page.index('class="pagefoot"')


def test_an_empty_list_still_has_the_ribbon(shop):
    """The page with no data is exactly the one that showed the problem."""
    page = shop.get("/inspections").text
    assert 'class="marques"' in page


def test_the_section_is_called_inspections_throughout(shop):
    """It was briefly called "Checks"; the buttons kept the old word."""
    page = shop.get("/inspections").text
    assert "New check" not in page
    assert "No checks recorded" not in page
    assert "New inspection" in page
