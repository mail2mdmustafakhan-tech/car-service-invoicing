"""The check that happens before anyone quotes.

The point of this feature is the handover: what a technician found becomes
what the customer is asked to pay for, without anyone retyping it. Most of
these tests are about that handover being faithful, and about the things that
must not cross it.
"""

from __future__ import annotations

import pytest

from app import repository as repo


def _check_payload(**overrides):
    """A filled-in walk-round: mostly fine, one urgent finding priced up."""
    data = {
        "customer_id": "1",
        "vehicle_id": "1",
        "inspected_on": "2026-11-17",
        "odometer": "84000",
        "technician": "Rashid",
        "summary": "Brakes need doing now.",
        "notes": "",
        "status": "checked",
        "item_area": ["Brake pads — front", "Tyres", "Battery"],
        "item_area_ar": ["", "", ""],
        "item_condition": ["urgent", "attention", "ok"],
        "item_finding": ["Pads at 2mm", "4mm, plan to replace", ""],
        "item_finding_ar": ["", "", ""],
        "item_issue_id": ["", "", ""],
        "item_catalog_id": ["", "", ""],
        "item_qty": ["1", "4", "1"],
        "item_price": ["620", "", ""],
        "item_quote": ["1", "0", "0"],
    }
    data.update(overrides)
    return data


def test_a_check_records_what_was_fine_as_well_as_what_was_not(shop, read_web_db):
    """Half of a check is good news, and that is worth keeping.

    A row left blank is ambiguous forever after: not checked, or checked and
    fine? Every row carries an answer.
    """
    shop.post("/inspections/new", data=_check_payload())

    with read_web_db() as c:
        rows = c.execute(
            "SELECT area, condition FROM inspection_items ORDER BY line_no"
        ).fetchall()

    assert [r["condition"] for r in rows] == ["urgent", "attention", "ok"]
    assert rows[2]["area"] == "Battery"       # nothing wrong, still recorded


def test_the_standard_walk_round_is_offered_so_nobody_types_it(shop):
    page = shop.get("/inspections/new").text
    assert "Brake pads — front" in page
    assert "Fault code scan" in page
    assert page.count('name="item_area"') >= len(repo.DEFAULT_CHECKLIST)


def test_findings_marked_for_quoting_become_the_estimate(shop, read_web_db):
    """The handover. What the technician found is what the customer is quoted."""
    shop.post("/inspections/new", data=_check_payload())
    response = shop.post("/inspections/1/estimate", follow_redirects=False)
    assert response.status_code in (302, 303)

    with read_web_db() as c:
        lines = c.execute(
            "SELECT description, qty_milli, unit_price_minor FROM estimate_items"
        ).fetchall()

    assert len(lines) == 1
    assert lines[0]["description"] == "Pads at 2mm"
    assert lines[0]["unit_price_minor"] == 62000


def test_an_advisory_with_no_price_is_not_quoted_at_zero(shop, read_web_db):
    """A finding without a price is a note, not an offer to work for nothing."""
    shop.post("/inspections/new", data=_check_payload(
        item_quote=["1", "1", "0"],           # tyres ticked, but never priced
    ))
    shop.post("/inspections/1/estimate")

    with read_web_db() as c:
        descriptions = [r["description"] for r in
                        c.execute("SELECT description FROM estimate_items")]

    assert descriptions == ["Pads at 2mm"]


def test_the_summary_travels_to_the_estimate(shop, read_web_db):
    """What the customer was told in words should not have to be retyped."""
    shop.post("/inspections/new", data=_check_payload())
    shop.post("/inspections/1/estimate")

    with read_web_db() as c:
        notes = c.execute("SELECT notes FROM estimates WHERE id = 1").fetchone()["notes"]

    assert notes == "Brakes need doing now."


def test_the_estimate_arrives_as_a_draft(shop, read_web_db):
    """A check becoming a quote is not the same as a quote being sent."""
    shop.post("/inspections/new", data=_check_payload())
    shop.post("/inspections/1/estimate")

    with read_web_db() as c:
        status = c.execute("SELECT status FROM estimates WHERE id = 1").fetchone()["status"]

    assert status == "draft"


def test_a_check_cannot_be_quoted_twice(shop, read_web_db):
    """Two offers from one check is how a customer gets two prices for one job."""
    shop.post("/inspections/new", data=_check_payload())
    shop.post("/inspections/1/estimate")
    shop.post("/inspections/1/estimate")

    with read_web_db() as c:
        count = c.execute("SELECT COUNT(*) AS n FROM estimates").fetchone()["n"]

    assert count == 1


def test_a_quoted_check_is_closed_to_editing(shop):
    """The check is the record of what was found. The quote is the offer."""
    shop.post("/inspections/new", data=_check_payload())
    shop.post("/inspections/1/estimate")

    page = shop.get("/inspections/1").text
    assert "/inspections/1/edit" not in page

    # And the route itself refuses, not only the button.
    shop.post("/inspections/1/edit", data=_check_payload(technician="Someone else"))
    assert "Someone else" not in shop.get("/inspections/1").text


def test_the_quote_and_the_check_point_at_each_other(shop):
    shop.post("/inspections/new", data=_check_payload())
    shop.post("/inspections/1/estimate")
    assert "EST-" in shop.get("/inspections/1").text


def test_nothing_to_quote_is_refused_with_a_reason(shop, read_web_db):
    shop.post("/inspections/new", data=_check_payload(
        item_quote=["0", "0", "0"], item_price=["", "", ""],
    ))
    shop.post("/inspections/1/estimate")

    with read_web_db() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM estimates").fetchone()["n"] == 0


def test_the_quote_column_keeps_its_own_row(shop, read_web_db):
    """A checkbox would not submit when unticked and would shift the column."""
    shop.post("/inspections/new", data=_check_payload(
        item_price=["620", "400", "300"],
        item_quote=["0", "1", "0"],
    ))
    with read_web_db() as c:
        flags = [r["quote_it"] for r in
                 c.execute("SELECT quote_it FROM inspection_items ORDER BY line_no")]
    assert flags == [0, 1, 0]


@pytest.mark.parametrize("path", [
    "/inspections", "/inspections/new", "/inspections/1",
    "/inspections/1/edit", "/inspections/1/print",
])
def test_every_page_loads(shop, path):
    shop.post("/inspections/new", data=_check_payload())
    assert shop.get(path).status_code == 200


def test_the_printed_check_does_not_read_as_a_bill(shop):
    """It carries prices. It must not be mistaken for a demand for money."""
    shop.post("/inspections/new", data=_check_payload())
    page = shop.get("/inspections/1/print").text

    assert "not a bill" in page
    assert "VEHICLE CHECK" in page
    assert "TAX INVOICE" not in page
    assert "Amount due" not in page
