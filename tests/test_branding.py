"""The watermark in the margins and the marque ribbon along the bottom.

Both are decoration, and decoration in a ledger has one duty: to stay out of
the way of the figures. These tests are mostly about it staying out of the
way -- off the paper, behind the content, and never swallowing a click.
"""

from __future__ import annotations

from pathlib import Path


def test_the_ribbon_names_the_marques(shop):
    page = shop.get("/").text
    ribbon = page[page.index('class="marques"'):page.index("</ul>", page.index('class="marques"'))]
    for marque in ("BMW", "Mercedes-Benz", "Audi", "Porsche", "Rolls-Royce"):
        assert marque in ribbon, marque


def test_the_ribbon_follows_the_list_in_settings(shop, read_web_db):
    """It should say what the workshop works on, not what was true in 2026."""
    with read_web_db() as c:
        porsche = c.execute(
            "SELECT id FROM list_options WHERE list_name='marques' AND value='Porsche'"
        ).fetchone()["id"]

    shop.post(
        "/settings/lists/save",
        data={
            "list_name": "marques",
            "option_id": [str(porsche)],
            "label_en": ["Porsche"],
            "label_ar": ["بورشه"],
            "sort_order": ["70"],
            "active": ["0"],
        },
    )
    page = shop.get("/").text
    ribbon = page[page.index('class="marques"'):page.index("</ul>", page.index('class="marques"'))]
    assert "Porsche" not in ribbon
    assert "BMW" in ribbon


def test_a_new_marque_reaches_the_ribbon(shop):
    shop.post(
        "/settings/lists/add",
        data={"list_name": "marques", "value": "MINI", "label_en": "MINI"},
    )
    assert "MINI" in shop.get("/").text


def test_marques_are_separate_from_part_manufacturers(shop, read_web_db):
    """"Used market" is a real answer to who made a part. It is not a marque."""
    with read_web_db() as c:
        marques = {
            r["value"]
            for r in c.execute("SELECT value FROM list_options WHERE list_name='marques'")
        }
    assert "Used market" not in marques
    assert "Other" not in marques
    assert "BMW" in marques


def test_the_ribbon_is_on_every_page(shop):
    for path in ("/", "/invoices", "/customers", "/settings"):
        assert 'class="marques"' in shop.get(path).text, path


def test_the_ribbon_stays_off_the_customer_documents(shop):
    """The printed sheet is standalone; this is belt and braces."""
    css = Path("app/static/css/app.css").read_text()
    print_block = css[css.index("@media print"):]
    assert ".pagefoot" in print_block


def test_the_watermark_is_the_workshops_own_logo(shop, read_web_db):
    """Not a manufacturer's badge. Their marks are theirs."""
    from app import repository as repo

    # A real file, because the watermark now depends on what is inside one:
    # it is painted as a mask, so a logo with a solid background has no shape
    # to paint and is refused. The forty bytes of nonsense this used to
    # insert were refused for exactly that reason, and rightly.
    with read_web_db() as c:
        repo.set_logo(c, Path("branding/arc-logo-512.png").read_bytes(),
                      filename="arc-logo-512.png")
        c.commit()
    page = shop.get("/").text
    assert "--watermark: url('/logo" in page


def test_there_is_no_watermark_without_a_logo(shop):
    """An empty url() would be a broken image request on every page."""
    page = shop.get("/").text
    assert "--watermark" not in page


def test_the_watermark_cannot_swallow_a_click(shop):
    css = Path("app/static/css/app.css").read_text()
    # The block that actually draws it -- not the one-line print override,
    # which also starts "body::before".
    start = css.index("mask-image: var(--watermark)")
    block = css[css.rindex("body::before", 0, start):css.index("}", start)]
    assert "pointer-events: none" in block


def test_the_content_sits_above_the_watermark(shop):
    css = Path("app/static/css/app.css").read_text()
    start = css.index("\nmain.container {") + 1
    block = css[start:css.index("}", start)]
    # The properties, not their formatting: this test asserted the exact
    # one-line rule and broke the moment the rule gained a second property,
    # which told nobody anything about the watermark.
    assert "position: relative" in block
    assert "z-index: 1" in block


def test_no_manufacturer_logo_is_drawn_anywhere(shop):
    """The ribbon and watermark are names and the workshop's own roundel.

    Nothing in the templates should be drawing a marque's badge -- not as
    SVG, not as a fetched image file.
    """
    for template in Path("app/templates").glob("*.html"):
        text = template.read_text().lower()
        for marque in ("bmw", "mercedes", "audi", "porsche", "rolls"):
            for ext in (".svg", ".png", ".jpg", ".webp"):
                assert f"{marque}{ext}" not in text, f"{template.name}: {marque}{ext}"
                assert f"{marque}-logo{ext}" not in text, template.name
