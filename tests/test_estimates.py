"""Tests for estimates, and for the split between tax and plain invoices.

An estimate is a price promised before any work is agreed, so the things
worth pinning down are that it cannot be invoiced before the customer says
yes, that the figures quoted survive a later change of settings, and that a
plain invoice never prints as a tax invoice.
"""

from __future__ import annotations

import pytest

from app import repository as repo

# --------------------------------------------------------------------------
# Numbering and totals
# --------------------------------------------------------------------------

def test_estimates_have_their_own_number_series(conn):
    assert repo.reserve_estimate_no(conn) == "EST-00001"
    assert repo.reserve_estimate_no(conn) == "EST-00002"
    # Untouched by the other two series.
    assert repo.reserve_invoice_no(conn) == "INV-00001"
    assert repo.reserve_contract_no(conn) == "RC-00001"


@pytest.fixture()
def quoted(conn):
    """A customer with one estimate: a service and 2.5 hours of labour."""
    customer_id = repo.create_customer(conn, {"name": "Ahmed", "phone": "0551234567"})
    vehicle_id = repo.create_vehicle(
        conn, {"customer_id": customer_id, "plate_no": "ABC 1234", "make": "BMW"}
    )
    estimate_id = repo.create_estimate(
        conn,
        {"customer_id": customer_id, "vehicle_id": vehicle_id,
         "issue_date": "2026-11-15", "valid_until": "2026-11-29",
         "vat_rate_bp": 1500, "status": "draft"},
        [
            {"description": "Engine oil change", "description_ar": "تغيير زيت",
             "kind": "service", "unit": "pcs", "qty_milli": 1000,
             "unit_price_minor": 18500},
            {"description": "Bodywork", "kind": "service", "unit": "hour",
             "qty_milli": 2500, "unit_price_minor": 14000},
        ],
    )
    return conn, customer_id, vehicle_id, estimate_id


def test_estimate_totals_are_stored(quoted):
    conn, _, _, estimate_id = quoted
    estimate = repo.get_estimate(conn, estimate_id)
    assert estimate["subtotal_minor"] == 53500     # 185.00 + 2.5 x 140.00
    assert estimate["vat_minor"] == 8025
    assert estimate["total_minor"] == 61525


def test_an_estimate_can_exclude_vat_entirely(conn):
    """The quote is the price; no tax line at all."""
    customer_id = repo.create_customer(conn, {"name": "Walk-in"})
    estimate_id = repo.create_estimate(
        conn,
        {"customer_id": customer_id, "issue_date": "2026-11-15", "vat_rate_bp": 0},
        [{"description": "Diagnostic", "kind": "service", "unit": "pcs",
          "qty_milli": 1000, "unit_price_minor": 20000}],
    )
    estimate = repo.get_estimate(conn, estimate_id)
    assert estimate["vat_minor"] == 0
    assert estimate["total_minor"] == 20000


def test_vat_inclusive_estimate_quotes_the_price_the_customer_pays(conn):
    customer_id = repo.create_customer(conn, {"name": "Walk-in"})
    estimate_id = repo.create_estimate(
        conn,
        {"customer_id": customer_id, "issue_date": "2026-11-15",
         "vat_rate_bp": 1500, "prices_include_vat": 1},
        [{"description": "All-in", "kind": "service", "unit": "pcs",
          "qty_milli": 1000, "unit_price_minor": 11500}],
    )
    estimate = repo.get_estimate(conn, estimate_id)
    assert estimate["taxable_minor"] == 10000
    assert estimate["vat_minor"] == 1500
    assert estimate["total_minor"] == 11500


def test_editing_recomputes_the_total(quoted):
    conn, customer_id, _, estimate_id = quoted
    repo.update_estimate(
        conn, estimate_id,
        {"customer_id": customer_id, "issue_date": "2026-11-15", "vat_rate_bp": 1500},
        [{"description": "Wash only", "kind": "service", "unit": "pcs",
          "qty_milli": 1000, "unit_price_minor": 5000}],
    )
    assert repo.get_estimate(conn, estimate_id)["total_minor"] == 5750


# --------------------------------------------------------------------------
# Draft, sent, approved
# --------------------------------------------------------------------------

def test_a_new_estimate_starts_as_a_draft(quoted):
    conn, _, _, estimate_id = quoted
    assert repo.get_estimate(conn, estimate_id)["status"] == "draft"


def test_approval_records_when_and_who(quoted):
    conn, _, _, estimate_id = quoted
    repo.set_estimate_status(conn, estimate_id, "approved", approved_by="Ahmed")

    estimate = repo.get_estimate(conn, estimate_id)
    assert estimate["status"] == "approved"
    assert estimate["decided_on"]            # stamped by the system, not typed
    assert estimate["approved_by"] == "Ahmed"


def test_sending_records_the_date(quoted):
    conn, _, _, estimate_id = quoted
    repo.set_estimate_status(conn, estimate_id, "sent")
    assert repo.get_estimate(conn, estimate_id)["sent_on"]


def test_declining_then_reopening(quoted):
    conn, _, _, estimate_id = quoted
    repo.set_estimate_status(conn, estimate_id, "declined")
    assert repo.get_estimate(conn, estimate_id)["status"] == "declined"

    repo.set_estimate_status(conn, estimate_id, "draft")
    estimate = repo.get_estimate(conn, estimate_id)
    assert estimate["status"] == "draft"
    assert estimate["decided_on"] is None


def test_unknown_status_is_rejected(quoted):
    conn, _, _, estimate_id = quoted
    with pytest.raises(ValueError):
        repo.set_estimate_status(conn, estimate_id, "maybe")


# --------------------------------------------------------------------------
# Becoming an invoice
# --------------------------------------------------------------------------

def test_an_unapproved_estimate_cannot_be_invoiced(quoted):
    """Invoicing something the customer has not agreed to is how disputes start."""
    conn, _, _, estimate_id = quoted
    with pytest.raises(repo.InUse, match="approved"):
        repo.convert_estimate_to_invoice(conn, estimate_id)

    repo.set_estimate_status(conn, estimate_id, "sent")
    with pytest.raises(repo.InUse):
        repo.convert_estimate_to_invoice(conn, estimate_id)


def test_conversion_carries_the_lines_and_the_figures(quoted):
    conn, _, vehicle_id, estimate_id = quoted
    repo.set_estimate_status(conn, estimate_id, "approved")
    invoice_id = repo.convert_estimate_to_invoice(conn, estimate_id)

    invoice = repo.get_invoice(conn, invoice_id)
    assert invoice["status"] == "draft"          # never issued automatically
    assert invoice["doc_type"] == "tax"
    assert invoice["vehicle_id"] == vehicle_id
    assert invoice["subtotal_minor"] == 53500
    assert invoice["total_minor"] == 61525
    assert [i["description"] for i in repo.get_invoice_items(conn, invoice_id)] == [
        "Engine oil change", "Bodywork",
    ]


def test_conversion_links_both_ways(quoted):
    conn, _, _, estimate_id = quoted
    repo.set_estimate_status(conn, estimate_id, "approved")
    invoice_id = repo.convert_estimate_to_invoice(conn, estimate_id)

    assert repo.get_estimate(conn, estimate_id)["invoice_id"] == invoice_id
    assert repo.get_estimate(conn, estimate_id)["status"] == "invoiced"
    assert repo.estimate_for_invoice(conn, invoice_id)["estimate_no"] == "EST-00001"


def test_converting_to_a_plain_invoice_drops_the_vat(quoted):
    """A plain invoice charges no tax, whatever the estimate quoted."""
    conn, _, _, estimate_id = quoted
    repo.set_estimate_status(conn, estimate_id, "approved")
    invoice_id = repo.convert_estimate_to_invoice(conn, estimate_id, doc_type="plain")

    invoice = repo.get_invoice(conn, invoice_id)
    assert invoice["doc_type"] == "plain"
    assert invoice["vat_rate_bp"] == 0
    assert invoice["vat_minor"] == 0
    assert invoice["total_minor"] == 53500


def test_an_estimate_cannot_be_invoiced_twice(quoted):
    conn, _, _, estimate_id = quoted
    repo.set_estimate_status(conn, estimate_id, "approved")
    repo.convert_estimate_to_invoice(conn, estimate_id)
    with pytest.raises(repo.InUse):
        repo.convert_estimate_to_invoice(conn, estimate_id)


def test_an_invoiced_estimate_is_frozen(quoted):
    conn, customer_id, _, estimate_id = quoted
    repo.set_estimate_status(conn, estimate_id, "approved")
    repo.convert_estimate_to_invoice(conn, estimate_id)

    with pytest.raises(repo.InUse):
        repo.update_estimate(
            conn, estimate_id,
            {"customer_id": customer_id, "issue_date": "2026-11-15"},
            [{"description": "x", "kind": "service", "unit": "pcs",
              "qty_milli": 1000, "unit_price_minor": 100}],
        )
    with pytest.raises(repo.InUse):
        repo.delete_estimate(conn, estimate_id)
    with pytest.raises(repo.InUse):
        repo.set_estimate_status(conn, estimate_id, "draft")


def test_the_quoted_rate_survives_a_settings_change(quoted):
    """Re-printing last month's quote must show the price that was promised."""
    conn, _, _, estimate_id = quoted
    repo.update_settings(conn, {"vat_rate_bp": 500})
    estimate = repo.get_estimate(conn, estimate_id)
    assert estimate["vat_rate_bp"] == 1500
    assert estimate["total_minor"] == 61525


# ==========================================================================
# Tax invoices and plain invoices
# ==========================================================================

def _invoice(conn, customer_id, **overrides):
    header = {
        "customer_id": customer_id, "issue_date": "2026-11-15",
        "status": "issued", "vat_rate_bp": 1500, "doc_type": "tax",
    }
    header.update(overrides)
    return repo.create_invoice(
        conn, header,
        [{"description": "Service", "kind": "service", "unit": "pcs",
          "qty_milli": 1000, "unit_price_minor": 10000}],
    )


def test_invoices_default_to_tax_invoices(conn):
    customer_id = repo.create_customer(conn, {"name": "Ahmed"})
    invoice = repo.get_invoice(conn, _invoice(conn, customer_id))
    assert invoice["doc_type"] == "tax"
    assert invoice["vat_minor"] == 1500


def test_a_plain_invoice_carries_no_vat(conn):
    customer_id = repo.create_customer(conn, {"name": "Ahmed"})
    invoice = repo.get_invoice(
        conn, _invoice(conn, customer_id, doc_type="plain", vat_rate_bp=0)
    )
    assert invoice["vat_minor"] == 0
    assert invoice["total_minor"] == 10000


def test_both_kinds_are_recorded_and_reported(conn):
    """A plain invoice is still a sale. It must not vanish from the figures."""
    customer_id = repo.create_customer(conn, {"name": "Ahmed"})
    _invoice(conn, customer_id)
    _invoice(conn, customer_id, doc_type="plain", vat_rate_bp=0)

    stats = repo.dashboard_stats(conn)
    assert stats["month_invoice_count"] == 2
    assert stats["month_total_minor"] == 11500 + 10000
    assert stats["month_tax_minor"] == 11500
    assert stats["month_plain_minor"] == 10000
    # Only the tax invoice contributes VAT, which is what makes the figure
    # usable for a return.
    assert stats["month_vat_minor"] == 1500


def test_the_view_exposes_the_document_type(conn):
    customer_id = repo.create_customer(conn, {"name": "Ahmed"})
    _invoice(conn, customer_id, doc_type="plain", vat_rate_bp=0)
    rows = repo.list_invoices(conn)
    assert rows[0]["doc_type"] == "plain"


# ==========================================================================
# The web layer
# ==========================================================================

def _estimate_payload(**overrides):
    payload = {
        "customer_id": "1",
        "vehicle_id": "1",
        "issue_date": "2026-11-15",
        "vat_rate": "15",
        "item_catalog_id": ["1", ""],
        "item_description": ["Oil change", "Bodywork"],
        "item_description_ar": ["تغيير زيت", ""],
        "item_kind": ["service", "service"],
        "item_unit": ["pcs", "hour"],
        "item_qty": ["1", "2"],
        "item_price": ["150", "100"],
    }
    payload.update(overrides)
    return payload


@pytest.mark.parametrize("url", ["/estimates", "/estimates/new"])
def test_estimate_pages_load_when_empty(client, url):
    assert client.get(url).status_code == 200


def test_creating_an_estimate_through_the_form(shop):
    response = shop.post("/estimates/new", data=_estimate_payload(), follow_redirects=True)
    assert response.status_code == 200
    assert "EST-00001" in response.text
    assert "402.50" in response.text        # (150 + 200) + 15%


def test_the_valid_until_date_is_filled_in_automatically(shop):
    shop.post("/estimates/new", data=_estimate_payload(valid_until=""), follow_redirects=True)
    page = shop.get("/estimates/1").text
    assert "2026-11-29" in page             # 14 days on from the issue date


def test_an_estimate_needs_a_customer(shop):
    response = shop.post("/estimates/new", data=_estimate_payload(customer_id=""))
    assert "Choose a customer" in response.text


def test_approving_and_invoicing_through_the_web(shop):
    shop.post("/estimates/new", data=_estimate_payload())

    blocked = shop.post("/estimates/1/invoice", follow_redirects=True)
    assert "Only an approved estimate" in blocked.text

    shop.post("/estimates/1/status", data={"status": "approved", "approved_by": "Ahmed"})
    response = shop.post("/estimates/1/invoice", data={"doc_type": "tax"},
                         follow_redirects=True)
    assert "Draft" in response.text
    assert "EST-00001" in response.text     # the invoice links back
    assert "402.50" in response.text


def test_a_plain_invoice_prints_without_tax_wording(shop):
    shop.post(
        "/invoices/new",
        data={"customer_id": "1", "issue_date": "2026-11-15", "doc_type": "plain",
              "vat_rate": "15", "status": "issued", "item_description": ["Cash sale"],
              "item_qty": ["1"], "item_price": ["150"], "item_kind": ["part"],
              "item_unit": ["pcs"], "item_catalog_id": [""], "item_description_ar": [""]},
    )
    page = shop.get("/invoices/1/print?autoprint=0").text
    assert "TAX INVOICE" not in page
    assert ">INVOICE<" in page
    assert "150.00" in page
    # The VAT rate posted with the form is ignored for a plain invoice.
    assert "فاتورة ضريبية" not in page


def test_a_tax_invoice_still_prints_as_one(shop):
    shop.post(
        "/invoices/new",
        data={"customer_id": "1", "issue_date": "2026-11-15", "doc_type": "tax",
              "vat_rate": "15", "status": "issued", "item_description": ["Service"],
              "item_qty": ["1"], "item_price": ["100"], "item_kind": ["service"],
              "item_unit": ["pcs"], "item_catalog_id": [""], "item_description_ar": [""]},
    )
    page = shop.get("/invoices/1/print?autoprint=0").text
    assert "TAX INVOICE" in page
    assert "115.00" in page


def test_the_printed_estimate_is_not_a_tax_invoice(shop):
    shop.post("/estimates/new", data=_estimate_payload())
    page = shop.get("/estimates/1/print?autoprint=0").text
    assert "ESTIMATE" in page and "عرض سعر" in page
    assert "TAX INVOICE" not in page
    assert "not a tax invoice" in page
    assert 'class="topnav"' not in page


def test_estimate_filters_narrow_the_list(shop):
    shop.post("/estimates/new", data=_estimate_payload())
    shop.post("/estimates/new", data=_estimate_payload())
    shop.post("/estimates/1/status", data={"status": "approved"})

    assert "EST-00002" not in shop.get("/estimates?status=approved").text
    assert "EST-00001" not in shop.get("/estimates?status=draft").text


def test_the_send_button_sits_beside_print_at_every_stage(shop):
    """A quote is discussed with the customer long before it is approved.

    Walking down the page to the send panel to do that was a step for
    nothing, so the button is in the header -- and it has to be there on a
    draft, not only once the customer has already said yes.
    """
    shop.post("/estimates/new", data={
        "customer_id": "1", "vehicle_id": "1", "issue_date": "2026-11-16",
        "vat_rate": "15", "item_catalog_id": [""],
        "item_description": ["Full service"], "item_description_ar": [""],
        "item_kind": ["service"], "item_unit": ["pcs"],
        "item_qty": ["1"], "item_price": ["450"],
    })

    def header_links(page):
        head = page.split('class="actions"')[1].split("</div>")[0]
        return head

    draft = shop.get("/estimates/1").text
    assert "wa.me" in header_links(draft), "draft has no send button"

    shop.post("/estimates/1/status", data={"status": "sent"})
    shop.post("/estimates/1/status", data={"status": "approved"})

    approved = shop.get("/estimates/1").text
    assert "wa.me" in header_links(approved), "approved has no send button"
    # And the gate it sits next to is still there.
    assert "/estimates/1/invoice" in approved
