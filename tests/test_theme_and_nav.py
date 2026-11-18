"""The top bar: the name, the sections, and the two themes.

These are the things that broke before and would break quietly again -- a
truncated name reads as a bug in the data, and a theme that flashes white on
every navigation is worse than no theme at all.
"""

from __future__ import annotations

import re


def test_the_business_name_is_printed_whole(shop):
    """It used to be cut to "Advance Repair Cen...". Nothing truncates it now.

    Set through the application rather than the database, because what is
    being checked is the whole path from settings to the rendered bar.
    """
    shop.post(
        "/settings",
        data={
            "business_name_en": "Advance Repair Center BMW Specialized",
            "vat_rate": "15",
            "currency_code": "SAR",
        },
    )
    page = shop.get("/").text
    assert "Advance Repair Center BMW Specialized" in page


def test_every_section_carries_an_icon(shop):
    page = shop.get("/").text
    nav = page[page.index('class="topnav"'):page.index("</nav>")]
    links = re.findall(r"<a [^>]*href=", nav)
    icons = nav.count('class="ico"')
    assert len(links) == 10
    assert icons == len(links), f"{icons} icons for {len(links)} sections"


def test_the_icons_are_hidden_from_a_screen_reader(shop):
    """They repeat the word beside them. Read aloud twice is noise."""
    page = shop.get("/").text
    nav = page[page.index('class="topnav"'):page.index("</nav>")]
    assert nav.count('aria-hidden="true"') == 10


def test_the_sections_keep_their_words(shop):
    """An icon is a second label, never the only one."""
    page = shop.get("/").text
    for word in ("Dashboard", "Inspections", "Estimates", "Invoices",
                 "Customers", "Vehicles", "Settings"):
        assert f"<span>{word}</span>" in page


def test_the_theme_is_set_before_the_stylesheet_loads(shop):
    """Applied after the page paints, a dark theme flashes white first."""
    page = shop.get("/").text
    script_at = page.index("cs-theme")
    css_at = page.index("css/app.css")
    assert script_at < css_at, "theme script must come before the stylesheet"


def test_the_toggle_is_on_every_page(shop):
    for path in ("/", "/invoices", "/customers", "/settings", "/inspections"):
        assert 'id="themetoggle"' in shop.get(path).text, path


def test_the_toggle_says_what_it_is_for(shop):
    """An unlabelled icon button is a guess for anyone not using a mouse."""
    page = shop.get("/").text
    button = page[page.index('class="themetoggle"'):]
    button = button[:button.index("</button>")]
    assert "aria-label=" in button and "title=" in button


def test_printing_is_not_affected_by_the_screen_theme(shop):
    """A charcoal page costs a cartridge and cannot be photocopied."""
    css = shop.get("/static/css/app.css").text
    block = css[css.index("@media print"):]
    assert '[data-theme="dark"]' in block
    assert "--paper:        #ffffff" in block


def test_the_customer_documents_never_carry_the_theme(shop, conn):
    """The printed sheet is a standalone template and must stay that way."""
    for name in ("invoice_print.html", "estimate_print.html"):
        from pathlib import Path
        text = Path("app/templates", name).read_text()
        assert "extends" not in text, f"{name} must not inherit the app shell"
