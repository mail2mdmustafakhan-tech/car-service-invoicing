"""Tests for the invoice arithmetic.

These are the most important tests in the project. Everything else can be
fixed later; a totals bug means a customer was charged the wrong amount and
the paperwork is already out of the door.
"""

from __future__ import annotations

import pytest

from app.invoicing import (
    balance_due,
    compute_totals,
    line_total,
    net_from_gross,
    payment_state,
    vat_on_net,
)
from app.money import format_money, format_qty, rate_to_bp, to_milli, to_minor

# --------------------------------------------------------------------------
# Line totals
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "qty_milli, price_minor, expected",
    [
        (1000, 15000, 15000),      # 1 x 150.00
        (500, 15000, 7500),        # half an hour
        (2500, 4000, 10000),       # 2.5 x 40.00
        (3000, 2533, 7599),        # 3 x 25.33 -- no float drift
        (1500, 3333, 5000),        # 1.5 x 33.33 = 49.995, rounds up to 50.00
        (1000, 0, 0),              # a zero-priced line is allowed
        (333, 10000, 3330),        # 0.333 x 100.00
    ],
)
def test_line_total(qty_milli, price_minor, expected):
    assert line_total(qty_milli, price_minor) == expected


def test_line_total_rejects_negatives():
    with pytest.raises(ValueError):
        line_total(-1000, 100)
    with pytest.raises(ValueError):
        line_total(1000, -100)


def test_many_small_lines_do_not_drift():
    """A hundred lines of 0.10 must total exactly 10.00, not 9.99 or 10.01.

    This is the failure that integer minor units exist to prevent: in
    floating point, 0.1 added a hundred times is 9.999999999999998.
    """
    totals = compute_totals([(1000, 10)] * 100, vat_rate_bp=0)
    assert totals.total_minor == 1000
    assert format_money(totals.total_minor) == "10.00"


# --------------------------------------------------------------------------
# VAT
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "net, rate_bp, expected",
    [
        (10000, 1500, 1500),    # 15% of 100.00
        (10000, 0, 0),          # not VAT registered
        (3333, 1500, 500),      # 4.9995 rounds to 5.00
        (1, 1500, 0),           # 0.0015 rounds to nothing
        (10000, 500, 500),      # a 5% rate
        (10000, 750, 750),      # a 7.5% rate
    ],
)
def test_vat_on_net(net, rate_bp, expected):
    assert vat_on_net(net, rate_bp) == expected


@pytest.mark.parametrize(
    "gross, rate_bp, expected_net",
    [
        (11500, 1500, 10000),
        (10000, 0, 10000),
        (100, 1500, 87),
    ],
)
def test_net_from_gross(gross, rate_bp, expected_net):
    assert net_from_gross(gross, rate_bp) == expected_net


def test_vat_extraction_round_trips():
    """Stripping VAT out and adding it back must land on the original total."""
    for gross in range(100, 100_000, 977):
        net = net_from_gross(gross, 1500)
        assert net + (gross - net) == gross


# --------------------------------------------------------------------------
# Whole invoices
# --------------------------------------------------------------------------

def test_simple_invoice():
    totals = compute_totals(
        [(1000, 18500), (1500, 9000), (1000, 4500)],  # oil change, 1.5h labour, filter
        vat_rate_bp=1500,
    )
    assert totals.subtotal_minor == 36500   # 365.00
    assert totals.discount_minor == 0
    assert totals.taxable_minor == 36500
    assert totals.vat_minor == 5475         # 54.75
    assert totals.total_minor == 41975      # 419.75


def test_discount_reduces_the_vat_too():
    """A discount is a price reduction, so tax is charged on the lower price."""
    totals = compute_totals([(1000, 36500)], vat_rate_bp=1500, discount_minor=2500)
    assert totals.subtotal_minor == 36500
    assert totals.discount_minor == 2500
    assert totals.taxable_minor == 34000
    assert totals.vat_minor == 5100
    assert totals.total_minor == 39100


def test_discount_larger_than_the_bill_is_clamped():
    """An invoice can be reduced to zero but never below it."""
    totals = compute_totals([(1000, 10000)], vat_rate_bp=1500, discount_minor=99999)
    assert totals.discount_minor == 10000
    assert totals.taxable_minor == 0
    assert totals.vat_minor == 0
    assert totals.total_minor == 0


def test_negative_discount_is_rejected():
    with pytest.raises(ValueError):
        compute_totals([(1000, 10000)], vat_rate_bp=1500, discount_minor=-100)


def test_vat_inclusive_pricing():
    """With tax-inclusive prices the customer pays the quoted figure exactly."""
    totals = compute_totals([(1000, 11500)], vat_rate_bp=1500, prices_include_vat=True)
    assert totals.subtotal_minor == 11500
    assert totals.taxable_minor == 10000
    assert totals.vat_minor == 1500
    assert totals.total_minor == 11500      # the price on the board


def test_vat_inclusive_parts_always_add_up():
    """However the rounding falls, net + VAT must equal the gross exactly."""
    for gross in (999, 1234, 5050, 78999, 100001):
        totals = compute_totals(
            [(1000, gross)], vat_rate_bp=1500, prices_include_vat=True
        )
        assert totals.taxable_minor + totals.vat_minor == totals.total_minor == gross


def test_zero_rated_invoice():
    totals = compute_totals([(2000, 5000)], vat_rate_bp=0)
    assert totals.vat_minor == 0
    assert totals.total_minor == totals.taxable_minor == 10000


def test_empty_invoice_is_all_zeros():
    totals = compute_totals([], vat_rate_bp=1500)
    assert totals.as_dict() == {
        "subtotal_minor": 0,
        "discount_minor": 0,
        "taxable_minor": 0,
        "vat_minor": 0,
        "total_minor": 0,
    }


def test_accepts_objects_as_well_as_tuples():
    class Line:
        def __init__(self, qty_milli, unit_price_minor):
            self.qty_milli = qty_milli
            self.unit_price_minor = unit_price_minor

    from_objects = compute_totals([Line(1000, 10000), Line(2000, 500)], vat_rate_bp=1500)
    from_tuples = compute_totals([(1000, 10000), (2000, 500)], vat_rate_bp=1500)
    assert from_objects == from_tuples


# --------------------------------------------------------------------------
# Payment state
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "status, total, paid, expected",
    [
        ("draft", 10000, 0, "draft"),
        ("draft", 10000, 10000, "draft"),     # drafts are never "paid"
        ("void", 10000, 10000, "void"),
        ("issued", 10000, 0, "unpaid"),
        ("issued", 10000, 1, "partially_paid"),
        ("issued", 10000, 9999, "partially_paid"),
        ("issued", 10000, 10000, "paid"),
        ("issued", 10000, 12000, "paid"),     # overpayment still reads as paid
        ("issued", 0, 0, "paid"),             # a zero invoice owes nothing
    ],
)
def test_payment_state(status, total, paid, expected):
    assert payment_state(status, total, paid) == expected


@pytest.mark.parametrize(
    "total, paid, expected",
    [(10000, 0, 10000), (10000, 4000, 6000), (10000, 10000, 0), (10000, 11000, 0)],
)
def test_balance_due_never_goes_negative(total, paid, expected):
    assert balance_due(total, paid) == expected


# --------------------------------------------------------------------------
# Parsing what the user typed
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "text, expected",
    [
        ("150.75", 15075),
        ("150", 15000),
        ("1,200.50", 120050),
        (" 99.99 ", 9999),
        ("0", 0),
        ("١٥٠", 15000),            # Arabic-Indic digits
        ("١٢٫٥", 1250),            # Arabic decimal separator
        ("150.75 SAR", 15075),
        ("150.754", 15075),        # rounds to the halala
        ("150.755", 15076),        # halves go up
    ],
)
def test_amount_parsing(text, expected):
    assert to_minor(text) == expected


@pytest.mark.parametrize(
    "text, expected", [("1", 1000), ("0.5", 500), ("2.25", 2250), ("١٫٥", 1500)]
)
def test_quantity_parsing(text, expected):
    assert to_milli(text) == expected


@pytest.mark.parametrize("text, expected", [("15", 1500), ("7.5", 750), ("0", 0)])
def test_rate_parsing(text, expected):
    assert rate_to_bp(text) == expected


@pytest.mark.parametrize(
    "minor, expected", [(1234567, "12,345.67"), (0, "0.00"), (5, "0.05"), (-500, "-5.00")]
)
def test_money_formatting(minor, expected):
    assert format_money(minor) == expected


@pytest.mark.parametrize(
    "milli, expected", [(1000, "1"), (500, "0.5"), (2250, "2.25"), (10000, "10")]
)
def test_quantity_formatting(milli, expected):
    assert format_qty(milli) == expected
