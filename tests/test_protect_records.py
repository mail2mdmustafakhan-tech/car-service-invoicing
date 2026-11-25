"""The switch that stops the application deleting records.

Off by default, because the register is still being imported and tidied
up and removing a mistyped row is the right thing to do during that. On
afterwards, when a deleted customer is a customer whose history is gone.

What makes these tests worth their weight is that the failure mode is
silent and permanent: a delete that still deletes while the switch reads
"on" destroys exactly the records the switch was turned on to protect,
and nothing in the interface would say so.
"""

from __future__ import annotations


def _protect(client, on: bool = True) -> None:
    client.post("/settings/protect-records",
                data={"protect_records": "1"} if on else {})


def _invoice_payload(status: str = "issued", **overrides):
    payload = {
        "customer_id": "1",
        "vehicle_id": "1",
        "issue_date": "2026-11-11",
        "vat_rate": "15",
        "status": status,
        "item_catalog_id": ["1"],
        "item_description": ["Oil change"],
        "item_description_ar": ["تغيير زيت"],
        "item_kind": ["service"],
        "item_unit": ["pcs"],
        "item_qty": ["1"],
        "item_price": ["150"],
    }
    payload.update(overrides)
    return payload


def _row(read_web_db, table: str, row_id: int):
    with read_web_db() as c:
        return c.execute(f"SELECT * FROM {table} WHERE id = ?", (row_id,)).fetchone()


# --- the default ------------------------------------------------------------


def test_it_is_off_to_begin_with(client, read_web_db):
    """Turned on by default it would get in the way of the cleanup, and a
    setting somebody fights with on day one is a setting they switch off
    and never reconsider."""
    client.get("/settings")
    with read_web_db() as c:
        row = c.execute("SELECT protect_records FROM settings WHERE id = 1").fetchone()
    assert row["protect_records"] == 0


def test_it_can_be_turned_on_and_off_again(shop, read_web_db):
    _protect(shop, True)
    with read_web_db() as c:
        assert c.execute("SELECT protect_records FROM settings").fetchone()[0] == 1

    _protect(shop, False)
    with read_web_db() as c:
        assert c.execute("SELECT protect_records FROM settings").fetchone()[0] == 0


def test_the_switch_takes_effect_without_a_restart(shop, read_web_db):
    """Somebody will turn it on and immediately go and test it.

    Read once at startup instead, the first thing they tried would delete
    the record and they would conclude the setting does not work.
    """
    _protect(shop, True)
    shop.post("/customers/1/delete")

    assert _row(read_web_db, "customers", 1) is not None


# --- customers --------------------------------------------------------------


def test_a_customer_is_kept_and_marked_inactive(shop, read_web_db):
    _protect(shop, True)
    shop.post("/customers/1/delete")

    assert _row(read_web_db, "customers", 1)["is_active"] == 0


def test_an_inactive_customer_drops_out_of_the_list(shop):
    """The point of inactive: gone from view, present in the history."""
    _protect(shop, True)
    shop.post("/customers/1/delete")

    assert "Test Customer" not in shop.get("/customers").text


def test_without_the_switch_a_customer_is_still_deleted(shop, read_web_db):
    """The old behaviour has to survive, because it is what he needs while
    the register is being cleaned up."""
    shop.post("/customers/1/delete")

    assert _row(read_web_db, "customers", 1) is None


# --- vehicles ---------------------------------------------------------------


def test_a_vehicle_is_kept_and_marked_inactive(shop, read_web_db):
    _protect(shop, True)
    shop.post("/vehicles/1/delete")

    assert _row(read_web_db, "vehicles", 1)["is_active"] == 0


def test_a_retired_vehicles_history_is_still_there(shop, read_web_db):
    """A vehicle is retired, not deleted, precisely so this still works:
    the invoices raised against it stay attached to it."""
    shop.post("/invoices/new", data=_invoice_payload())
    _protect(shop, True)
    shop.post("/vehicles/1/delete")

    with read_web_db() as c:
        kept = c.execute(
            "SELECT COUNT(*) FROM invoices WHERE vehicle_id = 1").fetchone()[0]
    assert kept == 1
    assert "T-" in shop.get("/vehicles/1").text  # the history still renders


# --- invoices ---------------------------------------------------------------


def test_a_draft_invoice_is_voided_rather_than_deleted(shop, read_web_db):
    """The one real gap: an issued invoice already could not be deleted,
    but a draft vanished completely."""
    shop.post("/invoices/new", data=_invoice_payload(status="draft"))
    _protect(shop, True)
    shop.post("/invoices/1/delete")

    assert _row(read_web_db, "invoices", 1)["status"] == "void"


def test_a_voided_invoice_is_out_of_the_money(shop, read_web_db):
    """Kept but counted would be worse than deleted.

    Every total in the application filters on status = 'issued', so this
    asserts the thing that would actually go wrong: a voided invoice
    inflating what the workshop thinks it has earned.
    """
    shop.post("/invoices/new", data=_invoice_payload(status="draft"))
    _protect(shop, True)
    shop.post("/invoices/1/delete")

    with read_web_db() as c:
        counted = c.execute(
            "SELECT COALESCE(SUM(total_minor), 0) FROM invoices "
            "WHERE status = 'issued'").fetchone()[0]
    assert counted == 0


def test_without_the_switch_a_draft_is_still_deleted(shop, read_web_db):
    shop.post("/invoices/new", data=_invoice_payload(status="draft"))
    shop.post("/invoices/1/delete")

    assert _row(read_web_db, "invoices", 1) is None


def test_an_issued_invoice_was_never_deletable_either_way(shop, read_web_db):
    """True before this change and after it. Worth pinning: it is the
    guarantee the whole numbering scheme rests on."""
    shop.post("/invoices/new", data=_invoice_payload(status="issued"))
    shop.post("/invoices/1/delete")
    assert _row(read_web_db, "invoices", 1) is not None

    _protect(shop, True)
    shop.post("/invoices/1/delete")
    assert _row(read_web_db, "invoices", 1) is not None


# --- the interface ----------------------------------------------------------


def test_the_button_says_what_it_will_do(shop):
    """A button labelled Delete that does not delete is worse than either
    behaviour on its own."""
    _protect(shop, True)
    page = shop.get("/customers/1").text
    assert "Make inactive" in page
    assert ">Delete<" not in page

    _protect(shop, False)
    assert "Make inactive" not in shop.get("/customers/1").text


def test_a_stale_page_still_gets_the_safe_behaviour(shop, read_web_db):
    """Somebody with the page already open when the switch is flipped.

    Their button still says Delete. The route decides, not the label, so
    what they get is the protection -- the direction a stale page should
    always fail in.
    """
    assert "Make inactive" not in shop.get("/customers/1").text

    _protect(shop, True)
    shop.post("/customers/1/delete")

    assert _row(read_web_db, "customers", 1)["is_active"] == 0


def test_settings_offers_the_switch(client):
    assert "/settings/protect-records" in client.get("/settings").text


def test_the_switch_survives_an_upgrade_of_an_existing_database(tmp_path):
    """The migration adds a column to a table that already has rows.

    Every migration so far has had to be tested this way rather than on an
    empty database, because that is the only path his actual data takes.
    """
    import sqlite3

    from app.db import init_db

    path = tmp_path / "old.db"
    first = init_db(path)
    first.execute("UPDATE settings SET business_name_en = 'Advance Repair'")
    first.commit()
    # Pretend 017 never ran, as it had not on his copy.
    first.execute("ALTER TABLE settings DROP COLUMN protect_records")
    first.execute("DELETE FROM schema_migrations WHERE filename LIKE '017%'")
    first.commit()
    first.close()

    again = init_db(path)
    row = again.execute("SELECT * FROM settings WHERE id = 1").fetchone()
    assert row["protect_records"] == 0  # the new column, defaulted
    assert row["business_name_en"] == "Advance Repair"  # the old data, intact
    again.close()

    assert sqlite3.connect(path).execute(
        "SELECT COUNT(*) FROM schema_migrations WHERE filename LIKE '017%'"
    ).fetchone()[0] == 1
