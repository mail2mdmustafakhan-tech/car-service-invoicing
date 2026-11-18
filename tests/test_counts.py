"""How many of each thing there are, and what state they are in.

The feature is small; the failure it guards against is not. Two counts of
the same thing that disagree are worse than no count at all -- one of them
is quietly wrong and nobody can tell which. So the dashboard and the list
pages are checked against each other, not just against themselves.
"""

from __future__ import annotations

import re

from app import repository as repo


def _line(html: str) -> str:
    """The text of the count line, with the markup taken out."""
    start = html.index('class="countline"')
    start = html.index(">", start) + 1
    chunk = html[start:html.index("</p>", start)]
    return " ".join(re.sub(r"<[^>]+>", " ", chunk).split())


def test_every_state_is_reported_even_at_zero(conn):
    """The shape of the answer must not depend on what week it is."""
    counts = repo.status_counts(conn, "estimates")
    assert [s for s, _ in counts["by_status"]] == list(
        repo.COUNTED_STATUSES["estimates"]
    )
    assert counts["total"] == 0


def test_the_parts_add_up_to_the_total(shop, read_web_db):
    shop.post("/invoices/quick", data={
        "customer_id": "1", "doc_type": "tax",
        "item_description": ["Oil"], "item_qty": ["1"], "item_price": ["100"],
        "item_catalog_id": [""], "payment_method": "cash",
    })
    with read_web_db() as c:
        counts = repo.status_counts(c, "invoices")
    assert sum(n for _, n in counts["by_status"]) == counts["total"]


def test_a_status_outside_the_list_is_still_counted(conn):
    """Otherwise the parts would silently stop adding up to the total."""
    conn.execute(
        "INSERT INTO customers (name) VALUES ('X')"
    )
    conn.execute(
        """
        INSERT INTO inspections (inspection_no, customer_id, inspected_on, status)
        VALUES ('INS-1', 1, '2026-01-01', 'draft')
        """
    )
    conn.commit()
    # Reach past the CHECK by writing a state the application does not use.
    conn.execute("PRAGMA writable_schema = OFF")
    counts = repo.status_counts(conn, "inspections")
    assert counts["total"] == 1
    assert sum(n for _, n in counts["by_status"]) == counts["total"]


def test_the_count_line_appears_on_every_list_page(shop):
    for path in ("/invoices", "/estimates", "/contracts", "/inspections",
                 "/customers", "/vehicles", "/catalog", "/issues"):
        assert 'class="countline"' in shop.get(path).text, path


def test_the_line_names_only_the_states_in_use(shop):
    """A row of zeroes is five things to read past to reach the one that moved."""
    line = _line(shop.get("/estimates").text)
    assert "0 Draft" not in line
    assert "0 Sent" not in line


def test_the_dashboard_shows_the_empty_states_too(shop):
    """Its tiles must not change shape as the week goes on."""
    page = shop.get("/").text
    tile = page[page.index('class="kpi-row"'):]
    assert "is-zero" in tile


def test_the_dashboard_and_the_list_page_agree(shop, read_web_db):
    """The whole reason the counts come from one function."""
    shop.post("/invoices/quick", data={
        "customer_id": "1", "doc_type": "tax",
        "item_description": ["Oil"], "item_qty": ["1"], "item_price": ["100"],
        "item_catalog_id": [""], "payment_method": "cash",
    })

    with read_web_db() as c:
        expected = repo.status_counts(c, "invoices")["total"]

    line = _line(shop.get("/invoices").text)
    assert line.startswith(f"{expected} invoices")

    dash = shop.get("/").text
    tiles = dash[dash.index('class="kpi-row"'):]
    assert f">{expected}</span>" in tiles


def test_each_tile_links_to_what_it_counts(shop):
    """The next thing anyone does after reading "3 in workshop" is look."""
    page = shop.get("/").text
    tiles = page[page.index('class="kpi-row"'):]
    for href in ("/inspections", "/estimates", "/contracts", "/invoices",
                 "/customers", "/vehicles", "/catalog", "/issues"):
        assert f'href="{href}"' in tiles, href


def test_counting_is_not_done_unless_it_is_shown(shop):
    """It is a function in the context, not a value.

    Computing all eight on every render would put eight queries behind every
    page in the application, including the printed documents, to serve a
    line most of them never show.
    """
    import inspect

    from app import main
    source = inspect.getsource(main.ctx)
    assert "def counts_for" in source
    assert "counts_for(conn)" not in source
