"""The whole job, from the car arriving to the money being paid.

Every other test file checks one thing in isolation. This one walks the
route a real job takes, in order, because the breakages that actually reach
the workshop have all been at the joins: a form that no longer submits, a
status that will not advance, a button that points at a route that moved.

It is written against the application's own screens rather than the
repository, so a template that stops rendering its form fails here. That is
deliberate: the bug that prompted this file was a nested `<form>` which left
the Save button attached to nothing, and no repository test could ever have
seen it.
"""

from __future__ import annotations

import re


def _flash(html: str) -> str:
    match = re.search(r'class="flash[^"]*">([^<]*)', html)
    return match.group(1).strip() if match else ""


def _id_from(location: str) -> int:
    return int(re.search(r"/(\d+)", location).group(1))


def test_a_job_runs_from_the_car_arriving_to_the_money_being_paid(shop, read_web_db):
    """Inspection, estimate, approval, invoice, issue, payment."""
    # --- the car is looked at -------------------------------------------
    created = shop.post(
        "/inspections/new",
        data={
            "customer_id": "1",
            "vehicle_id": "1",
            "inspected_on": "2026-01-10",
            "technician": "Imran",
            "item_area": ["Front brakes"],
            "item_area_ar": [""],
            "item_condition": ["urgent"],
            "item_finding": ["Discs scored"],
            "item_known_issue_id": [""],
            "item_catalog_id": [""],
            "item_qty": ["1"],
            "item_price": ["900"],
            "item_quote": ["1"],
        },
        follow_redirects=False,
    )
    assert created.status_code in (302, 303), _flash(created.text)
    inspection_id = _id_from(created.headers["location"])

    # --- which becomes a quote -------------------------------------------
    quoted = shop.post(
        f"/inspections/{inspection_id}/estimate", follow_redirects=False
    )
    assert quoted.status_code in (302, 303)
    estimate_id = _id_from(quoted.headers["location"])

    with read_web_db() as c:
        line = c.execute(
            "SELECT description, unit_price_minor FROM estimate_items"
            " WHERE estimate_id = ?",
            (estimate_id,),
        ).fetchone()
    assert line["description"] == "Discs scored"
    assert line["unit_price_minor"] == 90000

    # --- the customer agrees ---------------------------------------------
    shop.post(f"/estimates/{estimate_id}/status", data={"status": "approved"})
    with read_web_db() as c:
        assert c.execute(
            "SELECT status FROM estimates WHERE id = ?", (estimate_id,)
        ).fetchone()["status"] == "approved"

    # --- and is invoiced for it ------------------------------------------
    invoiced = shop.post(f"/estimates/{estimate_id}/invoice", follow_redirects=False)
    assert invoiced.status_code in (302, 303)
    invoice_id = _id_from(invoiced.headers["location"])

    with read_web_db() as c:
        invoice = c.execute(
            "SELECT status, total_minor FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()
    # A draft, never an issued one: invoicing work nobody has checked is how
    # arguments start.
    assert invoice["status"] == "draft"

    shop.post(f"/invoices/{invoice_id}/status", data={"status": "issued"})
    with read_web_db() as c:
        assert c.execute(
            "SELECT status FROM invoices WHERE id = ?", (invoice_id,)
        ).fetchone()["status"] == "issued"

    # --- and pays ---------------------------------------------------------
    shop.post(
        f"/invoices/{invoice_id}/payments",
        data={"amount": "100", "method": "cash", "paid_on": "2026-01-20"},
    )
    with read_web_db() as c:
        paid = c.execute(
            "SELECT COALESCE(SUM(amount_minor), 0) AS n FROM payments"
            " WHERE invoice_id = ?",
            (invoice_id,),
        ).fetchone()["n"]
    assert paid == 10000


def test_a_car_booked_in_becomes_an_invoice(shop, read_web_db):
    """The other way in: the contract, signed at the counter."""
    created = shop.post(
        "/contracts/new",
        data={
            "customer_id": "1",
            "vehicle_id": "1",
            "date_in": "2026-01-10",
            "item_description": ["Front brake overhaul"],
            "item_description_ar": [""],
            "item_expense": ["900"],
            "item_remarks": [""],
            "item_catalog_id": [""],
        },
        follow_redirects=False,
    )
    assert created.status_code in (302, 303), _flash(created.text)
    contract_id = _id_from(created.headers["location"])

    invoiced = shop.post(f"/contracts/{contract_id}/invoice", follow_redirects=False)
    assert invoiced.status_code in (302, 303)

    # The contract holds the link, not the invoice.
    with read_web_db() as c:
        first = c.execute(
            "SELECT invoice_id FROM repair_orders WHERE id = ?", (contract_id,)
        ).fetchone()["invoice_id"]
    assert first is not None

    # An invoiced contract freezes: converting twice would bill the job twice.
    again = shop.post(f"/contracts/{contract_id}/invoice", follow_redirects=True)
    with read_web_db() as c:
        still = c.execute(
            "SELECT invoice_id FROM repair_orders WHERE id = ?", (contract_id,)
        ).fetchone()["invoice_id"]
        total = c.execute("SELECT COUNT(*) AS n FROM invoices").fetchone()["n"]
    assert still == first, _flash(again.text)
    assert total == 1, "a second invoice was raised for the same contract"


def test_a_contract_with_no_work_on_it_is_refused_and_says_so(shop):
    """It used to look like nothing happening at all."""
    page = shop.post(
        "/contracts/new",
        data={"customer_id": "1", "date_in": "2026-01-10"},
    ).text
    assert "at least one repair" in _flash(page).lower()


def test_every_new_screen_renders_a_working_form(shop):
    """The cheapest possible guard against the whole page being broken.

    Each of these must answer, carry a form that posts back, and have its
    submit button inside that form. This is the shape of the failure that
    made Save do nothing on six screens at once.
    """
    for path in ("/customers/new", "/vehicles/new", "/catalog/new", "/issues/new",
                 "/estimates/new", "/invoices/new", "/invoices/quick",
                 "/contracts/new", "/inspections/new"):
        page = shop.get(path)
        assert page.status_code == 200, path
        body = page.text[page.text.index("<body"):]
        assert "<form" in body, path
        assert body.count("<form") == body.count("</form>"), path
        last_open = body.rfind("<form")
        last_close = body.rfind("</form>")
        assert last_open < body.rfind('type="submit"') < last_close, path
