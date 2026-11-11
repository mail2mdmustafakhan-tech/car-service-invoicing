"""Tests for the web layer: the pages load, forms save, and bad input is caught."""

from __future__ import annotations

import pytest

# --------------------------------------------------------------------------
# Pages load
# --------------------------------------------------------------------------

@pytest.mark.parametrize(
    "url",
    ["/", "/customers", "/customers/new", "/vehicles", "/vehicles/new",
     "/catalog", "/catalog/new", "/invoices", "/invoices/new", "/settings",
     "/healthz"],
)
def test_pages_load_on_an_empty_database(client, url):
    assert client.get(url).status_code == 200


def test_unknown_page_returns_404(client):
    assert client.get("/no-such-page").status_code == 404


def test_health_check_reports_the_database(client):
    body = client.get("/healthz").json()
    assert body["status"] == "ok"
    assert "database" in body


# --------------------------------------------------------------------------
# Language
# --------------------------------------------------------------------------

def test_default_language_is_left_to_right(client):
    assert 'dir="ltr"' in client.get("/").text


def test_switching_to_arabic_flips_the_page(client):
    client.get("/lang/ar")
    page = client.get("/").text
    assert 'dir="rtl"' in page
    assert 'lang="ar"' in page
    assert "الفواتير" in page          # the navigation is translated


def test_language_choice_persists_across_pages(client):
    client.get("/lang/ar")
    assert 'dir="rtl"' in client.get("/customers").text
    client.get("/lang/en")
    assert 'dir="ltr"' in client.get("/customers").text


def test_an_unknown_language_falls_back_to_english(client):
    client.get("/lang/zz")
    assert 'dir="ltr"' in client.get("/").text


# --------------------------------------------------------------------------
# Creating records
# --------------------------------------------------------------------------

def test_creating_a_customer(client):
    response = client.post(
        "/customers/new",
        data={"name": "Ahmed Al-Qahtani", "name_ar": "أحمد القحطاني", "phone": "0551234567"},
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "Ahmed Al-Qahtani" in response.text
    assert "Ahmed Al-Qahtani" in client.get("/customers").text


def test_a_customer_needs_a_name(client):
    response = client.post("/customers/new", data={"name": "   ", "phone": "055"})
    assert response.status_code == 200
    assert "required" in response.text.lower()
    assert "No customers yet" in client.get("/customers").text


def test_duplicate_catalogue_codes_are_refused(shop):
    response = shop.post(
        "/catalog/new",
        data={"name_en": "Another", "kind": "part", "unit": "pcs",
              "unit_price": "10", "code": "OIL"},
    )
    assert "already used" in response.text


def test_a_vehicle_needs_an_owner(client):
    response = client.post("/vehicles/new", data={"customer_id": "", "plate_no": "X 1"})
    assert "Choose the customer" in response.text


# --------------------------------------------------------------------------
# The invoice flow
# --------------------------------------------------------------------------

def _invoice_payload(**overrides):
    payload = {
        "customer_id": "1",
        "vehicle_id": "1",
        "issue_date": "2026-11-11",
        "vat_rate": "15",
        "status": "issued",
        "item_catalog_id": ["1", ""],
        "item_description": ["Oil change", "Labour"],
        "item_description_ar": ["تغيير زيت", "أجرة عمل"],
        "item_kind": ["service", "service"],
        "item_unit": ["pcs", "hour"],
        "item_qty": ["1", "1.5"],
        "item_price": ["150", "90"],
    }
    payload.update(overrides)
    return payload


def test_creating_an_invoice_computes_the_totals(shop):
    response = shop.post("/invoices/new", data=_invoice_payload(), follow_redirects=True)
    assert response.status_code == 200
    # 150.00 + 135.00 = 285.00, VAT 15% = 42.75, total 327.75
    assert "285.00" in response.text
    assert "42.75" in response.text
    assert "327.75" in response.text
    assert "T-00001" in response.text


def test_an_invoice_needs_at_least_one_line(shop):
    response = shop.post(
        "/invoices/new",
        data=_invoice_payload(
            item_catalog_id=[""], item_description=[""], item_description_ar=[""],
            item_kind=["service"], item_unit=["pcs"], item_qty=[""], item_price=[""],
        ),
    )
    assert "at least one item" in response.text


def test_an_invoice_needs_a_customer(shop):
    response = shop.post("/invoices/new", data=_invoice_payload(customer_id=""))
    assert "Choose a customer" in response.text


def test_a_bad_price_is_reported_not_crashed(shop):
    response = shop.post("/invoices/new", data=_invoice_payload(item_price=["abc", "90"]))
    assert response.status_code == 200
    assert "not a valid number" in response.text


def test_blank_trailing_rows_are_ignored(shop):
    """The form always carries a spare empty row; submitting it is not an error."""
    response = shop.post(
        "/invoices/new",
        data=_invoice_payload(
            item_catalog_id=["1", ""], item_description=["Oil change", ""],
            item_description_ar=["", ""], item_kind=["service", "service"],
            item_unit=["pcs", "pcs"], item_qty=["1", ""], item_price=["150", ""],
        ),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "172.50" in response.text     # one line only: 150 + 15% VAT


def test_issuing_and_paying_an_invoice(shop):
    shop.post("/invoices/new", data=_invoice_payload(status="draft"))

    draft = shop.get("/invoices/1").text
    assert "Draft" in draft

    shop.post("/invoices/1/status", data={"status": "issued"})
    shop.post(
        "/invoices/1/payments",
        data={"amount": "327.75", "method": "cash", "paid_on": "2026-11-11"},
    )

    page = shop.get("/invoices/1").text
    assert "Paid" in page
    assert "327.75" in page


def test_a_payment_cannot_be_recorded_against_a_draft(shop):
    shop.post("/invoices/new", data=_invoice_payload(status="draft"))
    response = shop.post(
        "/invoices/1/payments", data={"amount": "100", "method": "cash"},
        follow_redirects=True,
    )
    assert "Issue the invoice" in response.text


def test_a_zero_payment_is_refused(shop):
    shop.post("/invoices/new", data=_invoice_payload())
    response = shop.post(
        "/invoices/1/payments", data={"amount": "0", "method": "cash"},
        follow_redirects=True,
    )
    assert "greater than zero" in response.text


def test_editing_an_invoice_updates_the_totals(shop):
    shop.post("/invoices/new", data=_invoice_payload())
    response = shop.post(
        "/invoices/1/edit",
        data=_invoice_payload(
            item_catalog_id=[""], item_description=["Wash only"],
            item_description_ar=[""], item_kind=["service"], item_unit=["pcs"],
            item_qty=["1"], item_price=["100"], discount="10",
        ),
        follow_redirects=True,
    )
    assert "Wash only" in response.text
    assert "103.50" in response.text     # (100 - 10) + 15% VAT


def test_vat_inclusive_invoice_totals_the_quoted_price(shop):
    response = shop.post(
        "/invoices/new",
        data=_invoice_payload(
            prices_include_vat="1",
            item_catalog_id=[""], item_description=["All-in price"],
            item_description_ar=[""], item_kind=["service"], item_unit=["pcs"],
            item_qty=["1"], item_price=["115"],
        ),
        follow_redirects=True,
    )
    assert "115.00" in response.text     # the customer pays exactly the quote
    assert "15.00" in response.text      # VAT shown separately


# --------------------------------------------------------------------------
# Printing
# --------------------------------------------------------------------------

def test_the_print_view_has_no_navigation(shop):
    shop.post("/invoices/new", data=_invoice_payload())
    page = shop.get("/invoices/1/print?autoprint=0").text
    assert "TAX INVOICE" in page
    assert "T-00001" in page
    assert 'class="topnav"' not in page


def test_a_draft_is_marked_on_the_printed_copy(shop):
    shop.post("/invoices/new", data=_invoice_payload(status="draft"))
    assert "NOT A VALID INVOICE" in shop.get("/invoices/1/print?autoprint=0").text


def test_a_void_invoice_is_stamped(shop):
    shop.post("/invoices/new", data=_invoice_payload())
    shop.post("/invoices/1/status", data={"status": "void"})
    assert "VOID" in shop.get("/invoices/1/print?autoprint=0").text


def test_the_printed_invoice_is_labelled_in_both_languages(shop):
    """Whatever the interface language, the customer's copy carries both."""
    shop.post("/invoices/new", data=_invoice_payload())
    for lang in ("en", "ar"):
        shop.get(f"/lang/{lang}")
        page = shop.get("/invoices/1/print?autoprint=0").text
        assert "BILL TO" in page and "فاتورة إلى" in page


# --------------------------------------------------------------------------
# Settings and filters
# --------------------------------------------------------------------------

def test_saving_settings(client):
    client.post(
        "/settings",
        data={"business_name_en": "Al Faisal Auto", "business_name_ar": "الفيصل",
              "vat_rate": "15", "currency_code": "sar", "invoice_prefix": "AF-",
              "next_invoice_seq": "1041", "default_language": "en"},
    )
    page = client.get("/settings").text
    assert "Al Faisal Auto" in page
    assert 'value="AF-"' in page
    assert "SAR" in page                 # the code is upper-cased on save


def test_the_invoice_number_series_can_be_continued(client):
    client.post(
        "/settings",
        data={"business_name_en": "Shop", "vat_rate": "15", "currency_code": "SAR",
              "invoice_prefix": "AF-", "next_invoice_seq": "1041",
              "default_language": "en"},
    )
    client.post("/customers/new", data={"name": "A customer"})
    response = client.post(
        "/invoices/new",
        data={"customer_id": "1", "issue_date": "2026-11-11", "vat_rate": "15",
              "status": "issued", "item_description": ["Service"], "item_qty": ["1"],
              "item_price": ["100"], "item_kind": ["service"], "item_unit": ["pcs"],
              "item_catalog_id": [""], "item_description_ar": [""]},
        follow_redirects=True,
    )
    assert "AF-01041" in response.text


def test_invoice_filters_narrow_the_list(shop):
    shop.post("/invoices/new", data=_invoice_payload(status="issued"))
    shop.post("/invoices/new", data=_invoice_payload(status="draft"))

    assert shop.get("/invoices").text.count("T-0000") >= 2
    assert "T-00002" not in shop.get("/invoices?status=issued").text
    assert "T-00001" not in shop.get("/invoices?status=draft").text
    assert "T-00001" in shop.get("/invoices?state=unpaid").text


def test_backup_downloads_a_database_file(shop):
    response = shop.get("/settings/backup")
    assert response.status_code == 200
    assert response.content.startswith(b"SQLite format 3")


# --------------------------------------------------------------------------
# The helper endpoints the invoice form uses
# --------------------------------------------------------------------------

def test_vehicle_lookup_returns_only_that_customers_cars(shop):
    shop.post("/customers/new", data={"name": "Second customer"})
    shop.post("/vehicles/new", data={"customer_id": "2", "plate_no": "OTHER 1"})

    first = shop.get("/api/customers/1/vehicles").json()
    assert [v["label"] for v in first] == ["TEST 1 — Toyota Hilux"]
    assert len(shop.get("/api/customers/2/vehicles").json()) == 1


def test_catalog_lookup_lists_items(shop):
    items = shop.get("/api/catalog").json()
    assert items[0]["name_en"] == "Oil change"
    assert items[0]["price"] == "150.00"


def test_browser_preview_totals_match_the_server(shop):
    """The figures the invoice form shows while typing must be the ones saved."""
    preview = shop.get(
        "/api/preview-totals",
        params={"qty": ["1", "1.5"], "price": ["150", "90"], "vat_rate": "15",
                "discount": "0", "include_vat": 0},
    ).json()
    assert preview == {
        "subtotal_minor": 28500,
        "discount_minor": 0,
        "taxable_minor": 28500,
        "vat_minor": 4275,
        "total_minor": 32775,
    }

    shop.post("/invoices/new", data=_invoice_payload())
    saved = shop.get("/invoices/1").text
    assert "327.75" in saved
