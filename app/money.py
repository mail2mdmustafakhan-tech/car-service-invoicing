"""Money and quantity handling.

Everything about money in this application follows one rule: **money is never
stored or calculated as a floating-point number.** Floats cannot represent
0.10 exactly, so adding them up drifts by fractions of a halala, and those
fractions eventually make an invoice total disagree with the sum of its lines.

Instead:

* Money is an ``int`` in *minor units* -- halalas for SAR, cents for USD.
  ``150.75`` is ``15075``. Call it a "minor" amount throughout the code.
* Quantity is an ``int`` in thousandths, called "milli".
  ``1`` is ``1000``, ``0.5`` is ``500``, ``2.25`` is ``2250``.
* Any division or percentage uses :class:`decimal.Decimal` and rounds
  half-up, the convention people expect on a printed invoice.

Converting happens only at the edges: parsing what the user typed in, and
formatting what gets displayed.
"""

from __future__ import annotations

from decimal import ROUND_HALF_UP, Decimal, InvalidOperation

#: Minor units per major unit. 100 halalas = 1 SAR.
MINOR_PER_MAJOR = 100

#: Milli-units per whole quantity unit.
MILLI_PER_UNIT = 1000

_CENT = Decimal(1)


class MoneyError(ValueError):
    """Raised when text cannot be read as an amount or a quantity."""


def round_half_up(value: Decimal) -> int:
    """Round a ``Decimal`` to the nearest whole number, halves going up.

    Python's built-in :func:`round` uses banker's rounding, where ``0.5``
    rounds to ``0`` and ``1.5`` rounds to ``2``. That surprises people reading
    an invoice, so this function always rounds ``.5`` away from zero.
    """
    return int(value.quantize(_CENT, rounding=ROUND_HALF_UP))


def _to_decimal(raw: str | int | float | Decimal, *, what: str) -> Decimal:
    """Read user input as a ``Decimal``, tolerating the ways people type numbers."""
    if isinstance(raw, Decimal):
        return raw
    if isinstance(raw, int):
        return Decimal(raw)
    if isinstance(raw, float):
        # Route through str so 0.1 becomes Decimal("0.1") and not the
        # 0.1000000000000000055511151231257827 that the float actually holds.
        return Decimal(str(raw))

    text = str(raw).strip()
    if not text:
        raise MoneyError(f"{what} is required")

    # Tolerate thousands separators, currency symbols and Arabic-Indic digits.
    text = text.replace(",", "").replace("٬", "").replace("،", "")
    text = text.replace("SAR", "").replace("ر.س", "").replace("﷼", "").strip()
    text = text.translate(_ARABIC_DIGITS)
    text = text.replace("٫", ".")  # Arabic decimal separator

    try:
        return Decimal(text)
    except InvalidOperation as exc:
        raise MoneyError(f"{what} is not a valid number: {raw!r}") from exc


#: Maps Arabic-Indic and Eastern Arabic-Indic digits onto ASCII digits, so a
#: user with an Arabic keyboard layout can type amounts naturally.
_ARABIC_DIGITS = str.maketrans("٠١٢٣٤٥٦٧٨٩۰۱۲۳۴۵۶۷۸۹", "01234567890123456789")


# --------------------------------------------------------------------------
# Money
# --------------------------------------------------------------------------

def to_minor(raw: str | int | float | Decimal, *, what: str = "Amount") -> int:
    """Parse a user-entered amount into integer minor units.

    >>> to_minor("150.75")
    15075
    >>> to_minor("1,200")
    120000
    >>> to_minor(0)
    0
    """
    amount = _to_decimal(raw, what=what)
    return round_half_up(amount * MINOR_PER_MAJOR)


def from_minor(minor: int) -> Decimal:
    """Convert integer minor units back to a ``Decimal`` major amount.

    >>> from_minor(15075)
    Decimal('150.75')
    """
    return (Decimal(int(minor)) / MINOR_PER_MAJOR).quantize(Decimal("0.01"))


def format_money(minor: int, currency: str = "") -> str:
    """Format minor units for display, with thousands separators.

    >>> format_money(1234567, "SAR")
    '12,345.67 SAR'
    >>> format_money(-500)
    '-5.00'
    """
    amount = from_minor(minor)
    text = f"{amount:,.2f}"
    return f"{text} {currency}".strip() if currency else text


def multiply_minor(minor: int, factor: Decimal) -> int:
    """Multiply a minor amount by a ``Decimal`` factor, rounding half-up."""
    return round_half_up(Decimal(int(minor)) * factor)


# --------------------------------------------------------------------------
# Quantity
# --------------------------------------------------------------------------

def to_milli(raw: str | int | float | Decimal, *, what: str = "Quantity") -> int:
    """Parse a user-entered quantity into thousandths.

    >>> to_milli("1")
    1000
    >>> to_milli("0.5")
    500
    >>> to_milli("2.25")
    2250
    """
    qty = _to_decimal(raw, what=what)
    return round_half_up(qty * MILLI_PER_UNIT)


def from_milli(milli: int) -> Decimal:
    """Convert thousandths back to a ``Decimal`` quantity.

    >>> from_milli(2250)
    Decimal('2.250')
    """
    return (Decimal(int(milli)) / MILLI_PER_UNIT).quantize(Decimal("0.001"))


def format_qty(milli: int) -> str:
    """Format a quantity without pointless trailing zeros.

    >>> format_qty(1000)
    '1'
    >>> format_qty(500)
    '0.5'
    >>> format_qty(2250)
    '2.25'
    """
    qty = from_milli(milli).normalize()
    text = f"{qty:f}"
    return text


# --------------------------------------------------------------------------
# VAT rate
# --------------------------------------------------------------------------

def rate_to_bp(raw: str | int | float | Decimal) -> int:
    """Parse a VAT percentage into hundredths of a percent ("basis points").

    15% becomes 1500. Storing the rate as an integer keeps it exact.

    >>> rate_to_bp("15")
    1500
    >>> rate_to_bp("7.5")
    750
    >>> rate_to_bp(0)
    0
    """
    pct = _to_decimal(raw, what="VAT rate")
    if pct < 0:
        raise MoneyError("VAT rate cannot be negative")
    return round_half_up(pct * 100)


def rate_from_bp(bp: int) -> Decimal:
    """Convert stored basis points back to a percentage.

    >>> rate_from_bp(1500)
    Decimal('15.00')
    """
    return (Decimal(int(bp)) / 100).quantize(Decimal("0.01"))


def format_rate(bp: int) -> str:
    """Format a VAT rate for display, without trailing zeros.

    >>> format_rate(1500)
    '15'
    >>> format_rate(750)
    '7.5'
    """
    return f"{rate_from_bp(bp).normalize():f}"
