"""The whole business as one Excel workbook.

The zip backup is the one to restore from: it holds the database and every
attachment, and putting it back gives you the system exactly as it was. What
it cannot do is be *read*. Open ``carservice.db`` in anything but this
software and you get binary noise.

That matters more than it sounds. The records here outlive the software by
law -- Saudi bookkeeping rules expect invoices to be produceable years after
the fact -- and "you need the application" is a poor answer when the
application is what has stopped working, or when an accountant, an auditor or
a buyer asks for the books. A workbook anyone can double-click is the answer
that survives this program being deleted.

So: the zip restores, the workbook reads, and the two are offered side by
side rather than one pretending to be the other. :func:`write_workbook` is
deliberately explicit that it produces a readable copy and not a backup.

Figures are written as real numbers, not text, so a column actually sums in
Excel. They come from the ``v_*`` reporting views wherever one exists, which
is what those views were built for -- they expose decimals rather than the
integer minor units the tables store, so nobody has to know that a riyal is
kept as 100 halalas to read their own takings.
"""

from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path
from typing import Any

#: What goes in the workbook, in the order a person would look for it.
#:
#: ``(sheet title, source, description)``. The source is a view where one
#: exists. Tables holding no business record -- ``schema_migrations``,
#: ``branding``, ``import_batches`` -- are left out: they would be noise in a
#: file whose whole purpose is being readable by somebody in a hurry.
SHEETS: list[tuple[str, str, str]] = [
    ("Customers", "customers", "Every customer and their contact details"),
    ("Vehicles", "vehicles", "Every vehicle, linked to its customer"),
    ("Services and parts", "catalog_items", "The price list"),
    ("Estimates", "v_estimates", "Quotes, with their status and totals"),
    ("Estimate items", "estimate_items", "The lines of each quote"),
    ("Repair contracts", "v_repair_orders", "Signed contracts and their totals"),
    ("Contract work", "repair_order_items", "Work recorded against each contract"),
    ("Contract parts", "v_repair_order_parts", "Parts used on each contract"),
    ("Invoices", "v_invoices", "Every invoice issued, tax and plain"),
    ("Invoice lines", "v_invoice_lines", "The lines of each invoice"),
    ("Payments", "v_payments", "Money received, against which invoice"),
    ("Attachments", "customer_attachments", "Scanned documents held per customer"),
]

#: Columns never worth a reader's attention, or actively unhelpful in a
#: spreadsheet: stored filenames are generated, not what anyone named the file.
HIDDEN_COLUMNS = {"stored_name"}

#: Columns holding money, which get two decimal places.
#:
#: Without this a total of 810.00 arrives in the cell as the number 810 and
#: Excel shows "810", while 931.50 shows as "931.5". Figures that do not line
#: up down a column are figures somebody has to check by hand.
MONEY_WORDS = ("subtotal", "taxable", "total", "amount", "price", "balance", "paid", "discount")

#: ...except where one of those words appears in something that is not money.
#: ``vat_rate_percent`` is a rate; ``vat_number`` is a registration.
NOT_MONEY_WORDS = ("rate", "number", "count", "qty", "no", "id")

MONEY_FORMAT = "#,##0.00"


def is_money(column: str) -> bool:
    """Whether a column name describes an amount of money.

    >>> is_money("total_minor"), is_money("vat_amount"), is_money("unit_price")
    (True, True, True)
    >>> is_money("vat_rate_percent"), is_money("vat_number"), is_money("line_no")
    (False, False, False)
    >>> is_money("description"), is_money("qty")
    (False, False)
    """
    parts = set(column.lower().split("_"))
    if parts & set(NOT_MONEY_WORDS):
        return False
    return any(word in column.lower() for word in MONEY_WORDS)


def _rows(conn: sqlite3.Connection, source: str) -> tuple[list[str], list[tuple[Any, ...]]]:
    """Read one table or view, dropping columns nobody would want to see."""
    cursor = conn.execute(f"SELECT * FROM [{source}]")  # noqa: S608 - fixed names above
    names = [d[0] for d in cursor.description]
    keep = [i for i, name in enumerate(names) if name not in HIDDEN_COLUMNS]
    headers = [names[i] for i in keep]
    rows = [tuple(row[i] for i in keep) for row in cursor.fetchall()]
    return headers, rows


def _heading(name: str) -> str:
    """``vat_rate_bp`` is a column name. "Vat rate bp" is a heading."""
    return name.replace("_", " ").capitalize()


def write_workbook(destination: Path | str, conn: sqlite3.Connection) -> Path:
    """Write every business record to an .xlsx file and return its path.

    Raises ``ModuleNotFoundError`` if openpyxl is missing, which the caller
    turns into a message rather than a stack trace.
    """
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)

    book = Workbook()
    book.remove(book.active)

    head_font = Font(bold=True, color="FFFFFF")
    head_fill = PatternFill("solid", fgColor="16202B")

    # A first sheet saying what this file is, because in two years the person
    # opening it will not be the person who downloaded it.
    cover = book.create_sheet("About this file")
    business = conn.execute(
        "SELECT business_name_en FROM settings WHERE id = 1"
    ).fetchone()
    cover.append([business[0] if business else "Car service"])
    cover.append([f"Records exported {date.today().isoformat()}"])
    cover.append([])
    cover.append(["This workbook is a READABLE copy of the records. It is not a backup."])
    cover.append(["It cannot be loaded back into the software."])
    cover.append([])
    cover.append(["To restore the system, use the zip backup, which holds the"])
    cover.append(["database and the scanned attachments together."])
    cover.append([])
    cover.append(["Sheet", "What it holds", "Rows"])
    cover["A1"].font = Font(bold=True, size=14)
    cover["A4"].font = Font(bold=True)
    for cell in cover[10]:
        cell.font = head_font
        cell.fill = head_fill

    for title, source, description in SHEETS:
        try:
            headers, rows = _rows(conn, source)
        except sqlite3.OperationalError:
            # A view or table from a future or past schema. Skipping one sheet
            # is better than failing the whole export.
            continue

        cover.append([title, description, len(rows)])

        sheet = book.create_sheet(title[:31])
        sheet.append([_heading(h) for h in headers])
        for row in rows:
            sheet.append(list(row))

        for cell in sheet[1]:
            cell.font = head_font
            cell.fill = head_fill
            cell.alignment = Alignment(vertical="center")
        # The headings stay put while someone scrolls a thousand invoices.
        sheet.freeze_panes = "A2"
        if rows:
            sheet.auto_filter.ref = sheet.dimensions

        # Width from the widest value actually present, capped so one long
        # note does not push every other column off the screen.
        for index, header in enumerate(headers, start=1):
            letter = get_column_letter(index)
            longest = max(
                [len(_heading(header))]
                + [len(str(row[index - 1])) for row in rows[:200] if row[index - 1] is not None]
            )
            sheet.column_dimensions[letter].width = min(max(longest + 2, 10), 48)

            if is_money(header):
                for cell in sheet[letter][1:]:
                    cell.number_format = MONEY_FORMAT

    cover.column_dimensions["A"].width = 24
    cover.column_dimensions["B"].width = 52
    cover.column_dimensions["C"].width = 10

    book.save(dest)
    return dest
