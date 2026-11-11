"""Turning submitted HTML forms into clean values.

Browsers submit everything as text: a blank number box arrives as ``""``, an
unticked checkbox does not arrive at all, and a repeated field arrives as a
list. These helpers absorb that so the route handlers in :mod:`app.main` stay
readable, and so nothing untrusted reaches the database untyped.

Validation raises :class:`FormError`, which the web layer catches and shows
back on the form rather than as a stack trace.
"""

from __future__ import annotations

from collections.abc import Sequence
from datetime import date
from typing import Any

from .money import MoneyError, to_milli, to_minor


class FormError(ValueError):
    """A submitted form could not be accepted. The message is shown to the user."""


def text(raw: str | None, *, default: str = "") -> str:
    """A trimmed string, never ``None``."""
    return (raw or "").strip() or default


def required_text(raw: str | None, *, field: str) -> str:
    value = text(raw)
    if not value:
        raise FormError(f"{field} is required.")
    return value


def opt_int(raw: str | None) -> int | None:
    """An integer, or ``None`` when the box was left empty."""
    value = text(raw)
    if not value:
        return None
    try:
        return int(float(value.replace(",", "")))
    except ValueError as exc:
        raise FormError(f"{raw!r} is not a whole number.") from exc


def checkbox(raw: str | None) -> int:
    """``1`` when ticked, ``0`` when not.

    An unticked checkbox is simply absent from the submission, which arrives
    here as ``None``.
    """
    return 1 if text(raw).lower() in {"1", "on", "true", "yes"} else 0


def iso_date(raw: str | None, *, default_today: bool = False) -> str | None:
    """Validate a ``YYYY-MM-DD`` date from a date input."""
    value = text(raw)
    if not value:
        return date.today().isoformat() if default_today else None
    try:
        return date.fromisoformat(value).isoformat()
    except ValueError as exc:
        raise FormError(f"{value!r} is not a valid date.") from exc


def money(raw: str | None, *, field: str = "Amount", default: int = 0) -> int:
    """Parse an amount into minor units, empty meaning ``default``."""
    value = text(raw)
    if not value:
        return default
    try:
        return to_minor(value, what=field)
    except MoneyError as exc:
        raise FormError(str(exc)) from exc


def quantity(raw: str | None, *, field: str = "Quantity") -> int:
    """Parse a quantity into thousandths. Must be greater than zero."""
    value = text(raw)
    if not value:
        raise FormError(f"{field} is required.")
    try:
        milli = to_milli(value, what=field)
    except MoneyError as exc:
        raise FormError(str(exc)) from exc
    if milli <= 0:
        raise FormError(f"{field} must be greater than zero.")
    return milli


def vat_rate(raw: str | None, *, default: int = 0) -> int:
    """Parse a VAT percentage into basis points."""
    from .money import rate_to_bp

    value = text(raw)
    if not value:
        return default
    try:
        return rate_to_bp(value)
    except MoneyError as exc:
        raise FormError(str(exc)) from exc


def one_of(raw: str | None, allowed: Sequence[str], *, default: str) -> str:
    """Keep a value only if it is one of the options we offer."""
    value = text(raw)
    return value if value in allowed else default


# --------------------------------------------------------------------------
# Invoice lines
# --------------------------------------------------------------------------

def parse_invoice_lines(
    *,
    descriptions: Sequence[str],
    descriptions_ar: Sequence[str],
    kinds: Sequence[str],
    units: Sequence[str],
    quantities: Sequence[str],
    prices: Sequence[str],
    catalog_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """Assemble the repeated line fields into a list of line dictionaries.

    The invoice form posts one parallel list per column, so row *n* is
    ``descriptions[n]``, ``quantities[n]`` and so on. Completely blank rows are
    dropped silently -- the form always keeps a spare empty row at the bottom,
    and leaving it untouched should not be an error.
    """
    def at(seq: Sequence[str], index: int) -> str:
        return seq[index] if index < len(seq) else ""

    row_count = max(
        len(descriptions), len(quantities), len(prices), len(catalog_ids), 0
    )
    lines: list[dict[str, Any]] = []

    for i in range(row_count):
        description = text(at(descriptions, i))
        qty_raw = text(at(quantities, i))
        price_raw = text(at(prices, i))

        if not description and not qty_raw and not price_raw:
            continue  # untouched spare row
        if not description:
            raise FormError(f"Line {len(lines) + 1}: a description is required.")

        lines.append(
            {
                "catalog_item_id": opt_int(at(catalog_ids, i)),
                "description": description,
                "description_ar": text(at(descriptions_ar, i)),
                "kind": one_of(at(kinds, i), ("service", "part"), default="service"),
                "unit": text(at(units, i), default="pcs"),
                "qty_milli": quantity(qty_raw or "1", field=f"Line {len(lines) + 1} quantity"),
                "unit_price_minor": money(
                    price_raw, field=f"Line {len(lines) + 1} unit price"
                ),
            }
        )

    if not lines:
        raise FormError("Add at least one item to the invoice.")
    return lines


# --------------------------------------------------------------------------
# Repair contract lines
# --------------------------------------------------------------------------

def _at(seq: Sequence[str], index: int) -> str:
    return seq[index] if index < len(seq) else ""


def parse_contract_items(
    *,
    descriptions: Sequence[str],
    descriptions_ar: Sequence[str],
    expenses: Sequence[str],
    remarks: Sequence[str],
    catalog_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """The three columns of the repair contract's main table.

    Unlike an invoice line, a contract line may legitimately carry no money:
    "check the air conditioning" with the technician's finding beside it and
    nothing in the expenses column is a perfectly normal row. Only the
    description is required.
    """
    row_count = max(len(descriptions), len(expenses), len(remarks), 0)
    items: list[dict[str, Any]] = []

    for i in range(row_count):
        description = text(_at(descriptions, i))
        expense_raw = text(_at(expenses, i))
        remark = text(_at(remarks, i))

        if not description and not expense_raw and not remark:
            continue  # untouched spare row
        if not description:
            raise FormError(
                f"Repair line {len(items) + 1}: describe the work before adding a cost or a remark."
            )

        items.append(
            {
                "catalog_item_id": opt_int(_at(catalog_ids, i)),
                "description": description,
                "description_ar": text(_at(descriptions_ar, i)),
                "expense_minor": money(
                    expense_raw, field=f"Repair line {len(items) + 1} cost"
                ),
                "technician_remarks": remark,
            }
        )

    if not items:
        raise FormError("Add at least one repair to the contract.")
    return items


def parse_contract_parts(
    *,
    part_numbers: Sequence[str],
    descriptions: Sequence[str],
    descriptions_ar: Sequence[str],
    quantities: Sequence[str],
    prices: Sequence[str],
    sourced: Sequence[str],
    catalog_ids: Sequence[str],
) -> list[dict[str, Any]]:
    """The spare parts sheet. A contract may have no parts at all.

    ``sourced`` is a select rather than a checkbox on purpose: an unticked
    checkbox is simply absent from the submission, which would shift every
    later row's value up by one and silently attach the wrong flag to the
    wrong part. A select always submits, so the columns stay aligned.
    """
    row_count = max(len(descriptions), len(quantities), len(prices), 0)
    parts: list[dict[str, Any]] = []

    for i in range(row_count):
        description = text(_at(descriptions, i))
        part_number = text(_at(part_numbers, i))
        qty_raw = text(_at(quantities, i))
        price_raw = text(_at(prices, i))

        if not description and not part_number and not price_raw:
            continue
        if not description:
            raise FormError(f"Part line {len(parts) + 1}: a part name is required.")

        parts.append(
            {
                "catalog_item_id": opt_int(_at(catalog_ids, i)),
                "part_number": part_number,
                "description": description,
                "description_ar": text(_at(descriptions_ar, i)),
                "qty_milli": quantity(
                    qty_raw or "1", field=f"Part line {len(parts) + 1} quantity"
                ),
                "unit_price_minor": money(
                    price_raw, field=f"Part line {len(parts) + 1} price"
                ),
                "sourced_externally": 1 if text(_at(sourced, i)) == "1" else 0,
            }
        )

    return parts
