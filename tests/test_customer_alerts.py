"""Warnings on a customer's file.

The register marks some customers "do not receive this car". That decision
is worth nothing unless it reaches whoever is booking the car in, at the
moment they pick the name. So most of these tests are about the warning
being *present at the point of choosing*, not about it being stored
correctly -- storing it correctly and never showing it is the failure that
matters here.
"""

from __future__ import annotations

import re

import pytest

from app import repository as repo

PICKERS = (
    "/estimates/new",
    "/contracts/new",
    "/inspections/new",
    "/invoices/new",
    "/invoices/quick",
    "/vehicles/new",
)


def _flag(conn, customer_id=1, level="refuse", note="PLEASE DO NOT RECEIVE THIS CAR"):
    repo.set_customer_alert(conn, customer_id, level=level, note=note)


@pytest.fixture()
def customer(conn):
    """A customer to hang a warning on. `conn` starts empty."""
    return repo.create_customer(conn, {"name": "Test Customer", "phone": "0500000000"})


def _flag_via_web(shop, level, note, customer_id=1):
    """Set the warning the way the office does: through the form.

    Writing it straight into the database would skip the handler, which is
    one of the places it could be dropped.
    """
    shop.post(f"/customers/{customer_id}/edit", data={
        "name": "Test Customer", "phone": "0500000000", "category": "regular",
        "alert_level": level, "alert_note": note, "is_active": "on",
    })


# --- storing it ------------------------------------------------------------

def test_a_warning_records_its_reason_and_its_date(conn, customer):
    _flag(conn)
    c = repo.get_customer(conn, 1)
    assert c["alert_level"] == "refuse"
    assert c["alert_note"] == "PLEASE DO NOT RECEIVE THIS CAR"
    assert c["alert_set_on"]


def test_lifting_a_warning_leaves_nothing_behind(conn, customer):
    """A reason still on file could be read as a warning still standing."""
    _flag(conn)
    repo.set_customer_alert(conn, 1, level="", note="")
    c = repo.get_customer(conn, 1)
    assert c["alert_level"] == ""
    assert c["alert_note"] == ""
    assert c["alert_set_on"] == ""


def test_an_invented_level_is_refused(conn, customer):
    with pytest.raises(ValueError):
        repo.set_customer_alert(conn, 1, level="probably-fine", note="")


def test_the_worst_come_first(conn, customer):
    """The reason anyone opens the list is to see the refusals."""
    repo.create_customer(conn, {"name": "B"})
    repo.create_customer(conn, {"name": "C"})
    repo.set_customer_alert(conn, 1, level="note", note="driver")
    repo.set_customer_alert(conn, 2, level="refuse", note="no")
    repo.set_customer_alert(conn, 3, level="check", note="ask")
    assert [c["alert_level"] for c in repo.list_flagged_customers(conn)] == [
        "refuse", "check", "note"
    ]


def test_the_counts_cover_every_level_even_at_zero(conn, customer):
    _flag(conn)
    counts = repo.alert_counts(conn)
    assert counts == {"refuse": 1, "check": 0, "note": 0, "total": 1}


# --- showing it where it matters ------------------------------------------

@pytest.mark.parametrize("path", PICKERS)
def test_the_warning_travels_with_the_customer_list(shop, path):
    """Every screen where a car can be booked in must carry it.

    This is the test that would have caught the warning being added to the
    estimate form and forgotten on the other five.
    """
    _flag_via_web(shop, "refuse", "DO NOT RECEIVE")
    page = shop.get(path).text
    assert 'data-alert-level="refuse"' in page, path
    assert "DO NOT RECEIVE" in page, path


@pytest.mark.parametrize("path", PICKERS)
def test_every_picker_can_actually_interrupt(shop, path):
    """The data is useless without the script and the dialog to show it."""
    page = shop.get(path).text
    assert 'id="customer-alert"' in page, path
    assert "customer-alert.js" in page, path


def test_an_unflagged_customer_carries_nothing(shop):
    """Several hundred options should not each carry four empty attributes."""
    page = shop.get("/estimates/new").text
    assert "data-alert-level" not in page


def test_the_customers_own_page_shows_it(shop):
    _flag_via_web(shop, "refuse", "DO NOT RECEIVE")
    page = shop.get("/customers/1").text
    assert "alert-panel" in page
    assert "DO NOT RECEIVE" in page


def test_a_refusal_is_announced_to_a_screen_reader(shop):
    """role=alert interrupts; role=status waits its turn. A refusal cannot."""
    _flag_via_web(shop, "refuse", "no")
    assert 'role="alert"' in shop.get("/customers/1").text

    _flag_via_web(shop, "note", "driver")
    assert 'role="status"' in shop.get("/customers/1").text


def test_the_list_marks_a_flagged_customer(shop):
    _flag_via_web(shop, "check", "ask first")
    page = shop.get("/customers").text
    assert "alert-dot-check" in page
    assert "ask first" in page


def test_the_dashboard_tile_appears_only_when_there_is_something_to_say(shop):
    """A tile reading "0 flagged" every day is a tile people stop seeing."""
    assert "kpi-flagged" not in shop.get("/").text

    _flag_via_web(shop, "refuse", "no")
    page = shop.get("/").text
    assert "kpi-flagged" in page
    assert 'href="/customers/flagged"' in page


def test_the_warning_list_gives_the_reason_not_just_the_name(shop):
    """A red heading says something is wrong without saying what to do."""
    _flag_via_web(shop, "refuse", "Unpaid since 2024")
    page = shop.get("/customers/flagged").text
    assert "Unpaid since 2024" in page


def test_flagged_is_not_read_as_a_customer_id(shop):
    assert shop.get("/customers/flagged").status_code == 200


# --- setting it through the form ------------------------------------------

def test_a_warning_can_be_set_on_the_customer_form(shop, read_web_db):
    shop.post("/customers/1/edit", data={
        "name": "Test", "phone": "0500000000", "category": "regular",
        "alert_level": "check", "alert_note": "Ask the manager first",
        "is_active": "on",
    })
    with read_web_db() as c:
        row = c.execute("SELECT alert_level, alert_note FROM customers WHERE id=1").fetchone()
    assert row["alert_level"] == "check"
    assert row["alert_note"] == "Ask the manager first"


def test_a_warning_can_be_set_when_the_customer_is_created(shop, read_web_db):
    shop.post("/customers/new", data={
        "name": "Walk-in", "phone": "0551111111", "category": "regular",
        "alert_level": "refuse", "alert_note": "Do not accept",
    })
    with read_web_db() as c:
        row = c.execute(
            "SELECT alert_level FROM customers WHERE name='Walk-in'"
        ).fetchone()
    assert row["alert_level"] == "refuse"


def test_the_customer_type_is_saved_when_they_are_created(shop, read_web_db):
    """It was accepted by the form and thrown away by the handler, so a
    customer added as VIP came back as regular."""
    shop.post("/customers/new", data={
        "name": "Sheikh Important", "phone": "0552222222", "category": "vip",
    })
    with read_web_db() as c:
        row = c.execute(
            "SELECT category FROM customers WHERE name='Sheikh Important'"
        ).fetchone()
    assert row["category"] == "vip"


def test_a_customer_type_added_in_settings_is_accepted(shop, read_web_db):
    """It used to be checked against a tuple written in the handler, so a
    type added on the one screen that offers it was silently refused."""
    shop.post("/settings/lists/add", data={
        "list_name": "customer_types", "value": "insurance",
        "label_en": "Insurance company",
    })
    shop.post("/customers/new", data={
        "name": "Tawuniya", "phone": "0553333333", "category": "insurance",
    })
    with read_web_db() as c:
        row = c.execute("SELECT category FROM customers WHERE name='Tawuniya'").fetchone()
    assert row["category"] == "insurance"


# --- the table rebuild that made the above possible ------------------------

def test_the_rebuild_kept_everything(shop, read_web_db):
    """Migration 012 drops and recreates `customers` to lose a CHECK.

    Dropping a table that six views select from and five tables reference is
    the sort of thing that works in an empty database and loses the lot in a
    full one, so this checks the result rather than the recipe.
    """
    shop.post("/invoices/new", data={
        "customer_id": "1", "doc_type": "tax", "invoice_date": "2026-01-01",
        "item_description": ["Service"], "item_qty": ["1"],
        "item_price": ["100"], "item_unit": ["pcs"], "item_kind": ["service"],
        "item_catalog_id": [""], "item_description_ar": [""],
    })

    with read_web_db() as c:
        assert c.execute("SELECT COUNT(*) n FROM customers").fetchone()["n"] >= 1
        # The invoice still finds its customer.
        joined = c.execute(
            "SELECT COUNT(*) n FROM invoices i JOIN customers c ON c.id = i.customer_id"
        ).fetchone()["n"]
        assert joined == c.execute("SELECT COUNT(*) n FROM invoices").fetchone()["n"]
        # Nothing dangling anywhere.
        assert c.execute("PRAGMA foreign_key_check").fetchall() == []
        # The views over customers still resolve.
        for view in ("v_invoices", "v_estimates", "v_repair_orders", "v_payments"):
            c.execute(f"SELECT COUNT(*) FROM {view}").fetchone()


def test_the_alert_level_is_still_constrained(read_web_db, shop):
    """The three levels are not configurable and are not meant to be.

    Each one means a different amount of interruption, written into the
    templates and the script. A fourth value would simply not be shown.
    """
    with read_web_db() as c:
        sql = c.execute(
            "SELECT sql FROM sqlite_master WHERE name = 'customers'"
        ).fetchone()["sql"]
    assert "alert_level IN" in sql
    assert "CHECK (category" not in sql


def test_a_self_managed_migration_is_recognised():
    """The marker has to match the file, or the rebuild silently runs
    inside a transaction with foreign keys still on."""
    from pathlib import Path

    from app import db

    script = Path("app/migrations/012_category_not_constrained.sql").read_text()
    assert db.SELF_MANAGED.search(script)
    # And an ordinary migration must not be treated that way.
    ordinary = Path("app/migrations/011_customer_alerts.sql").read_text()
    assert not db.SELF_MANAGED.search(ordinary)


# --- the nested form that broke every one of these screens -----------------

FORM_PAGES = (
    "/inspections/new",
    "/estimates/new",
    "/contracts/new",
    "/invoices/new",
    "/invoices/quick",
    "/vehicles/new",
    "/customers/new",
)


@pytest.mark.parametrize("path", FORM_PAGES)
def test_no_page_puts_a_form_inside_a_form(shop, path):
    """HTML does not allow it, and the browser does not complain.

    The warning dialog's close button was written the usual way, as
    <form method="dialog">, and the dialog sits beside the customer picker
    -- inside the page's own form. The parser quietly closed the outer form
    at the nested tag, so on the inspection screen the vehicle, the
    odometer, all eighteen checklist rows and the Save button ended up
    outside it. Save submitted nothing and the page just sat there. Every
    screen where a customer is picked was broken the same way.

    Counting <form> tags is the check that would have caught it in a second,
    which is why it is here rather than in a comment.
    """
    page = shop.get(path).text
    body = page[page.index("<body"):]
    opens = body.count("<form")
    closes = body.count("</form>")
    assert opens == closes, f"{path}: {opens} <form> vs {closes} </form>"

    # And no <form> may appear between another <form> and its </form>.
    depth = 0
    for token in re.findall(r"</?form", body):
        if token == "<form":
            depth += 1
            assert depth <= 1, f"{path}: a form is nested inside another form"
        else:
            depth -= 1


@pytest.mark.parametrize("path", FORM_PAGES)
def test_the_save_button_is_inside_the_form_it_saves(shop, path):
    """A submit button outside its form is a button that does nothing."""
    page = shop.get(path).text
    body = page[page.index("<body"):]
    last_open = body.rfind("<form")
    last_close = body.rfind("</form>")
    submit = body.rfind('type="submit"')
    assert submit != -1, f"{path}: no submit button at all"
    assert last_open < submit < last_close, (
        f"{path}: the submit button is outside the form"
    )
