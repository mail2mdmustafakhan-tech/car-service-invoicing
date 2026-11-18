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
from dataclasses import dataclass
from datetime import date, timedelta
from typing import Any

from . import images
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
                   logo_has_alpha = ?, updated_at = datetime('now')
             WHERE id = 1
            """,
            (data, mime, filename[:120], int(images.has_transparency(data, mime))),
        )
    return mime


def clear_logo(conn: sqlite3.Connection) -> None:
    with transaction(conn):
        conn.execute(
            """
            UPDATE branding
               SET logo_blob = NULL, logo_mime = '', logo_filename = '',
                   logo_has_alpha = NULL, updated_at = datetime('now')
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
    row = _require(
        _one(
            conn,
            "SELECT logo_mime, logo_filename, updated_at, logo_has_alpha"
            "  FROM branding WHERE id = 1",
        ),
        "Branding",
    )
    if row["logo_mime"] and row["logo_has_alpha"] is None:
        # An install that had a logo before this column existed. Work the
        # answer out once from the file itself and write it back, rather than
        # asking somebody to re-upload a logo that is perfectly good.
        return _record_logo_alpha(conn)
    return row


def _record_logo_alpha(conn: sqlite3.Connection) -> Row:
    """Look at the stored logo once, and remember what was seen.

    The only place this application reads the logo's bytes outside of serving
    it. It happens once per install, not once per page: the answer is written
    back to the row that is read on every render.
    """
    stored = get_logo(conn)
    answer = int(images.has_transparency(*stored)) if stored else None
    with transaction(conn):
        conn.execute("UPDATE branding SET logo_has_alpha = ? WHERE id = 1", (answer,))
    return _require(
        _one(
            conn,
            "SELECT logo_mime, logo_filename, updated_at, logo_has_alpha"
            "  FROM branding WHERE id = 1",
        ),
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
    # Whether this customer is ever charged VAT. A default for the documents
    # raised for them, not a lock on those documents -- see migration 016.
    "no_vat",
    # The warning on their file. See migration 011: a level and a reason,
    # where the level decides how hard the application interrupts.
    "alert_level", "alert_note", "alert_set_on",
)

#: Warning levels, mildest first. The order is the severity order and is
#: relied on by the templates, which show the strongest styling to the last
#: of them.
ALERT_LEVELS = ("note", "check", "refuse")


# ---------------------------------------------------------------------------
# Sorting a list page
# ---------------------------------------------------------------------------
#
# A column heading is a link that re-sorts the list. The column arrives from
# the query string, which is to say from anybody, so it never reaches the SQL
# as text: it is a key into one of the maps below, and a key that is not
# there falls back to the list's natural order. String interpolation into an
# ORDER BY is how a sortable table becomes an injection.

#: Columns where a blank is common and should sit at the end whichever way
#: the list runs. Sorting 1,900 cars by year with 1,400 of them unrecorded
#: otherwise fills the first screen with dashes, and the click looks like it
#: did nothing. A blank is not a small value; it is a missing one.
#: The unique column each listing is finally ordered by. Paging makes this
#: necessary rather than merely tidy: every sortable column above is
#: non-unique -- two customers share a name, four hundred cars share a make --
#: and a window taken with LIMIT/OFFSET over an order with ties is not
#: well-defined. SQLite is free to return tied rows in a different order for
#: page 2 than it did for page 1, so a row can appear twice, or never. Ending
#: every order with the row's own id makes the sequence total, and paging
#: through it exact.
IDS: dict[str, str] = {
    "customers": "c.id",
    "vehicles": "v.id",
    "catalog": "id",
    "issues": "id",
}

BLANKS_LAST: dict[str, set[str]] = {
    "customers": {"phone"},
    "vehicles": {"year", "colour", "odometer", "model"},
    "catalog": {"manufacturer"},
    "issues": set(),
}

#: What each list can be sorted by, and the SQL that does it. The default is
#: named first in each map and is what an unrecognised key falls back to.
SORTS: dict[str, dict[str, str]] = {
    "customers": {
        "name": "c.name COLLATE NOCASE",
        "phone": "c.phone COLLATE NOCASE",
        "vehicles": "vehicle_count",
        "balance": "balance_minor",
        "added": "c.created_at",
    },
    "vehicles": {
        "plate": "v.plate_no COLLATE NOCASE",
        "make": "v.make COLLATE NOCASE, v.model COLLATE NOCASE",
        "model": "v.model COLLATE NOCASE",
        "year": "v.model_year",
        "colour": "v.colour COLLATE NOCASE",
        "owner": "c.name COLLATE NOCASE",
        "odometer": "v.odometer",
        "invoices": "invoice_count",
    },
    "catalog": {
        "name": "name_en COLLATE NOCASE",
        "kind": "kind, name_en COLLATE NOCASE",
        "price": "unit_price_minor",
        "manufacturer": "manufacturer COLLATE NOCASE",
    },
    "issues": {
        "make": "make COLLATE NOCASE, title_en COLLATE NOCASE",
        "title": "title_en COLLATE NOCASE",
        "severity": "CASE severity WHEN 'high' THEN 1 WHEN 'medium' THEN 2 ELSE 3 END",
    },
}


def order_clause(listing: str, sort: str, direction: str) -> tuple[str, str, str]:
    """Turn a requested sort into SQL, and report what was actually used.

    Returns ``(sql, sort, direction)``. The caller passes the sort and the
    direction straight back to the template, so the heading arrow always
    shows what the list is really doing rather than what was asked for.

    >>> order_clause("vehicles", "plate", "desc")[0]
    'v.plate_no COLLATE NOCASE DESC, v.id'
    >>> order_clause("vehicles", "year", "desc")[0].endswith("v.model_year DESC, v.id")
    True
    >>> order_clause("vehicles", "'; DROP TABLE vehicles --", "asc")[1]
    'plate'
    """
    columns = SORTS[listing]
    if sort not in columns:
        sort = next(iter(columns))
    direction = "desc" if str(direction).lower() == "desc" else "asc"
    suffix = " DESC" if direction == "desc" else ""
    # Applied to the first expression only: "a, b DESC" would reverse b
    # alone, which is not what anybody clicking a heading means.
    parts = columns[sort].split(", ")
    parts[0] += suffix

    if sort in BLANKS_LAST.get(listing, ()):
        first = columns[sort].split(", ")[0].split(" COLLATE")[0]
        parts.insert(0, f"CASE WHEN {first} IS NULL OR {first} = '' THEN 1 ELSE 0 END")

    # The tiebreaker goes last and is always ascending, like every other
    # column after the first: "DESC applies to the first column only" is the
    # rule the headings behave by, and the id is no exception to it. Which way
    # it runs does not matter for paging -- only that the order is total.
    tiebreak = IDS.get(listing)
    if tiebreak and tiebreak not in parts:
        parts.append(tiebreak)
    return ", ".join(parts), sort, direction


# --------------------------------------------------------------------------
# Paging
# --------------------------------------------------------------------------
#
# The vehicle list was 3.7 MB of HTML -- six thousand rows, every one of them
# rendered, for a screen that shows twenty at a time. Three of the other lists
# had a bare ``LIMIT 500`` instead, which is worse than slow: rows past the
# five hundredth were simply not there, and nothing on the page said so.
#
# Both are the same bug. A list shows one page at a time and says how many
# there are, so nothing is hidden and nothing is sent that nobody will read.
#
# Each listing is built in one place, by a ``_*_query`` function returning the
# SELECT without its ORDER BY. ``list_*`` adds the order and an optional
# limit; ``page_*`` adds the order, a window, and a count. There is one copy
# of each WHERE clause, so a filter can never apply to the rows and not to the
# count that describes them -- which is how a list comes to say "50 of 120"
# while showing something else entirely.

#: Rows per page. Enough that scrolling is rare on a normal screen, few
#: enough that the page arrives instantly over the workshop's network.
PER_PAGE = 50


@dataclass(frozen=True)
class Page:
    """One window onto a listing, and enough about the rest to navigate it."""

    rows: list[Row]
    total: int
    number: int
    per_page: int

    def __iter__(self) -> Any:
        """Iterate the rows, so ``{% for x in page %}`` works unchanged."""
        return iter(self.rows)

    def __len__(self) -> int:
        return len(self.rows)

    def __bool__(self) -> bool:
        """Truthy when this page has rows -- *not* when the listing does.

        ``{% if page %}`` in a template asks "is there anything to draw here",
        and on an empty page the answer is no.
        """
        return bool(self.rows)

    @property
    def pages(self) -> int:
        if self.per_page <= 0:
            return 1
        return max(1, -(-self.total // self.per_page))

    @property
    def first(self) -> int:
        """1-based index of the first row shown, or 0 on an empty listing."""
        return 0 if not self.rows else (self.number - 1) * self.per_page + 1

    @property
    def last(self) -> int:
        return 0 if not self.rows else self.first + len(self.rows) - 1

    @property
    def has_prev(self) -> bool:
        return self.number > 1

    @property
    def has_next(self) -> bool:
        return self.number < self.pages

    @property
    def prev(self) -> int:
        return max(1, self.number - 1)

    @property
    def next(self) -> int:
        return min(self.pages, self.number + 1)


def _paginate(
    conn: sqlite3.Connection,
    sql: str,
    params: Sequence[Any],
    order: str,
    *,
    page: int = 1,
    per_page: int = PER_PAGE,
) -> Page:
    """Fetch one window of ``sql`` plus the total it is a window onto.

    The count wraps the listing's own SELECT rather than rebuilding its FROM
    and WHERE. That costs nothing worth measuring: SQLite drops the select
    list's correlated subqueries when nothing reads them, so counting four
    thousand customers takes 1.6ms against the 20ms the rows themselves cost.
    """
    params = list(params)
    total = int(_one(conn, f"SELECT COUNT(*) AS n FROM ({sql})", params)["n"])  # type: ignore[index]

    per_page = max(1, int(per_page))
    pages = max(1, -(-total // per_page))
    number = min(max(1, int(page or 1)), pages)

    rows = _all(
        conn,
        f"{sql} ORDER BY {order} LIMIT ? OFFSET ?",
        [*params, per_page, (number - 1) * per_page],
    )
    return Page(rows=rows, total=total, number=number, per_page=per_page)


# --------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------

# --------------------------------------------------------------------------
# Searching
# --------------------------------------------------------------------------
#
# Three things were wrong with it, all found by typing into the real register
# rather than by reading the query:
#
#   * A phone stored as 0559081935 could not be found by typing 055 908 1935,
#     and one stored with spaces could not be found by typing it without. In a
#     register written up by hand over years, the same number appears both
#     ways, so this is not an edge case -- it is most of the phone book.
#   * A name pasted in from somewhere else carries spaces around it, and
#     `LIKE '%  Al-Harbi  %'` matches nothing at all.
#   * `%` and `_` are LIKE's own wildcards. Typed into a search box they
#     quietly mean "anything", so searching for `50%` returned the whole list.
#
# And one thing was missing rather than wrong: at a service centre the thing
# in front of you is a car, so the plate is what gets typed. It now finds the
# owner.

#: How many digits make a search worth comparing against phone numbers.
#: Fewer than this and it matches most of the register by accident.
PHONE_DIGITS = 4

#: Characters people put in phone numbers that carry no meaning.
_PHONE_NOISE = (" ", "-", "(", ")", ".", "+", "\u00a0")


def _digits(value: str) -> str:
    """Just the digits, for comparing one written phone number with another."""
    return "".join(ch for ch in value if ch.isdigit())


def _digits_sql(column: str) -> str:
    """SQL that strips the same noise out of a stored number.

    A chain of REPLACE rather than anything cleverer because SQLite has no
    regular expressions, and adding an extension to a program that has to
    install on a workshop PC without a compiler is a poor trade for a
    full-table scan of four thousand short strings.
    """
    expression = f"COALESCE({column}, '')"
    for ch in _PHONE_NOISE:
        expression = f"REPLACE({expression}, '{ch}', '')"
    return expression


def _like(term: str) -> str:
    """A pattern matching *term* anywhere, with LIKE's wildcards made literal.

    Paired with ``ESCAPE '\\'`` at every use.
    """
    for ch in ("\\", "%", "_"):
        term = term.replace(ch, "\\" + ch)
    return f"%{term}%"


def clean_search(term: str) -> str:
    """What somebody typed, with the accidents taken out.

    >>> clean_search("  Al-Harbi  ")
    'Al-Harbi'
    >>> clean_search("055   908  1935")
    '055 908 1935'
    """
    return " ".join(str(term or "").split())


def _customers_query(
    *,
    search: str = "",
    include_inactive: bool = False,
    category: str = "",
    alert: str = "",
) -> tuple[str, list[Any]]:
    where, params = ["1 = 1"], []
    if not include_inactive:
        where.append("c.is_active = 1")

    search = clean_search(search)
    if search:
        like = _like(search)
        # The name, in either language, and the phone as it happens to be
        # written.
        clauses = [
            r"c.name LIKE ? ESCAPE '\'",
            r"c.name_ar LIKE ? ESCAPE '\'",
            r"c.phone LIKE ? ESCAPE '\'",
        ]
        params += [like, like, like]

        # ...and the phone compared digit to digit, so that 0559081935 and
        # 055 908 1935 find each other.
        #
        # Only once there are enough digits to be a piece of a phone number.
        # Two or three match far too much: searching "G12" for a model, or
        # "50%" for a company name, turned up every customer whose number
        # happens to contain 12 or 50, which is most of them.
        digits = _digits(search)
        if len(digits) >= PHONE_DIGITS:
            clauses.append(f"{_digits_sql('c.phone')} LIKE ?")
            params.append(f"%{digits}%")

        # ...and the cars, because the thing in front of you at the counter
        # is the car. One pass over the vehicles rather than a correlated
        # subquery per customer.
        clauses.append(
            "c.id IN (SELECT v.customer_id FROM vehicles v"
            r"          WHERE v.plate_no LIKE ? ESCAPE '\'"
            r"             OR v.make     LIKE ? ESCAPE '\'"
            r"             OR v.model    LIKE ? ESCAPE '\'"
            r"             OR v.vin      LIKE ? ESCAPE '\'"
            f"             OR {_digits_sql('v.plate_no')} LIKE ?)"
        )
        # The last pattern is the search with its spaces taken out, matched
        # against the stored plate with its spaces taken out: "4616UAR" and
        # "4616 UAR" are the same car, written up by two different people.
        params += [like, like, like, like, _like(search.replace(" ", ""))]

        where.append("(" + " OR ".join(clauses) + ")")
    if category:
        where.append("c.category = ?")
        params.append(category)
    if alert:
        where.append("COALESCE(c.alert_level, '') = ?")
        params.append(alert)

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
    """
    return sql, params


def list_customers(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    include_inactive: bool = False,
    category: str = "",
    alert: str = "",
    limit: int | None = None,
    sort: str = "",
    direction: str = "asc",
) -> list[Row]:
    """Customers with their vehicle count and outstanding balance."""
    order, _, _ = order_clause("customers", sort, direction)
    sql, params = _customers_query(
        search=search, include_inactive=include_inactive, category=category, alert=alert
    )
    sql += f" ORDER BY {order}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return _all(conn, sql, params)


def page_customers(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    include_inactive: bool = False,
    category: str = "",
    alert: str = "",
    sort: str = "",
    direction: str = "asc",
    page: int = 1,
    per_page: int = PER_PAGE,
) -> Page:
    order, _, _ = order_clause("customers", sort, direction)
    sql, params = _customers_query(
        search=search, include_inactive=include_inactive, category=category, alert=alert
    )
    return _paginate(conn, sql, params, order, page=page, per_page=per_page)


#: How many customers a form's dropdown carries before anybody searches.
#: Enough to cover "I just added them and now I am invoicing them", short
#: enough that the page is small and the list is scannable.
PICKER_LIMIT = 50


def picker_customers(
    conn: sqlite3.Connection, chosen: int | None = None, limit: int = PICKER_LIMIT
) -> list[Row]:
    """The customers a form's dropdown starts with: recent ones, plus *chosen*.

    *chosen* is included however old they are. An edit form whose customer is
    not in its own dropdown clears the field on the first save, which turns
    "fix a typo on this invoice" into "this invoice now belongs to nobody".
    """
    # Ordered by id, not by `created_at`. The timestamp has one-second
    # resolution and an import writes thousands of rows inside one
    # transaction, so every customer from the ARC register carries the same
    # one: ordering by it would leave "the fifty most recent" to be decided
    # arbitrarily among two thousand ties. The id is the real insertion order.
    sql, params = _customers_query()
    recent = _all(conn, f"{sql} ORDER BY c.id DESC LIMIT ?", [*params, limit])
    if chosen is None or any(row["id"] == chosen for row in recent):
        return recent

    # Read through the listing's own SELECT so the row carries the same
    # columns as the others -- the template reads `alert_level` off each one,
    # and a row fetched with a bare SELECT * would be missing nothing today
    # but would be the odd one out the moment the listing grows a column.
    sql, params = _customers_query(include_inactive=True)
    one = _one(conn, f"{sql} AND c.id = ?", [*params, chosen])
    if one is None:
        return recent
    # First, where it can be seen, rather than buried in a list ordered by
    # something it has nothing to do with.
    return [one, *recent]


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


def _vehicles_query(
    *,
    customer_id: int | None = None,
    search: str = "",
    include_inactive: bool = False,
    make: str = "",
    colour: str = "",
) -> tuple[str, list[Any]]:
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
    if make:
        where.append("TRIM(v.make) = ? COLLATE NOCASE")
        params.append(make.strip())
    if colour:
        where.append("TRIM(v.colour) = ? COLLATE NOCASE")
        params.append(colour.strip())

    sql = f"""
        SELECT v.*, c.name AS customer_name,
               (SELECT COUNT(*) FROM invoices i WHERE i.vehicle_id = v.id) AS invoice_count
          FROM vehicles v
          JOIN customers c ON c.id = v.customer_id
         WHERE {' AND '.join(where)}
    """
    return sql, params


def list_vehicles(
    conn: sqlite3.Connection,
    *,
    customer_id: int | None = None,
    search: str = "",
    include_inactive: bool = False,
    make: str = "",
    colour: str = "",
    limit: int | None = None,
    sort: str = "",
    direction: str = "asc",
) -> list[Row]:
    order, _, _ = order_clause("vehicles", sort, direction)
    sql, params = _vehicles_query(
        customer_id=customer_id, search=search, include_inactive=include_inactive,
        make=make, colour=colour,
    )
    sql += f" ORDER BY {order}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return _all(conn, sql, params)


def page_vehicles(
    conn: sqlite3.Connection,
    *,
    customer_id: int | None = None,
    search: str = "",
    include_inactive: bool = False,
    make: str = "",
    colour: str = "",
    sort: str = "",
    direction: str = "asc",
    page: int = 1,
    per_page: int = PER_PAGE,
) -> Page:
    order, _, _ = order_clause("vehicles", sort, direction)
    sql, params = _vehicles_query(
        customer_id=customer_id, search=search, include_inactive=include_inactive,
        make=make, colour=colour,
    )
    return _paginate(conn, sql, params, order, page=page, per_page=per_page)


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


def _catalog_query(
    *,
    kind: str = "",
    search: str = "",
    include_inactive: bool = False,
) -> tuple[str, list[Any]]:
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

    sql = f"""
        SELECT * FROM catalog_items
         WHERE {' AND '.join(where)}
    """  # noqa: S608 -- `where` holds only the fixed strings above
    return sql, params


def list_catalog(
    conn: sqlite3.Connection,
    *,
    sort: str = "",
    direction: str = "asc",
    kind: str = "",
    search: str = "",
    include_inactive: bool = False,
    limit: int | None = None,
) -> list[Row]:
    order, _, _ = order_clause("catalog", sort, direction)
    sql, params = _catalog_query(kind=kind, search=search, include_inactive=include_inactive)
    sql += f" ORDER BY {order}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return _all(conn, sql, params)


def page_catalog(
    conn: sqlite3.Connection,
    *,
    sort: str = "",
    direction: str = "asc",
    kind: str = "",
    search: str = "",
    include_inactive: bool = False,
    page: int = 1,
    per_page: int = PER_PAGE,
) -> Page:
    order, _, _ = order_clause("catalog", sort, direction)
    sql, params = _catalog_query(kind=kind, search=search, include_inactive=include_inactive)
    return _paginate(conn, sql, params, order, page=page, per_page=per_page)


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


def _invoices_query(
    *,
    search: str = "",
    status: str = "",
    payment_state: str = "",
    customer_id: int | None = None,
    date_from: str = "",
    date_to: str = "",
) -> tuple[str, list[Any]]:
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

    sql = f"""
        SELECT vi.*,
               i.total_minor,
               i.customer_id,
               i.vehicle_id,
               COALESCE((SELECT SUM(p.amount_minor) FROM payments p
                          WHERE p.invoice_id = i.id), 0) AS paid_minor
          FROM v_invoices vi
          JOIN invoices  i ON i.id = vi.id
         WHERE {' AND '.join(where)}
    """
    return sql, params


#: Newest first, which is what anybody opening the invoice list is looking for.
_INVOICE_ORDER = "vi.issue_date DESC, vi.id DESC"


def list_invoices(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "",
    payment_state: str = "",
    customer_id: int | None = None,
    date_from: str = "",
    date_to: str = "",
    limit: int | None = None,
) -> list[Row]:
    """Invoices from the reporting view, newest first."""
    sql, params = _invoices_query(
        search=search, status=status, payment_state=payment_state,
        customer_id=customer_id, date_from=date_from, date_to=date_to,
    )
    sql += f" ORDER BY {_INVOICE_ORDER}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return _all(conn, sql, params)


def page_invoices(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "",
    payment_state: str = "",
    customer_id: int | None = None,
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
    per_page: int = PER_PAGE,
) -> Page:
    sql, params = _invoices_query(
        search=search, status=status, payment_state=payment_state,
        customer_id=customer_id, date_from=date_from, date_to=date_to,
    )
    return _paginate(conn, sql, params, _INVOICE_ORDER, page=page, per_page=per_page)


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


def _repair_orders_query(
    *,
    search: str = "",
    status: str = "",
    customer_id: int | None = None,
    vehicle_id: int | None = None,
) -> tuple[str, list[Any]]:
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

    sql = f"""
        SELECT ro.*, o.customer_id, o.vehicle_id, o.invoice_id
          FROM v_repair_orders ro
          JOIN repair_orders   o ON o.id = ro.id
         WHERE {' AND '.join(where)}
    """
    return sql, params


_ORDER_ORDER = "ro.date_in DESC, ro.id DESC"


def list_repair_orders(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "",
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    limit: int | None = None,
) -> list[Row]:
    sql, params = _repair_orders_query(
        search=search, status=status, customer_id=customer_id, vehicle_id=vehicle_id
    )
    sql += f" ORDER BY {_ORDER_ORDER}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return _all(conn, sql, params)


def page_repair_orders(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "",
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    page: int = 1,
    per_page: int = PER_PAGE,
) -> Page:
    sql, params = _repair_orders_query(
        search=search, status=status, customer_id=customer_id, vehicle_id=vehicle_id
    )
    return _paginate(conn, sql, params, _ORDER_ORDER, page=page, per_page=per_page)


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


def _estimates_query(
    *,
    search: str = "",
    status: str = "",
    customer_id: int | None = None,
) -> tuple[str, list[Any]]:
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

    sql = f"""
        SELECT ve.*, e.customer_id, e.vehicle_id, e.invoice_id, e.total_minor
          FROM v_estimates ve
          JOIN estimates   e ON e.id = ve.id
         WHERE {' AND '.join(where)}
    """
    return sql, params


_ESTIMATE_ORDER = "ve.issue_date DESC, ve.id DESC"


def list_estimates(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "",
    customer_id: int | None = None,
    limit: int | None = None,
) -> list[Row]:
    sql, params = _estimates_query(search=search, status=status, customer_id=customer_id)
    sql += f" ORDER BY {_ESTIMATE_ORDER}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return _all(conn, sql, params)


def page_estimates(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "",
    customer_id: int | None = None,
    page: int = 1,
    per_page: int = PER_PAGE,
) -> Page:
    sql, params = _estimates_query(search=search, status=status, customer_id=customer_id)
    return _paginate(conn, sql, params, _ESTIMATE_ORDER, page=page, per_page=per_page)


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
    conn: sqlite3.Connection, estimate_id: int, *, doc_type: str | None = None
) -> int:
    """Raise an invoice from an approved estimate.

    Only an approved estimate converts. Invoicing something the customer has
    not agreed to is how disputes start, and the system should not make that
    the easy path.
    """
    estimate = get_estimate(conn, estimate_id)
    if estimate["invoice_id"] is not None:
        raise InUse(f"Already invoiced as {estimate['invoice_no']}.")

    # An estimate quoted without VAT becomes an invoice without VAT, unless
    # the caller says otherwise. Quoting a customer one figure and then
    # invoicing them a taxed one is the kind of surprise that ends in an
    # argument at the counter, and the default should not be the surprising
    # one.
    if doc_type is None:
        doc_type = "tax" if estimate["vat_rate_bp"] else "plain"
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


def mark_import_batch_done(
    conn: sqlite3.Connection, batch_id: int, *, imported: int = 0, skipped: int = 0
) -> None:
    """Close a batch so the same file cannot be loaded twice by a refresh."""
    with transaction(conn):
        conn.execute(
            """
            UPDATE import_batches
               SET status = 'imported', imported = ?, skipped = ?
             WHERE id = ? AND status = 'pending'
            """,
            (imported, skipped, batch_id),
        )


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
    sort: str = "",
    direction: str = "asc",
    make: str = "",
    search: str = "",
    include_inactive: bool = False,
) -> list[Row]:
    order, _, _ = order_clause("issues", sort, direction)
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
         ORDER BY {order}
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


def monthly_money(conn: sqlite3.Connection, months: int = 12) -> list[dict[str, Any]]:
    """Invoiced and collected per month, with the balance owed at month end.

    The month-end balance is cumulative -- everything issued up to that point
    less everything paid up to that point -- which is the figure a person
    means by "what are we owed". A per-month difference would show the month's
    movement and be mistaken for the balance.

    Written as two grouped scans and a running total rather than four
    correlated subqueries per month. The old version re-read every invoice
    and every payment once for each month on the chart, with ``strftime`` on
    each row so no index could help: twelve months over five thousand
    invoices took 60ms of the dashboard's 93, and it grew worse every month
    the workshop stayed open -- the cumulative column made it quadratic.
    This reads each table once however many months are shown.

    The running total is accumulated over *every* month and the window is
    taken afterwards. Cutting to twelve months first and then accumulating
    would restart the balance from zero at the left edge of the chart, which
    would quietly understate what is owed by everything older than a year.
    """
    rows = _all(
        conn,
        """
        WITH invoiced AS (
            SELECT strftime('%Y-%m', issue_date) AS ym,
                   SUM(total_minor)              AS total
              FROM invoices
             WHERE status = 'issued'
             GROUP BY ym
        ),
        collected AS (
            SELECT strftime('%Y-%m', paid_on) AS ym,
                   SUM(amount_minor)          AS total
              FROM payments
             GROUP BY ym
        ),
        months AS (
            SELECT ym FROM invoiced
            UNION
            SELECT ym FROM collected
        )
        SELECT m.ym,
               COALESCE(i.total, 0) AS invoiced_minor,
               COALESCE(c.total, 0) AS collected_minor
          FROM months m
          LEFT JOIN invoiced  i ON i.ym = m.ym
          LEFT JOIN collected c ON c.ym = m.ym
         ORDER BY m.ym
        """,
    )

    running = 0
    out: list[dict[str, Any]] = []
    for row in rows:
        running += int(row["invoiced_minor"]) - int(row["collected_minor"])
        out.append(
            {
                "ym": row["ym"],
                "invoiced_minor": int(row["invoiced_minor"]),
                "collected_minor": int(row["collected_minor"]),
                "outstanding_minor": running,
            }
        )
    return out[-months:] if months else out


def _make_filter(make: str) -> tuple[str, list[Any]]:
    """A WHERE fragment restricting the car charts to one make.

    Shared by all four so they cannot drift apart: a dashboard where the
    colour chart is filtered and the age chart is not would be worse than
    one with no filter at all.
    """
    make = (make or "").strip()
    if not make:
        return "", []
    return " AND UPPER(TRIM(make)) = ? ", [make.upper()]


def cars_by_make(conn: sqlite3.Connection, limit: int = 8, make: str = "") -> list[Row]:
    clause, params = _make_filter(make)
    return _all(
        conn,
        f"""
        SELECT COALESCE(NULLIF(TRIM(make), ''), 'Unknown') AS label,
               COUNT(*) AS cars,
               COUNT(DISTINCT customer_id) AS customers
          FROM vehicles
         WHERE 1 = 1 {clause}
         GROUP BY label
         ORDER BY cars DESC
         LIMIT ?
        """,
        [*params, limit],
    )


def cars_by_model(conn: sqlite3.Connection, limit: int = 10, make: str = "") -> list[Row]:
    """Cars grouped by make and model, for the cars that have a model.

    A car with no model recorded is left out rather than counted under its
    bare make. It used to be included, which put "BMW 979" at the top of a
    chart headed "Cars by model" -- 979 cars whose model nobody wrote down,
    reading as if they were all one model. How many of those there are is
    worth knowing, but it is a different fact and `cars_without_model` is
    where it is reported.
    """
    clause, params = _make_filter(make)
    return _all(
        conn,
        f"""
        SELECT TRIM(COALESCE(make, '') || ' ' || COALESCE(model, '')) AS label,
               COUNT(*) AS cars
          FROM vehicles
         WHERE TRIM(COALESCE(model, '')) <> '' {clause}
         GROUP BY label
         ORDER BY cars DESC
         LIMIT ?
        """,
        [*params, limit],
    )


def cars_without_model(conn: sqlite3.Connection, make: str = "") -> int:
    """How many cars have no model recorded -- a gap worth seeing."""
    clause, params = _make_filter(make)
    return _one(
        conn,
        "SELECT COUNT(*) AS n FROM vehicles"
        " WHERE TRIM(COALESCE(model, '')) = '' " + clause,
        params,
    )["n"]


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


def _inspections_query(*, search: str = "", status: str = "") -> tuple[str, list[Any]]:
    """Inspections, optionally narrowed.

    Searched across the sheet number, the customer and the car, because
    those are the three things somebody at the desk has in front of them
    when they come looking for one.
    """
    where, params = ["1 = 1"], []

    search = (search or "").strip()
    if search:
        like = f"%{search}%"
        where.append(
            "(inspection_no LIKE ? OR customer LIKE ? OR plate_no LIKE ?"
            " OR make LIKE ? OR model LIKE ?)"
        )
        params.extend([like] * 5)

    status = (status or "").strip()
    if status in ("draft", "checked", "quoted"):
        where.append("status = ?")
        params.append(status)

    sql = f"""
        SELECT * FROM v_inspections
         WHERE {' AND '.join(where)}
    """  # noqa: S608 -- `where` holds only the fixed strings above
    return sql, params


_INSPECTION_ORDER = "inspected_on DESC, id DESC"


def list_inspections(
    conn: sqlite3.Connection,
    limit: int | None = None,
    *,
    search: str = "",
    status: str = "",
) -> list[Row]:
    sql, params = _inspections_query(search=search, status=status)
    sql += f" ORDER BY {_INSPECTION_ORDER}"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return _all(conn, sql, params)


def page_inspections(
    conn: sqlite3.Connection,
    *,
    search: str = "",
    status: str = "",
    page: int = 1,
    per_page: int = PER_PAGE,
) -> Page:
    sql, params = _inspections_query(search=search, status=status)
    return _paginate(conn, sql, params, _INSPECTION_ORDER, page=page, per_page=per_page)


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


# ---------------------------------------------------------------------------
# Dropdown lists
# ---------------------------------------------------------------------------
#
# The values behind every dropdown in the application. See migration 009 for
# why they are data: a workshop finds a new supplier far more often than
# anyone edits a Python constant.

#: The lists that exist, and the English name shown for each in Settings.
#: A list not named here cannot be reached from the Settings screen, which is
#: deliberate -- the screen edits the lists the application actually offers,
#: not any string somebody manages to post.
OPTION_LISTS: dict[str, str] = {
    "sources": "Part sources",
    "manufacturers": "Manufacturers",
    "units": "Units",
    "payment_methods": "Payment methods",
    "customer_types": "Customer types",
    "marques": "Marques serviced",
}


def list_options(
    conn: sqlite3.Connection,
    list_name: str,
    *,
    include_inactive: bool = False,
) -> list[Row]:
    """The choices for one dropdown, in the order they should be offered."""
    where = "list_name = ?"
    params: list[Any] = [list_name]
    if not include_inactive:
        where += " AND is_active = 1"
    return _all(
        conn,
        f"SELECT * FROM list_options WHERE {where} ORDER BY sort_order, id",
        params,
    )


def all_options(
    conn: sqlite3.Connection,
) -> tuple[dict[str, list[Row]], dict[tuple[str, str], Row]]:
    """Every choice, as two views of one query.

    The first is the active choices grouped by list: what a dropdown offers.
    The second is every choice including the switched-off ones, keyed by
    (list, value): what a stored value is called.

    They have to differ. Switching "Cheque" off should stop it being offered
    on new work, but an invoice that was paid by cheque last year still has
    to print the word "Cheque" -- not the bare code it happens to be stored
    as. Retiring a choice is about what you can pick next, never about
    rewriting what already happened.

    One query rather than one per dropdown: a form with a source, a
    manufacturer and a unit on every row would otherwise ask the same small
    table three times for every line on the page.
    """
    offered: dict[str, list[Row]] = {name: [] for name in OPTION_LISTS}
    labels: dict[tuple[str, str], Row] = {}
    for row in _all(conn, "SELECT * FROM list_options ORDER BY sort_order, id"):
        labels[(row["list_name"], row["value"])] = row
        if row["is_active"]:
            offered.setdefault(row["list_name"], []).append(row)
    return offered, labels


def get_option(conn: sqlite3.Connection, option_id: int) -> Row:
    row = _one(conn, "SELECT * FROM list_options WHERE id = ?", [option_id])
    if row is None:
        raise NotFound(f"No list value with id {option_id}")
    return row


def create_option(
    conn: sqlite3.Connection,
    *,
    list_name: str,
    value: str,
    label_en: str,
    label_ar: str = "",
) -> int:
    """Add a choice to a list, at the end of it."""
    if list_name not in OPTION_LISTS:
        raise ValueError(f"Unknown list: {list_name}")
    value = value.strip()
    if not value:
        raise ValueError("A value is required")

    existing = _one(
        conn,
        "SELECT id, is_active FROM list_options WHERE list_name = ? AND value = ?",
        [list_name, value],
    )
    if existing is not None:
        # Re-adding something switched off earlier is the same wish as
        # switching it back on, and is what someone who cannot see the
        # inactive rows will try. Refusing with "already exists" about a row
        # they cannot see would be a dead end.
        conn.execute(
            "UPDATE list_options SET is_active = 1, label_en = ?, label_ar = ?,"
            " updated_at = datetime('now') WHERE id = ?",
            (label_en.strip() or value, label_ar.strip(), existing["id"]),
        )
        conn.commit()
        return int(existing["id"])

    last = _one(
        conn,
        "SELECT COALESCE(MAX(sort_order), 0) AS n FROM list_options WHERE list_name = ?",
        [list_name],
    )
    cursor = conn.execute(
        """
        INSERT INTO list_options (list_name, value, label_en, label_ar, sort_order)
        VALUES (?, ?, ?, ?, ?)
        """,
        (
            list_name,
            value,
            label_en.strip() or value,
            label_ar.strip(),
            int(last["n"]) + 10,
        ),
    )
    conn.commit()
    return int(cursor.lastrowid)


def update_option(
    conn: sqlite3.Connection,
    option_id: int,
    *,
    label_en: str | None = None,
    label_ar: str | None = None,
    sort_order: int | None = None,
    is_active: bool | None = None,
) -> None:
    """Change a choice. The stored value itself is never changed here.

    Renaming the value would leave every invoice, part and payment that
    already records the old one pointing at nothing. The label can say
    anything; the value is what the documents are written in.
    """
    option = get_option(conn, option_id)
    conn.execute(
        """
        UPDATE list_options
           SET label_en   = ?,
               label_ar   = ?,
               sort_order = ?,
               is_active  = ?,
               updated_at = datetime('now')
         WHERE id = ?
        """,
        (
            option["label_en"] if label_en is None else label_en.strip(),
            option["label_ar"] if label_ar is None else label_ar.strip(),
            option["sort_order"] if sort_order is None else int(sort_order),
            option["is_active"] if is_active is None else int(is_active),
            option_id,
        ),
    )
    conn.commit()


def delete_option(conn: sqlite3.Connection, option_id: int) -> None:
    """Remove a choice that was added here.

    A built-in is switched off instead. Deleting one would not remove it from
    the invoices that already record it; it would leave those invoices
    referring to something with no label.
    """
    option = get_option(conn, option_id)
    if option["is_builtin"]:
        update_option(conn, option_id, is_active=False)
        return
    conn.execute("DELETE FROM list_options WHERE id = ?", (option_id,))
    conn.commit()


# ---------------------------------------------------------------------------
# Counts
# ---------------------------------------------------------------------------
#
# "2 inspections -- 1 draft, 1 checked", at the top of each list page and
# again on the dashboard.
#
# They come from here rather than being counted separately in each place,
# because two counts of the same thing that disagree are worse than no count
# at all: the one on the dashboard would be quietly wrong and nobody would
# know which to believe.

#: Which statuses each section reports, in the order they should be read.
#: Listed explicitly rather than taken from whatever happens to be in the
#: table, so the answer has the same shape whether or not anything is in that
#: state yet. What to do with the empty ones is a question for the screen:
#: the dashboard shows them, so its tiles do not change shape as the week
#: goes on, and the list pages leave them out, because the list underneath
#: already says what is there.
COUNTED_STATUSES: dict[str, tuple[str, ...]] = {
    "invoices": ("draft", "issued", "void"),
    "estimates": ("draft", "sent", "approved", "declined", "invoiced"),
    "contracts": ("open", "completed", "invoiced", "cancelled"),
    "inspections": ("draft", "checked", "quoted"),
}

_COUNT_TABLES = {
    "invoices": "invoices",
    "estimates": "estimates",
    "contracts": "repair_orders",
    "inspections": "inspections",
}


def status_counts(conn: sqlite3.Connection, section: str) -> dict[str, Any]:
    """How many records a section holds, and how they are split by status.

    Returns ``{"total": n, "by_status": [(status, count), ...]}`` with every
    status the section can have, including the ones at zero.
    """
    table = _COUNT_TABLES[section]
    rows = _all(
        conn,
        f"SELECT status, COUNT(*) AS n FROM {table} GROUP BY status",  # noqa: S608
    )
    found = {row["status"]: row["n"] for row in rows}
    ordered = [(s, found.get(s, 0)) for s in COUNTED_STATUSES[section]]
    # A status that is in the data but not in the list above still has to be
    # counted, or the parts would not add up to the total.
    for status, n in found.items():
        if status not in COUNTED_STATUSES[section]:
            ordered.append((status, n))
    return {"total": sum(found.values()), "by_status": ordered}


def simple_counts(conn: sqlite3.Connection) -> dict[str, Any]:
    """The sections that have no status: how many, and how many are active."""
    def pair(table: str) -> dict[str, int]:
        row = _one(
            conn,
            f"SELECT COUNT(*) AS total,"  # noqa: S608
            f" SUM(CASE WHEN is_active = 1 THEN 1 ELSE 0 END) AS active"
            f" FROM {table}",
        )
        return {"total": row["total"] or 0, "active": row["active"] or 0}

    return {
        "customers": pair("customers"),
        "vehicles": pair("vehicles"),
        "catalog": pair("catalog_items"),
        "issues": pair("known_issues"),
    }


def all_counts(conn: sqlite3.Connection) -> dict[str, Any]:
    """Every count on one call, for the dashboard."""
    counts: dict[str, Any] = {
        section: status_counts(conn, section) for section in COUNTED_STATUSES
    }
    counts.update(simple_counts(conn))
    return counts


def set_customer_alert(
    conn: sqlite3.Connection,
    customer_id: int,
    *,
    level: str,
    note: str,
) -> None:
    """Put a warning on a customer's file, or take one off.

    An empty level clears it, and clears the reason and the date with it: a
    warning that has been lifted should leave nothing behind that could be
    read as still standing.
    """
    level = (level or "").strip()
    if level and level not in ALERT_LEVELS:
        raise ValueError(f"Unknown warning level: {level}")
    get_customer(conn, customer_id)
    with transaction(conn):
        conn.execute(
            """
            UPDATE customers
               SET alert_level  = ?,
                   alert_note   = ?,
                   alert_set_on = ?,
                   updated_at   = datetime('now')
             WHERE id = ?
            """,
            (
                level,
                note.strip() if level else "",
                (date.today().isoformat() if level else ""),
                customer_id,
            ),
        )


def list_flagged_customers(conn: sqlite3.Connection) -> list[Row]:
    """Everyone carrying a warning, worst first.

    Ordered by severity rather than by name, because the reason anyone opens
    this list is to see the refusals.
    """
    return _all(
        conn,
        """
        SELECT *,
               CASE alert_level
                   WHEN 'refuse' THEN 1
                   WHEN 'check'  THEN 2
                   WHEN 'note'   THEN 3
                   ELSE 4
               END AS severity
          FROM customers
         WHERE alert_level <> ''
         ORDER BY severity, name COLLATE NOCASE
        """,
    )


def alert_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """How many customers carry each level of warning."""
    rows = _all(
        conn,
        "SELECT alert_level, COUNT(*) AS n FROM customers"
        " WHERE alert_level <> '' GROUP BY alert_level",
    )
    found = {row["alert_level"]: row["n"] for row in rows}
    counts = {level: found.get(level, 0) for level in ALERT_LEVELS}
    counts["total"] = sum(found.values())
    return counts


def commit_register_import(
    conn: sqlite3.Connection,
    customers: Sequence[Mapping[str, Any]],
    vehicles: Sequence[Mapping[str, Any]],
) -> dict[str, int]:
    """Write a prepared car register: owners first, then their cars.

    One transaction for the lot. A register half-loaded is worse than one
    not loaded at all -- the second attempt would duplicate everything that
    got in on the first, and nobody would know where the join was.

    An existing customer with the same name and number is reused rather than
    duplicated, so running the same file twice does not produce two of
    everybody.
    """
    created_customers = reused_customers = created_vehicles = skipped = 0

    with transaction(conn):
        existing: dict[tuple[str, str], int] = {}
        for row in conn.execute("SELECT id, name, phone FROM customers"):
            key = (
                row["name"].strip().upper(),
                "".join(ch for ch in (row["phone"] or "") if ch.isdigit())[-9:],
            )
            existing.setdefault(key, row["id"])

        ids: list[int] = []
        for customer in customers:
            name = (customer.get("name") or "").strip()
            phone = (customer.get("phone") or "").strip()
            key = (
                name.upper(),
                "".join(ch for ch in phone if ch.isdigit())[-9:],
            )
            if key in existing:
                customer_id = existing[key]
                reused_customers += 1
            else:
                cur = conn.execute(
                    """
                    INSERT INTO customers (name, phone, notes, category)
                    VALUES (?, ?, ?, 'regular')
                    """,
                    (name, phone, (customer.get("notes") or "").strip()),
                )
                customer_id = int(cur.lastrowid)
                existing[key] = customer_id
                created_customers += 1

            level = (customer.get("alert_level") or "").strip()
            if level:
                conn.execute(
                    """
                    UPDATE customers
                       SET alert_level = ?, alert_note = ?, alert_set_on = ?
                     WHERE id = ?
                    """,
                    (
                        level,
                        (customer.get("alert_note") or "").strip(),
                        date.today().isoformat(),
                        customer_id,
                    ),
                )
            ids.append(customer_id)

        for vehicle in vehicles:
            if vehicle.get("skipped"):
                skipped += 1
                continue
            index = vehicle.get("customer_index", -1)
            if not (0 <= index < len(ids)):
                skipped += 1
                continue
            conn.execute(
                """
                INSERT INTO vehicles
                    (customer_id, plate_no, make, model, model_year, vin,
                     colour, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    ids[index],
                    (vehicle.get("plate") or "").strip(),
                    (vehicle.get("make") or "").strip(),
                    (vehicle.get("model") or "").strip(),
                    vehicle.get("model_year"),
                    (vehicle.get("vin") or "").strip(),
                    (vehicle.get("colour") or "").strip(),
                    (vehicle.get("notes") or "").strip(),
                ),
            )
            created_vehicles += 1

    return {
        "customers": created_customers,
        "reused": reused_customers,
        "vehicles": created_vehicles,
        "skipped": skipped,
    }


def cars_by_colour(conn: sqlite3.Connection, limit: int = 8, make: str = "") -> list[Row]:
    """The fleet by colour, commonest first.

    Case-folded, because a register typed over years holds BLACK, Black and
    black and they are one colour.
    """
    clause, params = _make_filter(make)
    return _all(
        conn,
        f"""
        SELECT UPPER(TRIM(colour)) AS label, COUNT(*) AS cars
          FROM vehicles
         WHERE TRIM(COALESCE(colour, '')) <> '' {clause}
         GROUP BY label
         ORDER BY cars DESC
         LIMIT ?
        """,
        [*params, limit],
    )


def cars_by_decade(conn: sqlite3.Connection, make: str = "") -> list[Row]:
    """How old the fleet is, in five-year bands.

    Bands rather than single years: one bar per year over twenty-odd years
    is a picket fence nobody reads, and the question a workshop is asking is
    "how old are these cars", not "exactly how many 2017s".
    """
    clause, params = _make_filter(make)
    return _all(
        conn,
        f"""
        SELECT (model_year / 5) * 5 AS band, COUNT(*) AS cars
          FROM vehicles
         WHERE model_year IS NOT NULL AND model_year BETWEEN 1950 AND 2100 {clause}
         GROUP BY band
         ORDER BY band DESC
        """,
        params,
    )


def cars_with_a_colour(conn: sqlite3.Connection, make: str = "") -> int:
    """How many cars have any colour recorded.

    The donut's slices are shares of this, not of the whole fleet: a car
    with the box left empty belongs to no slice, and putting the fleet
    total in the middle would make the percentages not add up.
    """
    clause, params = _make_filter(make)
    return _one(
        conn,
        "SELECT COUNT(*) AS n FROM vehicles"
        " WHERE TRIM(COALESCE(colour, '')) <> '' " + clause,
        params,
    )["n"]


def colour_values_that_are_not_colours(conn: sqlite3.Connection, make: str = "") -> int:
    """How many cars have something other than a colour in the colour box.

    A register kept by hand collects model codes where the colour goes --
    "320I", "E300", "G12". Counting them is not cleaning them: it is how
    somebody who knows the cars finds out there is something to clean.
    """
    clause, params = _make_filter(make)
    return _one(
        conn,
        f"""
        SELECT COUNT(*) AS n
          FROM vehicles
         WHERE TRIM(COALESCE(colour, '')) <> ''
           AND colour GLOB '*[0-9]*' {clause}
        """,
        params,
    )["n"]


# ---------------------------------------------------------------------------
# Colour and model, written in each other's boxes
# ---------------------------------------------------------------------------
#
# A register kept by hand for years collects this: "320I" where the colour
# goes, "BLUE" where the model goes, and sometimes both at once. It is not a
# fault in the import -- the spreadsheet says exactly that -- but it spoils
# both charts and makes the columns unsortable in any useful way.
#
# Nothing here changes anything on its own. It reports what it would do, and
# the office decides. The rule it applies is deliberately narrow: a value is
# only moved when the box it is in cannot be right and the box it belongs in
# is empty, or when the two are plainly swapped. Anything it is unsure about
# it leaves alone, because a register half-corrected by a guess is worse
# than one left as it was.

#: Colour words a workshop actually writes, including the two-word ones.
#: Matched whole, lower-cased, after collapsing spaces -- "Sky Blue" and
#: "skyblue" are the same answer.
COLOUR_WORDS: frozenset[str] = frozenset({
    "black", "white", "blue", "grey", "gray", "silver", "brown", "beige",
    "red", "green", "gold", "golden", "maroon", "navy", "orange", "yellow",
    "purple", "pink", "bronze", "champagne", "cream", "ivory", "tan",
    "burgundy", "turquoise", "copper", "charcoal", "sand", "olive",
    "sky blue", "skyblue", "dark blue", "light blue", "dark grey",
    "light grey", "dark gray", "light gray", "dark green", "light green",
    "off white", "pearl white", "metallic grey", "dark red", "wine",
})


def _is_colour(value: str) -> bool:
    text = " ".join(str(value or "").strip().lower().split())
    return text in COLOUR_WORDS


def _looks_like_a_model(value: str) -> bool:
    """A model code, as opposed to a colour or a note.

    Short, and carrying a digit or a known body-code shape: "320I", "G12",
    "X5", "E300". Length is part of it -- "Individual" is a trim name and
    "Imported from Germany" is a sentence, and neither belongs in the model
    column just because it is not a colour.
    """
    text = str(value or "").strip()
    if not text or len(text) > 12 or _is_colour(text):
        return False
    compact = text.replace(" ", "").replace("-", "")
    if not compact.isalnum():
        return False
    return any(ch.isdigit() for ch in compact)


def colour_model_mixups(conn: sqlite3.Connection) -> list[dict[str, Any]]:
    """Cars whose colour and model boxes hold each other's answers."""
    found: list[dict[str, Any]] = []
    rows = _all(
        conn,
        """
        SELECT id, plate_no, vin, make, model, colour
          FROM vehicles
         WHERE TRIM(COALESCE(model, '')) <> '' OR TRIM(COALESCE(colour, '')) <> ''
         ORDER BY plate_no COLLATE NOCASE
        """,
    )
    for row in rows:
        model = (row["model"] or "").strip()
        colour = (row["colour"] or "").strip()

        model_is_colour = bool(model) and _is_colour(model)
        colour_is_model = bool(colour) and _looks_like_a_model(colour)

        if model_is_colour and colour_is_model:
            action = "swap"
        elif model_is_colour and not colour:
            action = "to_colour"
        elif colour_is_model and not model:
            action = "to_model"
        else:
            # Includes the case where both boxes hold a colour, or both a
            # model: there is no way to tell which is the right one, so it
            # stays as written.
            continue

        found.append({
            "id": row["id"],
            "plate_no": row["plate_no"] or row["vin"] or "",
            "make": row["make"],
            "model": model,
            "colour": colour,
            "action": action,
            # A moved value leaves its old box empty. Written as `colour`
            # here at first, which left the model code sitting in both
            # columns and fixed nothing.
            "new_model": colour if action in ("swap", "to_model") else "",
            "new_colour": model if action in ("swap", "to_colour") else "",
        })
    return found


def apply_colour_model_fixes(
    conn: sqlite3.Connection, ids: Sequence[int] | None = None
) -> int:
    """Move the values the preview identified. Returns how many cars changed.

    The work is recomputed here rather than taken from the form, so what is
    written is what the preview was built from -- not whatever a posted
    field happens to say.
    """
    wanted = set(ids) if ids is not None else None
    changes = [
        fix for fix in colour_model_mixups(conn)
        if wanted is None or fix["id"] in wanted
    ]
    if not changes:
        return 0
    with transaction(conn):
        for fix in changes:
            conn.execute(
                "UPDATE vehicles SET model = ?, colour = ?,"
                " updated_at = datetime('now') WHERE id = ?",
                (fix["new_model"], fix["new_colour"], fix["id"]),
            )
    return len(changes)
