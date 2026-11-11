"""Invoice arithmetic.

This module is deliberately *pure*: it has no database, no web framework and
no global state, just functions that take numbers and return numbers. That
makes it the easiest part of the application to test, and the totals are the
part you least want to get wrong -- so this is where the test coverage goes.

Every amount in and out is an integer in minor units (see :mod:`app.money`).
"""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass
from decimal import Decimal
from typing import Protocol

from .money import MILLI_PER_UNIT, round_half_up

#: Basis points in 100%. A rate of 1500bp is 15%, so 1500/10000 = 0.15.
BP_PER_UNIT = 10_000


class LineLike(Protocol):
    """Anything with a quantity and a unit price can be totalled."""

    qty_milli: int
    unit_price_minor: int


@dataclass(frozen=True)
class InvoiceTotals:
    """The computed money figures for one invoice, all in minor units."""

    subtotal_minor: int
    """Sum of all line totals, before any discount."""

    discount_minor: int
    """Discount actually applied -- never more than the subtotal."""

    taxable_minor: int
    """The amount VAT is calculated on (net of discount, excluding VAT)."""

    vat_minor: int
    """VAT charged."""

    total_minor: int
    """What the customer owes: ``taxable_minor + vat_minor``."""

    def as_dict(self) -> dict[str, int]:
        return {
            "subtotal_minor": self.subtotal_minor,
            "discount_minor": self.discount_minor,
            "taxable_minor": self.taxable_minor,
            "vat_minor": self.vat_minor,
            "total_minor": self.total_minor,
        }


def line_total(qty_milli: int, unit_price_minor: int) -> int:
    """Total for a single invoice line, rounded half-up to the nearest halala.

    >>> line_total(1000, 15000)      # 1 x 150.00
    15000
    >>> line_total(500, 15000)       # 0.5 x 150.00
    7500
    >>> line_total(3000, 2533)       # 3 x 25.33
    7599
    >>> line_total(1500, 3333)       # 1.5 x 33.33 = 49.995 -> 50.00
    5000
    """
    if qty_milli < 0:
        raise ValueError("Quantity cannot be negative")
    if unit_price_minor < 0:
        raise ValueError("Unit price cannot be negative")
    exact = Decimal(qty_milli) * Decimal(unit_price_minor) / MILLI_PER_UNIT
    return round_half_up(exact)


def vat_on_net(net_minor: int, vat_rate_bp: int) -> int:
    """VAT to add on top of a VAT-exclusive amount.

    >>> vat_on_net(10000, 1500)      # 15% of 100.00
    1500
    >>> vat_on_net(3333, 1500)       # 15% of 33.33 = 4.9995 -> 5.00
    500
    >>> vat_on_net(10000, 0)
    0
    """
    if vat_rate_bp < 0:
        raise ValueError("VAT rate cannot be negative")
    return round_half_up(Decimal(net_minor) * vat_rate_bp / BP_PER_UNIT)


def net_from_gross(gross_minor: int, vat_rate_bp: int) -> int:
    """Strip VAT out of a VAT-inclusive amount.

    Used when the shop quotes prices with VAT already included, so the invoice
    has to work backwards to show the tax separately.

    >>> net_from_gross(11500, 1500)  # 115.00 inc. 15% VAT
    10000
    >>> net_from_gross(10000, 0)
    10000
    """
    if vat_rate_bp < 0:
        raise ValueError("VAT rate cannot be negative")
    return round_half_up(
        Decimal(gross_minor) * BP_PER_UNIT / (BP_PER_UNIT + vat_rate_bp)
    )


def compute_totals(
    lines: Iterable[LineLike] | Iterable[tuple[int, int]],
    *,
    vat_rate_bp: int,
    discount_minor: int = 0,
    prices_include_vat: bool = False,
) -> InvoiceTotals:
    """Total up an invoice.

    ``lines`` may be objects with ``qty_milli`` / ``unit_price_minor``
    attributes, or plain ``(qty_milli, unit_price_minor)`` tuples.

    The discount is taken off the *line subtotal* before VAT is worked out, so
    a discount reduces the tax as well -- which is how a price reduction is
    normally treated. A discount larger than the subtotal is clamped, so an
    invoice can never go negative.

    With ``prices_include_vat`` the entered prices already contain VAT, so the
    subtotal is a gross figure and the tax is extracted from it rather than
    added to it. Either way ``total_minor`` is what the customer pays.

    >>> t = compute_totals([(1000, 10000), (2000, 5000)], vat_rate_bp=1500)
    >>> t.subtotal_minor, t.vat_minor, t.total_minor
    (20000, 3000, 23000)

    >>> t = compute_totals([(1000, 11500)], vat_rate_bp=1500,
    ...                    prices_include_vat=True)
    >>> t.subtotal_minor, t.taxable_minor, t.vat_minor, t.total_minor
    (11500, 10000, 1500, 11500)
    """
    if discount_minor < 0:
        raise ValueError("Discount cannot be negative")

    subtotal = 0
    for item in lines:
        if isinstance(item, tuple):
            qty_milli, unit_price_minor = item
        else:
            qty_milli, unit_price_minor = item.qty_milli, item.unit_price_minor
        subtotal += line_total(qty_milli, unit_price_minor)

    discount = min(discount_minor, subtotal)
    after_discount = subtotal - discount

    if prices_include_vat:
        taxable = net_from_gross(after_discount, vat_rate_bp)
        vat = after_discount - taxable
        total = after_discount
    else:
        taxable = after_discount
        vat = vat_on_net(taxable, vat_rate_bp)
        total = taxable + vat

    return InvoiceTotals(
        subtotal_minor=subtotal,
        discount_minor=discount,
        taxable_minor=taxable,
        vat_minor=vat,
        total_minor=total,
    )


def payment_state(
    status: str, total_minor: int, paid_minor: int
) -> str:
    """Work out the label shown against an invoice.

    ``status`` is what the user set (draft/issued/void); the paid-ness is
    derived from the payments recorded, never stored, so it cannot drift out
    of step with the payment rows.

    >>> payment_state("issued", 10000, 0)
    'unpaid'
    >>> payment_state("issued", 10000, 4000)
    'partially_paid'
    >>> payment_state("issued", 10000, 10000)
    'paid'
    >>> payment_state("draft", 10000, 10000)
    'draft'
    """
    if status == "void":
        return "void"
    if status == "draft":
        return "draft"
    if total_minor <= 0:
        return "paid"
    if paid_minor >= total_minor:
        return "paid"
    if paid_minor > 0:
        return "partially_paid"
    return "unpaid"


def balance_due(total_minor: int, paid_minor: int) -> int:
    """How much is still owed. Never negative; overpayment shows as zero."""
    return max(0, total_minor - paid_minor)
