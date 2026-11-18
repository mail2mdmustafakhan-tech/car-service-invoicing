"""Bring a workshop's car register in from a spreadsheet.

This is a different shape of import from the customer list in `importing.py`.
There, one row is one customer. Here one row is one *car*, and the customer
is repeated down the sheet -- a register kept at a counter, in the order
cars arrived, over years. One owner with seven cars is seven rows.

So the work is mostly deciding what counts as the same person, and keeping
the parts of the sheet that are real information rather than formatting.

Nothing here writes to the database. It reads a file and returns what it
found, so the preview the office looks at is built from the same pass that
the import will use -- a preview assembled separately from the import is a
preview of something else.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field
from typing import Any

#: The columns this understands, and the headings a register actually uses.
#: Matched case-insensitively with spaces and punctuation removed.
REGISTER_COLUMNS: dict[str, tuple[str, ...]] = {
    "file_no": ("fileno", "file", "no", "serial", "sr", "رقمالملف"),
    "make": ("make", "car", "brand", "vehicle", "النوع", "الماركة"),
    "plate": ("plate", "plateno", "platenumber", "reg", "regno", "اللوحة", "رقماللوحة"),
    "colour": ("color", "colour", "اللون"),
    "model_year": ("year", "model", "modelyear", "السنة", "الموديل"),
    "vin": ("vin", "chassis", "chassisno", "الهيكل", "رقمالهيكل"),
    "name": ("customername", "customer", "name", "owner", "client", "الاسم", "العميل"),
    "phone": ("mobile", "phone", "mobileno", "contact", "tel", "الجوال", "الهاتف"),
    "comments": ("comments", "comment", "notes", "remarks", "ملاحظات"),
}

#: Columns that exist in the sheet but are somebody's scratch pad rather than
#: data about the car on that row -- a phone number for a supplier, a plate
#: belonging to a different job. Named so they can be reported as skipped
#: instead of quietly swept into a customer's notes.
SCRATCH_COLUMNS: tuple[str, ...] = ("numbers", "number", "extra")

#: Makes written more than one way. The register has 151 cars under "MERC"
#: and 116 under "MERCEDES BENZ", which are the same make and should not be
#: two entries in a list of what the workshop works on.
MAKE_ALIASES: dict[str, str] = {
    "MERC": "Mercedes-Benz",
    "MERCEDES": "Mercedes-Benz",
    "MERCEDES BENZ": "Mercedes-Benz",
    "MERCEDES-BENZ": "Mercedes-Benz",
    "BENZ": "Mercedes-Benz",
    "BMW": "BMW",
    "AUDI": "Audi",
    "VW": "Volkswagen",
    "VOLKSWAGEN": "Volkswagen",
    "PORSCHE": "Porsche",
    "VOLVO": "Volvo",
    "ROLLS ROYCE": "Rolls-Royce",
    "ROLLSROYCE": "Rolls-Royce",
    "ROLLS-ROYCE": "Rolls-Royce",
    "RR": "Rolls-Royce",
    "RANGE ROVER": "Range Rover",
    "LAND ROVER": "Land Rover",
    "MINI": "MINI",
    "TOYOTA": "Toyota",
    "LEXUS": "Lexus",
    "NISSAN": "Nissan",
    "HYUNDAI": "Hyundai",
    "KIA": "Kia",
    "FORD": "Ford",
    "CHEVROLET": "Chevrolet",
    "GMC": "GMC",
    "JAGUAR": "Jaguar",
    "BENTLEY": "Bentley",
    "MASERATI": "Maserati",
    "FERRARI": "Ferrari",
    "LAMBORGHINI": "Lamborghini",
    "CADILLAC": "Cadillac",
    "DODGE": "Dodge",
    "JEEP": "Jeep",
    "HONDA": "Honda",
    "MAZDA": "Mazda",
    "MITSUBISHI": "Mitsubishi",
    "INFINITI": "Infiniti",
    "PEUGEOT": "Peugeot",
    "RENAULT": "Renault",
    "ISUZU": "Isuzu",
    "CHRYSLER": "Chrysler",
    "LINCOLN": "Lincoln",
    "CHANGAN": "Changan",
    "ALPINA": "Alpina",
    "MG": "MG",
    # The same word misspelt. These are not guesses at an unfamiliar name --
    # they are one make written two ways, and left alone they would show up
    # as separate makes in a workshop's own list of what it works on.
    "BWM": "BMW",
    "BMV": "BMW",
    "PORCSHE": "Porsche",
    "PORCHE": "Porsche",
    "JAUGAR": "Jaguar",
    "CHYSLER": "Chrysler",
    "MERCEDES BENZ AMG": "Mercedes-Benz",
    # A Range Rover written as just "Range": there is nothing else it is.
    "RANGE": "Range Rover",
}

#: Phrases that turn a red mark into a refusal rather than a note. Matched
#: against the comment, lowercased, punctuation and spacing loosened --
#: the register has "PLEASE DO NOT RECEIVE THIS CAR", "Do Not Receive this
#: car" and "Don't Receive this car and don't give history", which are one
#: instruction written three ways on three different days.
REFUSE_PHRASES: tuple[str, ...] = (
    "do not receive",
    "dont receive",
    "donot receive",
    "do not accept",
    "dont accept",
    "blacklist",
    "black list",
)

#: Phrases that mean "ask somebody first".
CHECK_PHRASES: tuple[str, ...] = (
    "inform before",
    "before receiving",
    "please discuss",
    "discuss and open",
    "caution",
    "check with",
    "ask before",
)

MAX_REGISTER_ROWS = 20_000


class RegisterImportError(ValueError):
    """The file cannot be read as a register at all."""


@dataclass
class VehicleRow:
    """One car, and whatever the register knows about whose it is."""

    line: int
    plate: str = ""
    make: str = ""
    model: str = ""
    model_year: int | None = None
    vin: str = ""
    colour: str = ""
    notes: str = ""
    #: Which prepared customer this car belongs to, by index.
    customer_index: int = -1
    skipped: str = ""


@dataclass
class CustomerRow:
    """One owner, gathered from every row that names them."""

    name: str
    phone: str = ""
    notes: str = ""
    alert_level: str = ""
    alert_note: str = ""
    #: Lines of the sheet this customer was built from, for the report.
    lines: list[int] = field(default_factory=list)
    placeholder: bool = False


def _key(heading: Any) -> str:
    return re.sub(r"[^a-z؀-ۿ]", "", str(heading or "").lower())


def map_columns(headings: list[Any]) -> tuple[dict[int, str], list[str]]:
    """Work out which column is which. Returns the map and what was ignored."""
    lookup = {
        alias: field_name
        for field_name, aliases in REGISTER_COLUMNS.items()
        for alias in aliases
    }
    mapping: dict[int, str] = {}
    ignored: list[str] = []
    for index, heading in enumerate(headings):
        key = _key(heading)
        if not key:
            continue
        if key in SCRATCH_COLUMNS:
            ignored.append(str(heading).strip())
            continue
        field_name = lookup.get(key)
        # First column to claim a field keeps it: a register often has a
        # second "notes" further along that holds something else entirely.
        if field_name and field_name not in mapping.values():
            mapping[index] = field_name
        elif str(heading).strip():
            ignored.append(str(heading).strip())
    return mapping, ignored


def clean(value: Any) -> str:
    """One line of text, with the register's own punctuation taken off.

    Phone numbers in this register are written "*0501234567" -- the asterisk
    is a mark somebody made at a counter, not part of the number.
    """
    if value is None:
        return ""
    text = str(value).replace(" ", " ").strip()
    text = re.sub(r"\s+", " ", text)
    return text.lstrip("*").strip()


def split_phones(raw: str) -> tuple[str, list[str]]:
    """The first number, and any others written in the same cell.

    "0506095406/0502478888" is two numbers for one person. The first becomes
    the phone; the rest are kept as a note rather than thrown away, because
    the second number is often the one that answers.
    """
    text = clean(raw)
    if not text:
        return "", []
    # "0504161769 (Driver 0539575410)" -- the bracket holds a second person,
    # not more of the first number.
    text = text.replace("(", "/").replace(")", " ")
    parts = [p.strip() for p in re.split(r"[/,;]| or ", text) if p.strip()]
    if not parts:
        return "", []
    return parts[0], [p for p in parts[1:] if p]


def split_plates(raw: str) -> tuple[str, list[str]]:
    """The plate, and any others in the same cell.

    120 rows hold two: a car that was re-plated, or a pair kept together.
    """
    text = clean(raw)
    if not text:
        return "", []
    parts = [p.strip() for p in text.split("/") if p.strip()]
    if not parts:
        return "", []
    return parts[0], parts[1:]


def split_makes(raw: str) -> tuple[str, list[str]]:
    """The make, and any others written in the same cell.

    Some rows record two cars on one line -- "BMW/RR" against plates
    "76XKA/4710KGJ". The first make is taken and the rest noted, rather than
    a second vehicle being conjured out of the pairing: the register is
    ambiguous about which plate belongs to which, and a car record invented
    from a guess is worse than a note saying what was written.
    """
    text = clean(raw)
    if not text:
        return "", []
    parts = [p.strip() for p in re.split(r"[/&+]| and ", text) if p.strip()]
    if not parts:
        return "", []
    return normalise_make(parts[0]), [normalise_make(p) for p in parts[1:]]


def normalise_make(raw: str) -> str:
    text = clean(raw)
    if not text:
        return ""
    key = re.sub(r"[^A-Z ]", "", text.upper()).strip()
    if key in MAKE_ALIASES:
        return MAKE_ALIASES[key]
    squashed = key.replace(" ", "")
    for alias, proper in MAKE_ALIASES.items():
        if alias.replace(" ", "") == squashed:
            return proper
    # Unknown make: title-cased rather than left shouting in capitals, but
    # otherwise exactly as written. Guessing at an unfamiliar name is how a
    # register ends up with cars nobody can find.
    return text.title() if text.isupper() else text


def split_year(raw: Any) -> tuple[int | None, str]:
    """A model year, and anything else that was written in that column.

    The column is headed "Year" and holds 2013 most of the time, but also
    "420I" and "G12" -- a model, written where the year goes. Both are worth
    keeping; only one of them is a year.
    """
    text = clean(raw)
    if not text:
        return None, ""
    match = re.search(r"(19|20)\d{2}", text)
    if match:
        year = int(match.group(0))
        rest = (text[: match.start()] + " " + text[match.end() :]).strip(" -/,")
        return year, rest
    return None, text


def _phone_digits(value: str) -> str:
    return re.sub(r"\D", "", value)


def classify_alert(comment: str, marked: bool) -> tuple[str, str]:
    """Decide what a comment means, given whether the row was marked.

    The mark says "look at this row". The words say what to do about it, and
    they are what decides the level -- a row marked because somebody wrote
    the driver's name in red is not a refusal, and treating it as one would
    teach people to dismiss refusals.

    A marked row whose words say nothing in particular still gets a flag, at
    the mildest level. Somebody marked it for a reason that may not be in the
    file, and quietly dropping it would lose the only trace of that reason.
    """
    text = clean(comment).lower()
    loose = re.sub(r"[^a-z ]", "", text.replace("’", "").replace("'", ""))

    if marked or text:
        for phrase in REFUSE_PHRASES:
            if phrase in loose:
                return "refuse", clean(comment)
        for phrase in CHECK_PHRASES:
            if phrase in loose:
                return "check", clean(comment)
    if marked:
        return "note", clean(comment)
    return "", ""


def prepare(
    rows: list[list[Any]],
    marked_lines: dict[int, set[int]] | set[int],
    *,
    existing_customers: dict[tuple[str, str], int] | None = None,
    existing_plates: set[str] | None = None,
) -> dict[str, Any]:
    """Read the sheet into customers and cars, ready to be written.

    `marked_lines` maps a 1-based row number to the columns that were
    highlighted in it. How a highlight was made is the file reader's
    question, not this one's.

    A mark only counts if it is in a column this import reads. Red in a
    scratch column is about whatever somebody jotted there -- a supplier's
    number, a plate from another job -- and flagging a customer over it
    would put warnings on people nobody warned about.
    """
    if not rows:
        raise RegisterImportError("The file is empty.")
    if len(rows) > MAX_REGISTER_ROWS:
        raise RegisterImportError(
            f"The file holds {len(rows):,} rows. The most this can take at "
            f"once is {MAX_REGISTER_ROWS:,}."
        )

    if isinstance(marked_lines, set):  # older callers, and the simple case
        marked_lines = {line: set() for line in marked_lines}

    mapping, ignored = map_columns(rows[0])
    read_columns = set(mapping)
    fields = set(mapping.values())
    if "plate" not in fields and "vin" not in fields:
        raise RegisterImportError(
            "No Plate or Vin column was found, so there is no way to tell "
            "one car from another. The file needs at least one of them."
        )

    existing_customers = dict(existing_customers or {})
    existing_plates = set(existing_plates or ())

    customers: list[CustomerRow] = []
    by_key: dict[tuple[str, str], int] = {}
    vehicles: list[VehicleRow] = []
    seen_plates: set[str] = set()

    for line_no, raw in enumerate(rows[1:], start=2):
        cell = {
            name: clean(raw[index]) if index < len(raw) else ""
            for index, name in mapping.items()
        }

        name = cell.get("name", "")
        phone, extra_phones = split_phones(cell.get("phone", ""))
        plate, extra_plates = split_plates(cell.get("plate", ""))
        vin = cell.get("vin", "")
        make, extra_makes = split_makes(cell.get("make", ""))
        year, model_from_year = split_year(cell.get("model_year", ""))
        comment = cell.get("comments", "")

        if not any((name, phone, plate, vin, make)):
            continue

        # --- whose car is it ------------------------------------------------
        # Same name and same number is the same person. A name with no number
        # is kept apart from the same name with one: this register holds
        # several bare "MOHAMMED"s, and merging them would invent a
        # relationship between people who have nothing to do with each other.
        placeholder = False
        if not name:
            # The car is real even when the owner's name was never written
            # down. Each gets its own placeholder rather than all of them
            # sharing one, which would read as a single person's fleet.
            label = plate or vin or f"row {line_no}"
            name = f"(no name) {label}"
            placeholder = True

        key = (name.upper(), _phone_digits(phone)[-9:])
        if key in by_key:
            customer = customers[by_key[key]]
            customer.lines.append(line_no)
            if not customer.phone and phone:
                customer.phone = phone
        else:
            customer = CustomerRow(name=name, phone=phone, placeholder=placeholder)
            customer.lines.append(line_no)
            by_key[key] = len(customers)
            customers.append(customer)

        notes: list[str] = []
        if extra_phones:
            notes.append("Also: " + ", ".join(extra_phones))
        for note in notes:
            if note not in customer.notes:
                customer.notes = (customer.notes + "\n" + note).strip()

        # --- the warning ----------------------------------------------------
        marked_columns = marked_lines.get(line_no)
        # An empty set means the caller did not say which columns, so take
        # the row's word for it.
        row_marked = marked_columns is not None and (
            not marked_columns or bool(marked_columns & read_columns)
        )
        level, reason = classify_alert(comment, row_marked)
        if level:
            order = {"refuse": 3, "check": 2, "note": 1, "": 0}
            if order[level] > order[customer.alert_level]:
                customer.alert_level = level
                customer.alert_note = reason or ""
            elif level == customer.alert_level and reason and reason not in customer.alert_note:
                customer.alert_note = f"{customer.alert_note}; {reason}".strip("; ")

        # --- the car --------------------------------------------------------
        car_notes: list[str] = []
        if model_from_year:
            car_notes.append(model_from_year)
        if extra_plates:
            car_notes.append("Also plated: " + ", ".join(extra_plates))
        if extra_makes:
            car_notes.append("Also written on this line: " + ", ".join(extra_makes))
        # A comment that became a warning is on the customer; one that did
        # not is about this car, and belongs with it.
        if comment and not level:
            car_notes.append(comment)
        elif comment and level == "note":
            car_notes.append(comment)

        vehicle = VehicleRow(
            line=line_no,
            plate=plate,
            make=make,
            model=model_from_year,
            model_year=year,
            vin=vin,
            colour=cell.get("colour", ""),
            notes="\n".join(n for n in car_notes if n),
            customer_index=by_key[key],
        )

        plate_key = plate.upper().replace(" ", "")
        if not plate and not vin:
            vehicle.skipped = "no plate or chassis number"
        elif plate_key and plate_key in seen_plates:
            vehicle.skipped = "this plate is already in the file"
        elif plate_key and plate_key in existing_plates:
            vehicle.skipped = "this plate is already in the system"
        else:
            if plate_key:
                seen_plates.add(plate_key)
        vehicles.append(vehicle)

    # --- one safe merge -----------------------------------------------------
    # A row that names somebody but gives no number is its own customer so
    # far, because several different people in this register are written
    # down as just "MOHAMMED" and joining them would invent a relationship.
    # But where a name appears with exactly one number anywhere in the file,
    # the numberless rows for that name are that person -- there is nobody
    # else they could be. Where the name has two or more numbers against it,
    # they stay apart: that is precisely the case we cannot resolve.
    merged = _merge_numberless(customers, vehicles)

    flagged = [c for c in customers if c.alert_level]
    return {
        "customers": customers,
        "vehicles": vehicles,
        "merged": merged,
        "ignored_columns": ignored,
        "mapping": mapping,
        "summary": {
            "rows": len(rows) - 1,
            "customers": len(customers),
            "placeholders": sum(1 for c in customers if c.placeholder),
            "vehicles": sum(1 for v in vehicles if not v.skipped),
            "skipped": sum(1 for v in vehicles if v.skipped),
            "merged": merged,
            "flagged": len(flagged),
            "refuse": sum(1 for c in flagged if c.alert_level == "refuse"),
            "check": sum(1 for c in flagged if c.alert_level == "check"),
            "note": sum(1 for c in flagged if c.alert_level == "note"),
            "makes": sorted({v.make for v in vehicles if v.make}),
        },
    }


# ---------------------------------------------------------------------------
# Reading the file
# ---------------------------------------------------------------------------

#: Red, in the handful of ways a spreadsheet writes it. A register marked up
#: over years by different people at different times will hold more than one.
RED_ARGB = {"FFFF0000", "FFC00000", "FFCC0000", "FFE60000", "FF9C0006", "FFFF3300"}


def _is_red(colour: Any) -> bool:
    """Whether a cell's colour counts as the red somebody marked it with."""
    if colour is None:
        return False
    rgb = getattr(colour, "rgb", None)
    # openpyxl hands back a descriptor object rather than a string when the
    # colour is a theme or an index, and comparing that to a string is how
    # you silently decide nothing is red.
    if not isinstance(rgb, str):
        return False
    return rgb.upper() in RED_ARGB


def read_xlsx(data: bytes) -> tuple[list[list[Any]], dict[int, set[int]]]:
    """Rows, and which of them the spreadsheet marked.

    The mark is the whole reason this reader exists rather than a plain
    table read: in this register the red is the warning, and a reader that
    only takes the values throws away the most important column in the file
    -- the one that was never a column.

    Red text and a red fill both count. People reach for whichever is to
    hand, and both mean "look at this row".
    """
    try:
        import openpyxl
    except ImportError:  # pragma: no cover - openpyxl ships with the app
        raise RegisterImportError("Reading .xlsx files needs openpyxl.") from None

    import io

    try:
        book = openpyxl.load_workbook(io.BytesIO(data), data_only=True)
    except Exception:
        raise RegisterImportError(
            "That file could not be opened as a spreadsheet."
        ) from None

    # The sheet with the most rows: a register workbook usually carries a
    # chart tab and a scratch tab beside the real one.
    sheet = max(book.worksheets, key=lambda ws: ws.max_row * max(ws.max_column, 1))

    rows: list[list[Any]] = []
    # Which columns were marked, not merely that the row was. A register
    # usually has a scratch column where somebody keeps a supplier's phone
    # number, and red in there is about the number, not about the customer.
    marked: dict[int, set[int]] = {}
    for r, row in enumerate(sheet.iter_rows(), start=1):
        rows.append([c.value for c in row])
        if r == 1:
            continue  # the heading row is often filled; that is not a mark
        for index, cell in enumerate(row):
            font = getattr(cell, "font", None)
            fill = getattr(cell, "fill", None)
            red = (font is not None and _is_red(font.color)) or (
                fill is not None
                and getattr(fill, "fill_type", None) == "solid"
                and _is_red(fill.start_color)
            )
            if red:
                marked.setdefault(r, set()).add(index)
    return rows, marked


def _merge_numberless(
    customers: list[CustomerRow], vehicles: list[VehicleRow]
) -> int:
    """Fold "NAME with no number" into "NAME with one number", where safe.

    Only when that name has exactly one number against it in the whole file.
    With two or more it is left alone, because choosing between them would
    be a guess, and a guess here puts one person's car on another person's
    record.

    Returns how many customers were folded away.
    """
    with_phone: dict[str, list[int]] = {}
    without: dict[str, list[int]] = {}
    for index, customer in enumerate(customers):
        if customer.placeholder:
            continue
        key = customer.name.upper()
        (with_phone if customer.phone else without).setdefault(key, []).append(index)

    moves: dict[int, int] = {}
    for key, idle in without.items():
        candidates = with_phone.get(key, [])
        if len(candidates) != 1:
            continue
        target = candidates[0]
        for index in idle:
            moves[index] = target

    if not moves:
        return 0

    for index, target in moves.items():
        source = customers[index]
        keeper = customers[target]
        keeper.lines.extend(source.lines)
        if source.notes and source.notes not in keeper.notes:
            keeper.notes = (keeper.notes + "\n" + source.notes).strip()
        order = {"refuse": 3, "check": 2, "note": 1, "": 0}
        if order[source.alert_level] > order[keeper.alert_level]:
            keeper.alert_level = source.alert_level
            keeper.alert_note = source.alert_note

    for vehicle in vehicles:
        if vehicle.customer_index in moves:
            vehicle.customer_index = moves[vehicle.customer_index]

    # Drop the folded customers and renumber what the cars point at.
    keep = [i for i in range(len(customers)) if i not in moves]
    renumber = {old: new for new, old in enumerate(keep)}
    kept = [customers[i] for i in keep]
    customers[:] = kept
    for vehicle in vehicles:
        vehicle.customer_index = renumber.get(vehicle.customer_index, vehicle.customer_index)
    return len(moves)


# ---------------------------------------------------------------------------
# A template to fill in
# ---------------------------------------------------------------------------

#: The headings this reader understands, in the order a register usually has
#: them. Offered as a download so there is a known-good shape to start from
#: rather than a guess at what the columns should be called.
TEMPLATE_HEADINGS = (
    "File No.", "Make", "Plate", "Colour", "Year", "Vin",
    "Customer Name", "Mobile", "Comments",
)

TEMPLATE_ROWS = (
    ("1", "BMW", "1234ABC", "White", "2019", "WBA7E2C50KB123456",
     "Ahmed Al-Qahtani", "0551234567", ""),
    ("2", "Mercedes-Benz", "5678XYZ", "Black", "2021", "W1K2050841R123456",
     "Riyadh Logistics Co.", "0112345678", "Fleet account — invoice monthly"),
    ("3", "Audi", "9012DEF", "Grey", "2017", "WAUZZZ4G1HN123456",
     "Example Customer", "0509876543", "PLEASE DO NOT RECEIVE THIS CAR"),
)


def template_xlsx() -> bytes:
    """An empty register with the right headings and three example rows.

    The third row is deliberately red, with a refusal written in its
    Comments cell. That is the convention this reader looks for, and a
    convention is far easier to copy than to describe: whoever opens this
    can see what a flagged row looks like and mark their own the same way.
    """
    import io

    import openpyxl
    from openpyxl.styles import Font, PatternFill

    book = openpyxl.Workbook()
    sheet = book.active
    sheet.title = "Register"

    heading_fill = PatternFill("solid", start_color="FF24306B")
    for column, heading in enumerate(TEMPLATE_HEADINGS, start=1):
        cell = sheet.cell(row=1, column=column, value=heading)
        cell.font = Font(bold=True, color="FFFFFFFF")
        cell.fill = heading_fill

    red = Font(color="FFFF0000")
    for index, values in enumerate(TEMPLATE_ROWS, start=2):
        for column, value in enumerate(values, start=1):
            cell = sheet.cell(row=index, column=column, value=value)
            # The last example is the flagged one.
            if index == len(TEMPLATE_ROWS) + 1:
                cell.font = red

    widths = (8, 16, 14, 12, 8, 22, 24, 18, 34)
    for column, width in enumerate(widths, start=1):
        sheet.column_dimensions[
            openpyxl.utils.get_column_letter(column)
        ].width = width
    sheet.freeze_panes = "A2"

    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()
