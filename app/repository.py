"""All database queries, in one file.

Every piece of SQL the application runs lives here. Nothing else in the
codebase touches the database directly. That is a deliberate choice: when you
need to know how something is stored, or change a query, there is exactly one
file to open -- and the web layer above stays readable because it reads like a
list of instructions rather than a pile of SQL.

There is no ORM. The tables are simple, the queries are plain SQL, and a
column name in a template matches a column name in ``001_initial.sql``.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterable, Mapping, Sequence
from datetime import date
from typing import Any

from .db import transaction
from .invoicing import compute_totals, line_total

Row = sqlite3.Row


class NotFound(LookupError):
    """Raised when a record that must exist does not."""


class InUse(RuntimeError):
    """Raised when deleting a record would break invoices that reference it."""


def _one(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> Row | None:
    return conn.execute(sql, params).fetchone()


def _all(conn: sqlite3.Connection, sql: str, params: Sequence[Any] = ()) -> list[Row]:
    return conn.execute(sql, params).fetchall()


def _require(row: Row | None, what: str) -> Row:
    if row is None:
        raise NotFound(f"{what} not found")
    return row


def _pick(data: Mapping[str, Any], fields: Iterable[str]) -> dict[str, Any]:
    """Keep only the named keys, so a stray form field can never reach the SQL."""
    return {f: data[f] for f in fields if f in data}


def _update(
    conn: sqlite3.Connection, table: str, record_id: int, values: Mapping[str, Any]
) -> None:
    """Build and run an UPDATE for the supplied columns only."""
    if not values:
        return
    sets = ", ".join(f"{col} = ?" for col in values)
    params = [*values.values(), record_id]
    conn.execute(
        f"UPDATE {table} SET {sets}, updated_at = datetime('now') WHERE id = ?", params
    )


# ==========================================================================
# Settings
# ==========================================================================

SETTINGS_FIELDS = (
    "business_name_en", "business_name_ar", "vat_number", "cr_number",
    "address_en", "address_ar", "phone", "email", "vat_rate_bp",
    "prices_include_vat", "currency_code", "invoice_prefix",
    "next_invoice_seq", "default_language", "invoice_footer_en",
    "invoice_footer_ar",
    # Added in migration 002, for the printed repair contract.
    "business_tagline_en", "business_tagline_ar",
    "contract_terms_en", "contract_terms_ar",
    "contract_authorization_en", "contract_authorization_ar",
    "contract_prefix", "next_contract_seq", "parts_markup_bp",
)


def get_settings(conn: sqlite3.Connection) -> Row:
    return _require(_one(conn, "SELECT * FROM settings WHERE id = 1"), "Settings")


def update_settings(conn: sqlite3.Connection, data: Mapping[str, Any]) -> None:
    values = _pick(data, SETTINGS_FIELDS)
    if not values:
        return
    sets = ", ".join(f"{col} = ?" for col in values)
    with transaction(conn):
        conn.execute(
            f"UPDATE settings SET {sets}, updated_at = datetime('now') WHERE id = 1",
            list(values.values()),
        )


def reserve_invoice_no(conn: sqlite3.Connection) -> str:
    """Take the next invoice number and bump the counter.

    The read and the increment happen in one ``UPDATE ... RETURNING`` so two
    invoices can never be handed the same number, even if the shop ends up
    running this on a shared machine later.
    """
    row = conn.execute(
        """
        UPDATE settings
           SET next_invoice_seq = next_invoice_seq + 1
         WHERE id = 1
        RETURNING invoice_prefix, next_invoice_seq - 1 AS seq
        """
    ).fetchone()
    return f"{row['invoice_prefix']}{row['seq']:05d}"


def reserve_contract_no(conn: sqlite3.Connection) -> str:
    """Take the next repair contract number and bump its counter.

    Contracts are numbered in their own series, separate from invoices: a car
    can be booked in and the job then abandoned, and the invoice numbering
    should not carry a gap where that happened.
    """
    row = conn.execute(
        """
        UPDATE settings
           SET next_contract_seq = next_contract_seq + 1
         WHERE id = 1
        RETURNING contract_prefix, next_contract_seq - 1 AS seq
        """
    ).fetchone()
    return f"{row['contract_prefix']}{row['seq']:05d}"


# ==========================================================================
# Customers
# ==========================================================================

CUSTOMER_FIELDS = (
    "name", "name_ar", "phone", "email", "address", "vat_number", "notes",
    "is_active",
)


def list_customers(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    include_inactive: bool = False,
    limit: int | None = None,
) -> list[Row]:
    """Customers with their vehicle count and outstanding balance."""
    where, params = ["1 = 1"], []
    if not include_inactive:
        where.append("c.is_active = 1")
    if search:
        where.append("(c.name LIKE ? OR c.name_ar LIKE ? OR c.phone LIKE ?)")
        like = f"%{search}%"
        params += [like, like, like]

    sql = f"""
        SELECT c.*,
               (SELECT COUNT(*) FROM vehicles v
                 WHERE v.customer_id = c.id AND v.is_active = 1) AS vehicle_count,
               MAX(0,
                   COALESCE((SELECT SUM(i.total_minor) FROM invoices i
                              WHERE i.customer_id = c.id AND i.status = 'issued'), 0)
                 - COALESCE((SELECT SUM(p.amount_minor) FROM payments p
                               JOIN invoices i ON i.id = p.invoice_id
                              WHERE i.customer_id = c.id AND i.status = 'issued'), 0)
               ) AS balance_minor
          FROM customers c
         WHERE {' AND '.join(where)}
         ORDER BY c.name COLLATE NOCASE
    """
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return _all(conn, sql, params)


def get_customer(conn: sqlite3.Connection, customer_id: int) -> Row:
    return _require(
        _one(conn, "SELECT * FROM customers WHERE id = ?", (customer_id,)), "Customer"
    )


def create_customer(conn: sqlite3.Connection, data: Mapping[str, Any]) -> int:
    values = _pick(data, CUSTOMER_FIELDS)
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    with transaction(conn):
        cur = conn.execute(
            f"INSERT INTO customers ({cols}) VALUES ({marks})", list(values.values())
        )
    return int(cur.lastrowid)


def update_customer(
    conn: sqlite3.Connection, customer_id: int, data: Mapping[str, Any]
) -> None:
    get_customer(conn, customer_id)
    with transaction(conn):
        _update(conn, "customers", customer_id, _pick(data, CUSTOMER_FIELDS))


def delete_customer(conn: sqlite3.Connection, customer_id: int) -> None:
    """Remove a customer, or refuse if they have invoices.

    Invoices are financial records, so a customer attached to one is never
    deleted. Deactivate them instead -- they drop out of the lists but their
    history stays intact.
    """
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM invoices WHERE customer_id = ?", (customer_id,)
    ).fetchone()["n"]
    if count:
        raise InUse(
            f"This customer has {count} invoice(s). "
            "Mark them inactive instead of deleting."
        )
    with transaction(conn):
        conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))


# ==========================================================================
# Vehicles
# ==========================================================================

VEHICLE_FIELDS = (
    "customer_id", "plate_no", "make", "model", "model_year", "vin", "colour",
    "odometer", "notes", "is_active",
)


def list_vehicles(
    conn: sqlite3.Connection,
    *,
    customer_id: int | None = None,
    search: str = "",
    include_inactive: bool = False,
) -> list[Row]:
    where, params = ["1 = 1"], []
    if customer_id is not None:
        where.append("v.customer_id = ?")
        params.append(customer_id)
    if not include_inactive:
        where.append("v.is_active = 1")
    if search:
        where.append("(v.plate_no LIKE ? OR v.make LIKE ? OR v.model LIKE ? OR v.vin LIKE ?)")
        like = f"%{search}%"
        params += [like, like, like, like]

    return _all(
        conn,
        f"""
        SELECT v.*, c.name AS customer_name,
               (SELECT COUNT(*) FROM invoices i WHERE i.vehicle_id = v.id) AS invoice_count
          FROM vehicles v
          JOIN customers c ON c.id = v.customer_id
         WHERE {' AND '.join(where)}
         ORDER BY v.plate_no COLLATE NOCASE
        """,
        params,
    )


def get_vehicle(conn: sqlite3.Connection, vehicle_id: int) -> Row:
    return _require(
        _one(
            conn,
            """
            SELECT v.*, c.name AS customer_name
              FROM vehicles v
              JOIN customers c ON c.id = v.customer_id
             WHERE v.id = ?
            """,
            (vehicle_id,),
        ),
        "Vehicle",
    )


def create_vehicle(conn: sqlite3.Connection, data: Mapping[str, Any]) -> int:
    values = _pick(data, VEHICLE_FIELDS)
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    with transaction(conn):
        cur = conn.execute(
            f"INSERT INTO vehicles ({cols}) VALUES ({marks})", list(values.values())
        )
    return int(cur.lastrowid)


def update_vehicle(
    conn: sqlite3.Connection, vehicle_id: int, data: Mapping[str, Any]
) -> None:
    get_vehicle(conn, vehicle_id)
    with transaction(conn):
        _update(conn, "vehicles", vehicle_id, _pick(data, VEHICLE_FIELDS))


def delete_vehicle(conn: sqlite3.Connection, vehicle_id: int) -> None:
    count = conn.execute(
        "SELECT COUNT(*) AS n FROM invoices WHERE vehicle_id = ?", (vehicle_id,)
    ).fetchone()["n"]
    if count:
        raise InUse(
            f"This vehicle appears on {count} invoice(s). "
            "Mark it inactive instead of deleting."
        )
    with transaction(conn):
        conn.execute("DELETE FROM vehicles WHERE id = ?", (vehicle_id,))


def vehicle_history(conn: sqlite3.Connection, vehicle_id: int) -> list[Row]:
    """Every invoice raised against one vehicle, newest first."""
    return _all(
        conn,
        """
        SELECT i.id, i.invoice_no, i.issue_date, i.odometer, i.status,
               i.total_minor, i.currency_code,
               COALESCE((SELECT SUM(p.amount_minor) FROM payments p
                          WHERE p.invoice_id = i.id), 0) AS paid_minor
          FROM invoices i
         WHERE i.vehicle_id = ?
         ORDER BY i.issue_date DESC, i.id DESC
        """,
        (vehicle_id,),
    )


# ==========================================================================
# Service and parts catalogue
# ==========================================================================

CATALOG_FIELDS = (
    "code", "name_en", "name_ar", "kind", "unit", "unit_price_minor", "is_active",
)


def list_catalog(
    conn: sqlite3.Connection,
    *,
    kind: str = "",
    search: str = "",
    include_inactive: bool = False,
) -> list[Row]:
    where, params = ["1 = 1"], []
    if kind:
        where.append("kind = ?")
        params.append(kind)
    if not include_inactive:
        where.append("is_active = 1")
    if search:
        where.append("(name_en LIKE ? OR name_ar LIKE ? OR code LIKE ?)")
        like = f"%{search}%"
        params += [like, like, like]

    return _all(
        conn,
        f"""
        SELECT * FROM catalog_items
         WHERE {' AND '.join(where)}
         ORDER BY kind, name_en COLLATE NOCASE
        """,
        params,
    )


def get_catalog_item(conn: sqlite3.Connection, item_id: int) -> Row:
    return _require(
        _one(conn, "SELECT * FROM catalog_items WHERE id = ?", (item_id,)),
        "Catalogue item",
    )


def create_catalog_item(conn: sqlite3.Connection, data: Mapping[str, Any]) -> int:
    values = _pick(data, CATALOG_FIELDS)
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    with transaction(conn):
        cur = conn.execute(
            f"INSERT INTO catalog_items ({cols}) VALUES ({marks})",
            list(values.values()),
        )
    return int(cur.lastrowid)


def update_catalog_item(
    conn: sqlite3.Connection, item_id: int, data: Mapping[str, Any]
) -> None:
    get_catalog_item(conn, item_id)
    with transaction(conn):
        _update(conn, "catalog_items", item_id, _pick(data, CATALOG_FIELDS))


def delete_catalog_item(conn: sqlite3.Connection, item_id: int) -> None:
    """Delete a catalogue entry.

    Invoice lines keep their own copy of the description and price, so
    removing a catalogue entry never alters a historic invoice -- the line just
    loses its link back to the catalogue.
    """
    with transaction(conn):
        conn.execute("DELETE FROM catalog_items WHERE id = ?", (item_id,))


# ==========================================================================
# Invoices
# ==========================================================================

INVOICE_HEADER_FIELDS = (
    "customer_id", "vehicle_id", "issue_date", "due_date", "odometer",
    "status", "vat_rate_bp", "prices_include_vat", "currency_code",
    "discount_minor", "notes",
)

ITEM_FIELDS = (
    "catalog_item_id", "description", "description_ar", "kind", "unit",
    "qty_milli", "unit_price_minor",
)


def list_invoices(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "",
    payment_state: str = "",
    customer_id: int | None = None,
    date_from: str = "",
    date_to: str = "",
    limit: int = 500,
) -> list[Row]:
    """Invoices from the reporting view, newest first."""
    where, params = ["1 = 1"], []
    if search:
        where.append(
            "(vi.invoice_no LIKE ? OR vi.customer_name LIKE ? OR vi.vehicle_plate LIKE ?)"
        )
        like = f"%{search}%"
        params += [like, like, like]
    if status:
        where.append("vi.status = ?")
        params.append(status)
    if payment_state:
        where.append("vi.payment_state = ?")
        params.append(payment_state)
    if customer_id is not None:
        where.append("vi.id IN (SELECT id FROM invoices WHERE customer_id = ?)")
        params.append(customer_id)
    if date_from:
        where.append("vi.issue_date >= ?")
        params.append(date_from)
    if date_to:
        where.append("vi.issue_date <= ?")
        params.append(date_to)

    params.append(limit)
    return _all(
        conn,
        f"""
        SELECT vi.*,
               i.total_minor,
               i.customer_id,
               i.vehicle_id,
               COALESCE((SELECT SUM(p.amount_minor) FROM payments p
                          WHERE p.invoice_id = i.id), 0) AS paid_minor
          FROM v_invoices vi
          JOIN invoices  i ON i.id = vi.id
         WHERE {' AND '.join(where)}
         ORDER BY vi.issue_date DESC, vi.id DESC
         LIMIT ?
        """,
        params,
    )


def get_invoice(conn: sqlite3.Connection, invoice_id: int) -> Row:
    """One invoice with its customer, vehicle, totals and amount paid."""
    return _require(
        _one(
            conn,
            """
            SELECT i.*,
                   c.name       AS customer_name,
                   c.name_ar    AS customer_name_ar,
                   c.phone      AS customer_phone,
                   c.email      AS customer_email,
                   c.address    AS customer_address,
                   c.vat_number AS customer_vat_number,
                   v.plate_no   AS vehicle_plate,
                   v.make       AS vehicle_make,
                   v.model      AS vehicle_model,
                   v.model_year AS vehicle_year,
                   v.vin        AS vehicle_vin,
                   v.colour     AS vehicle_colour,
                   COALESCE((SELECT SUM(p.amount_minor) FROM payments p
                              WHERE p.invoice_id = i.id), 0) AS paid_minor
              FROM invoices i
              JOIN customers c ON c.id = i.customer_id
         LEFT JOIN vehicles  v ON v.id = i.vehicle_id
             WHERE i.id = ?
            """,
            (invoice_id,),
        ),
        "Invoice",
    )


def get_invoice_items(conn: sqlite3.Connection, invoice_id: int) -> list[Row]:
    return _all(
        conn,
        "SELECT * FROM invoice_items WHERE invoice_id = ? ORDER BY line_no",
        (invoice_id,),
    )


def _write_items(
    conn: sqlite3.Connection, invoice_id: int, items: Sequence[Mapping[str, Any]]
) -> None:
    """Replace an invoice's lines wholesale.

    Editing an invoice deletes its lines and writes the submitted set back.
    Reconciling which line was added, changed or removed would add a lot of
    code for no benefit: an invoice has a handful of lines and the whole thing
    is rewritten inside one transaction.
    """
    conn.execute("DELETE FROM invoice_items WHERE invoice_id = ?", (invoice_id,))
    for line_no, raw in enumerate(items, start=1):
        values = _pick(raw, ITEM_FIELDS)
        values["invoice_id"] = invoice_id
        values["line_no"] = line_no
        values["line_total_minor"] = line_total(
            int(raw["qty_milli"]), int(raw["unit_price_minor"])
        )
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn.execute(
            f"INSERT INTO invoice_items ({cols}) VALUES ({marks})",
            list(values.values()),
        )


def _write_totals(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Recompute and store the invoice totals from its current lines."""
    header = _require(
        _one(
            conn,
            """
            SELECT vat_rate_bp, prices_include_vat, discount_minor
              FROM invoices WHERE id = ?
            """,
            (invoice_id,),
        ),
        "Invoice",
    )
    lines = _all(
        conn,
        "SELECT qty_milli, unit_price_minor FROM invoice_items WHERE invoice_id = ?",
        (invoice_id,),
    )
    totals = compute_totals(
        [(int(r["qty_milli"]), int(r["unit_price_minor"])) for r in lines],
        vat_rate_bp=int(header["vat_rate_bp"]),
        discount_minor=int(header["discount_minor"]),
        prices_include_vat=bool(header["prices_include_vat"]),
    )
    conn.execute(
        """
        UPDATE invoices
           SET subtotal_minor = ?, taxable_minor = ?, vat_minor = ?,
               total_minor = ?, updated_at = datetime('now')
         WHERE id = ?
        """,
        (
            totals.subtotal_minor,
            totals.taxable_minor,
            totals.vat_minor,
            totals.total_minor,
            invoice_id,
        ),
    )


def create_invoice(
    conn: sqlite3.Connection,
    header: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> int:
    """Create an invoice, its lines and its totals in one transaction."""
    values = _pick(header, INVOICE_HEADER_FIELDS)
    values.setdefault("issue_date", date.today().isoformat())
    with transaction(conn):
        values["invoice_no"] = reserve_invoice_no(conn)
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        cur = conn.execute(
            f"INSERT INTO invoices ({cols}) VALUES ({marks})", list(values.values())
        )
        invoice_id = int(cur.lastrowid)
        _write_items(conn, invoice_id, items)
        _write_totals(conn, invoice_id)
    return invoice_id


def update_invoice(
    conn: sqlite3.Connection,
    invoice_id: int,
    header: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> None:
    get_invoice(conn, invoice_id)
    with transaction(conn):
        _update(conn, "invoices", invoice_id, _pick(header, INVOICE_HEADER_FIELDS))
        _write_items(conn, invoice_id, items)
        _write_totals(conn, invoice_id)


def set_invoice_status(conn: sqlite3.Connection, invoice_id: int, status: str) -> None:
    if status not in {"draft", "issued", "void"}:
        raise ValueError(f"Unknown invoice status: {status}")
    get_invoice(conn, invoice_id)
    with transaction(conn):
        conn.execute(
            "UPDATE invoices SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, invoice_id),
        )


def delete_invoice(conn: sqlite3.Connection, invoice_id: int) -> None:
    """Delete a draft invoice.

    Once an invoice has been issued it is a financial record and is voided
    rather than deleted, so the number stays accounted for and the paper the
    customer holds still matches something in the system.
    """
    invoice = get_invoice(conn, invoice_id)
    if invoice["status"] != "draft":
        raise InUse(
            "Only draft invoices can be deleted. "
            "Void this invoice instead so the number stays on record."
        )
    with transaction(conn):
        conn.execute("DELETE FROM invoices WHERE id = ?", (invoice_id,))


# ==========================================================================
# Payments
# ==========================================================================

PAYMENT_FIELDS = ("invoice_id", "paid_on", "amount_minor", "method", "reference", "notes")


def list_payments(conn: sqlite3.Connection, invoice_id: int) -> list[Row]:
    return _all(
        conn,
        "SELECT * FROM payments WHERE invoice_id = ? ORDER BY paid_on, id",
        (invoice_id,),
    )


def recent_payments(conn: sqlite3.Connection, limit: int = 20) -> list[Row]:
    return _all(
        conn,
        "SELECT * FROM v_payments ORDER BY paid_on DESC, id DESC LIMIT ?",
        (limit,),
    )


def add_payment(conn: sqlite3.Connection, data: Mapping[str, Any]) -> int:
    values = _pick(data, PAYMENT_FIELDS)
    values.setdefault("paid_on", date.today().isoformat())
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    with transaction(conn):
        cur = conn.execute(
            f"INSERT INTO payments ({cols}) VALUES ({marks})", list(values.values())
        )
    return int(cur.lastrowid)


def delete_payment(conn: sqlite3.Connection, payment_id: int) -> int:
    """Remove a payment. Returns the invoice it belonged to."""
    row = _require(
        _one(conn, "SELECT invoice_id FROM payments WHERE id = ?", (payment_id,)),
        "Payment",
    )
    with transaction(conn):
        conn.execute("DELETE FROM payments WHERE id = ?", (payment_id,))
    return int(row["invoice_id"])


# ==========================================================================
# Repair contracts (job cards)
# ==========================================================================
# The contract is written when the car arrives and signed by the owner. It
# holds estimates and the technician's findings; the money owed only becomes
# real when it is converted into an invoice.

ORDER_HEADER_FIELDS = (
    "customer_id", "vehicle_id", "date_in", "expected_date_out", "odometer",
    "car_code", "status", "technician_name", "customer_signed", "signed_on",
    "damage_notes", "notes",
)

ORDER_ITEM_FIELDS = (
    "catalog_item_id", "description", "description_ar", "expense_minor",
    "technician_remarks",
)

ORDER_PART_FIELDS = (
    "catalog_item_id", "part_number", "description", "description_ar",
    "qty_milli", "unit_price_minor", "sourced_externally",
)


def list_repair_orders(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "",
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    limit: int = 500,
) -> list[Row]:
    where, params = ["1 = 1"], []
    if search:
        where.append(
            "(ro.contract_no LIKE ? OR ro.customer_name LIKE ? OR ro.vehicle_plate LIKE ?)"
        )
        like = f"%{search}%"
        params += [like, like, like]
    if status:
        where.append("ro.status = ?")
        params.append(status)
    if customer_id is not None:
        where.append("o.customer_id = ?")
        params.append(customer_id)
    if vehicle_id is not None:
        where.append("o.vehicle_id = ?")
        params.append(vehicle_id)

    params.append(limit)
    return _all(
        conn,
        f"""
        SELECT ro.*, o.customer_id, o.vehicle_id, o.invoice_id
          FROM v_repair_orders ro
          JOIN repair_orders   o ON o.id = ro.id
         WHERE {' AND '.join(where)}
         ORDER BY ro.date_in DESC, ro.id DESC
         LIMIT ?
        """,
        params,
    )


def get_repair_order(conn: sqlite3.Connection, order_id: int) -> Row:
    return _require(
        _one(
            conn,
            """
            SELECT o.*,
                   c.name       AS customer_name,
                   c.name_ar    AS customer_name_ar,
                   c.phone      AS customer_phone,
                   c.email      AS customer_email,
                   c.address    AS customer_address,
                   c.vat_number AS customer_vat_number,
                   v.plate_no   AS vehicle_plate,
                   v.make       AS vehicle_make,
                   v.model      AS vehicle_model,
                   v.model_year AS vehicle_year,
                   v.vin        AS vehicle_vin,
                   v.colour     AS vehicle_colour,
                   i.invoice_no AS invoice_no
              FROM repair_orders o
              JOIN customers c ON c.id = o.customer_id
         LEFT JOIN vehicles  v ON v.id = o.vehicle_id
         LEFT JOIN invoices  i ON i.id = o.invoice_id
             WHERE o.id = ?
            """,
            (order_id,),
        ),
        "Repair contract",
    )


def get_order_items(conn: sqlite3.Connection, order_id: int) -> list[Row]:
    return _all(
        conn,
        "SELECT * FROM repair_order_items WHERE repair_order_id = ? ORDER BY line_no",
        (order_id,),
    )


def get_order_parts(conn: sqlite3.Connection, order_id: int) -> list[Row]:
    return _all(
        conn,
        "SELECT * FROM repair_order_parts WHERE repair_order_id = ? ORDER BY line_no",
        (order_id,),
    )


def order_totals(conn: sqlite3.Connection, order_id: int) -> dict[str, int]:
    """Estimated labour, parts and combined total for a contract, in minor units.

    These are estimates written on the contract, not amounts owed. Nothing is
    due until the contract becomes an invoice.
    """
    labour = conn.execute(
        "SELECT COALESCE(SUM(expense_minor), 0) AS t FROM repair_order_items WHERE repair_order_id = ?",
        (order_id,),
    ).fetchone()["t"]
    parts = conn.execute(
        "SELECT COALESCE(SUM(line_total_minor), 0) AS t FROM repair_order_parts WHERE repair_order_id = ?",
        (order_id,),
    ).fetchone()["t"]
    return {
        "labour_minor": labour,
        "parts_minor": parts,
        "total_minor": labour + parts,
    }


def _write_order_items(
    conn: sqlite3.Connection, order_id: int, items: Sequence[Mapping[str, Any]]
) -> None:
    conn.execute(
        "DELETE FROM repair_order_items WHERE repair_order_id = ?", (order_id,)
    )
    for line_no, raw in enumerate(items, start=1):
        values = _pick(raw, ORDER_ITEM_FIELDS)
        values["repair_order_id"] = order_id
        values["line_no"] = line_no
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn.execute(
            f"INSERT INTO repair_order_items ({cols}) VALUES ({marks})",
            list(values.values()),
        )


def _write_order_parts(
    conn: sqlite3.Connection, order_id: int, parts: Sequence[Mapping[str, Any]]
) -> None:
    conn.execute(
        "DELETE FROM repair_order_parts WHERE repair_order_id = ?", (order_id,)
    )
    for line_no, raw in enumerate(parts, start=1):
        values = _pick(raw, ORDER_PART_FIELDS)
        values["repair_order_id"] = order_id
        values["line_no"] = line_no
        values["line_total_minor"] = line_total(
            int(raw["qty_milli"]), int(raw["unit_price_minor"])
        )
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn.execute(
            f"INSERT INTO repair_order_parts ({cols}) VALUES ({marks})",
            list(values.values()),
        )


def create_repair_order(
    conn: sqlite3.Connection,
    header: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]] = (),
    parts: Sequence[Mapping[str, Any]] = (),
) -> int:
    values = _pick(header, ORDER_HEADER_FIELDS)
    values.setdefault("date_in", date.today().isoformat())
    with transaction(conn):
        values["contract_no"] = reserve_contract_no(conn)
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        cur = conn.execute(
            f"INSERT INTO repair_orders ({cols}) VALUES ({marks})",
            list(values.values()),
        )
        order_id = int(cur.lastrowid)
        _write_order_items(conn, order_id, items)
        _write_order_parts(conn, order_id, parts)
    return order_id


def update_repair_order(
    conn: sqlite3.Connection,
    order_id: int,
    header: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]] = (),
    parts: Sequence[Mapping[str, Any]] = (),
) -> None:
    order = get_repair_order(conn, order_id)
    if order["invoice_id"] is not None:
        raise InUse(
            f"This contract has already been invoiced as {order['invoice_no']}. "
            "Edit that invoice instead."
        )
    with transaction(conn):
        _update(conn, "repair_orders", order_id, _pick(header, ORDER_HEADER_FIELDS))
        _write_order_items(conn, order_id, items)
        _write_order_parts(conn, order_id, parts)


def set_order_status(conn: sqlite3.Connection, order_id: int, status: str) -> None:
    if status not in {"open", "completed", "invoiced", "cancelled"}:
        raise ValueError(f"Unknown contract status: {status}")
    get_repair_order(conn, order_id)
    with transaction(conn):
        conn.execute(
            "UPDATE repair_orders SET status = ?, updated_at = datetime('now') WHERE id = ?",
            (status, order_id),
        )


def sign_repair_order(conn: sqlite3.Connection, order_id: int, signed: bool) -> None:
    """Record that the customer has signed (or un-signed) the printed contract."""
    get_repair_order(conn, order_id)
    with transaction(conn):
        conn.execute(
            """
            UPDATE repair_orders
               SET customer_signed = ?, signed_on = ?, updated_at = datetime('now')
             WHERE id = ?
            """,
            (1 if signed else 0, date.today().isoformat() if signed else None, order_id),
        )


def delete_repair_order(conn: sqlite3.Connection, order_id: int) -> None:
    order = get_repair_order(conn, order_id)
    if order["invoice_id"] is not None:
        raise InUse(
            f"This contract has been invoiced as {order['invoice_no']} and cannot be deleted. "
            "Cancel it instead."
        )
    with transaction(conn):
        conn.execute("DELETE FROM repair_orders WHERE id = ?", (order_id,))


def convert_order_to_invoice(conn: sqlite3.Connection, order_id: int) -> int:
    """Raise an invoice from a repair contract, and link the two together.

    Labour estimates become one service line each; every spare part becomes a
    part line with its quantity and price. The contract is left in place and
    marked as invoiced, so the job can be traced from the signed paper the
    customer holds through to the money that was charged for it.
    """
    order = get_repair_order(conn, order_id)
    if order["invoice_id"] is not None:
        raise InUse(f"Already invoiced as {order['invoice_no']}.")
    if order["status"] == "cancelled":
        raise InUse("This contract was cancelled, so it cannot be invoiced.")

    settings = get_settings(conn)
    lines: list[dict[str, Any]] = []

    for item in get_order_items(conn, order_id):
        if item["expense_minor"] <= 0:
            continue  # inspection notes with no charge are not invoice lines
        lines.append(
            {
                "catalog_item_id": item["catalog_item_id"],
                "description": item["description"],
                "description_ar": item["description_ar"],
                "kind": "service",
                "unit": "pcs",
                "qty_milli": 1000,
                "unit_price_minor": item["expense_minor"],
            }
        )

    for part in get_order_parts(conn, order_id):
        lines.append(
            {
                "catalog_item_id": part["catalog_item_id"],
                "description": part["description"],
                "description_ar": part["description_ar"],
                "kind": "part",
                "unit": "pcs",
                "qty_milli": part["qty_milli"],
                "unit_price_minor": part["unit_price_minor"],
            }
        )

    if not lines:
        raise InUse(
            "There is nothing to invoice: no repair has a charge and no parts are listed."
        )

    invoice_id = create_invoice(
        conn,
        {
            "customer_id": order["customer_id"],
            "vehicle_id": order["vehicle_id"],
            "issue_date": date.today().isoformat(),
            "odometer": order["odometer"],
            "status": "draft",
            "vat_rate_bp": settings["vat_rate_bp"],
            "prices_include_vat": settings["prices_include_vat"],
            "currency_code": settings["currency_code"],
            "notes": order["notes"],
        },
        lines,
    )

    with transaction(conn):
        conn.execute(
            """
            UPDATE repair_orders
               SET invoice_id = ?, status = 'invoiced', updated_at = datetime('now')
             WHERE id = ?
            """,
            (invoice_id, order_id),
        )
    return invoice_id


def order_for_invoice(conn: sqlite3.Connection, invoice_id: int) -> Row | None:
    """The contract an invoice came from, if it came from one."""
    return _one(
        conn,
        "SELECT id, contract_no FROM repair_orders WHERE invoice_id = ?",
        (invoice_id,),
    )


# ==========================================================================
# Dashboard
# ==========================================================================

def dashboard_stats(conn: sqlite3.Connection) -> dict[str, Any]:
    """Headline numbers for the home page."""
    today = date.today()
    month_start = today.replace(day=1).isoformat()

    month = _one(
        conn,
        """
        SELECT COUNT(*) AS invoice_count,
               COALESCE(SUM(total_minor), 0) AS total_minor,
               COALESCE(SUM(vat_minor), 0)   AS vat_minor
          FROM invoices
         WHERE status = 'issued' AND issue_date >= ?
        """,
        (month_start,),
    )

    outstanding = _one(
        conn,
        """
        SELECT COUNT(*) AS invoice_count,
               COALESCE(SUM(i.total_minor - COALESCE(p.paid, 0)), 0) AS total_minor
          FROM invoices i
     LEFT JOIN (SELECT invoice_id, SUM(amount_minor) AS paid
                  FROM payments GROUP BY invoice_id) p ON p.invoice_id = i.id
         WHERE i.status = 'issued'
           AND i.total_minor > COALESCE(p.paid, 0)
        """,
    )

    counts = _one(
        conn,
        """
        SELECT (SELECT COUNT(*) FROM customers WHERE is_active = 1) AS customers,
               (SELECT COUNT(*) FROM vehicles  WHERE is_active = 1) AS vehicles,
               (SELECT COUNT(*) FROM invoices  WHERE status = 'draft') AS drafts,
               (SELECT COUNT(*) FROM repair_orders WHERE status = 'open') AS open_contracts,
               (SELECT COUNT(*) FROM repair_orders
                 WHERE status = 'completed') AS contracts_to_invoice
        """,
    )

    return {
        "month_label": today.strftime("%B %Y"),
        "month_invoice_count": month["invoice_count"],
        "month_total_minor": month["total_minor"],
        "month_vat_minor": month["vat_minor"],
        "outstanding_count": outstanding["invoice_count"],
        "outstanding_minor": outstanding["total_minor"],
        "customer_count": counts["customers"],
        "vehicle_count": counts["vehicles"],
        "draft_count": counts["drafts"],
        "open_contract_count": counts["open_contracts"],
        "contracts_to_invoice": counts["contracts_to_invoice"],
    }


def monthly_revenue(conn: sqlite3.Connection, months: int = 12) -> list[Row]:
    """Issued invoice totals grouped by month, oldest first."""
    return _all(
        conn,
        """
        SELECT substr(issue_date, 1, 7) AS month,
               COUNT(*)                 AS invoice_count,
               SUM(total_minor)         AS total_minor
          FROM invoices
         WHERE status = 'issued'
         GROUP BY month
         ORDER BY month DESC
         LIMIT ?
        """,
        (months,),
    )[::-1]


def unpaid_invoices(conn: sqlite3.Connection, limit: int = 10) -> list[Row]:
    return list_invoices(conn, status="issued", payment_state="unpaid", limit=limit)


def cars_in_workshop(conn: sqlite3.Connection, limit: int = 10) -> list[Row]:
    """Open contracts: the cars currently in the workshop, longest first."""
    return _all(
        conn,
        """
        SELECT ro.*, o.customer_id, o.vehicle_id
          FROM v_repair_orders ro
          JOIN repair_orders   o ON o.id = ro.id
         WHERE ro.status = 'open'
         ORDER BY ro.date_in ASC
         LIMIT ?
        """,
        (limit,),
    )
