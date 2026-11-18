"""Colour and model written in each other's boxes.

The register has "320I" where the colour goes and "BLUE" where the model
goes, sometimes both at once. These tests are almost entirely about what the
tool refuses to touch: moving somebody's data on a guess is worse than
leaving it as they wrote it, and the value of the thing is that the rows it
lists are the ones there is no argument about.
"""

from __future__ import annotations

import pytest

from app import repository as repo


@pytest.fixture()
def car(conn):
    repo.create_customer(conn, {"name": "Owner"})

    def add(plate, model, colour, make="BMW"):
        conn.execute(
            "INSERT INTO vehicles (customer_id, plate_no, make, model, colour)"
            " VALUES (1, ?, ?, ?, ?)",
            (plate, make, model, colour),
        )
        conn.commit()

    return add


def _one(conn):
    fixes = repo.colour_model_mixups(conn)
    assert len(fixes) == 1, fixes
    return fixes[0]


# --- what it moves ----------------------------------------------------------

def test_a_plain_swap_is_put_back_the_right_way_round(conn, car):
    car("AAA", model="BLUE", colour="A8")
    fix = _one(conn)
    assert fix["action"] == "swap"
    assert fix["new_model"] == "A8"
    assert fix["new_colour"] == "BLUE"


def test_a_model_code_in_an_empty_model_slot_moves_across(conn, car):
    car("AAA", model="", colour="G12")
    fix = _one(conn)
    assert (fix["new_model"], fix["new_colour"]) == ("G12", "")


def test_a_colour_in_an_empty_colour_slot_moves_across(conn, car):
    car("AAA", model="BLACK", colour="")
    fix = _one(conn)
    assert (fix["new_model"], fix["new_colour"]) == ("", "BLACK")


def test_a_moved_value_leaves_its_old_box_empty(conn, car):
    """Written as "keep the old colour" at first, which left the model code
    sitting in both columns and fixed nothing."""
    car("AAA", model="", colour="X5")
    repo.apply_colour_model_fixes(conn)
    row = conn.execute("SELECT model, colour FROM vehicles").fetchone()
    assert row["model"] == "X5"
    assert row["colour"] == ""


def test_two_word_colours_are_recognised(conn, car):
    car("AAA", model="SKY BLUE", colour="")
    assert _one(conn)["new_colour"] == "SKY BLUE"


def test_case_and_spacing_do_not_matter(conn, car):
    car("AAA", model="  black  ", colour="")
    assert _one(conn)["action"] == "to_colour"


# --- what it leaves alone ---------------------------------------------------

def test_a_car_recorded_correctly_is_not_touched(conn, car):
    car("AAA", model="X5", colour="BLACK")
    assert repo.colour_model_mixups(conn) == []


def test_two_colours_are_left_alone(conn, car):
    """Both boxes hold a colour. There is no way to tell which is the real
    one, so it stays as written."""
    car("AAA", model="BLUE", colour="BLACK")
    assert repo.colour_model_mixups(conn) == []


def test_a_trim_name_is_not_a_model(conn, car):
    """"Individual" is a BMW trim, not a model code, and moving it into the
    model column would invent a model that does not exist."""
    car("AAA", model="", colour="INDIVIDUAL")
    assert repo.colour_model_mixups(conn) == []


def test_a_sentence_is_not_a_model(conn, car):
    car("AAA", model="", colour="Imported from Germany 2019")
    assert repo.colour_model_mixups(conn) == []


def test_a_word_with_no_digit_is_not_a_model_code(conn, car):
    car("AAA", model="", colour="SPORT")
    assert repo.colour_model_mixups(conn) == []


def test_an_empty_car_is_not_listed(conn, car):
    car("AAA", model="", colour="")
    assert repo.colour_model_mixups(conn) == []


# --- applying it ------------------------------------------------------------

def test_nothing_changes_until_it_is_applied(conn, car):
    car("AAA", model="BLUE", colour="A8")
    repo.colour_model_mixups(conn)
    row = conn.execute("SELECT model, colour FROM vehicles").fetchone()
    assert (row["model"], row["colour"]) == ("BLUE", "A8")


def test_applying_it_twice_changes_nothing_the_second_time(conn, car):
    car("AAA", model="BLUE", colour="A8")
    assert repo.apply_colour_model_fixes(conn) == 1
    assert repo.apply_colour_model_fixes(conn) == 0


def test_only_the_named_cars_are_touched(conn, car):
    car("AAA", model="BLUE", colour="A8")
    car("BBB", model="GREY", colour="X5")
    first = repo.colour_model_mixups(conn)[0]["id"]
    assert repo.apply_colour_model_fixes(conn, [first]) == 1
    assert len(repo.colour_model_mixups(conn)) == 1


def test_what_is_written_is_what_the_preview_showed(conn, car):
    """The work is recomputed on apply rather than taken from the posted
    form, so a tampered field cannot write something nobody was shown."""
    car("AAA", model="BLUE", colour="A8")
    repo.apply_colour_model_fixes(conn, [9999])
    row = conn.execute("SELECT model, colour FROM vehicles").fetchone()
    assert (row["model"], row["colour"]) == ("BLUE", "A8")


# --- through the web --------------------------------------------------------

def test_the_preview_lists_the_cars_without_changing_them(shop, read_web_db):
    shop.post("/vehicles/new", data={
        "customer_id": "1", "plate_no": "TIDY 1", "make": "BMW",
        "model": "BLUE", "colour": "A8",
    })
    page = shop.get("/vehicles/tidy").text
    assert "TIDY 1" in page
    with read_web_db() as c:
        row = c.execute("SELECT model FROM vehicles WHERE plate_no='TIDY 1'").fetchone()
    assert row["model"] == "BLUE"


def test_applying_it_through_the_web_moves_them(shop, read_web_db):
    shop.post("/vehicles/new", data={
        "customer_id": "1", "plate_no": "TIDY 2", "make": "BMW",
        "model": "BLUE", "colour": "A8",
    })
    shop.post("/vehicles/tidy")
    with read_web_db() as c:
        row = c.execute(
            "SELECT model, colour FROM vehicles WHERE plate_no='TIDY 2'"
        ).fetchone()
    assert (row["model"], row["colour"]) == ("A8", "BLUE")


def test_tidy_is_not_read_as_a_vehicle_id(shop):
    assert shop.get("/vehicles/tidy").status_code == 200
