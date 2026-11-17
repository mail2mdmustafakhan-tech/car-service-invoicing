"""Where a part came from, and who made it.

The two questions are different -- a genuine BMW part can be bought from the
agency, found on the used market, or shipped from Germany -- but the same
names answer both, so one list serves both fields.

Nothing here is enforced by the database. These are suggestions offered as
you type, and anything typed instead is kept as written. A workshop finds a
new supplier far more often than anyone edits a constraint, and an origin
recorded in unexpected words is still worth more than one recorded wrongly
because the list had no room for the truth.
"""

from __future__ import annotations

#: ``(stored value, English, Arabic)``.
#:
#: The stored value is what lands in the database. For the suggestions it is
#: the English name, so what the person picked is what the column holds and a
#: spreadsheet of this data reads without a lookup table. Only the two
#: original answers keep short codes, because rows written before this list
#: existed already hold them.
SOURCES: list[tuple[str, str, str]] = [
    ("own_stock", "Own stock", "مخزوننا"),
    ("BMW", "BMW agency", "وكالة BMW"),
    ("Mercedes-Benz", "Mercedes-Benz agency", "وكالة مرسيدس"),
    ("Audi", "Audi agency", "وكالة أودي"),
    ("Volkswagen", "Volkswagen agency", "وكالة فولكس واجن"),
    ("Rolls-Royce", "Rolls-Royce agency", "وكالة رولز رويس"),
    ("Used market", "Used market", "السوق المستعمل"),
    ("Germany", "Imported from Germany", "مستورد من ألمانيا"),
    ("outside", "Other supplier", "مورد آخر"),
]

#: Who made the part, for the price list. Same names, without the word
#: "agency": a part is made by BMW whoever you bought it from.
MANUFACTURERS: list[tuple[str, str, str]] = [
    ("BMW", "BMW", "BMW"),
    ("Mercedes-Benz", "Mercedes-Benz", "مرسيدس بنز"),
    ("Audi", "Audi", "أودي"),
    ("Volkswagen", "Volkswagen", "فولكس واجن"),
    ("Rolls-Royce", "Rolls-Royce", "رولز رويس"),
    ("Used market", "Used market", "السوق المستعمل"),
    ("Germany", "Imported from Germany", "مستورد من ألمانيا"),
    ("Other", "Other", "أخرى"),
]

#: A part we did not already own was bought in for this customer, and the
#: contract's handling percentage applies to it. That is the only thing the
#: old yes/no column ever meant, so it is derived rather than asked twice.
OWN_STOCK = "own_stock"


def normalise(source: str) -> str:
    """Settle a submitted source into what should be stored.

    The field used to be a two-option select posting ``0`` or ``1``, and
    those values are still out there: in saved forms, in anything that posts
    to this endpoint, and in the tests that pinned the old behaviour. Read
    literally they are supplier names, which would quietly put a handling
    markup on every part marked ``0`` -- a charge to a customer, arrived at
    by a misreading. They are translated instead.

    >>> normalise("0"), normalise(""), normalise("   ")
    ('own_stock', 'own_stock', 'own_stock')
    >>> normalise("1")
    'outside'
    >>> normalise("  BMW  ")
    'BMW'
    """
    value = source.strip()
    if not value or value == "0":
        return OWN_STOCK
    if value == "1":
        return "outside"
    return value


def is_external(source: str) -> bool:
    """Whether the handling percentage applies to a part from this source.

    Blank counts as own stock: a part with no recorded origin is far more
    likely to be one nobody bothered to label than one bought in specially,
    and quietly adding a markup to it would overcharge the customer.

    >>> is_external("own_stock"), is_external(""), is_external("0")
    (False, False, False)
    >>> is_external("BMW"), is_external("Used market"), is_external("1")
    (True, True, True)
    """
    return normalise(source) != OWN_STOCK


def label(value: str, lang: str = "en", *, table: list[tuple[str, str, str]] | None = None) -> str:
    """The name to show for a stored value, falling back to the value itself.

    >>> label("own_stock"), label("own_stock", "ar")
    ('Own stock', 'مخزوننا')
    >>> label("Germany")
    'Imported from Germany'
    >>> label("Al-Jazeera Spare Parts")      # typed by hand, kept as written
    'Al-Jazeera Spare Parts'
    >>> label("")
    ''
    """
    for stored, english, arabic in (table if table is not None else SOURCES):
        if stored == value:
            return arabic if lang == "ar" else english
    return value


def manufacturer_label(value: str, lang: str = "en") -> str:
    """As :func:`label`, against the manufacturer list.

    >>> manufacturer_label("Mercedes-Benz", "ar")
    'مرسيدس بنز'
    >>> manufacturer_label("Bosch")
    'Bosch'
    """
    return label(value, lang, table=MANUFACTURERS)
