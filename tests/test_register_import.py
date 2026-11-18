"""Reading a workshop's car register out of a spreadsheet.

One row is a car, the owner is repeated down the sheet, and the red somebody
marked a row with years ago is a warning rather than formatting. Most of
these tests are about judgement calls on messy data -- which is where an
import of this kind goes wrong, not in the SQL.
"""

from __future__ import annotations

import pytest

from app import register_import as reg

HEAD = ["File No.", "Make", "Plate", "Color", "Year", "Vin",
        "Customer Name", "Mobile", "Comments", "NUMBERS"]


def sheet(*rows):
    return [HEAD, *rows]


def row(file_no="1", make="BMW", plate="1234ABC", colour="WHITE", year="2015",
        vin="D123456", name="AHMED", mobile="*0501234567", comment="", numbers=""):
    return [file_no, make, plate, colour, year, vin, name, mobile, comment, numbers]


# --- what counts as the same person ---------------------------------------

def test_one_owner_with_several_cars_is_one_customer(conn):
    out = reg.prepare(sheet(
        row(plate="AAA", name="KHALID", mobile="*0551100065"),
        row(plate="BBB", name="KHALID", mobile="*0551100065"),
        row(plate="CCC", name="KHALID", mobile="0551100065"),
    ), {})
    assert out["summary"]["customers"] == 1
    assert out["summary"]["vehicles"] == 3


def test_the_same_name_with_different_numbers_stays_two_people(conn):
    """A register holds several bare "MOHAMMED"s who have nothing to do with
    each other. Merging them would invent a relationship."""
    out = reg.prepare(sheet(
        row(plate="AAA", name="MOHAMMED", mobile="*0500000001"),
        row(plate="BBB", name="MOHAMMED", mobile="*0500000002"),
    ), {})
    assert out["summary"]["customers"] == 2


def test_a_numberless_row_joins_the_one_person_of_that_name(conn):
    """There is nobody else they could be."""
    out = reg.prepare(sheet(
        row(plate="AAA", name="FAISAL", mobile="*0569666612"),
        row(plate="BBB", name="FAISAL", mobile=""),
    ), {})
    assert out["summary"]["customers"] == 1
    assert out["summary"]["merged"] == 1


def test_a_numberless_row_stays_apart_when_the_name_is_ambiguous(conn):
    """Two numbers against that name: choosing between them is a guess, and
    a guess here puts one person's car on another person's record."""
    out = reg.prepare(sheet(
        row(plate="AAA", name="MOHAMMED", mobile="*0500000001"),
        row(plate="BBB", name="MOHAMMED", mobile="*0500000002"),
        row(plate="CCC", name="MOHAMMED", mobile=""),
    ), {})
    assert out["summary"]["customers"] == 3
    assert out["summary"]["merged"] == 0


def test_a_car_with_no_owner_name_is_kept(conn):
    """The car is real even when nobody wrote the owner down, and a plate
    and chassis number are worth more than a tidy customer list."""
    out = reg.prepare(sheet(row(plate="5063HZJ", name="", mobile="")), {})
    assert out["summary"]["vehicles"] == 1
    assert out["summary"]["placeholders"] == 1
    assert "5063HZJ" in out["customers"][0].name


def test_nameless_cars_do_not_pile_up_on_one_placeholder(conn):
    """Sharing one would read as a single person's fleet."""
    out = reg.prepare(sheet(
        row(plate="AAA", name="", mobile=""),
        row(plate="BBB", name="", mobile=""),
    ), {})
    assert out["summary"]["placeholders"] == 2


# --- the marks --------------------------------------------------------------

def test_do_not_receive_becomes_a_refusal(conn):
    out = reg.prepare(
        sheet(row(comment="PLEASE DO NOT RECEIVE THIS CAR")), {2: {8}}
    )
    assert out["customers"][0].alert_level == "refuse"


@pytest.mark.parametrize("wording", [
    "PLEASE DO NOT RECEIVE THIS CAR",
    "Do Not Receive this car",
    "Don't Receive this car and don't give history",
    "do not accept this vehicle",
])
def test_one_instruction_written_many_ways(conn, wording):
    """Three days, three people, one meaning."""
    out = reg.prepare(sheet(row(comment=wording)), {2: {8}})
    assert out["customers"][0].alert_level == "refuse", wording


@pytest.mark.parametrize("wording", [
    "PLEASE INFORM BEFORE RECEIVING THIS CAR",
    "CAUTION",
    "PLEASE DISCUSS AND OPEN",
])
def test_ask_first_is_not_a_refusal(conn, wording):
    out = reg.prepare(sheet(row(comment=wording)), {2: {8}})
    assert out["customers"][0].alert_level == "check", wording


def test_a_marked_row_with_ordinary_words_is_only_a_note(conn):
    """Interrupting someone to tell them a driver's name is how people learn
    to dismiss warnings without reading them."""
    out = reg.prepare(sheet(row(comment="DRIVER JAMEEL KHAN")), {2: {8}})
    assert out["customers"][0].alert_level == "note"


def test_a_marked_row_with_no_words_still_gets_a_flag(conn):
    """Somebody marked it for a reason that may not be in the file."""
    out = reg.prepare(sheet(row(comment="")), {2: {1}})
    assert out["customers"][0].alert_level == "note"


def test_red_in_a_column_that_is_not_read_is_not_a_warning(conn):
    """The scratch column holds a supplier's phone number. Red there is
    about the number, and flagging the customer over it would put warnings
    on people nobody warned about."""
    out = reg.prepare(sheet(row(comment="", numbers="TURKI 0567745365")), {2: {9}})
    assert out["customers"][0].alert_level == ""


def test_an_unmarked_row_with_a_refusal_written_in_it_still_counts(conn):
    """The words are what matter. Somebody who typed the instruction and
    forgot to colour the row still typed the instruction."""
    out = reg.prepare(sheet(row(comment="PLEASE DO NOT RECEIVE THIS CAR")), {})
    assert out["customers"][0].alert_level == "refuse"


def test_the_worst_warning_wins_across_an_owners_rows(conn):
    out = reg.prepare(sheet(
        row(plate="AAA", name="X", mobile="*0500000001", comment="DRIVER SAID HELLO"),
        row(plate="BBB", name="X", mobile="*0500000001", comment="DO NOT RECEIVE"),
    ), {2: {8}, 3: {8}})
    assert out["customers"][0].alert_level == "refuse"


# --- messy cells ------------------------------------------------------------

def test_the_asterisk_is_not_part_of_the_number(conn):
    out = reg.prepare(sheet(row(mobile="*0501234567")), {})
    assert out["customers"][0].phone == "0501234567"


def test_a_second_number_is_kept_not_thrown_away(conn):
    """The second number is often the one that answers."""
    out = reg.prepare(sheet(row(mobile="0506095406/0502478888")), {})
    customer = out["customers"][0]
    assert customer.phone == "0506095406"
    assert "0502478888" in customer.notes


def test_a_driver_in_brackets_is_not_part_of_the_number(conn):
    out = reg.prepare(sheet(row(mobile="*0504161769 (Driver *0539575410)")), {})
    assert out["customers"][0].phone == "0504161769"


def test_a_second_plate_is_noted_on_the_car(conn):
    out = reg.prepare(sheet(row(plate="2521HBD/705AVH")), {})
    vehicle = out["vehicles"][0]
    assert vehicle.plate == "2521HBD"
    assert "705AVH" in vehicle.notes


@pytest.mark.parametrize("written,expected", [
    ("MERC", "Mercedes-Benz"),
    ("MERCEDES BENZ", "Mercedes-Benz"),
    ("VW", "Volkswagen"),
    ("ROLLS ROYCE", "Rolls-Royce"),
    ("BWM", "BMW"),          # the same word misspelt
    ("PORCSHE", "Porsche"),
])
def test_one_make_written_many_ways_is_one_make(conn, written, expected):
    out = reg.prepare(sheet(row(make=written)), {})
    assert out["vehicles"][0].make == expected


def test_an_unfamiliar_make_is_kept_as_written(conn):
    """Guessing at an unfamiliar name is how a register ends up with cars
    nobody can find."""
    out = reg.prepare(sheet(row(make="Koenigsegg")), {})
    assert out["vehicles"][0].make == "Koenigsegg"


def test_two_makes_on_one_line_do_not_become_two_cars(conn):
    """The register is ambiguous about which plate goes with which, and a
    car record invented from a guess is worse than a note."""
    out = reg.prepare(sheet(row(make="BMW/RR", plate="76XKA/4710KGJ")), {})
    assert out["summary"]["vehicles"] == 1
    assert out["vehicles"][0].make == "BMW"
    assert "Rolls-Royce" in out["vehicles"][0].notes


def test_a_model_written_in_the_year_column_is_kept(conn):
    """The column is headed Year and holds "G12". Both are worth keeping;
    only one of them is a year."""
    out = reg.prepare(sheet(row(year="G12")), {})
    assert out["vehicles"][0].model_year is None
    assert "G12" in out["vehicles"][0].notes


def test_a_year_is_read_as_a_year(conn):
    out = reg.prepare(sheet(row(year="2015")), {})
    assert out["vehicles"][0].model_year == 2015


# --- what it refuses to do --------------------------------------------------

def test_a_repeated_plate_is_left_out(conn):
    out = reg.prepare(sheet(
        row(plate="166NUZ", vin="A1"),
        row(plate="166NUZ", vin="A2"),
    ), {})
    assert out["summary"]["vehicles"] == 1
    assert out["summary"]["skipped"] == 1


def test_a_row_with_no_plate_and_no_chassis_is_left_out(conn):
    out = reg.prepare(sheet(row(plate="", vin="")), {})
    assert out["summary"]["skipped"] == 1


def test_a_file_with_nothing_to_identify_a_car_is_refused(conn):
    with pytest.raises(reg.RegisterImportError):
        reg.prepare([["Name", "Mobile"], ["Ahmed", "0500000000"]], {})


def test_an_empty_file_is_refused(conn):
    with pytest.raises(reg.RegisterImportError):
        reg.prepare([], {})


def test_the_scratch_column_is_reported_not_swept_in(conn):
    out = reg.prepare(sheet(row(numbers="TAQDEER 0591204010")), {})
    assert "NUMBERS" in out["ignored_columns"]
    assert "TAQDEER" not in out["customers"][0].notes


# --- writing it ------------------------------------------------------------

def test_the_import_writes_owners_and_their_cars(conn):
    out = reg.prepare(sheet(
        row(plate="AAA", name="KHALID", mobile="*0551100065"),
        row(plate="BBB", name="KHALID", mobile="*0551100065"),
        row(plate="CCC", name="SARA", mobile="*0551100066",
            comment="PLEASE DO NOT RECEIVE THIS CAR"),
    ), {4: {8}})

    from app import repository as repo
    result = repo.commit_register_import(
        conn, [vars(c) for c in out["customers"]], [vars(v) for v in out["vehicles"]]
    )
    assert result["customers"] == 2
    assert result["vehicles"] == 3

    khalid = conn.execute(
        "SELECT id FROM customers WHERE name = 'KHALID'"
    ).fetchone()["id"]
    assert conn.execute(
        "SELECT COUNT(*) n FROM vehicles WHERE customer_id = ?", (khalid,)
    ).fetchone()["n"] == 2

    sara = conn.execute(
        "SELECT alert_level, alert_note FROM customers WHERE name = 'SARA'"
    ).fetchone()
    assert sara["alert_level"] == "refuse"
    assert "DO NOT RECEIVE" in sara["alert_note"]


def test_importing_the_same_file_twice_does_not_double_the_customers(conn):
    """A register reloaded after a correction should not produce two of
    everybody."""
    from app import repository as repo

    prepared = reg.prepare(sheet(row(name="KHALID", mobile="*0551100065")), {})
    payload = (
        [vars(c) for c in prepared["customers"]],
        [vars(v) for v in prepared["vehicles"]],
    )
    repo.commit_register_import(conn, *payload)
    second = repo.commit_register_import(conn, *payload)

    assert second["customers"] == 0
    assert second["reused"] == 1
    assert conn.execute("SELECT COUNT(*) n FROM customers").fetchone()["n"] == 1


# --- the blank template ----------------------------------------------------

def test_the_template_can_be_read_by_the_importer_that_offers_it():
    """A template whose own importer rejects it is worse than none."""
    data = reg.template_xlsx()
    rows, marked = reg.read_xlsx(data)
    out = reg.prepare(rows, marked)
    assert out["summary"]["vehicles"] == 3
    assert out["summary"]["skipped"] == 0
    assert not out["ignored_columns"]


def test_the_template_demonstrates_the_red_convention():
    """A convention is easier to copy than to describe: the third example
    is marked red with a refusal in its Comments cell, so whoever opens the
    file can see what a flagged car looks like."""
    rows, marked = reg.read_xlsx(reg.template_xlsx())
    out = reg.prepare(rows, marked)
    flagged = [c for c in out["customers"] if c.alert_level]
    assert len(flagged) == 1
    assert flagged[0].alert_level == "refuse"


def test_the_template_headings_are_the_ones_the_reader_knows():
    rows, _ = reg.read_xlsx(reg.template_xlsx())
    mapping, ignored = reg.map_columns(rows[0])
    assert not ignored
    for field in ("make", "plate", "name", "phone", "comments", "vin"):
        assert field in mapping.values(), field


def test_the_template_downloads_as_a_spreadsheet(shop):
    response = shop.get("/vehicles/import/template")
    assert response.status_code == 200
    assert "spreadsheetml" in response.headers["content-type"]
    assert ".xlsx" in response.headers["content-disposition"]


def test_both_templates_are_offered_where_somebody_would_look(shop):
    assert "/vehicles/import/template" in shop.get("/vehicles").text
    assert "/customers/import/template" in shop.get("/customers").text
