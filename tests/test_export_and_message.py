"""The Excel export, and the priced message sent to a customer.

Both are things somebody else reads -- an accountant opening a workbook, a
customer reading a quote on their phone -- so the tests are about what comes
out the far end rather than about how it was built.
"""

from __future__ import annotations

import json
from io import BytesIO

import pytest
from openpyxl import load_workbook

from app import exporting, messaging
from app import repository as repo

# ---------------------------------------------------------------------------
# The priced breakdown
# ---------------------------------------------------------------------------


def test_a_single_item_reads_as_a_price_not_a_sum():
    """Quantity one is noise. "Oil change: 200.00" is how a person says it."""
    line = {"description": "Oil change", "qty": "1", "price": "200.00", "amount": "200.00"}
    assert messaging.itemise([line]) == "- Oil change: 200.00"


def test_several_of_something_shows_the_working():
    line = {"description": "Brake pads", "qty": "2", "price": "150.00", "amount": "300.00"}
    assert messaging.itemise([line]) == "- Brake pads: 2 × 150.00 = 300.00"


def test_a_long_list_is_cut_short_in_the_sent_language():
    lines = [
        {"description": f"Part {n}", "qty": "1", "price": "10.00", "amount": "10.00"}
        for n in range(1, 10)
    ]
    english = messaging.itemise(lines, limit=3)
    assert english.endswith("- ...and 6 more")

    arabic = messaging.itemise(lines, limit=3, more="و{n} أخرى")
    assert arabic.endswith("- ...و6 أخرى")


def test_the_message_carries_every_item_and_the_vat_working(shop):
    """The whole point: a total alone invites "what for?" by phone."""
    shop.post("/estimates/new", data={
        "customer_id": "1", "vehicle_id": "1", "issue_date": "2026-11-16",
        "valid_until": "2026-11-30", "vat_rate": "15",
        "item_catalog_id": ["", ""],
        "item_description": ["Full service", "Brake pads"],
        "item_description_ar": ["", ""],
        "item_kind": ["service", "part"],
        "item_unit": ["pcs", "pcs"],
        "item_qty": ["1", "2"],
        "item_price": ["450", "180"],
    })

    page = shop.get("/estimates/1").text

    assert "Full service: 450.00" in page
    assert "Brake pads: 2 × 180.00 = 360.00" in page
    # The lines add to 810; the total is 931.50. Without these two the
    # customer is left to work out where the other 121.50 came from.
    assert "Subtotal: 810.00 SAR" in page
    assert "VAT: 121.50 SAR" in page
    assert "Total: 931.50 SAR" in page


def test_both_languages_are_ready_before_either_is_chosen(shop):
    """Switching language must not need a reload, so both travel with the page."""
    shop.post("/estimates/new", data={
        "customer_id": "1", "vehicle_id": "1", "issue_date": "2026-11-16",
        "valid_until": "2026-11-30", "vat_rate": "15",
        "item_catalog_id": [""],
        "item_description": ["Full service"],
        "item_description_ar": ["صيانة شاملة"],
        "item_kind": ["service"], "item_unit": ["pcs"],
        "item_qty": ["1"], "item_price": ["450"],
    })

    page = shop.get("/estimates/1").text
    assert 'id="message-data"' in page

    # Read it the way the browser does. The block is JSON, so Arabic arrives
    # escaped as \\uXXXX -- searching the raw HTML for the Arabic would pass
    # or fail for reasons that have nothing to do with the feature.
    block = page.split('id="message-data" type="application/json">')[1]
    data = json.loads(block.split("</script>")[0])

    assert "صيانة شاملة" in data["messages"]["ar"]
    assert "Full service" in data["messages"]["en"]
    # Each language needs its own link, or switching sends the wrong text.
    assert data["whatsapp"]["ar"] != data["whatsapp"]["en"]


# ---------------------------------------------------------------------------
# The Excel export
# ---------------------------------------------------------------------------


def test_the_workbook_says_it_is_not_a_backup(tmp_path, conn):
    """The one sentence that stops somebody relying on the wrong file."""
    target = exporting.write_workbook(tmp_path / "records.xlsx", conn)
    book = load_workbook(target)

    assert book.sheetnames[0] == "About this file"
    text = " ".join(
        str(value)
        for row in book["About this file"].iter_rows(values_only=True)
        for value in row
        if value is not None
    )
    assert "not a backup" in text
    assert "zip" in text


def test_every_business_record_gets_a_sheet(tmp_path, conn):
    target = exporting.write_workbook(tmp_path / "records.xlsx", conn)
    sheets = load_workbook(target).sheetnames
    for expected in ("Customers", "Vehicles", "Invoices", "Payments", "Estimates"):
        assert expected in sheets


def test_money_arrives_as_a_number_that_adds_up(tmp_path, conn):
    """Figures stored as text look right and silently refuse to sum."""
    customer = repo.create_customer(
        conn, {"name": "Khalid", "phone": "", "email": "", "vat_number": "",
               "address": "", "notes": "", "name_ar": ""}
    )
    invoice = repo.create_invoice(
        conn,
        {"customer_id": customer, "vehicle_id": None, "issue_date": "2026-11-16",
         "due_date": None, "odometer": None, "vat_rate_bp": 1500,
         "prices_include_vat": 0, "discount_minor": 0, "currency_code": "SAR",
         "notes": "", "doc_type": "tax"},
        [{"description": "Full service", "description_ar": "", "kind": "service",
          "unit": "pcs", "qty_milli": 1000, "unit_price_minor": 45000,
          "catalog_item_id": None}],
    )
    assert invoice
    conn.commit()

    target = exporting.write_workbook(tmp_path / "records.xlsx", conn)
    sheet = load_workbook(target)["Invoices"]
    headers = [c.value for c in sheet[1]]
    total = sheet.cell(row=2, column=headers.index("Total") + 1)

    assert isinstance(total.value, (int, float))
    assert total.value == pytest.approx(517.50)
    assert total.number_format == exporting.MONEY_FORMAT


def test_a_rate_is_not_formatted_as_money():
    """15% VAT is a rate. Showing it as 15.00 next to riyals invites a misread."""
    assert exporting.is_money("vat_rate_percent") is False
    assert exporting.is_money("vat_amount") is True


def test_generated_filenames_stay_out_of_the_workbook(tmp_path, conn):
    """A stored name is an implementation detail, not something to read."""
    target = exporting.write_workbook(tmp_path / "records.xlsx", conn)
    headers = [c.value for c in load_workbook(target)["Attachments"][1]]
    assert "Stored name" not in headers


def test_the_download_is_a_real_workbook(client):
    response = client.get("/settings/backup.xlsx")
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    # Opens, rather than merely having the right extension.
    assert load_workbook(BytesIO(response.content)).sheetnames
