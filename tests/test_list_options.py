"""The dropdown lists, now that they are data rather than code.

The point of the feature is that a workshop can add a supplier without
anyone editing Python. The point of these tests is that doing so cannot
damage anything already written down.
"""

from __future__ import annotations

import pytest

from app import repository as repo


def test_the_lists_arrive_seeded(conn):
    """An empty list on first run would be a dropdown with nothing in it."""
    for name in repo.OPTION_LISTS:
        assert repo.list_options(conn, name), f"{name} is empty"


def test_a_new_value_is_offered(conn):
    repo.create_option(
        conn, list_name="payment_methods", value="stc_pay", label_en="STC Pay"
    )
    offered = [row["value"] for row in repo.list_options(conn, "payment_methods")]
    assert "stc_pay" in offered


def test_a_new_value_goes_to_the_end(conn):
    repo.create_option(
        conn, list_name="units", value="box", label_en="box"
    )
    rows = repo.list_options(conn, "units")
    assert rows[-1]["value"] == "box"


def test_the_label_defaults_to_the_value(conn):
    """A value added with no label still has to read as something."""
    option_id = repo.create_option(conn, list_name="units", value="drum", label_en="")
    assert repo.get_option(conn, option_id)["label_en"] == "drum"


def test_an_unknown_list_is_refused(conn):
    with pytest.raises(ValueError):
        repo.create_option(conn, list_name="../etc", value="x", label_en="x")


def test_a_blank_value_is_refused(conn):
    with pytest.raises(ValueError):
        repo.create_option(conn, list_name="units", value="   ", label_en="x")


def test_switching_one_off_stops_it_being_offered(conn):
    cheque = next(
        r for r in repo.list_options(conn, "payment_methods") if r["value"] == "cheque"
    )
    repo.update_option(conn, cheque["id"], is_active=False)
    offered = [r["value"] for r in repo.list_options(conn, "payment_methods")]
    assert "cheque" not in offered


def test_a_switched_off_value_keeps_its_words(conn):
    """An invoice paid by cheque last year still has to print "Cheque".

    Retiring a choice is about what can be picked next, never about
    rewriting what already happened.
    """
    cheque = next(
        r for r in repo.list_options(conn, "payment_methods") if r["value"] == "cheque"
    )
    repo.update_option(conn, cheque["id"], is_active=False)

    offered, labels = repo.all_options(conn)
    assert "cheque" not in [r["value"] for r in offered["payment_methods"]]
    assert labels[("payment_methods", "cheque")]["label_en"] == "Cheque"


def test_a_builtin_is_switched_off_rather_than_deleted(conn):
    """Deleting it would leave old invoices pointing at nothing."""
    cash = next(
        r for r in repo.list_options(conn, "payment_methods") if r["value"] == "cash"
    )
    repo.delete_option(conn, cash["id"])
    still_there = repo.get_option(conn, cash["id"])
    assert still_there["is_active"] == 0


def test_an_added_value_can_be_deleted_outright(conn):
    option_id = repo.create_option(
        conn, list_name="units", value="pallet", label_en="pallet"
    )
    repo.delete_option(conn, option_id)
    with pytest.raises(repo.NotFound):
        repo.get_option(conn, option_id)


def test_re_adding_a_retired_value_switches_it_back_on(conn):
    """Someone who cannot see the inactive rows will simply add it again.

    Answering "that already exists" about a row they cannot see is a dead
    end, so the same wish is honoured instead.
    """
    cheque = next(
        r for r in repo.list_options(conn, "payment_methods") if r["value"] == "cheque"
    )
    repo.update_option(conn, cheque["id"], is_active=False)

    again = repo.create_option(
        conn, list_name="payment_methods", value="cheque", label_en="Cheque"
    )
    assert again == cheque["id"]
    assert repo.get_option(conn, again)["is_active"] == 1


def test_the_stored_value_is_never_renamed(conn):
    """update_option has no parameter for it, and that is deliberate."""
    unit = repo.list_options(conn, "units")[0]
    repo.update_option(conn, unit["id"], label_en="Each")
    assert repo.get_option(conn, unit["id"])["value"] == unit["value"]


# --- through the web -------------------------------------------------------

def test_a_value_added_in_settings_reaches_the_form(shop):
    shop.post(
        "/settings/lists/add",
        data={
            "list_name": "payment_methods",
            "value": "stc_pay",
            "label_en": "STC Pay",
            "label_ar": "إس تي سي باي",
        },
    )
    assert "STC Pay" in shop.get("/invoices/quick").text


def test_units_come_from_the_list_not_the_template(shop):
    shop.post(
        "/settings/lists/add",
        data={"list_name": "units", "value": "drum", "label_en": "drum"},
    )
    assert "drum" in shop.get("/catalog/new").text


def test_the_lists_screen_shows_the_retired_ones(shop, read_web_db):
    """Their existence is what explains why re-adding says it exists."""
    with read_web_db() as c:
        cheque = c.execute(
            "SELECT id FROM list_options WHERE value = 'cheque'"
        ).fetchone()["id"]
    shop.post(
        "/settings/lists/save",
        data={
            "list_name": "payment_methods",
            "option_id": [str(cheque)],
            "label_en": ["Cheque"],
            "label_ar": ["شيك"],
            "sort_order": ["40"],
            "active": ["0"],
        },
    )
    page = shop.get("/settings/lists?list_name=payment_methods").text
    assert "cheque" in page
    assert "is-off" in page


def test_enter_in_a_label_saves_rather_than_deletes(shop):
    """The row Delete buttons are submits too, and come first in the form.

    A hidden save button is placed ahead of them so the Enter key -- the
    most natural thing to press after typing -- cannot delete a value.
    """
    page = shop.get("/settings/lists?list_name=units").text
    form = page[page.index('action="/settings/lists/save"'):]
    first_submit = form.index('type="submit"')
    first_delete = form.index("/delete") if "/delete" in form else len(form)
    assert first_submit < first_delete
    assert "default-submit" in form
