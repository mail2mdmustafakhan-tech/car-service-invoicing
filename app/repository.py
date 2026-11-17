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
from base64 import b64encode
from collections.abc import Iterable, Mapping, Sequence
from datetime import date, timedelta
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
    # Added in migration 004, for estimates and messaging.
    "estimate_prefix", "next_estimate_seq", "estimate_validity_days",
    "default_country_code", "message_template_en", "message_template_ar",
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


#: Image formats the logo may be uploaded in, by the bytes each one starts
#: with. The browser's declared content type is not trusted -- it is supplied
#: by whoever is uploading, and the file itself is the only honest witness.
#:
#: SVG is deliberately absent. It is XML that can carry script, and serving
#: one back from the application's own address would hand that script the run
#: of the page. Every drawing tool exports PNG.
LOGO_SIGNATURES: tuple[tuple[bytes, str], ...] = (
    (b"\x89PNG\r\n\x1a\n", "image/png"),
    (b"\xff\xd8\xff", "image/jpeg"),
    (b"GIF87a", "image/gif"),
    (b"GIF89a", "image/gif"),
)

#: Roughly a page's worth of image. A logo needs far less, and the file is
#: carried in every backup, so there is no reason to allow more.
MAX_LOGO_BYTES = 1_000_000


def sniff_image(data: bytes) -> str | None:
    """Return the media type of an image, or ``None`` if it is not one."""
    for signature, mime in LOGO_SIGNATURES:
        if data.startswith(signature):
            return mime
    # WebP announces itself as RIFF....WEBP, with the size in between.
    if data[:4] == b"RIFF" and data[8:12] == b"WEBP":
        return "image/webp"
    return None


def set_logo(
    conn: sqlite3.Connection, data: bytes, *, filename: str = ""
) -> str:
    """Store an uploaded logo. Returns its media type.

    Raises :class:`ValueError` if the upload is empty, too large, or not an
    image this application will serve.
    """
    if not data:
        raise ValueError("No file was uploaded.")
    if len(data) > MAX_LOGO_BYTES:
        raise ValueError(
            f"That image is {len(data) / 1_000_000:.1f} MB. Please use one "
            "under 1 MB — a logo needs far less than that."
        )
    mime = sniff_image(data)
    if mime is None:
        raise ValueError("That file is not a PNG, JPEG, GIF or WebP image.")

    with transaction(conn):
        conn.execute(
            """
            UPDATE branding
               SET logo_blob = ?, logo_mime = ?, logo_filename = ?,
                   updated_at = datetime('now')
             WHERE id = 1
            """,
            (data, mime, filename[:120]),
        )
    return mime


def clear_logo(conn: sqlite3.Connection) -> None:
    with transaction(conn):
        conn.execute(
            """
            UPDATE branding
               SET logo_blob = NULL, logo_mime = '', logo_filename = '',
                   updated_at = datetime('now')
             WHERE id = 1
            """
        )


def get_logo(conn: sqlite3.Connection) -> tuple[bytes, str] | None:
    """The stored logo and its media type, or ``None`` if none is set."""
    row = _one(conn, "SELECT logo_blob, logo_mime FROM branding WHERE id = 1")
    if row is None or not row["logo_blob"]:
        return None
    return bytes(row["logo_blob"]), row["logo_mime"] or "image/png"


def logo_state(conn: sqlite3.Connection) -> Row:
    """Whether a logo is set, and when it last changed -- without the bytes.

    Read on every page render to decide whether to show the logo in the top
    bar, so it deliberately does not touch the image itself. The timestamp
    goes on the end of the image URL so a replaced logo appears immediately
    instead of the browser showing the cached old one.
    """
    return _require(
        _one(conn, "SELECT logo_mime, logo_filename, updated_at FROM branding WHERE id = 1"),
        "Branding",
    )


def logo_data_uri(conn: sqlite3.Connection) -> str:
    """The logo as a ``data:`` URI, or an empty string.

    The printed documents embed the image this way rather than linking to it.
    A link works in the browser but not when the PDF renderer is handed a
    string of HTML with no server behind it, and a logo that silently
    disappears from the PDF is exactly the kind of thing nobody notices until
    a customer is holding the page.
    """
    stored = get_logo(conn)
    if stored is None:
        return ""
    data, mime = stored
    return f"data:{mime};base64,{b64encode(data).decode('ascii')}"


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
    "category", "is_active",
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
    "manufacturer",
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
    "discount_minor", "discount_mode", "discount_rate_bp", "notes", "doc_type",
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
    "qty_milli", "unit_price_minor", "sourced_externally", "source",
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
# Estimates
# ==========================================================================
# What a customer is quoted before anything is agreed. An estimate carries no
# obligation: it is written, shown, approved or declined, and only then does
# it become an invoice.

ESTIMATE_HEADER_FIELDS = (
    "customer_id", "vehicle_id", "issue_date", "valid_until", "status",
    "vat_rate_bp", "prices_include_vat", "currency_code", "discount_minor",
    "discount_mode", "discount_rate_bp", "notes", "approved_by", "inspection_id",
)

ESTIMATE_ITEM_FIELDS = (
    "catalog_item_id", "description", "description_ar", "kind", "unit",
    "qty_milli", "unit_price_minor",
)


def reserve_estimate_no(conn: sqlite3.Connection) -> str:
    """Take the next estimate number. Its own series, like contracts."""
    row = conn.execute(
        """
        UPDATE settings
           SET next_estimate_seq = next_estimate_seq + 1
         WHERE id = 1
        RETURNING estimate_prefix, next_estimate_seq - 1 AS seq
        """
    ).fetchone()
    return f"{row['estimate_prefix']}{row['seq']:05d}"


def list_estimates(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "",
    customer_id: int | None = None,
    limit: int = 500,
) -> list[Row]:
    where, params = ["1 = 1"], []
    if search:
        where.append(
            "(ve.estimate_no LIKE ? OR ve.customer_name LIKE ? OR ve.vehicle_plate LIKE ?)"
        )
        like = f"%{search}%"
        params += [like, like, like]
    if status:
        where.append("ve.status = ?")
        params.append(status)
    if customer_id is not None:
        where.append("e.customer_id = ?")
        params.append(customer_id)

    params.append(limit)
    return _all(
        conn,
        f"""
        SELECT ve.*, e.customer_id, e.vehicle_id, e.invoice_id, e.total_minor
          FROM v_estimates ve
          JOIN estimates   e ON e.id = ve.id
         WHERE {' AND '.join(where)}
         ORDER BY ve.issue_date DESC, ve.id DESC
         LIMIT ?
        """,
        params,
    )


def get_estimate(conn: sqlite3.Connection, estimate_id: int) -> Row:
    return _require(
        _one(
            conn,
            """
            SELECT e.*,
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
                   i.invoice_no AS invoice_no
              FROM estimates e
              JOIN customers c ON c.id = e.customer_id
         LEFT JOIN vehicles  v ON v.id = e.vehicle_id
         LEFT JOIN invoices  i ON i.id = e.invoice_id
             WHERE e.id = ?
            """,
            (estimate_id,),
        ),
        "Estimate",
    )


def get_estimate_items(conn: sqlite3.Connection, estimate_id: int) -> list[Row]:
    return _all(
        conn,
        "SELECT * FROM estimate_items WHERE estimate_id = ? ORDER BY line_no",
        (estimate_id,),
    )


def _write_estimate_items(
    conn: sqlite3.Connection, estimate_id: int, items: Sequence[Mapping[str, Any]]
) -> None:
    conn.execute("DELETE FROM estimate_items WHERE estimate_id = ?", (estimate_id,))
    for line_no, raw in enumerate(items, start=1):
        values = _pick(raw, ESTIMATE_ITEM_FIELDS)
        values["estimate_id"] = estimate_id
        values["line_no"] = line_no
        values["line_total_minor"] = line_total(
            int(raw["qty_milli"]), int(raw["unit_price_minor"])
        )
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn.execute(
            f"INSERT INTO estimate_items ({cols}) VALUES ({marks})",
            list(values.values()),
        )


def _write_estimate_totals(conn: sqlite3.Connection, estimate_id: int) -> None:
    header = _require(
        _one(
            conn,
            "SELECT vat_rate_bp, prices_include_vat, discount_minor FROM estimates WHERE id = ?",
            (estimate_id,),
        ),
        "Estimate",
    )
    lines = _all(
        conn,
        "SELECT qty_milli, unit_price_minor FROM estimate_items WHERE estimate_id = ?",
        (estimate_id,),
    )
    totals = compute_totals(
        [(int(r["qty_milli"]), int(r["unit_price_minor"])) for r in lines],
        vat_rate_bp=int(header["vat_rate_bp"]),
        discount_minor=int(header["discount_minor"]),
        prices_include_vat=bool(header["prices_include_vat"]),
    )
    conn.execute(
        """
        UPDATE estimates
           SET subtotal_minor = ?, taxable_minor = ?, vat_minor = ?,
               total_minor = ?, updated_at = datetime('now')
         WHERE id = ?
        """,
        (
            totals.subtotal_minor,
            totals.taxable_minor,
            totals.vat_minor,
            totals.total_minor,
            estimate_id,
        ),
    )


def create_estimate(
    conn: sqlite3.Connection,
    header: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> int:
    values = _pick(header, ESTIMATE_HEADER_FIELDS)
    values.setdefault("issue_date", date.today().isoformat())
    with transaction(conn):
        values["estimate_no"] = reserve_estimate_no(conn)
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        cur = conn.execute(
            f"INSERT INTO estimates ({cols}) VALUES ({marks})", list(values.values())
        )
        estimate_id = int(cur.lastrowid)
        _write_estimate_items(conn, estimate_id, items)
        _write_estimate_totals(conn, estimate_id)
    return estimate_id


def update_estimate(
    conn: sqlite3.Connection,
    estimate_id: int,
    header: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> None:
    estimate = get_estimate(conn, estimate_id)
    if estimate["invoice_id"] is not None:
        raise InUse(
            f"This estimate has been invoiced as {estimate['invoice_no']}. "
            "Edit that invoice instead."
        )
    with transaction(conn):
        _update(conn, "estimates", estimate_id, _pick(header, ESTIMATE_HEADER_FIELDS))
        _write_estimate_items(conn, estimate_id, items)
        _write_estimate_totals(conn, estimate_id)


def set_estimate_status(
    conn: sqlite3.Connection,
    estimate_id: int,
    status: str,
    *,
    approved_by: str = "",
) -> None:
    """Move an estimate along: sent, approved, declined, or back to draft.

    The date is stamped by the system rather than typed, so "when did they
    agree to this" always has an answer and it is never a guess.
    """
    if status not in {"draft", "sent", "approved", "declined"}:
        raise ValueError(f"Unknown estimate status: {status}")
    estimate = get_estimate(conn, estimate_id)
    if estimate["status"] == "invoiced":
        raise InUse("This estimate has already been invoiced.")

    today = date.today().isoformat()
    sent_on = today if status == "sent" else estimate["sent_on"]
    decided_on = today if status in {"approved", "declined"} else None

    with transaction(conn):
        conn.execute(
            """
            UPDATE estimates
               SET status = ?, sent_on = ?, decided_on = ?, approved_by = ?,
                   updated_at = datetime('now')
             WHERE id = ?
            """,
            (
                status,
                sent_on,
                decided_on,
                approved_by if status == "approved" else "",
                estimate_id,
            ),
        )


def delete_estimate(conn: sqlite3.Connection, estimate_id: int) -> None:
    estimate = get_estimate(conn, estimate_id)
    if estimate["invoice_id"] is not None:
        raise InUse(
            f"This estimate was invoiced as {estimate['invoice_no']} and cannot be deleted."
        )
    with transaction(conn):
        conn.execute("DELETE FROM estimates WHERE id = ?", (estimate_id,))


def convert_estimate_to_invoice(
    conn: sqlite3.Connection, estimate_id: int, *, doc_type: str = "tax"
) -> int:
    """Raise an invoice from an approved estimate.

    Only an approved estimate converts. Invoicing something the customer has
    not agreed to is how disputes start, and the system should not make that
    the easy path.
    """
    estimate = get_estimate(conn, estimate_id)
    if estimate["invoice_id"] is not None:
        raise InUse(f"Already invoiced as {estimate['invoice_no']}.")
    if estimate["status"] != "approved":
        raise InUse(
            "Only an approved estimate can be invoiced. "
            "Mark it approved once the customer has agreed to it."
        )

    items = get_estimate_items(conn, estimate_id)
    if not items:
        raise InUse("This estimate has no items.")

    lines = [
        {
            "catalog_item_id": item["catalog_item_id"],
            "description": item["description"],
            "description_ar": item["description_ar"],
            "kind": item["kind"],
            "unit": item["unit"],
            "qty_milli": item["qty_milli"],
            "unit_price_minor": item["unit_price_minor"],
        }
        for item in items
    ]

    invoice_id = create_invoice(
        conn,
        {
            "customer_id": estimate["customer_id"],
            "vehicle_id": estimate["vehicle_id"],
            "issue_date": date.today().isoformat(),
            "status": "draft",
            "doc_type": doc_type,
            # A plain invoice carries no VAT, whatever the estimate quoted.
            "vat_rate_bp": estimate["vat_rate_bp"] if doc_type == "tax" else 0,
            "prices_include_vat": estimate["prices_include_vat"],
            "currency_code": estimate["currency_code"],
            "discount_minor": estimate["discount_minor"],
            "discount_mode": estimate["discount_mode"],
            "discount_rate_bp": estimate["discount_rate_bp"],
            "notes": estimate["notes"],
        },
        lines,
    )

    with transaction(conn):
        conn.execute(
            """
            UPDATE estimates
               SET invoice_id = ?, status = 'invoiced', updated_at = datetime('now')
             WHERE id = ?
            """,
            (invoice_id, estimate_id),
        )
    return invoice_id


def estimate_for_invoice(conn: sqlite3.Connection, invoice_id: int) -> Row | None:
    """The estimate an invoice came from, if it came from one."""
    return _one(
        conn,
        "SELECT id, estimate_no FROM estimates WHERE invoice_id = ?",
        (invoice_id,),
    )


# ==========================================================================
# Customer attachments
# ==========================================================================
# Scans of invoices written before this system existed, so a customer's
# history is in one place.

#: What may be uploaded, by the bytes the file starts with. As with the logo,
#: the browser's declared type is not trusted -- the file is the only honest
#: witness to what it is.
ATTACHMENT_SIGNATURES: tuple[tuple[bytes, str, str], ...] = (
    (b"%PDF-", "application/pdf", ".pdf"),
    (b"\xff\xd8\xff", "image/jpeg", ".jpg"),
    (b"\x89PNG\r\n\x1a\n", "image/png", ".png"),
)

MAX_ATTACHMENT_BYTES = 10 * 1024 * 1024    # 10 MB


def sniff_attachment(data: bytes) -> tuple[str, str] | None:
    """Return ``(media type, file extension)``, or ``None`` if unacceptable."""
    for signature, mime, extension in ATTACHMENT_SIGNATURES:
        if data.startswith(signature):
            return mime, extension
    return None


def add_attachment(
    conn: sqlite3.Connection,
    customer_id: int,
    data: bytes,
    *,
    original_name: str = "",
    kind: str = "invoice",
    description: str = "",
    document_date: str | None = None,
) -> int:
    """Store an uploaded document against a customer.

    The file is written under the data folder with a generated name. The name
    it arrived with is kept only as a label: a filename from a browser is
    text someone else chose, and letting it decide where a file lands on disk
    is how a upload ends up somewhere it should never reach.
    """
    from uuid import uuid4

    from .db import attachments_dir

    get_customer(conn, customer_id)

    if not data:
        raise ValueError("No file was uploaded.")
    if len(data) > MAX_ATTACHMENT_BYTES:
        raise ValueError(
            f"That file is {len(data) / 1024 / 1024:.1f} MB. The limit is 10 MB."
        )
    sniffed = sniff_attachment(data)
    if sniffed is None:
        raise ValueError("Only PDF, JPEG and PNG files can be attached.")
    mime, extension = sniffed

    stored_name = f"{uuid4().hex}{extension}"
    folder = attachments_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / stored_name).write_bytes(data)

    try:
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO customer_attachments
                    (customer_id, stored_name, original_name, mime, size_bytes,
                     kind, description, document_date)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    customer_id,
                    stored_name,
                    (original_name or stored_name)[:200],
                    mime,
                    len(data),
                    kind if kind in {"invoice", "document", "photo", "other"} else "other",
                    description[:500],
                    document_date,
                ),
            )
    except Exception:
        # Do not leave a file on disk that nothing points at.
        (folder / stored_name).unlink(missing_ok=True)
        raise
    return int(cur.lastrowid)


def list_attachments(conn: sqlite3.Connection, customer_id: int) -> list[Row]:
    return _all(
        conn,
        """
        SELECT * FROM customer_attachments
         WHERE customer_id = ?
         ORDER BY COALESCE(document_date, uploaded_at) DESC, id DESC
        """,
        (customer_id,),
    )


def get_attachment(conn: sqlite3.Connection, attachment_id: int) -> Row:
    return _require(
        _one(
            conn, "SELECT * FROM customer_attachments WHERE id = ?", (attachment_id,)
        ),
        "Attachment",
    )


def attachment_file(conn: sqlite3.Connection, attachment_id: int):
    """The path on disk for an attachment, and its row."""
    from .db import attachments_dir

    row = get_attachment(conn, attachment_id)
    # stored_name is generated by this application, never user input, but it
    # is resolved and checked against the folder anyway: a single bad row
    # should not be able to reach outside it.
    folder = attachments_dir().resolve()
    path = (folder / row["stored_name"]).resolve()
    if folder not in path.parents:
        raise NotFound("Attachment not found")
    return path, row


def delete_attachment(conn: sqlite3.Connection, attachment_id: int) -> int:
    """Remove an attachment and its file. Returns the customer it belonged to."""
    path, row = attachment_file(conn, attachment_id)
    with transaction(conn):
        conn.execute("DELETE FROM customer_attachments WHERE id = ?", (attachment_id,))
    path.unlink(missing_ok=True)
    return int(row["customer_id"])


def attachment_totals(conn: sqlite3.Connection) -> dict[str, int]:
    row = _one(
        conn,
        "SELECT COUNT(*) AS n, COALESCE(SUM(size_bytes), 0) AS bytes FROM customer_attachments",
    )
    return {"count": row["n"], "bytes": row["bytes"]}


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
               COALESCE(SUM(vat_minor), 0)   AS vat_minor,
               COALESCE(SUM(CASE WHEN doc_type = 'tax'   THEN total_minor END), 0) AS tax_total,
               COALESCE(SUM(CASE WHEN doc_type = 'plain' THEN total_minor END), 0) AS plain_total
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
                 WHERE status = 'completed') AS contracts_to_invoice,
               (SELECT COUNT(*) FROM estimates
                 WHERE status IN ('draft', 'sent')) AS open_estimates,
               (SELECT COUNT(*) FROM estimates WHERE status = 'approved') AS approved_estimates
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
        "open_estimate_count": counts["open_estimates"],
        "approved_estimate_count": counts["approved_estimates"],
        # Tax and plain invoices are reported apart. Both are real sales and
        # both count towards the month's takings, but only tax invoices carry
        # VAT, so mixing them would make the VAT figure meaningless.
        "month_tax_minor": month["tax_total"],
        "month_plain_minor": month["plain_total"],
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


def open_estimates(conn: sqlite3.Connection, limit: int = 10) -> list[Row]:
    """Estimates still waiting on the customer, oldest first."""
    return _all(
        conn,
        """
        SELECT ve.*, e.customer_id, e.total_minor
          FROM v_estimates ve
          JOIN estimates   e ON e.id = ve.id
         WHERE ve.status IN ('draft', 'sent')
         ORDER BY ve.issue_date ASC
         LIMIT ?
        """,
        (limit,),
    )


# ==========================================================================
# Spreadsheet imports
# ==========================================================================
# An uploaded file is parsed and checked into a batch first. Nothing reaches
# the customers table until the preview has been looked at and confirmed.

def create_import_batch(
    conn: sqlite3.Connection, filename: str, rows: Sequence[Mapping[str, Any]]
) -> int:
    import json

    with transaction(conn):
        cur = conn.execute(
            """
            INSERT INTO import_batches (filename, rows_json, row_count)
            VALUES (?, ?, ?)
            """,
            (filename[:200], json.dumps(list(rows), ensure_ascii=False), len(rows)),
        )
    return int(cur.lastrowid)


def get_import_batch(conn: sqlite3.Connection, batch_id: int) -> tuple[Row, list[dict]]:
    import json

    row = _require(
        _one(conn, "SELECT * FROM import_batches WHERE id = ?", (batch_id,)),
        "Import",
    )
    return row, json.loads(row["rows_json"])


def commit_import_batch(conn: sqlite3.Connection, batch_id: int) -> dict[str, int]:
    """Create the customers in a batch. Rows flagged as skipped are left alone."""
    batch, rows = get_import_batch(conn, batch_id)
    if batch["status"] != "pending":
        raise InUse("This import has already been dealt with.")

    imported = skipped = 0
    with transaction(conn):
        for row in rows:
            if row.get("skip"):
                skipped += 1
                continue
            values = {
                field: row.get(field, "")
                for field in ("name", "name_ar", "phone", "email", "address",
                              "vat_number", "notes")
                if row.get(field)
            }
            if not values.get("name"):
                skipped += 1
                continue
            cols = ", ".join(values)
            marks = ", ".join("?" for _ in values)
            conn.execute(
                f"INSERT INTO customers ({cols}) VALUES ({marks})",
                list(values.values()),
            )
            imported += 1

        conn.execute(
            """
            UPDATE import_batches
               SET status = 'imported', imported = ?, skipped = ?
             WHERE id = ?
            """,
            (imported, skipped, batch_id),
        )
    return {"imported": imported, "skipped": skipped}


def cancel_import_batch(conn: sqlite3.Connection, batch_id: int) -> None:
    with transaction(conn):
        conn.execute(
            "UPDATE import_batches SET status = 'cancelled' WHERE id = ? AND status = 'pending'",
            (batch_id,),
        )


def existing_customer_keys(conn: sqlite3.Connection) -> tuple[set[str], set[str]]:
    """Names and phone numbers already on file, for spotting duplicates.

    Names are compared case-insensitively and phones with their punctuation
    stripped, because "0551234567" and "055-123 4567" are the same customer
    and importing both would be worse than importing neither.
    """
    names, phones = set(), set()
    for row in _all(conn, "SELECT name, phone FROM customers"):
        if row["name"]:
            names.add(row["name"].strip().casefold())
        if row["phone"]:
            phones.add("".join(ch for ch in row["phone"] if ch.isdigit()))
    return names, phones


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


# ==========================================================================
# Photographs of catalogue parts
# ==========================================================================

#: Pictures only. A PDF of a part is a catalogue page, not a photograph of
#: the thing on the shelf, and the gallery is there to answer "is this the
#: one?" at the counter.
ITEM_IMAGE_SIGNATURES: tuple[tuple[bytes, str, str], ...] = tuple(
    row for row in ATTACHMENT_SIGNATURES if row[1].startswith("image/")
)

MAX_ITEM_IMAGE_BYTES = 10 * 1024 * 1024


def sniff_item_image(data: bytes) -> tuple[str, str] | None:
    """What this file actually is, by its first bytes.

    Never the type the browser declared. That is a claim made by whoever
    sent the file, and a .jpg that is really something else should not be
    stored as one.
    """
    for signature, mime, extension in ITEM_IMAGE_SIGNATURES:
        if data.startswith(signature):
            return mime, extension
    return None


def add_item_image(
    conn: sqlite3.Connection,
    item_id: int,
    data: bytes,
    *,
    original_name: str = "",
    caption: str = "",
) -> int:
    """Store a photograph against a catalogue item.

    Same rules as a customer attachment, and for the same reasons: the bytes
    go beside the database under a generated name, so years of photographs
    never make the database awkward to copy, and a filename chosen by
    somebody else never decides where a file lands on disk.
    """
    from uuid import uuid4

    from .db import attachments_dir

    get_catalog_item(conn, item_id)

    if not data:
        raise ValueError("No file was uploaded.")
    if len(data) > MAX_ITEM_IMAGE_BYTES:
        raise ValueError(
            f"That image is {len(data) / 1024 / 1024:.1f} MB. The limit is 10 MB."
        )
    sniffed = sniff_item_image(data)
    if sniffed is None:
        raise ValueError("Only JPEG and PNG images can be added to a part.")
    mime, extension = sniffed

    stored_name = f"{uuid4().hex}{extension}"
    folder = attachments_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / stored_name).write_bytes(data)

    try:
        with transaction(conn):
            cur = conn.execute(
                """
                INSERT INTO catalog_item_images
                    (catalog_item_id, stored_name, original_name, mime,
                     size_bytes, caption)
                VALUES (?, ?, ?, ?, ?, ?)
                """,
                (item_id, stored_name, (original_name or stored_name)[:200],
                 mime, len(data), caption[:300]),
            )
    except Exception:
        (folder / stored_name).unlink(missing_ok=True)
        raise
    return int(cur.lastrowid)


def list_item_images(conn: sqlite3.Connection, item_id: int) -> list[Row]:
    return _all(
        conn,
        "SELECT * FROM catalog_item_images WHERE catalog_item_id = ? ORDER BY id",
        (item_id,),
    )


def get_item_image(conn: sqlite3.Connection, image_id: int) -> Row:
    return _require(
        _one(conn, "SELECT * FROM catalog_item_images WHERE id = ?", (image_id,)),
        "Image",
    )


def item_image_file(conn: sqlite3.Connection, image_id: int):
    """The path on disk, checked to be inside the attachments folder.

    The stored name is generated by us, so this should always hold. It is
    checked anyway: a path that escapes its folder is the kind of bug that
    is cheap to prevent and expensive to find.
    """
    from .db import attachments_dir

    row = get_item_image(conn, image_id)
    folder = attachments_dir().resolve()
    path = (folder / row["stored_name"]).resolve()
    if folder not in path.parents:
        raise NotFound("Image")
    return row, path


def delete_item_image(conn: sqlite3.Connection, image_id: int) -> None:
    row, path = item_image_file(conn, image_id)
    with transaction(conn):
        conn.execute("DELETE FROM catalog_item_images WHERE id = ?", (image_id,))
    path.unlink(missing_ok=True)


# ==========================================================================
# Known faults
# ==========================================================================

ISSUE_FIELDS = (
    "make", "model", "engine", "year_from", "year_to",
    "title_en", "title_ar", "symptoms_en", "symptoms_ar",
    "check_en", "check_ar", "severity", "is_active", "notes",
)


def list_known_issues(
    conn: sqlite3.Connection,
    *,
    make: str = "",
    search: str = "",
    include_inactive: bool = False,
) -> list[Row]:
    where, params = ["1 = 1"], []
    if make:
        where.append("make = ?")
        params.append(make)
    if not include_inactive:
        where.append("is_active = 1")
    if search:
        where.append(
            "(title_en LIKE ? OR title_ar LIKE ? OR model LIKE ? OR engine LIKE ?"
            " OR symptoms_en LIKE ?)"
        )
        params += [f"%{search}%"] * 5
    return _all(
        conn,
        f"""
        SELECT k.*,
               (SELECT COUNT(*) FROM repair_order_issues oi
                 WHERE oi.known_issue_id = k.id) AS case_count
          FROM known_issues k
         WHERE {' AND '.join(where)}
         ORDER BY make, model, title_en
        """,
        tuple(params),
    )


def known_issue_makes(conn: sqlite3.Connection) -> list[str]:
    return [
        row["make"]
        for row in _all(conn, "SELECT DISTINCT make FROM known_issues ORDER BY make")
    ]


def get_known_issue(conn: sqlite3.Connection, issue_id: int) -> Row:
    return _require(
        _one(conn, "SELECT * FROM known_issues WHERE id = ?", (issue_id,)),
        "Known issue",
    )


def create_known_issue(conn: sqlite3.Connection, data: Mapping[str, Any]) -> int:
    values = _pick(data, ISSUE_FIELDS)
    cols = ", ".join(values)
    marks = ", ".join("?" for _ in values)
    with transaction(conn):
        cur = conn.execute(
            f"INSERT INTO known_issues ({cols}) VALUES ({marks})", list(values.values())
        )
    return int(cur.lastrowid)


def update_known_issue(
    conn: sqlite3.Connection, issue_id: int, data: Mapping[str, Any]
) -> None:
    get_known_issue(conn, issue_id)
    values = _pick(data, ISSUE_FIELDS)
    if not values:
        return
    assignments = ", ".join(f"{col} = ?" for col in values)
    with transaction(conn):
        conn.execute(
            f"UPDATE known_issues SET {assignments}, updated_at = datetime('now')"
            " WHERE id = ?",
            [*values.values(), issue_id],
        )


def delete_known_issue(conn: sqlite3.Connection, issue_id: int) -> None:
    get_known_issue(conn, issue_id)
    with transaction(conn):
        conn.execute("DELETE FROM known_issues WHERE id = ?", (issue_id,))


# -- faults attached to a job ----------------------------------------------


def list_order_issues(conn: sqlite3.Connection, order_id: int) -> list[Row]:
    return _all(
        conn,
        """
        SELECT oi.*, k.make, k.model, k.engine, k.severity,
               k.title_en, k.title_ar, k.symptoms_en, k.symptoms_ar,
               k.check_en, k.check_ar
          FROM repair_order_issues oi
          JOIN known_issues k ON k.id = oi.known_issue_id
         WHERE oi.repair_order_id = ?
         ORDER BY oi.id
        """,
        (order_id,),
    )


def attach_issue(
    conn: sqlite3.Connection,
    order_id: int,
    issue_id: int,
    *,
    outcome: str = "suspected",
    show_on_print: bool = True,
    note: str = "",
) -> None:
    """Record that a known fault was considered on this job.

    Attaching the same fault twice is treated as editing the first, not as an
    error: the second attempt is somebody updating what they found, and an
    error message there would only be in the way.
    """
    get_repair_order(conn, order_id)
    get_known_issue(conn, issue_id)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO repair_order_issues
                (repair_order_id, known_issue_id, outcome, show_on_print, note)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT (repair_order_id, known_issue_id) DO UPDATE SET
                outcome = excluded.outcome,
                show_on_print = excluded.show_on_print,
                note = excluded.note
            """,
            (order_id, issue_id, outcome, 1 if show_on_print else 0, note[:500]),
        )


def detach_issue(conn: sqlite3.Connection, link_id: int) -> int:
    """Remove a fault from a job, returning the job it was on."""
    row = _require(
        _one(conn, "SELECT * FROM repair_order_issues WHERE id = ?", (link_id,)),
        "Linked issue",
    )
    with transaction(conn):
        conn.execute("DELETE FROM repair_order_issues WHERE id = ?", (link_id,))
    return int(row["repair_order_id"])


def issue_case_counts(conn: sqlite3.Connection, limit: int = 12) -> list[Row]:
    """How often each fault has actually been seen, most first."""
    return _all(
        conn,
        """
        SELECT k.id, k.make, k.model, k.title_en, k.title_ar, k.severity,
               COUNT(oi.id) AS cases,
               SUM(CASE WHEN oi.outcome IN ('confirmed', 'repaired') THEN 1 ELSE 0 END)
                   AS confirmed
          FROM known_issues k
          JOIN repair_order_issues oi ON oi.known_issue_id = k.id
         GROUP BY k.id
         ORDER BY cases DESC, confirmed DESC
         LIMIT ?
        """,
        (limit,),
    )


# ==========================================================================
# Analytics
# ==========================================================================
# All of this is worked out from the records rather than stored. A cached
# "active customer" flag is wrong the moment nobody updates it, and these
# queries run against a few thousand rows on one PC -- the cost of being
# right is nothing here.


def monthly_money(conn: sqlite3.Connection, months: int = 12) -> list[Row]:
    """Invoiced and collected per month, with the balance owed at month end.

    The month-end balance is cumulative -- everything issued up to that point
    less everything paid up to that point -- which is the figure a person
    means by "what are we owed". A per-month difference would show the month's
    movement and be mistaken for the balance.
    """
    return _all(
        conn,
        """
        WITH months AS (
            SELECT DISTINCT strftime('%Y-%m', issue_date) AS ym
              FROM invoices WHERE status = 'issued'
            UNION
            SELECT DISTINCT strftime('%Y-%m', paid_on) FROM payments
        )
        SELECT m.ym,
               COALESCE((SELECT SUM(i.total_minor) FROM invoices i
                          WHERE i.status = 'issued'
                            AND strftime('%Y-%m', i.issue_date) = m.ym), 0) AS invoiced_minor,
               COALESCE((SELECT SUM(p.amount_minor) FROM payments p
                          WHERE strftime('%Y-%m', p.paid_on) = m.ym), 0) AS collected_minor,
               COALESCE((SELECT SUM(i.total_minor) FROM invoices i
                          WHERE i.status = 'issued'
                            AND strftime('%Y-%m', i.issue_date) <= m.ym), 0)
               - COALESCE((SELECT SUM(p.amount_minor) FROM payments p
                            WHERE strftime('%Y-%m', p.paid_on) <= m.ym), 0) AS outstanding_minor
          FROM months m
         ORDER BY m.ym DESC
         LIMIT ?
        """,
        (months,),
    )[::-1]


def cars_by_make(conn: sqlite3.Connection, limit: int = 8) -> list[Row]:
    return _all(
        conn,
        """
        SELECT COALESCE(NULLIF(TRIM(make), ''), 'Unknown') AS label,
               COUNT(*) AS cars,
               COUNT(DISTINCT customer_id) AS customers
          FROM vehicles
         GROUP BY label
         ORDER BY cars DESC
         LIMIT ?
        """,
        (limit,),
    )


def cars_by_model(conn: sqlite3.Connection, limit: int = 10) -> list[Row]:
    return _all(
        conn,
        """
        SELECT TRIM(COALESCE(make, '') || ' ' || COALESCE(model, '')) AS label,
               COUNT(*) AS cars
          FROM vehicles
         WHERE TRIM(COALESCE(make, '') || COALESCE(model, '')) <> ''
         GROUP BY label
         ORDER BY cars DESC
         LIMIT ?
        """,
        (limit,),
    )


def customer_categories(conn: sqlite3.Connection) -> list[Row]:
    return _all(
        conn,
        """
        SELECT category AS label, COUNT(*) AS customers
          FROM customers
         WHERE is_active = 1
         GROUP BY category
         ORDER BY customers DESC
        """,
    )


def customer_activity(conn: sqlite3.Connection, months: int = 12) -> dict[str, int]:
    """How many customers have actually been in lately.

    "Active" is a question about the records, not a flag somebody remembers to
    tick. A customer who has not been seen in a year is not active however the
    box is set.
    """
    cutoff = (date.today() - timedelta(days=30 * months)).isoformat()
    row = _one(
        conn,
        """
        SELECT
          (SELECT COUNT(*) FROM customers WHERE is_active = 1) AS total,
          (SELECT COUNT(DISTINCT customer_id) FROM invoices
            WHERE status = 'issued' AND issue_date >= ?) AS invoiced,
          (SELECT COUNT(DISTINCT customer_id) FROM repair_orders
            WHERE date_in >= ?) AS visited
        """,
        (cutoff, cutoff),
    )
    seen = _one(
        conn,
        """
        SELECT COUNT(*) AS n FROM (
            SELECT customer_id FROM invoices
             WHERE status = 'issued' AND issue_date >= ?
            UNION
            SELECT customer_id FROM repair_orders WHERE date_in >= ?
        )
        """,
        (cutoff, cutoff),
    )
    total = int(row["total"] or 0)
    active = int(seen["n"] or 0)
    return {
        "total": total,
        "active": active,
        "dormant": max(total - active, 0),
        "months": months,
    }


def top_customers(conn: sqlite3.Connection, limit: int = 8) -> list[Row]:
    return _all(
        conn,
        """
        SELECT c.id, c.name, c.category,
               COUNT(i.id) AS invoices,
               COALESCE(SUM(i.total_minor), 0) AS total_minor
          FROM customers c
          JOIN invoices i ON i.customer_id = c.id AND i.status = 'issued'
         GROUP BY c.id
         ORDER BY total_minor DESC
         LIMIT ?
        """,
        (limit,),
    )


# ---------------------------------------------------------------------------
# Inspections — the check that happens before anyone quotes
# ---------------------------------------------------------------------------

#: The standard walk-round, offered as the starting rows of a new check.
#:
#: A blank checklist gets filled in where something is wrong and left empty
#: everywhere else, and an empty row is ambiguous forever after: was it not
#: checked, or checked and fine? Starting from a list means every row carries
#: an answer, and the ones nobody touched say 'ok' because that is what the
#: technician saw.
#:
#: Edit freely: rows can be removed and added on the form. This is where to
#: change what the workshop checks as standard.
DEFAULT_CHECKLIST: tuple[tuple[str, str], ...] = (
    ("Engine oil level and condition", "مستوى وحالة زيت المحرك"),
    ("Coolant level and condition", "مستوى وحالة سائل التبريد"),
    ("Brake pads — front", "فحمات الفرامل الأمامية"),
    ("Brake pads — rear", "فحمات الفرامل الخلفية"),
    ("Brake discs", "هوبات الفرامل"),
    ("Brake fluid", "زيت الفرامل"),
    ("Tyres — tread, pressure and age", "الإطارات: النقشة والضغط والعمر"),
    ("Battery and charging", "البطارية والشحن"),
    ("Air conditioning", "التكييف"),
    ("Lights and indicators", "الأضواء والإشارات"),
    ("Wipers and washers", "المساحات ورشاش الماء"),
    ("Suspension and shock absorbers", "التعليق والمساعدات"),
    ("Steering and alignment", "التوجيه وضبط الزوايا"),
    ("Belts and hoses", "السيور والخراطيم"),
    ("Exhaust system", "نظام العادم"),
    ("Leaks — oil and coolant", "التسريبات: الزيت وسائل التبريد"),
    ("Air and cabin filters", "فلاتر الهواء والمقصورة"),
    ("Fault code scan", "فحص أكواد الأعطال"),
)

INSPECTION_HEADER_FIELDS = (
    "customer_id", "vehicle_id", "inspected_on", "odometer", "technician",
    "status", "summary", "notes",
)

INSPECTION_ITEM_FIELDS = (
    "area", "area_ar", "condition", "finding", "finding_ar", "known_issue_id",
    "catalog_item_id", "qty_milli", "unit_price_minor", "quote_it",
)


def reserve_inspection_no(conn: sqlite3.Connection) -> str:
    """Take the next inspection number. Its own series, like contracts."""
    row = conn.execute(
        """
        UPDATE settings
           SET next_inspection_seq = next_inspection_seq + 1
         WHERE id = 1
        RETURNING inspection_prefix, next_inspection_seq - 1 AS seq
        """
    ).fetchone()
    return f"{row['inspection_prefix']}{row['seq']:05d}"


def _write_inspection_items(
    conn: sqlite3.Connection,
    inspection_id: int,
    items: Sequence[Mapping[str, Any]],
) -> None:
    conn.execute("DELETE FROM inspection_items WHERE inspection_id = ?", (inspection_id,))
    for line_no, item in enumerate(items, start=1):
        values = _pick(item, INSPECTION_ITEM_FIELDS)
        values["inspection_id"] = inspection_id
        values["line_no"] = line_no
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        conn.execute(
            f"INSERT INTO inspection_items ({cols}) VALUES ({marks})",
            list(values.values()),
        )


def create_inspection(
    conn: sqlite3.Connection,
    header: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> int:
    values = _pick(header, INSPECTION_HEADER_FIELDS)
    values.setdefault("inspected_on", date.today().isoformat())
    with transaction(conn):
        values["inspection_no"] = reserve_inspection_no(conn)
        cols = ", ".join(values)
        marks = ", ".join("?" for _ in values)
        cur = conn.execute(
            f"INSERT INTO inspections ({cols}) VALUES ({marks})", list(values.values())
        )
        inspection_id = int(cur.lastrowid)
        _write_inspection_items(conn, inspection_id, items)
    return inspection_id


def update_inspection(
    conn: sqlite3.Connection,
    inspection_id: int,
    header: Mapping[str, Any],
    items: Sequence[Mapping[str, Any]],
) -> None:
    inspection = get_inspection(conn, inspection_id)
    if inspection["estimate_id"] is not None:
        raise InUse(
            f"This check has been quoted as {inspection['estimate_no']}. "
            "Edit that estimate instead."
        )
    with transaction(conn):
        _update(conn, "inspections", inspection_id, _pick(header, INSPECTION_HEADER_FIELDS))
        _write_inspection_items(conn, inspection_id, items)


def get_inspection(conn: sqlite3.Connection, inspection_id: int) -> Row:
    row = conn.execute(
        """
        SELECT i.*,
               c.name     AS customer_name,
               c.name_ar  AS customer_name_ar,
               c.phone    AS customer_phone,
               v.plate_no, v.make, v.model, v.model_year,
               e.estimate_no
          FROM inspections i
          JOIN customers c ON c.id = i.customer_id
     LEFT JOIN vehicles  v ON v.id = i.vehicle_id
     LEFT JOIN estimates e ON e.id = i.estimate_id
         WHERE i.id = ?
        """,
        (inspection_id,),
    ).fetchone()
    if row is None:
        raise NotFound(f"Inspection {inspection_id} not found.")
    return row


def get_inspection_items(conn: sqlite3.Connection, inspection_id: int) -> list[Row]:
    return _all(
        conn,
        """
        SELECT t.*, k.title_en AS issue_title, k.title_ar AS issue_title_ar,
               k.severity      AS issue_severity
          FROM inspection_items t
     LEFT JOIN known_issues k ON k.id = t.known_issue_id
         WHERE t.inspection_id = ?
         ORDER BY t.line_no
        """,
        (inspection_id,),
    )


def list_inspections(conn: sqlite3.Connection, limit: int = 200) -> list[Row]:
    return _all(
        conn,
        "SELECT * FROM v_inspections ORDER BY inspected_on DESC, id DESC LIMIT ?",
        (limit,),
    )


def inspections_for_vehicle(conn: sqlite3.Connection, vehicle_id: int) -> list[Row]:
    return _all(
        conn,
        """
        SELECT * FROM v_inspections
         WHERE id IN (SELECT id FROM inspections WHERE vehicle_id = ?)
         ORDER BY inspected_on DESC
        """,
        (vehicle_id,),
    )


def convert_inspection_to_estimate(conn: sqlite3.Connection, inspection_id: int) -> int:
    """Turn the findings marked for quoting into a draft estimate.

    Only the rows ticked for quoting, and only those carrying a price: a
    finding with no price is a note to the customer, not a line on a bill,
    and quoting it at zero would say the work is free.

    Refuses a second time round. The inspection records what was found; the
    estimate is the offer made about it, and two offers from one check is how
    a customer ends up with two different prices for the same brake pads.
    """
    inspection = get_inspection(conn, inspection_id)
    if inspection["estimate_id"] is not None:
        raise InUse(
            f"This check has already been quoted as {inspection['estimate_no']}."
        )

    settings = get_settings(conn)
    items = [
        {
            "catalog_item_id": item["catalog_item_id"],
            "description": item["finding"] or item["area"],
            "description_ar": item["finding_ar"] or item["area_ar"],
            "kind": "service",
            "unit": "pcs",
            "qty_milli": item["qty_milli"],
            "unit_price_minor": item["unit_price_minor"],
        }
        for item in get_inspection_items(conn, inspection_id)
        if item["quote_it"] and item["unit_price_minor"] > 0
    ]
    if not items:
        raise InUse(
            "Nothing on this check is marked for quoting with a price on it."
        )

    with transaction(conn):
        estimate_id = create_estimate(
            conn,
            {
                "customer_id": inspection["customer_id"],
                "vehicle_id": inspection["vehicle_id"],
                "issue_date": date.today().isoformat(),
                "valid_until": None,
                "status": "draft",
                "vat_rate_bp": settings["vat_rate_bp"],
                "prices_include_vat": 0,
                "currency_code": settings["currency_code"],
                "discount_minor": 0,
                "discount_mode": "amount",
                "discount_rate_bp": 0,
                "notes": inspection["summary"],
                "inspection_id": inspection_id,
            },
            items,
        )
        conn.execute(
            """
            UPDATE inspections
               SET estimate_id = ?, status = 'quoted', updated_at = datetime('now')
             WHERE id = ?
            """,
            (estimate_id, inspection_id),
        )
    return estimate_id
