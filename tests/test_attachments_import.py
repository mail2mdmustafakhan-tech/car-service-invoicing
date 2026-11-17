"""Tests for customer attachments, spreadsheet import, and messaging links.

All three take input from outside the application -- an uploaded file, a
spreadsheet somebody else built, a phone number typed by hand -- so most of
what matters here is what happens when that input is not what it should be.
"""

from __future__ import annotations

import csv
import io

import pytest

from app import importing, messaging
from app import repository as repo

PDF = b"%PDF-1.4\n" + b"x" * 500
JPEG = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 200
PNG = (
    b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR\x00\x00\x00\x01\x00\x00\x00\x01"
    b"\x08\x06\x00\x00\x00\x1f\x15\xc4\x89\x00\x00\x00\nIDATx\x9cc\x00\x01"
    b"\x00\x00\x05\x00\x01\r\n-\xb4\x00\x00\x00\x00IEND\xaeB`\x82"
)


# ==========================================================================
# Attachments
# ==========================================================================

@pytest.fixture()
def customer(conn):
    return conn, repo.create_customer(conn, {"name": "Ahmed", "phone": "0551234567"})


@pytest.mark.parametrize(
    "data, mime", [(PDF, "application/pdf"), (JPEG, "image/jpeg"), (PNG, "image/png")]
)
def test_accepts_the_formats_a_scanner_produces(customer, data, mime):
    conn, customer_id = customer
    attachment_id = repo.add_attachment(
        conn, customer_id, data, original_name="scan.bin"
    )
    assert repo.get_attachment(conn, attachment_id)["mime"] == mime


@pytest.mark.parametrize(
    "data",
    [
        b"MZ\x90\x00" + b"x" * 100,                      # a Windows executable
        b"<html><script>alert(1)</script></html>",       # a web page
        b"<svg onload='x()'></svg>",                     # a scriptable image
        b"just some text",
    ],
)
def test_rejects_anything_else(customer, data):
    conn, customer_id = customer
    with pytest.raises(ValueError, match="Only PDF, JPEG and PNG"):
        repo.add_attachment(conn, customer_id, data, original_name="invoice.pdf")


def test_the_declared_name_does_not_decide_what_a_file_is(customer):
    """Renaming an executable to .pdf must not get it stored as one."""
    conn, customer_id = customer
    with pytest.raises(ValueError):
        repo.add_attachment(
            conn, customer_id, b"MZ\x90\x00" + b"x" * 100,
            original_name="old-invoice.pdf",
        )


def test_an_empty_or_oversized_file_is_refused(customer):
    conn, customer_id = customer
    with pytest.raises(ValueError, match="No file"):
        repo.add_attachment(conn, customer_id, b"")
    with pytest.raises(ValueError, match="10 MB"):
        repo.add_attachment(
            conn, customer_id, PDF + b"x" * repo.MAX_ATTACHMENT_BYTES
        )


def test_the_stored_name_is_generated_not_taken_from_the_upload(customer):
    """A filename from a browser must never decide where a file lands."""
    conn, customer_id = customer
    attachment_id = repo.add_attachment(
        conn, customer_id, PDF, original_name="../../etc/passwd.pdf"
    )
    row = repo.get_attachment(conn, attachment_id)
    assert row["original_name"] == "../../etc/passwd.pdf"   # kept as a label
    assert "/" not in row["stored_name"]
    assert ".." not in row["stored_name"]

    path, _ = repo.attachment_file(conn, attachment_id)
    assert path.is_file()
    assert path.parent.name == "attachments"


def test_metadata_is_kept(customer):
    conn, customer_id = customer
    attachment_id = repo.add_attachment(
        conn, customer_id, PDF, original_name="2019-invoice.pdf",
        kind="invoice", description="From the old book", document_date="2019-05-04",
    )
    row = repo.get_attachment(conn, attachment_id)
    assert row["kind"] == "invoice"
    assert row["description"] == "From the old book"
    assert row["document_date"] == "2019-05-04"
    assert row["size_bytes"] == len(PDF)


def test_deleting_removes_the_file_too(customer):
    conn, customer_id = customer
    attachment_id = repo.add_attachment(conn, customer_id, PDF)
    path, _ = repo.attachment_file(conn, attachment_id)
    assert path.is_file()

    assert repo.delete_attachment(conn, attachment_id) == customer_id
    assert not path.exists()
    assert repo.list_attachments(conn, customer_id) == []


def test_deleting_a_customer_takes_their_attachments_with_them(customer):
    conn, customer_id = customer
    repo.add_attachment(conn, customer_id, PDF)
    conn.execute("DELETE FROM customers WHERE id = ?", (customer_id,))
    conn.commit()
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM customer_attachments"
    ).fetchone()["n"] == 0


def test_attachments_are_listed_newest_first(customer):
    conn, customer_id = customer
    repo.add_attachment(conn, customer_id, PDF, original_name="old.pdf",
                        document_date="2019-01-01")
    repo.add_attachment(conn, customer_id, PDF, original_name="newer.pdf",
                        document_date="2024-06-01")
    names = [a["original_name"] for a in repo.list_attachments(conn, customer_id)]
    assert names == ["newer.pdf", "old.pdf"]


# --- Through the web -------------------------------------------------------

def test_uploading_and_serving(shop):
    response = shop.post(
        "/customers/1/attachments",
        files={"document": ("old-invoice.pdf", PDF, "application/pdf")},
        data={"kind": "invoice", "description": "2019 book"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "old-invoice.pdf" in response.text

    served = shop.get("/attachments/1")
    assert served.status_code == 200
    assert served.headers["content-type"].startswith("application/pdf")
    assert served.content == PDF
    # Uploaded files are served back from our own address, so the browser
    # must not be allowed to decide the type is really something else.
    assert served.headers["x-content-type-options"] == "nosniff"
    assert "default-src 'none'" in served.headers["content-security-policy"]


def test_a_rejected_upload_says_why(shop):
    response = shop.post(
        "/customers/1/attachments",
        files={"document": ("notes.txt", b"hello", "application/pdf")},
        follow_redirects=True,
    )
    assert "Only PDF, JPEG and PNG" in response.text


def test_a_hostile_filename_cannot_break_the_download_header(shop):
    """A quote or newline in the name would otherwise end the header early."""
    shop.post(
        "/customers/1/attachments",
        files={"document": ('bad"\r\nX-Injected: yes.pdf', PDF, "application/pdf")},
    )
    response = shop.get("/attachments/1/download")
    assert response.status_code == 200
    assert "x-injected" not in {k.lower() for k in response.headers}
    assert "\r" not in response.headers["content-disposition"]


def test_deleting_through_the_web(shop):
    shop.post("/customers/1/attachments",
              files={"document": ("a.pdf", PDF, "application/pdf")})
    assert shop.get("/attachments/1").status_code == 200
    shop.post("/attachments/1/delete", follow_redirects=True)
    assert shop.get("/attachments/1").status_code == 404


# ==========================================================================
# Importing customers
# ==========================================================================

def _csv(rows: list[list[str]]) -> bytes:
    buffer = io.StringIO()
    csv.writer(buffer).writerows(rows)
    return buffer.getvalue().encode("utf-8")


def test_the_template_is_importable_as_it_stands(conn):
    rows = importing.read_table(importing.template_csv(), "template.csv")
    prepared, summary = importing.prepare(
        rows, existing_names=set(), existing_phones=set()
    )
    assert summary["ready"] == 2
    assert summary["skipped"] == 0


def test_headings_are_matched_loosely(conn):
    rows = importing.read_table(
        _csv([["Customer Name", "MOBILE_NO", "E-Mail"], ["Ahmed", "0551234567", "a@x.com"]]),
        "list.csv",
    )
    prepared, summary = importing.prepare(
        rows, existing_names=set(), existing_phones=set()
    )
    assert summary["fields"] == ["email", "name", "phone"]
    assert prepared[0]["name"] == "Ahmed"


def test_arabic_headings_work_too(conn):
    rows = importing.read_table(
        _csv([["الاسم", "الجوال"], ["أحمد القحطاني", "0551234567"]]), "list.csv"
    )
    prepared, _ = importing.prepare(rows, existing_names=set(), existing_phones=set())
    assert prepared[0]["name"] == "أحمد القحطاني"


def test_a_file_with_no_name_column_is_refused(conn):
    rows = importing.read_table(_csv([["Phone", "City"], ["055", "Riyadh"]]), "x.csv")
    with pytest.raises(importing.ImportError_, match="name column"):
        importing.prepare(rows, existing_names=set(), existing_phones=set())


def test_duplicates_are_caught_within_the_file_and_against_what_is_stored(conn):
    rows = importing.read_table(
        _csv([
            ["Name", "Phone"],
            ["Ahmed", "0551234567"],
            ["Ahmed", "0559999999"],        # same name, later in the file
            ["Sara", "055-123 4567"],       # same phone, written differently
            ["", "0500000000"],             # no name
            ["Khalid", "0533344455"],       # already stored
        ]),
        "list.csv",
    )
    prepared, summary = importing.prepare(
        rows, existing_names={"khalid"}, existing_phones=set()
    )
    assert summary["ready"] == 1
    assert [r["note"] for r in prepared] == [
        "", "Repeated in this file", "Same phone as an earlier row in this file",
        "No name", "Already on file",
    ]


def test_unrecognised_columns_are_reported_not_guessed_at(conn):
    rows = importing.read_table(
        _csv([["Name", "Loyalty points"], ["Ahmed", "12"]]), "list.csv"
    )
    _, summary = importing.prepare(rows, existing_names=set(), existing_phones=set())
    assert summary["unmapped"] == ["Loyalty points"]


def test_excel_numbers_do_not_arrive_as_decimals(conn):
    """A phone in Excel is often a float: 551234567.0 is not a phone number."""
    from openpyxl import Workbook

    book = Workbook()
    book.active.append(["Name", "Phone"])
    book.active.append(["Ahmed", 551234567])
    buffer = io.BytesIO()
    book.save(buffer)

    rows = importing.read_table(buffer.getvalue(), "list.xlsx")
    prepared, _ = importing.prepare(rows, existing_names=set(), existing_phones=set())
    assert prepared[0]["phone"] == "551234567"


@pytest.mark.parametrize(
    "data, name",
    [
        (b"", "empty.csv"),
        (PDF, "list.csv"),
        (PNG, "list.csv"),
        (b"\xd0\xcf\x11\xe0" + b"x" * 50, "old.xls"),
    ],
)
def test_a_file_that_is_not_a_spreadsheet_is_refused(data, name):
    with pytest.raises(importing.ImportError_):
        importing.read_table(data, name)


def test_nothing_is_written_until_the_batch_is_confirmed(conn):
    rows = importing.read_table(_csv([["Name"], ["Ahmed"]]), "list.csv")
    prepared, _ = importing.prepare(rows, existing_names=set(), existing_phones=set())
    batch_id = repo.create_import_batch(conn, "list.csv", prepared)

    assert repo.list_customers(conn) == []          # still nothing

    result = repo.commit_import_batch(conn, batch_id)
    assert result == {"imported": 1, "skipped": 0}
    assert [c["name"] for c in repo.list_customers(conn)] == ["Ahmed"]


def test_a_batch_cannot_be_imported_twice(conn):
    rows = importing.read_table(_csv([["Name"], ["Ahmed"]]), "list.csv")
    prepared, _ = importing.prepare(rows, existing_names=set(), existing_phones=set())
    batch_id = repo.create_import_batch(conn, "list.csv", prepared)
    repo.commit_import_batch(conn, batch_id)
    with pytest.raises(repo.InUse):
        repo.commit_import_batch(conn, batch_id)


def test_cancelling_a_batch_imports_nothing(conn):
    rows = importing.read_table(_csv([["Name"], ["Ahmed"]]), "list.csv")
    prepared, _ = importing.prepare(rows, existing_names=set(), existing_phones=set())
    batch_id = repo.create_import_batch(conn, "list.csv", prepared)
    repo.cancel_import_batch(conn, batch_id)
    with pytest.raises(repo.InUse):
        repo.commit_import_batch(conn, batch_id)
    assert repo.list_customers(conn) == []


# --- Through the web -------------------------------------------------------

def test_the_whole_import_flow(client):
    data = _csv([
        ["Customer Name", "Mobile No"],
        ["Fatimah Al-Dosari", "0509876543"],
        ["Khalid Al-Harbi", "0566677788"],
    ])
    preview = client.post(
        "/customers/import",
        files={"spreadsheet": ("list.csv", data, "text/csv")},
        follow_redirects=True,
    )
    assert preview.status_code == 200
    assert "Fatimah Al-Dosari" in preview.text
    assert "Will be added" in preview.text
    # Still nothing created at this point.
    assert "Fatimah" not in client.get("/customers").text

    client.post("/customers/import/1/confirm", follow_redirects=True)
    listing = client.get("/customers").text
    assert "Fatimah Al-Dosari" in listing and "Khalid Al-Harbi" in listing


def test_a_bad_upload_is_explained_on_the_page(client):
    response = client.post(
        "/customers/import",
        files={"spreadsheet": ("photo.csv", PNG, "text/csv")},
        follow_redirects=True,
    )
    assert "not a spreadsheet" in response.text


def test_the_template_can_be_downloaded(client):
    response = client.get("/customers/import/template")
    assert response.status_code == 200
    assert response.content.startswith(b"\xef\xbb\xbf")   # BOM, so Excel reads UTF-8
    assert b"name" in response.content


# ==========================================================================
# WhatsApp and SMS
# ==========================================================================

def test_the_estimate_page_offers_a_whatsapp_link(shop):
    shop.post(
        "/estimates/new",
        data={"customer_id": "1", "issue_date": "2026-11-15", "vat_rate": "15",
              "item_description": ["Oil change"], "item_qty": ["1"],
              "item_price": ["150"], "item_kind": ["service"], "item_unit": ["pcs"],
              "item_catalog_id": [""], "item_description_ar": [""]},
    )
    page = shop.get("/estimates/1").text
    # The shop fixture's customer has 0500000000 on file.
    assert "https://wa.me/966500000000" in page
    assert "sms:+966500000000" in page
    assert "EST-00001" in page


def test_a_customer_with_no_phone_gets_an_explanation_not_a_dead_link(client):
    client.post("/customers/new", data={"name": "No Phone Ltd"})
    client.post(
        "/estimates/new",
        data={"customer_id": "1", "issue_date": "2026-11-15", "vat_rate": "15",
              "item_description": ["Service"], "item_qty": ["1"], "item_price": ["100"],
              "item_kind": ["service"], "item_unit": ["pcs"], "item_catalog_id": [""],
              "item_description_ar": [""]},
    )
    page = client.get("/estimates/1").text
    assert "wa.me" not in page
    assert "no phone number" in page.lower()


def test_the_message_is_built_from_the_settings_template(shop):
    shop.post("/settings", data={"message_template_en": "Quote {number} for {customer}: {total}"})
    shop.post(
        "/estimates/new",
        data={"customer_id": "1", "issue_date": "2026-11-15", "vat_rate": "15",
              "item_description": ["Service"], "item_qty": ["1"], "item_price": ["100"],
              "item_kind": ["service"], "item_unit": ["pcs"], "item_catalog_id": [""],
              "item_description_ar": [""]},
    )
    page = shop.get("/estimates/1").text
    assert "Quote EST-00001 for Test Customer: 115.00 SAR" in page


def test_the_country_code_is_configurable(shop):
    shop.post("/settings", data={"default_country_code": "971"})
    shop.post(
        "/estimates/new",
        data={"customer_id": "1", "issue_date": "2026-11-15", "vat_rate": "15",
              "item_description": ["Service"], "item_qty": ["1"], "item_price": ["100"],
              "item_kind": ["service"], "item_unit": ["pcs"], "item_catalog_id": [""],
              "item_description_ar": [""]},
    )
    assert "https://wa.me/971500000000" in shop.get("/estimates/1").text


def test_a_template_placeholder_that_does_not_exist_is_left_alone(shop):
    """A typo in the template should not break sending a quote."""
    assert messaging.render_template("Hi {nobody}", {"customer": "x"}) == "Hi {nobody}"


# ---------------------------------------------------------------------------
# Photographs of catalogue parts
# ---------------------------------------------------------------------------

PNG = (b"\x89PNG\r\n\x1a\n" + b"\x00" * 64)
JPEG = (b"\xff\xd8\xff\xe0" + b"\x00" * 64)


def test_a_photograph_can_be_added_to_a_part(shop):
    response = shop.post(
        "/catalog/1/images",
        files={"image": ("alternator.png", PNG, "image/png")},
        data={"caption": "Off the shelf, left bay"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Off the shelf, left bay" in response.text


def test_a_file_pretending_to_be_an_image_is_refused(shop):
    """The browser's declared type is a claim by whoever sent the file."""
    response = shop.post(
        "/catalog/1/images",
        files={"image": ("part.png", b"%PDF-1.7 not an image at all", "image/png")},
        data={"caption": ""},
        follow_redirects=True,
    )
    # A PDF is a fine customer attachment and a poor photograph of a part.
    assert "JPEG and PNG" in response.text


def test_a_part_photograph_is_served_with_sniffing_turned_off(shop):
    shop.post(
        "/catalog/1/images",
        files={"image": ("p.jpg", JPEG, "image/jpeg")},
        data={"caption": ""},
        follow_redirects=True,
    )
    response = shop.get("/item-images/1")
    assert response.status_code == 200
    assert response.headers["X-Content-Type-Options"] == "nosniff"
    assert "default-src 'none'" in response.headers["Content-Security-Policy"]


def test_deleting_a_photograph_removes_the_file_too(shop, tmp_path):
    """A row without its file is tidy; a file without its row is litter."""
    from app.db import attachments_dir

    shop.post(
        "/catalog/1/images",
        files={"image": ("p.png", PNG, "image/png")},
        data={"caption": ""},
        follow_redirects=True,
    )
    before = list(attachments_dir().glob("*"))
    assert before

    shop.post("/item-images/1/delete", follow_redirects=True)
    after = list(attachments_dir().glob("*"))
    assert len(after) == len(before) - 1
