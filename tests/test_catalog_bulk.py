"""Selecting catalogue rows and acting on them with one button.

A per-row Delete is fine when you remove one thing a month. It is the
wrong shape for the job actually in hand, which is tidying up a list of
seventy that has just been imported -- duplicates to drop, Arabic rows
that turned out to mirror English ones.

The risk a bulk action carries is proportional to how easy it is: one
careless click can take out forty rows. So what is tested here is mostly
restraint -- that it acts on exactly what was ticked, that it does
nothing when nothing was ticked, and that it cannot quietly damage an
invoice that has already gone to a customer.
"""

from __future__ import annotations


def _add(client, name: str, code: str = "") -> None:
    client.post("/catalog/new", data={
        "name_en": name, "name_ar": "", "kind": "service",
        "unit": "pcs", "unit_price": "100", "code": code})


def _ids(read_web_db) -> list[int]:
    with read_web_db() as c:
        return [r["id"] for r in
                c.execute("SELECT id FROM catalog_items ORDER BY id")]


def _names(read_web_db) -> list[str]:
    with read_web_db() as c:
        return [r["name_en"] for r in
                c.execute("SELECT name_en FROM catalog_items ORDER BY id")]


def _protect(client, on: bool = True) -> None:
    client.post("/settings/protect-records",
                data={"protect_records": "1"} if on else {})


# --- acting on exactly what was ticked --------------------------------------


def test_only_the_selected_items_go(shop, read_web_db):
    _add(shop, "Wheel alignment")
    _add(shop, "Brake fluid")
    ids = _ids(read_web_db)  # the fixture's "Oil change", then these two

    shop.post("/catalog/bulk-delete", data={"ids": [ids[0], ids[2]]})

    assert _names(read_web_db) == ["Wheel alignment"]


def test_one_selected_item_works_the_same_way(shop, read_web_db):
    """The bulk button replaced the per-row one, so it has to do that
    job too -- removing a single item is still the commonest case."""
    _add(shop, "Wheel alignment")
    ids = _ids(read_web_db)

    shop.post("/catalog/bulk-delete", data={"ids": [ids[1]]})

    assert "Wheel alignment" not in _names(read_web_db)
    assert len(_names(read_web_db)) == 1


def test_selecting_nothing_changes_nothing(shop, read_web_db):
    """Easy to reach: tick a row, untick it, press the button.

    Worth its own test because the alternative -- an empty id list
    reaching a DELETE with an empty IN clause -- is the shape of bug
    that quietly empties a table.
    """
    _add(shop, "Wheel alignment")
    before = _names(read_web_db)

    page = shop.post("/catalog/bulk-delete", data={}, follow_redirects=True)

    assert _names(read_web_db) == before
    assert "Nothing was selected" in page.text


def test_an_id_that_does_not_exist_is_ignored(shop, read_web_db):
    before = _names(read_web_db)

    shop.post("/catalog/bulk-delete", data={"ids": [99999]})

    assert _names(read_web_db) == before


# --- what it must not break -------------------------------------------------


def test_an_invoice_already_raised_is_untouched(shop, read_web_db):
    """The whole reason deleting a catalogue row is safe at all.

    Lines keep their own description, price and code and only lose the
    link back. If that ever stopped being true, a tidy-up of the
    catalogue would silently rewrite invoices that have already been
    handed to customers -- which is about the worst thing this
    application could do.
    """
    shop.post("/invoices/new", data={
        "customer_id": "1", "vehicle_id": "1", "issue_date": "2026-11-26",
        "vat_rate": "15", "status": "issued",
        "item_catalog_id": ["1"], "item_description": ["Oil change"],
        "item_description_ar": [""], "item_kind": ["service"],
        "item_unit": ["pcs"], "item_qty": ["1"], "item_price": ["150"]})

    with read_web_db() as c:
        before = dict(c.execute(
            "SELECT description, code, unit_price_minor FROM invoice_items"
        ).fetchone())

    shop.post("/catalog/bulk-delete", data={"ids": [1]})

    with read_web_db() as c:
        after = dict(c.execute(
            "SELECT description, code, unit_price_minor, catalog_item_id "
            "FROM invoice_items").fetchone())

    assert after["description"] == before["description"]
    assert after["code"] == before["code"]
    assert after["unit_price_minor"] == before["unit_price_minor"]
    assert after["catalog_item_id"] is None  # only the link goes


def test_the_invoice_still_opens_after_its_item_is_deleted(shop):
    shop.post("/invoices/new", data={
        "customer_id": "1", "vehicle_id": "1", "issue_date": "2026-11-26",
        "vat_rate": "15", "status": "issued",
        "item_catalog_id": ["1"], "item_description": ["Oil change"],
        "item_description_ar": [""], "item_kind": ["service"],
        "item_unit": ["pcs"], "item_qty": ["1"], "item_price": ["150"]})
    shop.post("/catalog/bulk-delete", data={"ids": [1]})

    assert shop.get("/invoices/1").status_code == 200
    assert shop.get("/invoices/1/print").status_code == 200


# --- the switch still governs -----------------------------------------------


def test_with_records_protected_the_items_are_retired_instead(shop, read_web_db):
    _add(shop, "Wheel alignment")
    _protect(shop, True)
    ids = _ids(read_web_db)

    shop.post("/catalog/bulk-delete", data={"ids": ids})

    with read_web_db() as c:
        rows = list(c.execute("SELECT name_en, is_active FROM catalog_items"))
    assert len(rows) == 2  # nothing removed
    assert all(r["is_active"] == 0 for r in rows)


def test_a_stale_page_still_gets_the_safe_behaviour(shop, read_web_db):
    """Their button says Delete because the page was drawn before the
    switch was flipped. The route decides, not the label."""
    _add(shop, "Wheel alignment")
    page = shop.get("/catalog").text
    assert "Make inactive" not in page

    _protect(shop, True)
    shop.post("/catalog/bulk-delete", data={"ids": _ids(read_web_db)})

    with read_web_db() as c:
        assert c.execute("SELECT COUNT(*) FROM catalog_items").fetchone()[0] == 2


def test_the_button_says_what_it_will_do(shop):
    _protect(shop, True)
    assert "Make inactive" in shop.get("/catalog").text

    _protect(shop, False)
    assert "Make inactive" not in shop.get("/catalog").text


# --- the page ---------------------------------------------------------------


def test_every_row_offers_a_tick_box_and_the_head_offers_select_all(shop):
    _add(shop, "Wheel alignment")
    page = shop.get("/catalog").text

    assert page.count('name="ids"') == 2
    assert "data-bulk-all" in page


def test_there_is_one_delete_button_not_one_per_row(shop):
    """The point of the request. Two items used to mean two buttons."""
    _add(shop, "Wheel alignment")
    _add(shop, "Brake fluid")
    page = shop.get("/catalog").text

    assert page.count("/catalog/bulk-delete") == 1
    assert "/delete" not in page.replace("/catalog/bulk-delete", "")


def test_the_list_still_works_with_nothing_in_it(shop):
    shop.post("/catalog/bulk-delete", data={"ids": [1]})

    page = shop.get("/catalog")
    assert page.status_code == 200
