"""Importing the service and parts list from a spreadsheet.

The third importer, after customers and vehicles, and it follows their
shape: read the file, map the columns by their headings, show every row
with what will happen to it, and only write once somebody has looked.

Why an importer and not a migration seeded with the list: a workshop's
item list is its own data. The software ships with an empty catalogue and
each centre fills it. A price list baked into the schema would arrive in
every other installation of this program, which is not a thing to do to
somebody. It also means the list can be imported again as it grows,
rather than once, by hand, forever.

Codes are read as text and never as numbers. Every code in the Advance
Repair Center list has a leading zero -- 0123, and one 00163 -- and a
spreadsheet cell holding 0123 often arrives as the number 123. Read as a
number it comes back 123, which no longer matches the paperwork the code
exists to match.
"""

from __future__ import annotations

from typing import Any

from .importing import ImportError_, _clean, _key, read_table

MAX_IMPORT_ROWS = 5000

#: What a column can be called. Case, spaces, underscores and hyphens are
#: ignored, and Arabic headings are matched because an office list is as
#: likely to be kept in Arabic as in English.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "code": (
        "code", "itemcode", "itemno", "itemnumber", "partno", "partnumber",
        "sku", "ref", "reference",
        "الرمز", "رقمالصنف", "كود", "رقمالقطعة",
        # Deliberately not a bare "no". A column headed No is almost
        # always the row counter down the left of a printed list, and
        # taking it as the code meant every item imported as 1, 2, 3 --
        # with the real "Item No" column left unmapped beside it.
    ),
    "name_en": (
        "name", "description", "item", "itemname", "englishname", "nameen",
        "descriptionen", "service", "particulars",
    ),
    "name_ar": (
        "namear", "arabicname", "namearabic", "descriptionar", "arabic",
        "الاسم", "الوصف", "البيان", "الصنف",
    ),
    "unit": ("unit", "uom", "unitofmeasure", "measure", "الوحدة"),
    "unit_price": (
        "price", "unitprice", "rate", "amount", "cost", "sellingprice",
        "السعر", "سعرالوحدة", "القيمة",
    ),
    "kind": ("kind", "type", "category", "النوع", "الفئة"),
}

#: The report Mohammed supplied calls every unit قطعة. The catalogue's own
#: unit values are the ones in Settings -> Dropdown lists, so anything not
#: recognised here is left for him to set rather than guessed at.
UNIT_ALIASES: dict[str, tuple[str, ...]] = {
    "pcs": ("pcs", "pc", "piece", "pieces", "each", "ea", "no", "nos",
            "قطعة", "قطع", "حبة", "عدد"),
    "hour": ("hour", "hours", "hr", "hrs", "ساعة", "ساعات"),
    "litre": ("litre", "liter", "litres", "liters", "l", "ltr", "لتر"),
    "set": ("set", "sets", "طقم"),
}

TEMPLATE_HEADERS = ["code", "name", "name_ar", "kind", "unit", "price"]

TEMPLATE_ROWS = [
    ["0123", "Oil Service With Filter", "خدمة تغيير الزيت مع الفلتر",
     "service", "pcs", "350"],
    ["0130", "Air Filter", "فلتر هواء", "part", "pcs", "120"],
]


def map_columns(headings: Any) -> dict[int, str]:
    """Work out which column holds which field: ``{column index: field}``.

    A heading that matches nothing is ignored rather than guessed at, and
    the preview lists what was ignored.

    >>> map_columns(["Item No", "Description", "Unit", "Quantity"])
    {0: 'code', 1: 'name_en', 2: 'unit'}
    """
    lookup = {alias: field
              for field, aliases in COLUMN_ALIASES.items()
              for alias in aliases}
    mapping: dict[int, str] = {}
    taken: set[str] = set()
    for index, heading in enumerate(headings):
        field = lookup.get(_key(heading))
        if field and field not in taken:
            mapping[index] = field
            taken.add(field)
    return mapping


def normalise_unit(value: str) -> str:
    """Map a written unit onto one the catalogue uses, or leave it alone.

    >>> normalise_unit("قطعة")
    'pcs'
    >>> normalise_unit("Hours")
    'hour'
    >>> normalise_unit("drum")
    'drum'
    """
    key = _key(value)
    for unit, aliases in UNIT_ALIASES.items():
        if key in aliases:
            return unit
    return _clean(value)


def _price_minor(value: str) -> int | None:
    """Read a price, or None when the cell holds nothing usable.

    None and zero are different answers and the preview says so: a blank
    price column means "he will fill these in", while a zero somebody
    typed means zero.
    """
    text = _clean(value).replace(",", "")
    if not text:
        return None
    try:
        return int(round(float(text) * 100))
    except ValueError:
        return None


def prepare(
    rows: list[list[Any]],
    *,
    existing_codes: set[str],
    existing_names: set[str],
    mapping: dict[int, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Turn raw rows into what the preview shows.

    Every row comes back, including the ones that will be skipped and
    why. A preview that silently drops rows is worse than no preview,
    because the count looks right.
    """
    empty = {"total": 0, "ready": 0, "skipped": 0, "unmapped": [],
             "fields": [], "priced": 0}
    if not rows:
        return [], empty

    headings = rows[0]
    column_map = mapping if mapping is not None else map_columns(headings)
    named = set(column_map.values())
    if not named & {"name_en", "name_ar"}:
        raise ImportError_(
            "No description column was found. The file needs a column "
            "headed Description or Name (or الوصف). Download the template "
            "to see the expected headings."
        )

    unmapped = [_clean(h) for i, h in enumerate(headings)
                if i not in column_map and _clean(h)]

    body = rows[1:]
    if len(body) > MAX_IMPORT_ROWS:
        raise ImportError_(
            f"That file has {len(body):,} rows. The most that can be "
            f"imported at once is {MAX_IMPORT_ROWS:,}."
        )

    seen_codes: set[str] = set()
    seen_names: set[str] = set()
    prepared: list[dict[str, Any]] = []

    for offset, raw in enumerate(body, start=2):
        values = {field: _clean(raw[i]) if i < len(raw) else ""
                  for i, field in column_map.items()}

        code = values.get("code", "")
        name_en = values.get("name_en", "")
        name_ar = values.get("name_ar", "")
        # A row written only in Arabic has no English wording of its own.
        # Carrying the Arabic across keeps it visible and pickable on the
        # English side instead of leaving a blank nobody can choose.
        if not name_en and name_ar:
            name_en = name_ar

        kind = values.get("kind", "").strip().lower()
        if kind not in ("service", "part"):
            kind = "service"

        row: dict[str, Any] = {
            "row": offset,
            "code": code,
            "name_en": name_en,
            "name_ar": name_ar,
            "kind": kind,
            "unit": normalise_unit(values.get("unit", "")) or "pcs",
            "unit_price_minor": _price_minor(values.get("unit_price", "")),
            "skip": "",
        }

        # A reason is a key and its argument, not a sentence. Built as a
        # sentence here it reaches the page already in English, and the
        # Arabic preview shows "Code 0123 is already in the catalogue"
        # in the middle of an otherwise Arabic table.
        if not name_en:
            row["skip"] = "iimp.skip_no_description"
        elif code and code in existing_codes:
            row["skip"] = "iimp.skip_code_exists"
        elif code and code in seen_codes:
            row["skip"] = "iimp.skip_code_repeated"
        elif not code and name_en.casefold() in existing_names:
            row["skip"] = "iimp.skip_exists"
        elif not code and name_en.casefold() in seen_names:
            row["skip"] = "iimp.skip_repeated"

        if not row["skip"]:
            if code:
                seen_codes.add(code)
            seen_names.add(name_en.casefold())
        prepared.append(row)

    ready = [r for r in prepared if not r["skip"]]
    summary = {
        "total": len(prepared),
        "ready": len(ready),
        "skipped": len(prepared) - len(ready),
        "unmapped": unmapped,
        "fields": sorted(named),
        # Said plainly on the preview, because a catalogue full of zeroes
        # is the sort of thing that is discovered halfway through raising
        # an invoice in front of a customer.
        "priced": sum(1 for r in ready if r["unit_price_minor"]),
    }
    return prepared, summary


def template_xlsx() -> bytes:
    """A blank file with the right headings, offered as a download."""
    from io import BytesIO

    from openpyxl import Workbook

    book = Workbook()
    sheet = book.active
    sheet.title = "Items"
    sheet.append(TEMPLATE_HEADERS)
    for row in TEMPLATE_ROWS:
        sheet.append(row)
    # Text, so a code keeps the zero somebody typed in front of it.
    for cell in sheet["A"]:
        cell.number_format = "@"
    for width, column in zip((12, 46, 36, 12, 10, 12), "ABCDEF", strict=False):
        sheet.column_dimensions[column].width = width

    buffer = BytesIO()
    book.save(buffer)
    return buffer.getvalue()


__all__ = [
    "COLUMN_ALIASES",
    "ImportError_",
    "map_columns",
    "normalise_unit",
    "prepare",
    "read_table",
    "template_xlsx",
]
