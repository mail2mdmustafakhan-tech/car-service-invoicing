"""Tests for the database layer: what gets stored, and what is refused."""

from __future__ import annotations

import pytest

from app import repository as repo
from app.db import backup_to, migrate, pending_migrations

# --------------------------------------------------------------------------
# Migrations
# --------------------------------------------------------------------------

def test_migrations_are_applied_once(conn):
    assert pending_migrations(conn) == []
    assert migrate(conn) == []          # running again changes nothing


def test_settings_row_exists(conn):
    settings = repo.get_settings(conn)
    assert settings["id"] == 1
    assert settings["vat_rate_bp"] == 1500
    assert settings["currency_code"] == "SAR"


# --------------------------------------------------------------------------
# Invoice numbering
# --------------------------------------------------------------------------

def test_invoice_numbers_are_sequential_and_padded(conn):
    assert repo.reserve_invoice_no(conn) == "INV-00001"
    assert repo.reserve_invoice_no(conn) == "INV-00002"
    assert repo.reserve_invoice_no(conn) == "INV-00003"


def test_invoice_number_uses_the_configured_prefix_and_start(conn):
    repo.update_settings(conn, {"invoice_prefix": "AF-", "next_invoice_seq": 1041})
    assert repo.reserve_invoice_no(conn) == "AF-01041"
    assert repo.reserve_invoice_no(conn) == "AF-01042"


def test_invoice_numbers_are_never_reused(conn):
    numbers = {repo.reserve_invoice_no(conn) for _ in range(200)}
    assert len(numbers) == 200


# --------------------------------------------------------------------------
# Customers and vehicles
# --------------------------------------------------------------------------

@pytest.fixture()
def seeded(conn):
    customer_id = repo.create_customer(
        conn, {"name": "Ahmed", "name_ar": "أحمد", "phone": "0551234567"}
    )
    vehicle_id = repo.create_vehicle(
        conn,
        {"customer_id": customer_id, "plate_no": "ABC 1234", "make": "Toyota",
         "model": "Camry", "odometer": 80000},
    )
    item_id = repo.create_catalog_item(
        conn,
        {"name_en": "Oil change", "name_ar": "تغيير زيت", "kind": "service",
         "unit": "pcs", "unit_price_minor": 15000, "code": "OIL"},
    )
    return conn, customer_id, vehicle_id, item_id


def test_customer_round_trip(seeded):
    conn, customer_id, _, _ = seeded
    customer = repo.get_customer(conn, customer_id)
    assert customer["name"] == "Ahmed"
    assert customer["name_ar"] == "أحمد"     # Arabic survives storage intact
    assert customer["is_active"] == 1


def test_customer_search_matches_name_and_phone(seeded):
    conn, _, _, _ = seeded
    assert len(repo.list_customers(conn, search="Ahm")) == 1
    assert len(repo.list_customers(conn, search="أحمد")) == 1
    assert len(repo.list_customers(conn, search="0551")) == 1
    assert len(repo.list_customers(conn, search="nobody")) == 0


def test_inactive_customers_are_hidden_by_default(seeded):
    conn, customer_id, _, _ = seeded
    repo.update_customer(conn, customer_id, {"is_active": 0})
    assert repo.list_customers(conn) == []
    assert len(repo.list_customers(conn, include_inactive=True)) == 1


def test_missing_records_raise_not_found(conn):
    with pytest.raises(repo.NotFound):
        repo.get_customer(conn, 999)
    with pytest.raises(repo.NotFound):
        repo.get_invoice(conn, 999)


def test_deleting_a_customer_cascades_to_vehicles(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    repo.delete_customer(conn, customer_id)
    with pytest.raises(repo.NotFound):
        repo.get_vehicle(conn, vehicle_id)


# --------------------------------------------------------------------------
# Invoices
# --------------------------------------------------------------------------

def _make_invoice(conn, customer_id, vehicle_id, **overrides):
    header = {
        "customer_id": customer_id,
        "vehicle_id": vehicle_id,
        "issue_date": "2026-11-11",
        "status": "issued",
        "vat_rate_bp": 1500,
        "odometer": 84500,
    }
    header.update(overrides)
    items = [
        {"description": "Oil change", "kind": "service", "unit": "pcs",
         "qty_milli": 1000, "unit_price_minor": 18500},
        {"description": "Labour", "kind": "service", "unit": "hour",
         "qty_milli": 1500, "unit_price_minor": 9000},
    ]
    return repo.create_invoice(conn, header, items)


def test_invoice_totals_are_stored(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id)

    invoice = repo.get_invoice(conn, invoice_id)
    assert invoice["subtotal_minor"] == 32000    # 185.00 + 135.00
    assert invoice["vat_minor"] == 4800
    assert invoice["total_minor"] == 36800
    assert invoice["invoice_no"] == "INV-00001"


def test_line_numbers_are_assigned_in_order(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id)
    items = repo.get_invoice_items(conn, invoice_id)
    assert [i["line_no"] for i in items] == [1, 2]
    assert items[0]["line_total_minor"] == 18500
    assert items[1]["line_total_minor"] == 13500


def test_editing_an_invoice_replaces_lines_and_recomputes(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id)

    repo.update_invoice(
        conn,
        invoice_id,
        {"customer_id": customer_id, "vehicle_id": vehicle_id,
         "issue_date": "2026-11-11", "status": "issued", "vat_rate_bp": 1500,
         "discount_minor": 1000},
        [{"description": "Wash", "kind": "service", "unit": "pcs",
          "qty_milli": 1000, "unit_price_minor": 5000}],
    )

    invoice = repo.get_invoice(conn, invoice_id)
    assert len(repo.get_invoice_items(conn, invoice_id)) == 1
    assert invoice["subtotal_minor"] == 5000
    assert invoice["taxable_minor"] == 4000
    assert invoice["total_minor"] == 4600


def test_invoice_keeps_its_own_vat_rate_when_settings_change(seeded):
    """Re-printing last year's invoice must show last year's tax rate."""
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id, vat_rate_bp=500)

    repo.update_settings(conn, {"vat_rate_bp": 1500})

    invoice = repo.get_invoice(conn, invoice_id)
    assert invoice["vat_rate_bp"] == 500
    assert invoice["vat_minor"] == 1600


def test_line_description_is_copied_not_linked(seeded):
    """Changing a catalogue price must not rewrite invoices already issued."""
    conn, customer_id, vehicle_id, item_id = seeded
    invoice_id = repo.create_invoice(
        conn,
        {"customer_id": customer_id, "issue_date": "2026-11-11", "status": "issued",
         "vat_rate_bp": 1500},
        [{"catalog_item_id": item_id, "description": "Oil change", "kind": "service",
          "unit": "pcs", "qty_milli": 1000, "unit_price_minor": 15000}],
    )

    repo.update_catalog_item(conn, item_id, {"name_en": "Renamed", "unit_price_minor": 99900})

    item = repo.get_invoice_items(conn, invoice_id)[0]
    assert item["description"] == "Oil change"
    assert item["unit_price_minor"] == 15000
    assert repo.get_invoice(conn, invoice_id)["total_minor"] == 17250


def test_deleting_a_catalogue_item_leaves_the_invoice_intact(seeded):
    conn, customer_id, _, item_id = seeded
    invoice_id = repo.create_invoice(
        conn,
        {"customer_id": customer_id, "issue_date": "2026-11-11", "status": "issued",
         "vat_rate_bp": 1500},
        [{"catalog_item_id": item_id, "description": "Oil change", "kind": "service",
          "unit": "pcs", "qty_milli": 1000, "unit_price_minor": 15000}],
    )
    repo.delete_catalog_item(conn, item_id)

    item = repo.get_invoice_items(conn, invoice_id)[0]
    assert item["description"] == "Oil change"
    assert item["catalog_item_id"] is None


# --------------------------------------------------------------------------
# Guard rails
# --------------------------------------------------------------------------

def test_a_customer_with_invoices_cannot_be_deleted(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    _make_invoice(conn, customer_id, vehicle_id)
    with pytest.raises(repo.InUse):
        repo.delete_customer(conn, customer_id)


def test_a_vehicle_on_an_invoice_cannot_be_deleted(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    _make_invoice(conn, customer_id, vehicle_id)
    with pytest.raises(repo.InUse):
        repo.delete_vehicle(conn, vehicle_id)


def test_issued_invoices_cannot_be_deleted_only_voided(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id)

    with pytest.raises(repo.InUse):
        repo.delete_invoice(conn, invoice_id)

    repo.set_invoice_status(conn, invoice_id, "void")
    assert repo.get_invoice(conn, invoice_id)["status"] == "void"


def test_draft_invoices_can_be_deleted(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id, status="draft")
    repo.delete_invoice(conn, invoice_id)
    with pytest.raises(repo.NotFound):
        repo.get_invoice(conn, invoice_id)


def test_unknown_status_is_rejected(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id)
    with pytest.raises(ValueError):
        repo.set_invoice_status(conn, invoice_id, "cancelled")


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------

def test_payments_accumulate_and_set_the_state(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id)   # total 368.00

    repo.add_payment(conn, {"invoice_id": invoice_id, "amount_minor": 20000,
                            "method": "cash", "paid_on": "2026-11-11"})
    row = conn.execute("SELECT * FROM v_invoices WHERE id = ?", (invoice_id,)).fetchone()
    assert row["payment_state"] == "partially_paid"
    assert row["balance_due"] == pytest.approx(168.0)

    repo.add_payment(conn, {"invoice_id": invoice_id, "amount_minor": 16800,
                            "method": "card", "paid_on": "2026-11-12"})
    row = conn.execute("SELECT * FROM v_invoices WHERE id = ?", (invoice_id,)).fetchone()
    assert row["payment_state"] == "paid"
    assert row["balance_due"] == pytest.approx(0.0)


def test_deleting_a_payment_reopens_the_balance(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id)
    payment_id = repo.add_payment(
        conn, {"invoice_id": invoice_id, "amount_minor": 36800, "method": "cash",
               "paid_on": "2026-11-11"}
    )
    assert repo.delete_payment(conn, payment_id) == invoice_id

    row = conn.execute("SELECT * FROM v_invoices WHERE id = ?", (invoice_id,)).fetchone()
    assert row["payment_state"] == "unpaid"


def test_deleting_an_invoice_removes_its_payments(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id, status="draft")
    conn.execute(
        "INSERT INTO payments (invoice_id, paid_on, amount_minor) VALUES (?, ?, ?)",
        (invoice_id, "2026-11-11", 100),
    )
    conn.commit()
    repo.delete_invoice(conn, invoice_id)
    assert conn.execute("SELECT COUNT(*) AS n FROM payments").fetchone()["n"] == 0


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def test_dashboard_counts_only_issued_invoices(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    _make_invoice(conn, customer_id, vehicle_id, status="issued")
    _make_invoice(conn, customer_id, vehicle_id, status="draft")

    stats = repo.dashboard_stats(conn)
    assert stats["draft_count"] == 1
    assert stats["outstanding_count"] == 1
    assert stats["outstanding_minor"] == 36800
    assert stats["customer_count"] == 1


def test_customer_balance_reflects_payments(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    invoice_id = _make_invoice(conn, customer_id, vehicle_id)
    repo.add_payment(conn, {"invoice_id": invoice_id, "amount_minor": 10000,
                            "method": "cash", "paid_on": "2026-11-11"})

    customer = repo.list_customers(conn)[0]
    assert customer["balance_minor"] == 26800


def test_vehicle_history_is_newest_first(seeded):
    conn, customer_id, vehicle_id, _ = seeded
    _make_invoice(conn, customer_id, vehicle_id, issue_date="2026-01-05")
    _make_invoice(conn, customer_id, vehicle_id, issue_date="2026-11-11")

    history = repo.vehicle_history(conn, vehicle_id)
    assert [h["issue_date"] for h in history] == ["2026-11-11", "2026-01-05"]


def test_reporting_views_expose_readable_decimals(seeded):
    """The views exist so a BI tool can read the file without doing the maths."""
    conn, customer_id, vehicle_id, _ = seeded
    _make_invoice(conn, customer_id, vehicle_id)

    row = conn.execute("SELECT * FROM v_invoices").fetchone()
    assert row["total"] == pytest.approx(368.00)
    assert row["vat_rate_percent"] == pytest.approx(15.0)

    line = conn.execute(
        "SELECT * FROM v_invoice_lines ORDER BY line_no"
    ).fetchall()[1]
    assert line["qty"] == pytest.approx(1.5)
    assert line["line_total"] == pytest.approx(135.00)


# --------------------------------------------------------------------------
# Backup
# --------------------------------------------------------------------------

def test_backup_produces_a_readable_copy(seeded, tmp_path):
    conn, customer_id, vehicle_id, _ = seeded
    _make_invoice(conn, customer_id, vehicle_id)

    import sqlite3

    source = conn.execute("PRAGMA database_list").fetchone()["file"]
    target = backup_to(tmp_path / "backup.db", source)

    copy = sqlite3.connect(target)
    copy.row_factory = sqlite3.Row
    assert copy.execute("SELECT COUNT(*) AS n FROM invoices").fetchone()["n"] == 1
    copy.close()
