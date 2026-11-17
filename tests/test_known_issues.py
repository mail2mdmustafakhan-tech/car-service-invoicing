"""Known faults, and the jobs they are attached to.

The list is reference material a workshop edits. What matters in these tests
is that it behaves like the workshop's own data rather than something the
software owns: editable, retirable, deletable, and never quietly reaching the
customer's copy when somebody said it should not.
"""

from __future__ import annotations

import pytest


@pytest.fixture()
def workshop(shop):
    """The shared shop, which already has a customer and a vehicle."""
    return shop


def test_the_shipped_list_arrives_with_the_database(shop):
    page = shop.get("/issues").text
    assert "Timing chain guide wear" in page
    assert "BMW" in page and "Mercedes-Benz" in page


def test_a_shipped_fault_is_the_workshops_to_change(shop):
    """Marked built-in, but nothing treats it as more authoritative."""
    first = shop.get("/issues").text
    assert "Timing chain guide wear" in first

    shop.post("/issues/1/edit", data={
        "make": "BMW", "model": "3 Series (F30)", "engine": "N20",
        "year_from": "2011", "year_to": "2015",
        "title_en": "Chain guides — our own wording",
        "title_ar": "", "symptoms_en": "", "symptoms_ar": "",
        "check_en": "", "check_ar": "", "severity": "high",
        "notes": "", "is_active": "1",
    })
    after = shop.get("/issues").text
    assert "Chain guides — our own wording" in after
    assert "Timing chain guide wear" not in after


def test_a_fault_can_be_retired_without_losing_the_history(shop):
    """An unticked box is simply absent, which is how it is switched off."""
    shop.post("/issues/2/edit", data={
        "make": "BMW", "model": "", "engine": "", "year_from": "", "year_to": "",
        "title_en": "Retired fault", "title_ar": "", "symptoms_en": "",
        "symptoms_ar": "", "check_en": "", "check_ar": "", "severity": "low",
        "notes": "",
        # is_active omitted: an unticked checkbox is simply absent
    })
    assert "Retired fault" not in shop.get("/issues").text
    assert "Retired fault" in shop.get("/issues?inactive=1").text


def test_a_fault_attached_to_a_job_shows_on_the_job(workshop):
    workshop.post("/contracts/new", data=_minimal_contract())
    workshop.post("/contracts/1/issues", data={
        "known_issue_id": "1", "outcome": "confirmed",
        "show_on_print": "1", "note": "Rattle on cold start",
    })
    page = workshop.get("/contracts/1").text
    assert "Rattle on cold start" in page
    assert "Confirmed" in page


def test_attaching_the_same_fault_twice_updates_rather_than_errors(workshop):
    """The second attempt is somebody correcting what they found."""
    workshop.post("/contracts/new", data=_minimal_contract())
    workshop.post("/contracts/1/issues", data={
        "known_issue_id": "1", "outcome": "suspected", "show_on_print": "1",
        "note": "first guess",
    })
    workshop.post("/contracts/1/issues", data={
        "known_issue_id": "1", "outcome": "ruled_out", "show_on_print": "1",
        "note": "checked, chain is fine",
    })
    page = workshop.get("/contracts/1").text
    assert "checked, chain is fine" in page
    assert "first guess" not in page
    # One attached row, not two. Counting the word would also catch the
    # outcome dropdown, which lists every outcome by design.
    assert page.count("/contract-issues/") == 1


def test_a_fault_marked_not_to_print_stays_off_the_customers_copy(workshop):
    """Ruling a fault out is worth recording and is not the customer's business."""
    workshop.post("/contracts/new", data=_minimal_contract())
    workshop.post("/contracts/1/issues", data={
        "known_issue_id": "1", "outcome": "ruled_out",
        "note": "checked, fine",
        # show_on_print omitted -- the tick was cleared
    })
    assert "checked, fine" in workshop.get("/contracts/1").text
    printed = workshop.get("/contracts/1/print?autoprint=0").text
    assert "checked, fine" not in printed


def test_a_fault_marked_to_print_does_reach_the_printed_contract(workshop):
    workshop.post("/contracts/new", data=_minimal_contract())
    workshop.post("/contracts/1/issues", data={
        "known_issue_id": "1", "outcome": "repaired",
        "show_on_print": "1", "note": "chain and guides replaced",
    })
    printed = workshop.get("/contracts/1/print?autoprint=0").text
    assert "chain and guides replaced" in printed


def _minimal_contract() -> dict:
    return {
        "customer_id": "1", "vehicle_id": "1", "date_in": "2026-11-16",
        "status": "open",
        "item_catalog_id": [""], "item_description": ["Diagnosis"],
        "item_description_ar": [""], "item_expense": ["150"], "item_remarks": [""],
        "part_catalog_id": [], "part_number": [], "part_description": [],
        "part_description_ar": [], "part_qty": [], "part_price": [],
        "part_sourced": [],
    }
