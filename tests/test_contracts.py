"""Tests for the repair contract: the paperwork the workshop runs on.

The contract is written and signed when the car arrives and becomes an invoice
once the work is done, so the things worth pinning down are its own numbering,
the estimate it carries, and that converting it into an invoice happens exactly
once and carries the right lines across.
"""

from __future__ import annotations

import pytest

from app import repository as repo

# --------------------------------------------------------------------------
# Numbering
# --------------------------------------------------------------------------

def test_contract_numbers_are_their_own_series(conn):
    """A contract that never becomes an invoice must not leave an invoice gap."""
    assert repo.reserve_contract_no(conn) == "RC-00001"
    assert repo.reserve_contract_no(conn) == "RC-00002"
    # The invoice series is untouched by any of that.
    assert repo.reserve_invoice_no(conn) == "INV-00001"


def test_contract_numbering_is_configurable(conn):
    repo.update_settings(conn, {"contract_prefix": "JC/", "next_contract_seq": 870})
    assert repo.reserve_contract_no(conn) == "JC/00870"


def test_migration_seeds_the_printed_notice(conn):
    settings = repo.get_settings(conn)
    assert len(settings["contract_terms_en"].strip().splitlines()) == 6
    assert len(settings["contract_terms_ar"].strip().splitlines()) == 6
    # The business name is substituted at print time rather than baked in, so
    # the project ships without one workshop's name in its database defaults.
    assert "{business}" in settings["contract_authorization_en"]
    assert "{business}" in settings["contract_authorization_ar"]


# --------------------------------------------------------------------------
# Writing one up
# --------------------------------------------------------------------------

@pytest.fixture()
def booked_in(conn):
    """A customer, their car, and a contract covering two jobs and one part."""
    customer_id = repo.create_customer(conn, {"name": "Ahmed", "phone": "0551234567"})
    vehicle_id = repo.create_vehicle(
        conn,
        {"customer_id": customer_id, "plate_no": "ABC 1234", "make": "Toyota",
         "model": "Land Cruiser", "odometer": 84000},
    )
    order_id = repo.create_repair_order(
        conn,
        {"customer_id": customer_id, "vehicle_id": vehicle_id, "date_in": "2026-11-11",
         "expected_date_out": "2026-11-13", "odometer": 84500, "car_code": "LC-200",
         "technician_name": "Rashid", "status": "open"},
        [
            {"description": "Engine oil change", "description_ar": "تغيير زيت المحرك",
             "expense_minor": 18500, "technician_remarks": "Done, 5L 5W-30"},
            {"description": "Check brake noise", "expense_minor": 0,
             "technician_remarks": "Front pads worn below 2mm"},
        ],
        [
            {"part_number": "04465-60280", "description": "Front brake pads",
             "qty_milli": 1000, "unit_price_minor": 32000, "sourced_externally": 1},
        ],
    )
    return conn, customer_id, vehicle_id, order_id


def test_contract_stores_its_lines_in_order(booked_in):
    conn, _, _, order_id = booked_in
    items = repo.get_order_items(conn, order_id)
    parts = repo.get_order_parts(conn, order_id)

    assert [i["line_no"] for i in items] == [1, 2]
    assert items[0]["description_ar"] == "تغيير زيت المحرك"
    assert items[1]["technician_remarks"] == "Front pads worn below 2mm"
    assert parts[0]["part_number"] == "04465-60280"
    assert parts[0]["sourced_externally"] == 1


def test_part_line_totals_are_computed_on_save(booked_in):
    conn, _, _, order_id = booked_in
    assert repo.get_order_parts(conn, order_id)[0]["line_total_minor"] == 32000


def test_estimate_splits_labour_from_parts(booked_in):
    conn, _, _, order_id = booked_in
    totals = repo.order_totals(conn, order_id)
    assert totals["labour_minor"] == 18500
    assert totals["parts_minor"] == 32000
    assert totals["total_minor"] == 50500


def test_a_repair_line_may_carry_no_charge(booked_in):
    """"Check the brake noise" with a finding and no price is a normal row."""
    conn, _, _, order_id = booked_in
    assert repo.get_order_items(conn, order_id)[1]["expense_minor"] == 0


def test_editing_replaces_lines_and_the_estimate_follows(booked_in):
    conn, customer_id, vehicle_id, order_id = booked_in
    repo.update_repair_order(
        conn,
        order_id,
        {"customer_id": customer_id, "vehicle_id": vehicle_id, "date_in": "2026-11-11"},
        [{"description": "Wash only", "expense_minor": 5000, "technician_remarks": ""}],
        [],
    )
    assert len(repo.get_order_items(conn, order_id)) == 1
    assert repo.get_order_parts(conn, order_id) == []
    assert repo.order_totals(conn, order_id)["total_minor"] == 5000


def test_signing_is_recorded_with_its_date(booked_in):
    conn, _, _, order_id = booked_in
    assert repo.get_repair_order(conn, order_id)["customer_signed"] == 0

    repo.sign_repair_order(conn, order_id, True)
    signed = repo.get_repair_order(conn, order_id)
    assert signed["customer_signed"] == 1
    assert signed["signed_on"]

    repo.sign_repair_order(conn, order_id, False)
    assert repo.get_repair_order(conn, order_id)["signed_on"] is None


def test_unknown_status_is_rejected(booked_in):
    conn, _, _, order_id = booked_in
    with pytest.raises(ValueError):
        repo.set_order_status(conn, order_id, "finished")


# --------------------------------------------------------------------------
# Becoming an invoice
# --------------------------------------------------------------------------

def test_conversion_carries_labour_and_parts_across(booked_in):
    conn, _, _, order_id = booked_in
    invoice_id = repo.convert_order_to_invoice(conn, order_id)

    lines = repo.get_invoice_items(conn, invoice_id)
    # The no-charge inspection line is not an invoice line.
    assert len(lines) == 2
    assert lines[0]["description"] == "Engine oil change"
    assert lines[0]["kind"] == "service"
    assert lines[0]["unit_price_minor"] == 18500
    assert lines[1]["description"] == "Front brake pads"
    assert lines[1]["kind"] == "part"

    invoice = repo.get_invoice(conn, invoice_id)
    assert invoice["subtotal_minor"] == 50500
    assert invoice["vat_minor"] == 7575      # 15% of 505.00
    assert invoice["total_minor"] == 58075


def test_conversion_produces_a_draft_for_checking(booked_in):
    """The invoice is never issued automatically -- somebody must look at it."""
    conn, _, _, order_id = booked_in
    invoice_id = repo.convert_order_to_invoice(conn, order_id)
    assert repo.get_invoice(conn, invoice_id)["status"] == "draft"


def test_conversion_links_the_two_together(booked_in):
    conn, _, _, order_id = booked_in
    invoice_id = repo.convert_order_to_invoice(conn, order_id)

    order = repo.get_repair_order(conn, order_id)
    assert order["invoice_id"] == invoice_id
    assert order["status"] == "invoiced"
    assert repo.order_for_invoice(conn, invoice_id)["contract_no"] == order["contract_no"]


def test_conversion_carries_the_car_and_odometer(booked_in):
    conn, _, vehicle_id, order_id = booked_in
    invoice = repo.get_invoice(conn, repo.convert_order_to_invoice(conn, order_id))
    assert invoice["vehicle_id"] == vehicle_id
    assert invoice["odometer"] == 84500


def test_a_contract_cannot_be_invoiced_twice(booked_in):
    conn, _, _, order_id = booked_in
    repo.convert_order_to_invoice(conn, order_id)
    with pytest.raises(repo.InUse):
        repo.convert_order_to_invoice(conn, order_id)


def test_an_invoiced_contract_is_frozen(booked_in):
    conn, customer_id, _, order_id = booked_in
    repo.convert_order_to_invoice(conn, order_id)
    with pytest.raises(repo.InUse):
        repo.update_repair_order(
            conn, order_id,
            {"customer_id": customer_id, "date_in": "2026-11-11"},
            [{"description": "x", "expense_minor": 100, "technician_remarks": ""}],
            [],
        )
    with pytest.raises(repo.InUse):
        repo.delete_repair_order(conn, order_id)


def test_a_cancelled_contract_cannot_be_invoiced(booked_in):
    conn, _, _, order_id = booked_in
    repo.set_order_status(conn, order_id, "cancelled")
    with pytest.raises(repo.InUse):
        repo.convert_order_to_invoice(conn, order_id)


def test_a_contract_with_nothing_chargeable_cannot_be_invoiced(conn):
    customer_id = repo.create_customer(conn, {"name": "Walk-in"})
    order_id = repo.create_repair_order(
        conn,
        {"customer_id": customer_id, "date_in": "2026-11-11"},
        [{"description": "Inspection, no fault found", "expense_minor": 0,
          "technician_remarks": "Nothing wrong"}],
        [],
    )
    with pytest.raises(repo.InUse):
        repo.convert_order_to_invoice(conn, order_id)


def test_deleting_a_contract_removes_its_lines(booked_in):
    conn, _, _, order_id = booked_in
    repo.delete_repair_order(conn, order_id)
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM repair_order_items"
    ).fetchone()["n"] == 0
    assert conn.execute(
        "SELECT COUNT(*) AS n FROM repair_order_parts"
    ).fetchone()["n"] == 0


# --------------------------------------------------------------------------
# Reporting
# --------------------------------------------------------------------------

def test_open_contracts_show_as_cars_in_the_workshop(booked_in):
    conn, _, _, order_id = booked_in
    in_workshop = repo.cars_in_workshop(conn)
    assert [c["id"] for c in in_workshop] == [order_id]

    repo.convert_order_to_invoice(conn, order_id)
    assert repo.cars_in_workshop(conn) == []


def test_dashboard_counts_contracts(booked_in):
    conn, _, _, order_id = booked_in
    assert repo.dashboard_stats(conn)["open_contract_count"] == 1

    repo.set_order_status(conn, order_id, "completed")
    stats = repo.dashboard_stats(conn)
    assert stats["open_contract_count"] == 0
    assert stats["contracts_to_invoice"] == 1


def test_reporting_view_exposes_the_estimate_as_decimals(booked_in):
    conn, _, _, order_id = booked_in
    row = conn.execute(
        "SELECT * FROM v_repair_orders WHERE id = ?", (order_id,)
    ).fetchone()
    assert row["labour_estimate"] == pytest.approx(185.00)
    assert row["parts_estimate"] == pytest.approx(320.00)
    assert row["estimate_total"] == pytest.approx(505.00)
    assert row["vehicle_plate"] == "ABC 1234"


# ==========================================================================
# The web layer
# ==========================================================================

def _contract_payload(**overrides):
    payload = {
        "customer_id": "1",
        "vehicle_id": "1",
        "date_in": "2026-11-11",
        "expected_date_out": "2026-11-13",
        "odometer": "84500",
        "car_code": "LC-200",
        "technician_name": "Rashid",
        "status": "open",
        "damage_notes": "Scratch on rear bumper.",
        "notes": "Noise when braking.",
        "item_catalog_id": ["1", ""],
        "item_description": ["Oil change", "Check brake noise"],
        "item_description_ar": ["تغيير زيت", ""],
        "item_expense": ["150", ""],
        "item_remarks": ["Done", "Pads worn"],
        "part_catalog_id": [""],
        "part_number": ["04465-60280"],
        "part_description": ["Front brake pads"],
        "part_description_ar": ["فحمات فرامل"],
        "part_qty": ["1"],
        "part_price": ["320"],
        "part_sourced": ["1"],
    }
    payload.update(overrides)
    return payload


@pytest.fixture()
def workshop(shop):
    """The shared `shop` fixture plus a vehicle, ready to write a contract."""
    return shop


@pytest.mark.parametrize("url", ["/contracts", "/contracts/new"])
def test_contract_pages_load_when_empty(client, url):
    assert client.get(url).status_code == 200


def test_creating_a_contract_through_the_form(workshop):
    response = workshop.post(
        "/contracts/new", data=_contract_payload(), follow_redirects=True
    )
    assert response.status_code == 200
    assert "RC-00001" in response.text
    assert "470.00" in response.text          # 150 labour + 320 parts


def test_a_contract_needs_a_customer(workshop):
    response = workshop.post("/contracts/new", data=_contract_payload(customer_id=""))
    assert "Choose the customer" in response.text


def test_a_contract_needs_at_least_one_repair(workshop):
    response = workshop.post(
        "/contracts/new",
        data=_contract_payload(
            item_catalog_id=[""], item_description=[""], item_description_ar=[""],
            item_expense=[""], item_remarks=[""],
        ),
    )
    assert "at least one repair" in response.text


def test_a_cost_without_a_description_is_rejected(workshop):
    """Otherwise a charge could end up on the contract with nothing naming it."""
    response = workshop.post(
        "/contracts/new",
        data=_contract_payload(
            item_catalog_id=[""], item_description=[""], item_description_ar=[""],
            item_expense=["500"], item_remarks=[""],
        ),
    )
    assert "describe the work" in response.text


def test_a_contract_may_have_no_parts(workshop):
    response = workshop.post(
        "/contracts/new",
        data=_contract_payload(
            part_catalog_id=[""], part_number=[""], part_description=[""],
            part_description_ar=[""], part_qty=[""], part_price=[""],
            part_sourced=["0"],
        ),
        follow_redirects=True,
    )
    assert response.status_code == 200
    assert "150.00" in response.text


def test_the_source_of_each_part_stays_with_the_right_part(workshop):
    """A checkbox would not submit when unticked and would shift the column."""
    workshop.post(
        "/contracts/new",
        data=_contract_payload(
            part_catalog_id=["", "", ""],
            part_number=["A1", "B2", "C3"],
            part_description=["Own part", "Agency part", "Own again"],
            part_description_ar=["", "", ""],
            part_qty=["1", "1", "1"],
            part_price=["10", "20", "30"],
            part_sourced=["0", "1", "0"],
        ),
    )
    page = workshop.get("/contracts/1").text
    agency_rows = page.count("From agency")
    assert agency_rows == 1


def test_the_printed_contract_follows_the_paper_form(workshop):
    workshop.post("/contracts/new", data=_contract_payload())
    page = workshop.get("/contracts/1/print?autoprint=0").text

    assert "CAR REPAIR CONTRACT" in page and "عقد اصلاح سيارة" in page
    assert "Important Notice" in page and "ملاحظة هامة" in page
    assert "Repairs Requested By Owner of Car" in page
    assert "Technician's Remarks" in page
    assert "Type of Spare" in page and "مسمى القطعة" in page
    assert "car-diagram" in page            # the damage sketch
    assert "Scratch on rear bumper." in page
    assert 'class="topnav"' not in page     # no app navigation on the paper


def test_the_business_name_is_substituted_into_the_authorization(workshop):
    workshop.post("/contracts/new", data=_contract_payload())
    page = workshop.get("/contracts/1/print?autoprint=0").text
    assert "{business}" not in page
    assert "Test Auto Service" in page


def test_the_printed_contract_does_not_change_with_the_interface_language(workshop):
    """The customer's copy must look the same whoever printed it."""
    workshop.post("/contracts/new", data=_contract_payload())

    workshop.get("/lang/en")
    english = workshop.get("/contracts/1/print?autoprint=0").text
    workshop.get("/lang/ar")
    arabic = workshop.get("/contracts/1/print?autoprint=0").text

    assert 'dir="ltr"' in english and 'dir="ltr"' in arabic
    assert "CAR REPAIR CONTRACT" in arabic and "عقد اصلاح سيارة" in english


def test_converting_through_the_web_lands_on_a_draft_invoice(workshop):
    workshop.post("/contracts/new", data=_contract_payload())
    response = workshop.post("/contracts/1/invoice", follow_redirects=True)

    assert response.status_code == 200
    assert "Draft" in response.text
    assert "RC-00001" in response.text        # links back to the contract
    assert "540.50" in response.text          # 470.00 plus 15% VAT


def test_signing_through_the_web(workshop):
    workshop.post("/contracts/new", data=_contract_payload())
    assert "Not signed" in workshop.get("/contracts/1").text

    workshop.post("/contracts/1/sign", data={"signed": "1"})
    assert "Not signed" not in workshop.get("/contracts/1").text


def test_contract_filters_narrow_the_list(workshop):
    workshop.post("/contracts/new", data=_contract_payload())
    workshop.post("/contracts/new", data=_contract_payload())
    workshop.post("/contracts/1/status", data={"status": "completed"})

    assert "RC-00002" not in workshop.get("/contracts?status=completed").text
    assert "RC-00001" not in workshop.get("/contracts?status=open").text


def test_contract_settings_can_be_edited(client):
    client.post(
        "/settings",
        data={"business_name_en": "Shop", "vat_rate": "15", "currency_code": "SAR",
              "invoice_prefix": "INV-", "next_invoice_seq": "1",
              "default_language": "en", "contract_prefix": "JOB-",
              "next_contract_seq": "500", "parts_markup": "12.5",
              "business_tagline_en": "Mechanical - Electrical",
              "contract_terms_en": "First point.\nSecond point.",
              "contract_authorization_en": "I authorize {business} to proceed."},
    )
    page = client.get("/settings").text
    assert 'value="JOB-"' in page
    assert 'value="500"' in page
    assert 'value="12.5"' in page
    assert "First point." in page


def test_the_notice_is_numbered_from_its_lines(workshop):
    workshop.post(
        "/settings",
        data={"business_name_en": "Test Auto Service", "vat_rate": "15",
              "currency_code": "SAR", "invoice_prefix": "T-", "next_invoice_seq": "1",
              "default_language": "en", "contract_prefix": "RC-",
              "next_contract_seq": "1", "parts_markup": "10",
              "contract_terms_en": "One.\n\nTwo.\nThree.",
              "contract_terms_ar": "واحد.\nاثنان."},
    )
    workshop.post("/contracts/new", data=_contract_payload())
    page = workshop.get("/contracts/1/print?autoprint=0").text
    # Three English points and two Arabic ones; the blank line is dropped.
    assert page.count("<li>") == 5
