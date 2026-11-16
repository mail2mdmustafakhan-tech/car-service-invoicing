"""Reading a customer list out of a spreadsheet.

Two jobs, and nothing else: turn an uploaded CSV or Excel file into rows, and
work out what each row would do if it were imported. It writes nothing --
:mod:`app.repository` stores the result as a batch, the user looks at the
preview, and only then is anything created.

That separation is the point. Importing a few hundred customers is the kind
of operation nobody wants to undo by hand, so the question "what exactly is
about to happen" has to be answerable before it happens.
"""

from __future__ import annotations

import csv
import io
from collections.abc import Iterable
from typing import Any

#: Fields a customer row can fill, and the headings people actually write for
#: them. Matching is case-insensitive and ignores spaces, underscores and
#: hyphens, so "Phone Number", "phone_number" and "PHONE-NUMBER" all land in
#: the same place. Arabic headings are matched too, because a list kept by
#: the office is as likely to be in Arabic as in English.
COLUMN_ALIASES: dict[str, tuple[str, ...]] = {
    "name": (
        "name", "customername", "customer", "client", "fullname",
        "الاسم", "اسمالعميل", "العميل",
    ),
    "name_ar": (
        "namear", "arabicname", "namearabic", "nameinarabic",
        "الاسمبالعربية", "الاسمعربي",
    ),
    "phone": (
        "phone", "phonenumber", "mobile", "mobileno", "mobilenumber", "tel",
        "telephone", "contact", "contactnumber",
        "الهاتف", "الجوال", "رقمالجوال", "رقمالهاتف",
    ),
    "email": ("email", "emailaddress", "mail", "البريد", "البريدالإلكتروني"),
    "address": ("address", "location", "city", "العنوان", "المدينة"),
    "vat_number": (
        "vatnumber", "vat", "vatno", "taxnumber", "trn", "vatregistration",
        "الرقمالضريبي", "رقمالضريبة",
    ),
    "notes": ("notes", "note", "remarks", "comment", "comments", "ملاحظات"),
}

#: Offered as a download, so there is a known-good shape to start from.
TEMPLATE_HEADERS = ["name", "name_ar", "phone", "email", "address", "vat_number", "notes"]

TEMPLATE_ROWS = [
    ["Ahmed Al-Qahtani", "أحمد القحطاني", "0551234567", "ahmed@example.com",
     "Al Malaz, Riyadh", "", "Prefers a call before any extra work"],
    ["Riyadh Logistics Co.", "شركة الرياض اللوجستية", "0112345678",
     "fleet@example.com", "Industrial City 2, Riyadh", "300099887700003",
     "Fleet account"],
]

MAX_IMPORT_ROWS = 5000


class ImportError_(ValueError):
    """The uploaded file could not be read. The message is shown to the user."""


def _key(heading: Any) -> str:
    """Reduce a column heading to something comparable."""
    text = str(heading or "").strip().casefold()
    for junk in (" ", "_", "-", ".", "/", "\\", "'", '"'):
        text = text.replace(junk, "")
    return text


def map_columns(headings: Iterable[Any]) -> dict[int, str]:
    """Work out which column holds which field: ``{column index: field}``.

    Unrecognised columns are left out rather than guessed at. A column whose
    heading matches nothing is ignored, and the preview says so, which is
    safer than quietly importing a VAT number into the notes field.

    >>> map_columns(["Customer Name", "Mobile No", "Something else"])
    {0: 'name', 1: 'phone'}
    >>> map_columns(["الاسم", "الجوال"])
    {0: 'name', 1: 'phone'}
    """
    lookup = {alias: field for field, aliases in COLUMN_ALIASES.items() for alias in aliases}
    mapping: dict[int, str] = {}
    taken: set[str] = set()
    for index, heading in enumerate(headings):
        field = lookup.get(_key(heading))
        if field and field not in taken:
            mapping[index] = field
            taken.add(field)
    return mapping


def _read_csv(data: bytes) -> list[list[Any]]:
    # utf-8-sig drops the byte-order mark Excel puts at the front of a CSV it
    # saved, which would otherwise become part of the first heading.
    for encoding in ("utf-8-sig", "utf-16", "cp1256", "latin-1"):
        try:
            text = data.decode(encoding)
            break
        except (UnicodeDecodeError, UnicodeError):
            continue
    else:
        raise ImportError_("That file's text encoding could not be read.")

    sample = text[:4096]
    try:
        dialect = csv.Sniffer().sniff(sample, delimiters=",;\t|")
    except csv.Error:
        dialect = csv.excel
    return [row for row in csv.reader(io.StringIO(text), dialect) if any(
        str(cell).strip() for cell in row
    )]


def _read_xlsx(data: bytes) -> list[list[Any]]:
    try:
        from openpyxl import load_workbook
    except ImportError as exc:  # pragma: no cover - depends on the install
        raise ImportError_(
            "Reading Excel files needs the openpyxl package: pip install openpyxl. "
            "Alternatively, save the sheet as CSV and upload that."
        ) from exc

    try:
        # read_only keeps a large sheet from being loaded into memory whole;
        # data_only takes the value a formula produced rather than the formula.
        book = load_workbook(io.BytesIO(data), read_only=True, data_only=True)
    except Exception as exc:
        raise ImportError_("That file could not be opened as a spreadsheet.") from exc

    sheet = book.active
    rows = [
        list(row) for row in sheet.iter_rows(values_only=True)
        if row and any(str(cell).strip() for cell in row if cell is not None)
    ]
    book.close()
    return rows


def read_table(data: bytes, filename: str) -> list[list[Any]]:
    """Read an upload into rows, choosing the parser by what the file is.

    The extension decides, but the bytes get the final say: a .csv that is
    really a workbook, or a .xlsx that is really a CSV, are both common when
    someone renames a file, and both are handled.
    """
    if not data:
        raise ImportError_("That file is empty.")

    # A file renamed to .csv is still whatever it was. Without this, a PDF or
    # an image decodes as latin-1 into thousands of lines of nonsense and the
    # preview fills with garbage rows instead of saying what went wrong.
    for signature, what in (
        (b"%PDF-", "a PDF"),
        (b"\x89PNG\r\n\x1a\n", "an image"),
        (b"\xff\xd8\xff", "an image"),
        (b"GIF8", "an image"),
        (b"\xd0\xcf\x11\xe0", "an old .xls file"),
    ):
        if data.startswith(signature):
            extra = (
                " Open it in Excel and save it as .xlsx or .csv."
                if what.endswith("file") else ""
            )
            raise ImportError_(f"That is {what}, not a spreadsheet.{extra}")

    looks_like_zip = data[:2] == b"PK"          # every .xlsx is a zip
    wants_excel = filename.lower().endswith((".xlsx", ".xlsm"))

    # Text files do not contain null bytes; binary ones almost always do.
    if not looks_like_zip and b"\x00" in data[:8192]:
        raise ImportError_("That does not look like a spreadsheet or a CSV file.")

    if looks_like_zip or wants_excel:
        if not looks_like_zip:
            raise ImportError_(
                "That does not look like an Excel file. If it is really a CSV, "
                "rename it to .csv and upload it again."
            )
        rows = _read_xlsx(data)
    else:
        rows = _read_csv(data)

    if not rows:
        raise ImportError_("No rows were found in that file.")
    if len(rows) > MAX_IMPORT_ROWS + 1:
        raise ImportError_(
            f"That file has more than {MAX_IMPORT_ROWS:,} rows. "
            "Split it and import it in parts."
        )
    return rows


def _clean(value: Any) -> str:
    if value is None:
        return ""
    # A phone number in Excel often arrives as a float: 551234567.0
    if isinstance(value, float) and value.is_integer():
        return str(int(value))
    return str(value).strip()


def prepare(
    rows: list[list[Any]],
    *,
    existing_names: set[str],
    existing_phones: set[str],
    mapping: dict[int, str] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any]]:
    """Turn raw rows into what the preview shows.

    Returns the prepared rows and a summary. Every row comes back, including
    the ones that will be skipped and why -- a preview that silently drops
    rows is worse than no preview, because the count looks right.

    Duplicates are detected within the file as well as against what is
    already stored: the same customer twice in one spreadsheet is common.
    """
    if not rows:
        return [], {"total": 0, "ready": 0, "skipped": 0, "unmapped": [], "fields": []}

    headings = rows[0]
    column_map = mapping if mapping is not None else map_columns(headings)
    if "name" not in column_map.values():
        raise ImportError_(
            "No name column was found. The file needs a column headed Name "
            "(or الاسم). Download the template to see the expected headings."
        )

    unmapped = [
        _clean(heading) for index, heading in enumerate(headings)
        if index not in column_map and _clean(heading)
    ]

    prepared: list[dict[str, Any]] = []
    seen_names: set[str] = set()
    seen_phones: set[str] = set()

    for line_no, raw in enumerate(rows[1:], start=2):
        record: dict[str, Any] = {"line": line_no, "skip": False, "note": ""}
        for index, field in column_map.items():
            record[field] = _clean(raw[index]) if index < len(raw) else ""

        name = record.get("name", "")
        phone_digits = "".join(ch for ch in record.get("phone", "") if ch.isdigit())

        if not name:
            record["skip"] = True
            record["note"] = "No name"
        elif name.casefold() in seen_names:
            record["skip"] = True
            record["note"] = "Repeated in this file"
        elif phone_digits and phone_digits in seen_phones:
            record["skip"] = True
            record["note"] = "Same phone as an earlier row in this file"
        elif name.casefold() in existing_names:
            record["skip"] = True
            record["note"] = "Already on file"
        elif phone_digits and phone_digits in existing_phones:
            record["skip"] = True
            record["note"] = "A customer with this phone is already on file"

        if not record["skip"]:
            seen_names.add(name.casefold())
            if phone_digits:
                seen_phones.add(phone_digits)

        prepared.append(record)

    ready = sum(1 for r in prepared if not r["skip"])
    summary = {
        "total": len(prepared),
        "ready": ready,
        "skipped": len(prepared) - ready,
        "unmapped": unmapped,
        "fields": sorted(set(column_map.values())),
    }
    return prepared, summary


def template_csv() -> bytes:
    """The downloadable starting point, with a couple of example rows."""
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(TEMPLATE_HEADERS)
    writer.writerows(TEMPLATE_ROWS)
    # The BOM makes Excel open a UTF-8 CSV with the Arabic intact instead of
    # as mojibake, which is otherwise the first thing that goes wrong.
    return b"\xef\xbb\xbf" + buffer.getvalue().encode("utf-8")
