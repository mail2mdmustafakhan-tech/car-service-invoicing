"""Sortable column headings.

The column to sort by arrives from the query string, which is to say from
anybody, so the first thing worth pinning is that it never reaches the SQL
as text. The rest is behaviour somebody notices immediately when it is
wrong: a filter dropped by a re-sort, an arrow pointing the wrong way, a
screen of blanks where the sorted values should be.
"""

from __future__ import annotations

import pytest

from app import repository as repo

LISTINGS = ("customers", "vehicles", "catalog", "issues")


# --- what reaches the database ---------------------------------------------

@pytest.mark.parametrize("listing", LISTINGS)
def test_an_unknown_column_falls_back_to_the_default(listing):
    sql, sort, direction = repo.order_clause(listing, "whatever", "asc")
    assert sort == next(iter(repo.SORTS[listing]))
    assert sql


@pytest.mark.parametrize("listing", LISTINGS)
def test_sql_is_never_built_from_the_query_string(listing):
    """A column name is a key into a map, never text pasted into ORDER BY."""
    nasty = "'; DROP TABLE customers; --"
    sql, sort, _ = repo.order_clause(listing, nasty, "asc")
    assert nasty not in sql
    assert sort in repo.SORTS[listing]


def test_the_injection_really_cannot_run(conn):
    """Belt and braces: ask the list for it and check the table survives."""
    repo.create_customer(conn, {"name": "Still here"})
    repo.list_customers(conn, sort="'; DROP TABLE customers; --", direction="x")
    assert conn.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"] == 1


def test_a_nonsense_direction_is_treated_as_ascending(listing="vehicles"):
    _, _, direction = repo.order_clause(listing, "plate", "sideways")
    assert direction == "asc"


def test_descending_applies_to_the_first_column_only():
    """"make, model DESC" would reverse the model within each make, which is
    not what anybody clicking a heading means."""
    sql, _, _ = repo.order_clause("vehicles", "make", "desc")
    assert sql.count("DESC") == 1
    assert sql.index("DESC") < sql.index("v.model")


# --- what the reader sees ---------------------------------------------------

def test_blanks_sort_last_whichever_way_the_list_runs(conn):
    """1,400 cars with no year would otherwise fill the first screen with
    dashes, and the click would look like it did nothing."""
    repo.create_customer(conn, {"name": "X"})
    for plate, year in (("A", 2019), ("B", None), ("C", 2005)):
        conn.execute(
            "INSERT INTO vehicles (customer_id, plate_no, make, model_year)"
            " VALUES (1, ?, 'BMW', ?)",
            (plate, year),
        )
    conn.commit()

    for direction in ("asc", "desc"):
        years = [r["model_year"] for r in repo.list_vehicles(conn, sort="year", direction=direction)]
        assert years[-1] is None, direction
        assert None not in years[:-1], direction


def test_sorting_actually_reorders(conn):
    repo.create_customer(conn, {"name": "Zoe"})
    repo.create_customer(conn, {"name": "Adam"})
    up = [c["name"] for c in repo.list_customers(conn, sort="name", direction="asc")]
    down = [c["name"] for c in repo.list_customers(conn, sort="name", direction="desc")]
    assert up == ["Adam", "Zoe"]
    assert down == ["Zoe", "Adam"]


# --- through the web --------------------------------------------------------

@pytest.mark.parametrize("path,column", [
    ("/customers", "name"),
    ("/vehicles", "plate"),
    ("/catalog", "name"),
    ("/issues", "make"),
])
def test_every_list_offers_sortable_headings(shop, path, column):
    page = shop.get(path).text
    assert f"sort={column}" in page


def test_the_arrow_marks_the_column_actually_in_use(shop):
    page = shop.get("/vehicles?sort=year&dir=desc").text
    assert 'aria-sort="descending"' in page
    assert page.count("sort-arrow") == 1, "an arrow on every heading says nothing"


def test_the_arrow_reflects_what_happened_not_what_was_asked(shop):
    """Asked for a column that does not exist, the list falls back -- and
    the heading has to show the fallback, not the request."""
    page = shop.get("/vehicles?sort=nonsense&dir=desc").text
    assert "aria-sort" in page
    assert 'href="?sort=plate' in page or "sort=plate" in page


def test_a_search_survives_a_re_sort(shop):
    """Re-sorting a filtered list must not quietly drop the filter."""
    page = shop.get("/vehicles?q=TEST").text
    assert "q=TEST" in page, "the headings dropped the search"


def test_an_empty_filter_does_not_break_the_page(shop):
    """A browser sends "&inactive=" for a box nobody ticked, and the
    headings generate the same. Declared as an int it answered 422 -- a
    blank page from a link the application wrote itself.
    """
    for path in ("/customers?q=&inactive=", "/vehicles?q=&inactive=",
                 "/catalog?q=&inactive="):
        assert shop.get(path).status_code == 200, path


def test_showing_inactive_still_works(shop, read_web_db):
    """The relaxed parameter must not have turned the filter off."""
    assert shop.get("/customers?inactive=1").status_code == 200
    assert shop.get("/customers?inactive=on").status_code == 200


def test_the_sort_direction_does_not_shadow_the_page_direction(shop):
    """It was called `dir` in the template, and so is the text direction.
    Every Arabic page rendered as <html dir="asc">."""
    shop.get("/lang/ar")
    page = shop.get("/vehicles?sort=year&dir=desc").text
    assert 'dir="rtl"' in page
    assert 'dir="asc"' not in page and 'dir="desc"' not in page


# --- a filter row on every list --------------------------------------------

FILTERED = ("/customers", "/vehicles", "/catalog", "/issues",
            "/invoices", "/estimates", "/contracts", "/inspections")


@pytest.mark.parametrize("path", FILTERED)
def test_every_list_has_a_filter_row(shop, path):
    """Inspections had none at all, and the two newer screens used different
    markup from the rest -- the same job looking like two different things
    on neighbouring pages."""
    page = shop.get(path).text
    assert 'class="toolbar"' in page or 'class="filterbar"' in page, path
    assert 'name="q"' in page, path


@pytest.mark.parametrize("path,query", [
    ("/customers", "q=zzz"),
    ("/vehicles", "q=zzz"),
    ("/catalog", "q=zzz"),
    ("/issues", "make=BMW"),
    ("/invoices", "status=draft"),
    ("/estimates", "status=draft"),
    ("/contracts", "status=open"),
    ("/inspections", "status=draft"),
])
def test_a_filtered_list_offers_a_way_out(shop, path, query):
    """Known faults filtered by make had no Clear, so the only way back to
    the full list was to edit the address."""
    page = shop.get(f"{path}?{query}").text
    assert ">Clear<" in page, f"{path}?{query}"


@pytest.mark.parametrize("path", FILTERED)
def test_an_unfiltered_list_does_not_offer_to_clear_nothing(shop, path):
    """A Clear button that does nothing teaches people to ignore the row."""
    assert ">Clear<" not in shop.get(path).text, path


def test_the_inspections_filter_actually_filters(shop, read_web_db):
    shop.post("/inspections/new", data={
        "customer_id": "1", "vehicle_id": "1", "inspected_on": "2026-01-10",
        "technician": "Imran",
        "item_area": ["Brakes"], "item_area_ar": [""], "item_condition": ["ok"],
        "item_finding": [""], "item_known_issue_id": [""], "item_catalog_id": [""],
        "item_qty": ["1"], "item_price": [""], "item_quote": ["0"],
    })
    with read_web_db() as c:
        name = c.execute("SELECT name FROM customers WHERE id = 1").fetchone()["name"]

    assert name in shop.get(f"/inspections?q={name[:6]}").text
    assert name not in shop.get("/inspections?q=zzzznothing").text
    assert name in shop.get("/inspections?status=draft").text
    assert name not in shop.get("/inspections?status=quoted").text
