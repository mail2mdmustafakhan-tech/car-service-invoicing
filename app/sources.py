"""Whether a part was bought in for this job, and therefore carries a markup.

The names a source can be called by are not here -- they are rows in the
`list_options` table, edited in Settings. What is here is the one thing
about a source that is a rule rather than a label: a part the workshop did
not already own was bought in for this customer, and the contract's handling
percentage applies to it.

Nothing is enforced against the column. The list offers suggestions, and an
origin typed in unexpected words is kept as written -- it is worth more than
one recorded wrongly because the list had no room for the truth. But however
it is written, it still has to answer the markup question, which is what
`normalise` exists to settle.
"""

from __future__ import annotations

# The lists of sources and manufacturers used to live here as constants.
# They are rows in the `list_options` table now (migration 009) and are
# edited in Settings, because a workshop finds a new supplier far more often
# than anyone edits Python. Keeping a second copy here would be a trap: it
# would look authoritative and change nothing.
#
# What stays is the part that is not a list of names but a rule about
# money -- below.

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
