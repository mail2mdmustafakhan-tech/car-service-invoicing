"""Excluding VAT, and saying what the discount was.

Three things, all of which come down to the same idea: what the customer was
told and what the system did must not be able to drift apart.

A quote given without VAT must not become a taxed invoice. A discount agreed
as "ten percent" must say ten percent wherever the customer reads it, not only
the riyals it worked out to. And the message -- which is the only one of these
documents most customers ever actually read -- must carry both.
"""

from __future__ import annotations

import pytest

from app import messaging
from app import repository as repo

# ---------------------------------------------------------------------------
# Excluding VAT
# ---------------------------------------------------------------------------

def _estimate(shop, **extra):
    data = {
        "customer_id": "1", "vehicle_id": "1", "issue_date": "2026-01-10",
        "valid_until": "", "notes": "", "discount": "", "discount_mode": "amount",
        "vat_rate": "15", "item_description": ["Full service"],
        "item_description_ar": [""], "item_kind": ["service"], "item_unit": ["pc"],
        "item_qty": ["1"], "item_price": ["1000"], "item_catalog_id": [""],
    }
    data.update(extra)
    return shop.post("/estimates/new", data=data, follow_redirects=True)


def _invoice(shop, **extra):
    data = {
        "customer_id": "1", "vehicle_id": "1", "issue_date": "2026-01-10",
        "due_date": "", "odometer": "", "notes": "", "discount": "",
        "discount_mode": "amount", "vat_rate": "15", "doc_type": "tax",
        "item_description": ["Full service"], "item_description_ar": [""],
        "item_kind": ["service"], "item_unit": ["pc"], "item_qty": ["1"],
        "item_price": ["1000"], "item_catalog_id": [""],
    }
    data.update(extra)
    return shop.post("/invoices/new", data=data, follow_redirects=True)


def _latest(read_web_db, table):
    with read_web_db() as conn:
        return conn.execute(f"SELECT * FROM {table} ORDER BY id DESC LIMIT 1").fetchone()


def test_an_estimate_can_be_quoted_without_vat(shop, read_web_db):
    _estimate(shop, exclude_vat="1")
    estimate = _latest(read_web_db, "estimates")

    assert estimate["vat_rate_bp"] == 0
    assert estimate["vat_minor"] == 0
    assert estimate["total_minor"] == 100000


def test_the_rate_in_the_box_is_ignored_when_the_box_is_ticked(shop, read_web_db):
    """Settled in the route, not trusted to the form. The quote and its
    arithmetic must not be able to disagree about whether tax was quoted."""
    _estimate(shop, exclude_vat="1", vat_rate="15")

    assert _latest(read_web_db, "estimates")["vat_rate_bp"] == 0


def test_an_invoice_can_be_issued_without_vat(shop, read_web_db):
    _invoice(shop, exclude_vat="1")
    invoice = _latest(read_web_db, "invoices")

    assert invoice["doc_type"] == "plain"
    assert invoice["vat_minor"] == 0


def test_the_older_field_still_works(shop, read_web_db):
    """`doc_type` remains what is stored and what the route accepts, so
    anything posting it directly -- an older form, a test, a script -- is
    unaffected by the tick-box being added in front of it."""
    _invoice(shop, doc_type="plain")

    assert _latest(read_web_db, "invoices")["doc_type"] == "plain"


def test_prices_including_vat_is_meaningless_without_vat(shop, read_web_db):
    """Ticking both would otherwise store "these prices include a tax that is
    not being charged"."""
    _estimate(shop, exclude_vat="1", prices_include_vat="1")

    assert _latest(read_web_db, "estimates")["prices_include_vat"] == 0


def test_a_quote_without_vat_becomes_an_invoice_without_vat(shop, read_web_db):
    """The one that matters. Quoting a customer one figure and invoicing them
    a taxed one is how an argument starts at the counter.
    """
    _estimate(shop, exclude_vat="1")
    estimate = _latest(read_web_db, "estimates")
    shop.post(f"/estimates/{estimate['id']}/status", data={"status": "approved"})

    shop.post(f"/estimates/{estimate['id']}/invoice", follow_redirects=True)
    invoice = _latest(read_web_db, "invoices")

    assert invoice["doc_type"] == "plain", "a quote given without VAT was taxed"
    assert invoice["vat_minor"] == 0


def test_a_normal_quote_still_becomes_a_tax_invoice(shop, read_web_db):
    _estimate(shop)
    estimate = _latest(read_web_db, "estimates")
    shop.post(f"/estimates/{estimate['id']}/status", data={"status": "approved"})

    shop.post(f"/estimates/{estimate['id']}/invoice", follow_redirects=True)

    assert _latest(read_web_db, "invoices")["doc_type"] == "tax"


def test_the_button_can_still_override_it(shop, read_web_db):
    """Posting the field explicitly wins, for whoever needs it to."""
    _estimate(shop, exclude_vat="1")
    estimate = _latest(read_web_db, "estimates")
    shop.post(f"/estimates/{estimate['id']}/status", data={"status": "approved"})

    shop.post(f"/estimates/{estimate['id']}/invoice",
              data={"doc_type": "tax"}, follow_redirects=True)

    assert _latest(read_web_db, "invoices")["doc_type"] == "tax"


def test_the_box_is_still_ticked_when_the_estimate_is_reopened(shop, read_web_db):
    _estimate(shop, exclude_vat="1")
    estimate = _latest(read_web_db, "estimates")

    page = shop.get(f"/estimates/{estimate['id']}/edit").text
    marker = page[page.index('name="exclude_vat"'):]
    assert "checked" in marker[:marker.index(">")]


# ---------------------------------------------------------------------------
# Saying what the discount was
# ---------------------------------------------------------------------------

def test_a_percentage_discount_is_shown_as_a_percentage(shop, read_web_db):
    """Both facts are stored -- what was agreed and what it came to -- and
    only the second was ever shown. A customer promised ten percent reads
    "Discount  -100.00" and has to work out whether that is what they were
    promised."""
    _estimate(shop, discount="10", discount_mode="percent")
    estimate = _latest(read_web_db, "estimates")

    assert estimate["discount_minor"] == 10000
    assert estimate["discount_rate_bp"] == 1000

    for path in (f"/estimates/{estimate['id']}", f"/estimates/{estimate['id']}/print"):
        assert "10%" in shop.get(path).text, path


def test_a_flat_discount_is_not_dressed_up_as_a_rate(shop, read_web_db):
    _estimate(shop, discount="100", discount_mode="amount")
    estimate = _latest(read_web_db, "estimates")

    page = shop.get(f"/estimates/{estimate['id']}").text
    assert "Discount" in page
    assert "Discount (" not in page


def test_an_invoice_shows_it_too(shop, read_web_db):
    _invoice(shop, discount="10", discount_mode="percent")
    invoice = _latest(read_web_db, "invoices")

    for path in (f"/invoices/{invoice['id']}", f"/invoices/{invoice['id']}/print"):
        assert "10%" in shop.get(path).text, path


# ---------------------------------------------------------------------------
# The message, which is the only one of these most customers read
# ---------------------------------------------------------------------------

def test_a_line_whose_placeholders_are_all_empty_is_dropped(shop):
    """What makes an optional line possible at all. Without it the choice is
    between "Discount:" with nothing after it -- which reads as a fault in
    the software -- and no discount line ever."""
    out = messaging.render_template(
        "Total: {total}\nDiscount {rate}: -{discount}",
        {"total": "900.00", "rate": "", "discount": ""},
    )
    assert out == "Total: 900.00"


def test_the_line_stays_when_there_is_something_to_say(shop):
    out = messaging.render_template(
        "Total: {total}\nDiscount {rate}: -{discount}",
        {"total": "900.00", "rate": "10%", "discount": "100.00"},
    )
    assert out.splitlines()[1] == "Discount 10%: -100.00"


def test_an_unknown_placeholder_never_deletes_its_line(shop):
    """It is left alone rather than treated as empty, so a typo in somebody's
    own template loses a word rather than a whole line of their message."""
    out = messaging.render_template("Ref {typo} here", {"total": "1"})
    assert out == "Ref {typo} here"


def test_the_message_carries_the_discount(shop, read_web_db):
    from app import db, main

    _estimate(shop, discount="10", discount_mode="percent")
    estimate = _latest(read_web_db, "estimates")

    with db.session(shop_db(read_web_db)) as conn:
        full = repo.get_estimate(conn, estimate["id"])
        items = repo.get_estimate_items(conn, estimate["id"])
        message = main._estimate_message(conn, full, items, "en")

    assert "Discount" in message
    assert "10%" in message
    assert "100.00" in message


def test_the_message_says_nothing_about_a_discount_there_was_not(shop, read_web_db):
    from app import db, main

    _estimate(shop)
    estimate = _latest(read_web_db, "estimates")

    with db.session(shop_db(read_web_db)) as conn:
        full = repo.get_estimate(conn, estimate["id"])
        items = repo.get_estimate_items(conn, estimate["id"])
        message = main._estimate_message(conn, full, items, "en")

    assert "Discount" not in message


def test_the_message_leaves_out_a_vat_line_when_there_is_no_vat(shop, read_web_db):
    """"VAT: 0.00" on a quote given without VAT is noise at best, and at
    worst reads as though tax was considered and came to nothing."""
    from app import db, main

    _estimate(shop, exclude_vat="1")
    estimate = _latest(read_web_db, "estimates")

    with db.session(shop_db(read_web_db)) as conn:
        full = repo.get_estimate(conn, estimate["id"])
        items = repo.get_estimate_items(conn, estimate["id"])
        message = main._estimate_message(conn, full, items, "en")

    assert "VAT" not in message


def shop_db(read_web_db):
    """The path behind the web client's database, for opening it directly."""
    with read_web_db() as conn:
        return conn.execute("PRAGMA database_list").fetchone()[2]


@pytest.mark.parametrize("language", ["en", "ar"])
def test_the_shipped_template_offers_the_discount_line(shop, read_web_db, language):
    """An install that never edited the template gets the line for free; one
    that did keeps its own words and is told about the placeholder in
    Settings."""
    with read_web_db() as conn:
        template = conn.execute(
            f"SELECT message_template_{language} FROM settings"
        ).fetchone()[0]

    assert "{discount}" in template


# ---------------------------------------------------------------------------
# Customers who are never charged VAT
# ---------------------------------------------------------------------------
#
# The tick-box above answers "is *this* document without VAT". For some
# customers the answer is always yes, and ticking it by hand every time is
# both tedious and a thing to forget -- and forgetting means billing somebody
# tax they do not owe, which they notice.

def _exempt(read_web_db, customer_id=1, exempt=True):
    with read_web_db() as conn:
        conn.execute("UPDATE customers SET no_vat = ? WHERE id = ?",
                     (1 if exempt else 0, customer_id))
        conn.commit()


def test_the_standing_arrangement_is_saved_on_the_customer(shop, read_web_db):
    shop.post("/customers/new", data={"name": "Exempt Co", "no_vat": "1"},
              follow_redirects=True)

    assert _latest(read_web_db, "customers")["no_vat"] == 1


def test_it_can_be_taken_off_again(shop, read_web_db):
    _exempt(read_web_db)
    shop.post("/customers/1/edit", data={"name": "Back to normal", "is_active": "1"},
              follow_redirects=True)

    with read_web_db() as conn:
        assert conn.execute("SELECT no_vat FROM customers WHERE id = 1").fetchone()[0] == 0


def test_a_new_invoice_for_them_starts_without_vat(shop, read_web_db):
    """Answered on the server as well as in the browser. The direction of the
    failure decides it: a script that does not run must not mean billing
    somebody tax they do not owe."""
    _exempt(read_web_db)

    page = shop.get("/invoices/new?customer_id=1").text
    marker = page[page.index('name="exclude_vat"'):]
    assert "checked" in marker[:marker.index(">")]


def test_and_a_new_estimate_too(shop, read_web_db):
    _exempt(read_web_db)

    page = shop.get("/estimates/new?customer_id=1").text
    marker = page[page.index('name="exclude_vat"'):]
    assert "checked" in marker[:marker.index(">")]


def test_an_ordinary_customer_is_unaffected(shop, read_web_db):
    _exempt(read_web_db, exempt=False)

    page = shop.get("/invoices/new?customer_id=1").text
    marker = page[page.index('name="exclude_vat"'):]
    assert "checked" not in marker[:marker.index(">")]


def test_the_reason_travels_with_the_customer_for_the_picker(shop, read_web_db):
    """So that choosing them ticks the box at the moment of choosing, rather
    than after a second trip to the server."""
    _exempt(read_web_db)

    assert 'data-no-vat="1"' in shop.get("/invoices/new").text
    assert shop.get("/api/customers?q=").json()[-1]["no_vat"] in (True, False)


def test_it_is_a_default_and_not_a_lock(shop, read_web_db):
    """A standing arrangement should save somebody from remembering it, not
    stop them departing from it on the one job where it does not apply."""
    _exempt(read_web_db)

    _invoice(shop, exclude_vat=None, doc_type="tax")
    invoice = _latest(read_web_db, "invoices")

    assert invoice["doc_type"] == "tax", "the form could not override the customer"
    assert invoice["vat_minor"] > 0


def test_marking_a_customer_exempt_does_not_rewrite_their_old_invoices(shop, read_web_db):
    """The one that would be unforgivable. An invoice records the tax
    decision made when it was raised; a box ticked today says nothing about
    what was charged last March, and must not be able to restate it.
    """
    _invoice(shop)                       # a normal, taxed invoice
    before = _latest(read_web_db, "invoices")
    assert before["vat_minor"] > 0

    _exempt(read_web_db)

    after = _latest(read_web_db, "invoices")
    assert after["doc_type"] == "tax"
    assert after["vat_minor"] == before["vat_minor"]

    # ...and reopening it still shows what it was raised as, not what the
    # customer's arrangement says today.
    page = shop.get(f"/invoices/{before['id']}/edit").text
    marker = page[page.index('name="exclude_vat"'):]
    assert "checked" not in marker[:marker.index(">")]


def test_the_customers_own_page_says_so(shop, read_web_db):
    """An invoice arriving without VAT should have a visible reason sitting
    one click away."""
    _exempt(read_web_db)

    assert "never charged VAT" in shop.get("/customers/1").text
