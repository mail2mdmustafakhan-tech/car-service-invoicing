"""The quick invoice — a wiper blade, a bulb, a litre of oil.

The whole feature is about removing steps, so these tests mostly check that
a step really is gone: no vehicle, no due date, no odometer, no second screen
to take the money, and no detour through the customer form for a walk-in.
"""

from __future__ import annotations


def _sale(**overrides):
    """One catalogue line and one typed line, paid in cash."""
    data = {
        "customer_name": "Mr Saleh",
        "customer_phone": "0551112222",
        "doc_type": "tax",
        "item_description": ["Wiper blades", "Fit and test", ""],
        "item_qty": ["1", "1", "1"],
        "item_price": ["220", "30", ""],
        "item_catalog_id": ["", "", ""],
        "paid_now": "1",
        "payment_method": "cash",
    }
    data.update(overrides)
    return data


def test_a_walk_in_gets_an_invoice_without_a_detour(shop, read_web_db):
    """Stopping to fill in a customer form is what sends people to a paper pad."""
    response = shop.post("/invoices/quick", data=_sale(), follow_redirects=False)
    assert response.status_code in (302, 303)
    assert "/print" in response.headers["location"]

    with read_web_db() as c:
        customer = c.execute(
            "SELECT name, phone FROM customers WHERE name = 'Mr Saleh'"
        ).fetchone()

    assert customer is not None
    assert customer["phone"] == "0551112222"


def test_the_sale_is_booked_to_somebody(shop, read_web_db):
    """An invoice with no customer behind it is a hole in the records."""
    shop.post("/invoices/quick", data=_sale())
    with read_web_db() as c:
        row = c.execute(
            "SELECT customer_id FROM invoices ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row["customer_id"] is not None


def test_an_existing_customer_is_not_duplicated(shop, read_web_db):
    """Picking somebody off the list must not create a second copy of them."""
    shop.post("/invoices/quick", data=_sale(customer_id="1", customer_name=""))
    with read_web_db() as c:
        total = c.execute("SELECT COUNT(*) AS n FROM customers").fetchone()["n"]
    assert total == 1


def test_it_is_issued_not_left_as_a_draft(shop, read_web_db):
    """A counter sale that needs a second visit to issue is not quick."""
    shop.post("/invoices/quick", data=_sale())
    with read_web_db() as c:
        status = c.execute(
            "SELECT status FROM invoices ORDER BY id DESC LIMIT 1"
        ).fetchone()["status"]
    assert status == "issued"


def test_the_money_is_recorded_in_the_same_breath(shop, read_web_db):
    """Counter sales are paid on the spot; a second screen for that is a step."""
    shop.post("/invoices/quick", data=_sale())
    with read_web_db() as c:
        invoice = c.execute(
            "SELECT id, total_minor FROM invoices ORDER BY id DESC LIMIT 1"
        ).fetchone()
        payment = c.execute(
            "SELECT amount_minor, method FROM payments WHERE invoice_id = ?",
            (invoice["id"],),
        ).fetchone()

    assert payment is not None
    assert payment["amount_minor"] == invoice["total_minor"]
    assert payment["method"] == "cash"


def test_nothing_is_recorded_when_the_customer_is_not_paying_yet(shop, read_web_db):
    shop.post("/invoices/quick", data=_sale(paid_now=""))
    with read_web_db() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM payments").fetchone()["n"] == 0


def test_untouched_rows_are_not_mistakes(shop, read_web_db):
    """The rows arrive with a quantity in them. Two of three stay empty."""
    shop.post("/invoices/quick", data=_sale())
    with read_web_db() as c:
        lines = c.execute("SELECT description FROM invoice_items").fetchall()
    assert [row["description"] for row in lines] == ["Wiper blades", "Fit and test"]


def test_an_empty_sale_is_refused(shop, read_web_db):
    page = shop.post("/invoices/quick", data=_sale(
        item_description=["", "", ""], item_price=["", "", ""],
    )).text
    assert "at least one line" in page
    with read_web_db() as c:
        assert c.execute("SELECT COUNT(*) AS n FROM invoices").fetchone()["n"] == 0


def test_a_cash_sale_can_carry_no_vat(shop, read_web_db):
    shop.post("/invoices/quick", data=_sale(doc_type="plain"))
    with read_web_db() as c:
        row = c.execute(
            "SELECT doc_type, vat_minor FROM invoices ORDER BY id DESC LIMIT 1"
        ).fetchone()
    assert row["doc_type"] == "plain"
    assert row["vat_minor"] == 0


def test_the_screen_is_reachable_by_its_own_name(shop):
    """/invoices/quick must not be read as an invoice whose id is "quick"."""
    assert shop.get("/invoices/quick").status_code == 200
