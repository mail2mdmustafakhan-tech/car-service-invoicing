"""Item codes: importing them, keeping them, and picking by them.

The code is the reference the workshop and the customer quote at each
other. Everything here protects one of two properties: that a code
arrives and survives exactly as written, and that a line which names an
item by its code ends up as that item rather than as a line whose
description is four digits.
"""

from __future__ import annotations

import io

import pytest
from openpyxl import Workbook

from app import importing, item_import
from app import repository as repo


def _book(rows: list[list], *, text_codes: bool = True) -> bytes:
    book = Workbook()
    sheet = book.active
    for row in rows:
        sheet.append(row)
    if text_codes:
        for cell in sheet["A"]:
            cell.number_format = "@"
    buffer = io.BytesIO()
    book.save(buffer)
    return buffer.getvalue()


# --- reading a file ---------------------------------------------------------


def test_a_leading_zero_survives_the_import():
    """Every code in his list has one, and one has two.

    Read as a number, 0123 comes back 123 and no longer matches the
    paperwork the code exists to match. This is the single most likely
    way for this feature to be quietly useless.
    """
    data = _book([["Item No", "Description"], ["0123", "Oil service"],
                  ["00163", "Car wash"]])
    rows = item_import.read_table(data, "items.xlsx")
    prepared, _ = item_import.prepare(
        rows, existing_codes=set(), existing_names=set())

    assert [r["code"] for r in prepared] == ["0123", "00163"]


def test_a_column_headed_no_is_not_the_item_code():
    """It is the row counter down the left of a printed list.

    Taken as the code, every item imports as 1, 2, 3 with the real
    "Item No" column sitting unmapped beside it -- which is exactly what
    happened the first time this ran against his file.
    """
    mapping = item_import.map_columns(
        ["No", "Item No", "Description", "Unit", "Quantity"])

    assert mapping[1] == "code"
    assert mapping.get(0) != "code"


def test_arabic_headings_are_understood():
    assert item_import.map_columns(["الرمز", "الوصف", "السعر"]) == {
        0: "code", 1: "name_ar", 2: "unit_price"}


def test_the_unit_is_mapped_onto_one_the_catalogue_uses():
    assert item_import.normalise_unit("قطعة") == "pcs"
    assert item_import.normalise_unit("Hours") == "hour"
    # Not recognised, so left alone rather than guessed at.
    assert item_import.normalise_unit("drum") == "drum"


def test_a_file_with_no_description_column_is_refused_with_a_reason():
    data = _book([["Item No", "Quantity"], ["0123", "4"]])
    rows = item_import.read_table(data, "items.xlsx")

    with pytest.raises(item_import.ImportError_, match="description"):
        item_import.prepare(rows, existing_codes=set(), existing_names=set())


def test_an_arabic_only_row_stays_pickable_in_english():
    """Fifteen of his rows are written only in Arabic.

    Left with an empty English name they would show as a blank line in
    the English catalogue and in the English dropdown -- present, and
    impossible to choose.
    """
    data = _book([["Item No", "الوصف"], ["0171", "موازنة العجلات"]])
    rows = item_import.read_table(data, "items.xlsx")
    prepared, _ = item_import.prepare(
        rows, existing_codes=set(), existing_names=set())

    assert prepared[0]["name_en"] == "موازنة العجلات"
    assert prepared[0]["name_ar"] == "موازنة العجلات"


def test_a_spreadsheet_that_excel_opens_but_openpyxl_refuses_is_read_anyway():
    """His report is one of these, and so were his other uploads.

    Some exporters write workbook.xml with the window attributes spelled
    WindowWidth rather than windowWidth. Excel and LibreOffice open the
    file without a murmur, so it looks perfectly good to whoever sent it;
    openpyxl refuses it outright. The same file would have been refused
    by the customer and vehicle importers too.
    """
    import zipfile

    good = _book([["Item No", "Description"], ["0123", "Oil service"]])
    broken = io.BytesIO()
    with zipfile.ZipFile(io.BytesIO(good)) as source:
        parts = {n: source.read(n) for n in source.namelist()}
    parts["xl/workbook.xml"] = parts["xl/workbook.xml"].replace(
        b"<sheets>",
        b'<bookViews><workbookView WindowWidth="21075"/></bookViews><sheets>')
    with zipfile.ZipFile(broken, "w") as target:
        for name, payload in parts.items():
            target.writestr(name, payload)

    rows = importing.read_table(broken.getvalue(), "report.xlsx")
    assert rows[1][1] == "Oil service"


def test_a_file_that_is_simply_not_a_spreadsheet_still_fails():
    """The repair must not turn every bad upload into a confusing one."""
    with pytest.raises(importing.ImportError_):
        importing.read_table(b"this is not a workbook at all", "notes.xlsx")


# --- the preview tells the truth --------------------------------------------


def test_a_code_already_in_the_catalogue_is_flagged_not_imported():
    data = _book([["Item No", "Description"], ["0123", "Oil service"]])
    rows = item_import.read_table(data, "items.xlsx")
    prepared, summary = item_import.prepare(
        rows, existing_codes={"0123"}, existing_names=set())

    assert summary["ready"] == 0
    assert prepared[0]["skip"] == "iimp.skip_code_exists"


def test_the_same_code_twice_in_one_file_is_imported_once():
    data = _book([["Item No", "Description"],
                  ["0123", "Oil service"], ["0123", "Oil service again"]])
    rows = item_import.read_table(data, "items.xlsx")
    prepared, summary = item_import.prepare(
        rows, existing_codes=set(), existing_names=set())

    assert summary["ready"] == 1
    assert prepared[1]["skip"]


def test_two_items_may_share_a_description_under_different_codes():
    """His list has Car Wash twice, as 0163 and 00163.

    The code is what makes them distinct, and refusing the second would
    throw away a reference that is on his paperwork.
    """
    data = _book([["Item No", "Description"],
                  ["0163", "Car Wash"], ["00163", "Car Wash"]])
    rows = item_import.read_table(data, "items.xlsx")
    _, summary = item_import.prepare(
        rows, existing_codes=set(), existing_names=set())

    assert summary["ready"] == 2


def test_a_missing_price_is_reported_rather_than_invented():
    data = _book([["Item No", "Description"], ["0123", "Oil service"]])
    rows = item_import.read_table(data, "items.xlsx")
    prepared, summary = item_import.prepare(
        rows, existing_codes=set(), existing_names=set())

    assert prepared[0]["unit_price_minor"] is None
    assert summary["priced"] == 0


# --- the whole flow through the application ---------------------------------


def _upload(client, data: bytes):
    return client.post(
        "/catalog/import",
        files={"spreadsheet": ("items.xlsx", data,
               "application/vnd.openxmlformats-officedocument."
               "spreadsheetml.sheet")},
        follow_redirects=True)


def test_importing_adds_the_items_with_their_codes(shop, read_web_db):
    page = _upload(shop, _book([["Item No", "Description", "Unit"],
                                ["0123", "Oil service", "قطعة"]]))
    assert "0123" in page.text

    import re
    batch = re.search(r"/catalog/import/(\d+)/confirm", page.text).group(1)
    shop.post(f"/catalog/import/{batch}/confirm")

    with read_web_db() as c:
        row = c.execute(
            "SELECT * FROM catalog_items WHERE code = '0123'").fetchone()
    assert row["name_en"] == "Oil service"
    assert row["unit"] == "pcs"


def test_confirming_the_same_batch_twice_imports_once(shop, read_web_db):
    import re
    page = _upload(shop, _book([["Item No", "Description"],
                                ["0123", "Oil service"]]))
    batch = re.search(r"/catalog/import/(\d+)/confirm", page.text).group(1)
    shop.post(f"/catalog/import/{batch}/confirm")
    shop.post(f"/catalog/import/{batch}/confirm")

    with read_web_db() as c:
        n = c.execute(
            "SELECT COUNT(*) FROM catalog_items WHERE code = '0123'").fetchone()[0]
    assert n == 1


def test_nothing_is_written_before_confirming(shop, read_web_db):
    _upload(shop, _book([["Item No", "Description"], ["0123", "Oil service"]]))

    with read_web_db() as c:
        n = c.execute(
            "SELECT COUNT(*) FROM catalog_items WHERE code = '0123'").fetchone()[0]
    assert n == 0


# --- picking an item by its code --------------------------------------------


def _raise_invoice(client, *, description: str, catalog_id: str = ""):
    return client.post("/invoices/new", data={
        "customer_id": "1", "vehicle_id": "1", "issue_date": "2026-11-25",
        "vat_rate": "15", "status": "draft",
        "item_catalog_id": [catalog_id], "item_description": [description],
        "item_description_ar": [""], "item_kind": ["service"],
        "item_unit": ["pcs"], "item_qty": ["1"], "item_price": ["150"]})


def test_a_typed_code_becomes_the_item(shop, read_web_db):
    """The whole point, and it has to work without JavaScript.

    A line can reach the database from a page whose scripts never ran.
    Resolved only in the browser, a typed code would be stored as the
    literal description "SVC-LAB" on a customer's invoice.
    """
    _raise_invoice(shop, description="OIL")

    with read_web_db() as c:
        row = c.execute("SELECT code, description, catalog_item_id "
                        "FROM invoice_items").fetchone()
    assert row["code"] == "OIL"
    assert row["description"] == "Oil change"  # not the four letters typed
    assert row["catalog_item_id"] is not None


def test_the_code_and_name_together_is_understood(shop, read_web_db):
    """What the dropdown puts in the box when somebody picks from it."""
    _raise_invoice(shop, description="OIL" + repo.CODE_SEPARATOR + "Oil change")

    with read_web_db() as c:
        row = c.execute("SELECT code, description FROM invoice_items").fetchone()
    assert row["code"] == "OIL"
    assert repo.CODE_SEPARATOR not in row["description"]


def test_a_name_typed_by_hand_keeps_its_own_capitals(shop, read_web_db):
    """Linking an item records the code; it is not a licence to rewrite.

    Somebody who typed "labour" in lower case meant that. Replacing it
    with the catalogue's capitalisation is a change to the words on a
    customer's invoice that nobody asked for.
    """
    _raise_invoice(shop, description="oil CHANGE")

    with read_web_db() as c:
        row = c.execute("SELECT code, description FROM invoice_items").fetchone()
    assert row["description"] == "oil CHANGE"
    assert row["code"] == "OIL"  # still linked


def test_a_custom_line_is_left_exactly_as_written(shop, read_web_db):
    _raise_invoice(shop, description="Collected the car from Jeddah")

    with read_web_db() as c:
        row = c.execute("SELECT code, description, catalog_item_id "
                        "FROM invoice_items").fetchone()
    assert row["code"] == ""
    assert row["catalog_item_id"] is None
    assert row["description"] == "Collected the car from Jeddah"





def test_the_stored_code_does_not_follow_a_later_catalogue_edit(shop, read_web_db):
    """A line snapshots its code for the same reason it snapshots its
    price: an invoice reprinted a year later must show what it was
    raised under, not what the catalogue says today."""
    shop.post("/invoices/new", data={
        "customer_id": "1", "vehicle_id": "1", "issue_date": "2026-11-25",
        "vat_rate": "15", "status": "issued",
        "item_catalog_id": ["1"], "item_description": ["Oil change"],
        "item_description_ar": [""], "item_kind": ["service"],
        "item_unit": ["pcs"], "item_qty": ["1"], "item_price": ["150"]})

    with read_web_db() as c:
        before = c.execute("SELECT code FROM invoice_items").fetchone()["code"]
    shop.post("/catalog/1", data={
        "code": "OIL-NEW", "name_en": "Oil change", "name_ar": "تغيير زيت",
        "kind": "service", "unit": "pcs", "unit_price": "150",
        "manufacturer": "", "is_active": "1"})

    with read_web_db() as c:
        after = c.execute("SELECT code FROM invoice_items").fetchone()["code"]
    assert after == before


def test_the_dropdown_offers_the_code_beside_the_name(shop):
    page = shop.get("/invoices/new").text
    assert "OIL" + repo.CODE_SEPARATOR + "Oil change" in page


def test_the_catalogue_can_be_searched_by_code(shop):
    assert "Oil change" in shop.get("/catalog?search=OIL").text


def test_the_item_import_never_talks_about_customers(shop):
    """It shared the customer importer's strings and said so out loud.

    The confirm button read "Import these customers" on a page full of
    brake pads. Worth a test rather than a careful read: these pages are
    built by copying the one next door, so the wording follows the
    copy unless something checks.
    """
    page = _upload(shop, _book([["Item No", "Description"],
                                ["0123", "Oil service"]]))
    # The page's own content, not the navigation bar, which links to
    # Customers from every page and rightly says so.
    body = page.text.split('<main class="container">', 1)[1].split("</main>")[0]

    for word in ("customer", "Customer", "\u0639\u0645\u064a\u0644", "\u0627\u0644\u0639\u0645\u0644\u0627\u0621"):
        assert word not in body, f"the item import page says {word!r}"


def test_the_message_after_importing_items_says_items(shop):
    import re

    page = _upload(shop, _book([["Item No", "Description"],
                                ["0123", "Oil service"]]))
    batch = re.search(r"/catalog/import/(\d+)/confirm", page.text).group(1)
    done = shop.post(f"/catalog/import/{batch}/confirm", follow_redirects=True)

    assert "Items imported" in done.text
    assert "Customers imported" not in done.text


def test_a_skip_reason_reads_in_the_language_of_the_page(shop):
    """It was built as an English sentence in Python, so the Arabic
    preview showed "Code 0123 is already in the catalogue" in the
    middle of an otherwise Arabic table."""
    _upload(shop, _book([["Item No", "Description"], ["OIL", "Oil change"]]))
    english = shop.get("/catalog/import/1").text
    assert "already in the catalogue" in english

    shop.get("/lang/ar")
    arabic = shop.get("/catalog/import/1").text
    assert "already in the catalogue" not in arabic
    assert "\u0645\u0648\u062c\u0648\u062f \u0645\u0633\u0628\u0642\u0627\u064b" in arabic
    assert "OIL" in arabic  # the code itself still shows
