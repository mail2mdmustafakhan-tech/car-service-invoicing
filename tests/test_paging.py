"""Paging, and the picker that replaced the ten-thousand-option dropdowns.

Both exist for the same reason: the application was built against a few
dozen records and then given a register of four thousand customers and six
thousand cars. Nothing was *wrong* at that size -- it was just all sent to
the browser at once. The vehicle list was 3.7 MB of HTML to show twenty rows,
and the invoice form was 1.7 MB of ``<option>`` tags.

The tests here are mostly about the ways paging goes quietly wrong rather
than loudly: a row that appears on two pages, a count that disagrees with the
rows beside it, a filter that survives to page 2 but a sort that does not.
"""

from __future__ import annotations

import pytest

from app import repository as repo

# ---------------------------------------------------------------------------
# Windows, counts, and the arithmetic of a pager
# ---------------------------------------------------------------------------

def _customers(conn, n):
    for i in range(n):
        repo.create_customer(conn, {"name": f"Customer {i:04d}", "phone": f"0500{i:06d}"})


def test_a_page_knows_what_it_is_a_page_of(conn):
    _customers(conn, 120)
    page = repo.page_customers(conn, per_page=50)

    assert len(page.rows) == 50
    assert page.total == 120
    assert page.pages == 3
    assert (page.first, page.last) == (1, 50)
    assert not page.has_prev
    assert page.has_next


def test_the_last_page_is_short_and_says_so(conn):
    _customers(conn, 120)
    page = repo.page_customers(conn, per_page=50, page=3)

    assert len(page.rows) == 20
    assert (page.first, page.last) == (101, 120)
    assert page.has_prev
    assert not page.has_next


def test_an_empty_listing_reports_nothing_rather_than_row_zero(conn):
    page = repo.page_customers(conn)
    assert (page.total, page.first, page.last, page.pages) == (0, 0, 0, 1)
    assert not page


@pytest.mark.parametrize("asked,expected", [(0, 1), (-5, 1), (99, 3), (2, 2)])
def test_a_page_number_out_of_range_lands_on_a_real_page(conn, asked, expected):
    """Not an error page. Somebody deletes rows while a pager is open, or
    edits the address bar; either way the answer is a page of customers."""
    _customers(conn, 120)
    assert repo.page_customers(conn, per_page=50, page=asked).number == expected


def test_the_count_is_the_filtered_count_not_the_whole_table(conn):
    """A pager reading "1-50 of 4,312" under a search for one name is worse
    than no pager: it describes a list that is not on the screen."""
    _customers(conn, 60)
    repo.create_customer(conn, {"name": "Findable Person"})

    page = repo.page_customers(conn, search="Findable")
    assert page.total == 1
    assert len(page.rows) == 1


# ---------------------------------------------------------------------------
# The quiet bug: ties
# ---------------------------------------------------------------------------

def test_no_row_appears_on_two_pages_when_the_sort_column_is_all_ties(conn):
    """Every column a list can be sorted by is non-unique, and a window taken
    over an order with ties is not well defined -- SQLite may return tied
    rows in one order for page 1 and another for page 2, so a row shows up
    twice while another never shows up at all. Every order therefore ends
    with the row's own id.

    Sorted by phone, where every customer's is empty, this is the worst case:
    the whole table is one tie.

    Worth knowing what this test is and is not: removing the tiebreaker does
    not make it fail. SQLite's sorter happens to leave tied rows in rowid
    order for a plan like this one, so the fault only shows when the plan
    changes -- a new index, a different filter, another release. The test
    below it, which reads the order clause itself, is the one that actually
    guards the rule. This one is here because it is the thing that goes wrong
    in front of a person, and because the day a plan change does break it,
    the failure will say so in those words.
    """
    for i in range(60):
        repo.create_customer(conn, {"name": f"Same {i:03d}"})

    seen: list[int] = []
    for number in (1, 2, 3):
        page = repo.page_customers(conn, sort="phone", per_page=25, page=number)
        seen.extend(row["id"] for row in page.rows)

    assert len(seen) == 60
    assert len(set(seen)) == 60, "a row was served on two different pages"


def test_every_listing_ends_its_order_with_something_unique(conn):
    for listing, column in (
        ("customers", "c.id"), ("vehicles", "v.id"), ("catalog", "id"), ("issues", "id"),
    ):
        for sort in repo.SORTS[listing]:
            for direction in ("asc", "desc"):
                order, _, _ = repo.order_clause(listing, sort, direction)
                assert order.split(", ")[-1] == column, (listing, sort, direction)


def test_descending_does_not_reverse_the_tiebreaker(conn):
    """The rule the headings behave by is "DESC applies to the first column
    only", and the id is not an exception to it."""
    order, _, _ = repo.order_clause("vehicles", "make", "desc")
    assert order.count("DESC") == 1


# ---------------------------------------------------------------------------
# What the page shows
# ---------------------------------------------------------------------------

LISTS = ("/customers", "/vehicles", "/catalog")
EMPTY = ("/invoices", "/estimates", "/contracts", "/inspections")


@pytest.mark.parametrize("path", LISTS)
def test_every_list_page_says_how_many_there_are(shop, path):
    assert "pager-count" in shop.get(path).text, path


@pytest.mark.parametrize("path", EMPTY)
def test_an_empty_list_says_it_is_empty_rather_than_showing_a_pager(shop, path):
    """"Showing 0-0 of 0" under a blank table tells somebody nothing they
    could not see. The empty state tells them what to do instead."""
    page = shop.get(path).text
    assert "pager-count" not in page, path
    assert "empty" in page, path


def test_a_short_list_gets_the_count_but_no_navigation(shop):
    """Previous/Next on a one-page list is furniture. The count stays: it is
    the proof that nothing is being hidden."""
    page = shop.get("/customers").text
    assert "pager-count" in page
    assert "pager-links" not in page


def test_a_long_list_is_paged_rather_than_truncated(shop, web_db):
    """Three of these lists used to carry a bare `LIMIT 500`, which is worse
    than slow: rows past the five hundredth were not there and nothing said
    so."""
    from app import db

    with db.session(web_db) as conn:
        _customers(conn, 120)

    first = shop.get("/customers").text
    assert "Customer 0000" in first
    assert "Customer 0119" not in first          # not on page 1
    assert "pager-links" in first

    last = shop.get("/customers?page=3").text
    assert "Customer 0119" in last


def test_the_pager_carries_the_filters_and_the_sort_to_the_next_page(shop, web_db):
    """A pager that drops them sends you to page 2 of a different list."""
    from app import db

    with db.session(web_db) as conn:
        for i in range(60):
            repo.create_vehicle(
                conn, {"customer_id": 1, "plate_no": f"BMW {i:03d}", "make": "BMW"}
            )

    page = shop.get("/vehicles?q=BMW&sort=make&dir=desc&page=1").text
    assert "pager-links" in page
    for fragment in ("q=BMW", "sort=make", "dir=desc", "page=2"):
        assert fragment in page, fragment


def test_page_is_not_in_the_link_twice(shop, web_db):
    """Built by dropping `page` from the query string and appending it once;
    appending blindly gave ?page=1&page=2, and which one wins is the
    framework's business rather than something to rely on."""
    from app import db

    with db.session(web_db) as conn:
        _customers(conn, 60)

    page = shop.get("/customers?page=1").text
    assert "page=1&page=" not in page
    assert shop.get("/customers?page=2").status_code == 200


# ---------------------------------------------------------------------------
# The picker
# ---------------------------------------------------------------------------

def test_the_forms_do_not_carry_every_customer(shop, web_db):
    from app import db

    with db.session(web_db) as conn:
        _customers(conn, 200)

    page = shop.get("/invoices/new").text
    assert page.count("<option") < 200, "the whole customer list is still in the page"
    assert "data-picker-search" in page, "and there is no way to reach the rest"


def test_the_chosen_customer_is_always_in_their_own_dropdown(conn):
    """An edit form whose customer is not among its own options clears the
    field on the first save -- "fix a typo" becomes "this invoice belongs to
    nobody". The oldest customer in the register is the test: they are
    nowhere near the recent fifty.
    """
    _customers(conn, 200)
    oldest = conn.execute("SELECT MIN(id) AS id FROM customers").fetchone()["id"]

    offered = repo.picker_customers(conn, oldest)
    assert offered[0]["id"] == oldest, "and first, where it can be seen"
    assert len(offered) <= repo.PICKER_LIMIT + 1


def test_the_short_list_is_the_most_recently_added(conn):
    """By id rather than by `created_at`: the timestamp has one-second
    resolution and the ARC import wrote two thousand customers inside one
    transaction, so they all share one. Ordering by it would pick fifty of
    those two thousand at random.
    """
    _customers(conn, 80)
    conn.execute("UPDATE customers SET created_at = '2026-01-01 00:00:00'")
    conn.commit()

    offered = [row["name"] for row in repo.picker_customers(conn)]
    assert offered[0] == "Customer 0079"
    assert "Customer 0000" not in offered


def test_picking_a_customer_that_no_longer_exists_is_not_a_crash(conn):
    _customers(conn, 5)
    assert len(repo.picker_customers(conn, 9999)) == 5


def test_the_search_endpoint_carries_the_alert_with_the_name(shop, web_db):
    """Choosing a flagged customer has to raise the warning at the moment of
    choosing, whether their name came from the page or from a search."""
    from app import db

    with db.session(web_db) as conn:
        cid = repo.create_customer(conn, {"name": "Refused Person"})
        repo.set_customer_alert(conn, cid, level="refuse", note="Do not receive this car")

    found = shop.get("/api/customers?q=Refused").json()
    assert found[0]["alert_level"] == "refuse"
    assert found[0]["alert_note"] == "Do not receive this car"


def test_the_search_endpoint_cannot_be_asked_for_everything(shop, web_db):
    """The point of the endpoint is that the whole table never crosses the
    wire; a limit somebody can set to a million gives that back."""
    from app import db

    with db.session(web_db) as conn:
        _customers(conn, 300)

    assert len(shop.get("/api/customers?limit=100000").json()) <= 200


def test_the_vehicle_list_holds_one_customers_cars_and_nobody_elses(shop, web_db):
    """It used to hold every car in the database, hidden client-side."""
    from app import db

    with db.session(web_db) as conn:
        mine = repo.create_customer(conn, {"name": "Mine"})
        theirs = repo.create_customer(conn, {"name": "Theirs"})
        repo.create_vehicle(conn, {"customer_id": mine, "plate_no": "MINE 1"})
        repo.create_vehicle(conn, {"customer_id": theirs, "plate_no": "THEIRS 1"})

    page = shop.get(f"/invoices/new?customer_id={mine}").text
    assert "MINE 1" in page
    assert "THEIRS 1" not in page
