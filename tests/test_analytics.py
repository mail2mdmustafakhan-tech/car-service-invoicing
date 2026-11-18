"""The advanced analytics panel, and the charts it draws.

The charts are plain functions returning markup, so they can be checked
without rendering a page or driving a browser.

What is worth pinning is the arithmetic behind them and the things that have
actually gone wrong. The bars were SVG once, and that one decision produced
three separate failures: a viewBox scaled into a narrow column shrank the
labels to nine pixels, a fixed height attribute letterboxed the drawing, and
right-to-left needed every coordinate mirrored by hand. They are HTML now,
and the tests below pin the behaviour that replaced each of those.

The fourth failure was colour: the chart colours were hex literals chosen
against white, so on the dark theme the whole panel rendered as an empty
rectangle. Hence `test_the_bars_carry_no_colour_of_their_own`.
"""

from __future__ import annotations

from app import charts
from app import repository as repo

# ---------------------------------------------------------------------------
# The charts themselves
# ---------------------------------------------------------------------------


def test_the_biggest_bar_is_marked_as_the_top_one():
    """The chart is asked "which make do we see most of". The answer should
    be the thing the eye lands on, not something to be worked out by
    comparing lengths.

    This replaced a five-step ramp. The ramp's pale end was lighter than the
    track behind it, so every small bar was invisible -- which is how the
    whole analytics panel came to look empty.
    """
    html = charts.meter_list([("Big", 100), ("Small", 5)])
    assert html.count("is-top") == 1
    top_row = html[html.index("is-top"):]
    assert "Big" in top_row[: top_row.index("</li>")]


def test_a_tie_for_the_top_marks_both():
    """Neither is "the" answer, and picking one would be arbitrary."""
    html = charts.meter_list([("A", 10), ("B", 10)])
    assert html.count("is-top") == 2


def test_an_empty_row_gets_no_bar_at_all():
    """A zero drawn at the minimum width would read as a small something."""
    html = charts.meter_list([("Has some", 10), ("Has none", 0)])
    assert 'style="width:0.0%"' in html


def test_a_tiny_value_still_draws_something():
    """15 against 1,325 is one per cent of the track. Rounded to nothing it
    would read as a zero, which is a different fact."""
    html = charts.meter_list([("Huge", 1325), ("Tiny", 15)])
    assert "width:0.0%" not in html


def test_every_bar_carries_its_own_figure():
    """Colour alone never has to carry a row: the name and the number do."""
    html = charts.meter_list([("BMW", 59), ("Audi", 4)])
    assert "59" in html and "4" in html
    assert "BMW" in html and "Audi" in html


def test_a_long_name_is_kept_whole():
    """It wraps now rather than being cut. An ellipsis loses the half of a
    fault description that says which fault it was -- "Timing chain guide…"
    and "Timing chain tensioner…" are different jobs."""
    html = charts.meter_list([("Timing chain guide wear on the N47", 3)], label_width=100)
    assert "Timing chain guide wear on the N47" in html
    assert "\u2026" not in html


def test_the_bars_carry_no_colour_of_their_own():
    """Every colour comes from a custom property, which is what lets one
    chart serve both themes. Hex literals here were chosen against white,
    and on the dark theme they drew near-black on near-black."""
    html = charts.meter_list([("BMW", 10)])
    assert "#" not in html


def test_the_track_says_nothing_to_a_screen_reader():
    """The name and the figure either side of it already carry the row."""
    html = charts.meter_list([("BMW", 10)])
    assert 'aria-hidden="true"' in html


# --- the donut -------------------------------------------------------------

def test_the_donut_names_every_slice_with_its_figure_and_share():
    """Three of the light slice colours sit under 3:1 against the card, so
    nothing is allowed to depend on telling the colours apart."""
    html = charts.donut([("BMW", 1325), ("Mercedes-Benz", 268)])
    assert "BMW" in html and "1,325" in html and "83.2%" in html
    assert "Mercedes-Benz" in html and "268" in html


def test_the_donut_folds_the_tail_into_one_slice():
    """Past six, the slices are slivers: too thin to compare, too thin to
    label, and the reader ends up reading the legend instead."""
    rows = [(f"Make {n}", 10 - n) for n in range(10)]
    html = charts.donut(rows, other_label="Other makes")
    assert html.count("donut-legend-row") == 6
    assert "Other makes" in html


def test_the_folded_tail_keeps_the_total_honest():
    rows = [("A", 50), ("B", 10), ("C", 9), ("D", 8), ("E", 7), ("F", 6), ("G", 5), ("H", 5)]
    html = charts.donut(rows, other_label="Other")
    # A is 50 of 100.
    assert "50.0%" in html
    # The tail is 5 + 5 = 10.
    assert ">10<" in html


def test_the_donut_ignores_empty_slices():
    """A zero slice is a legend row that explains nothing."""
    html = charts.donut([("BMW", 10), ("Nothing", 0)])
    assert "Nothing" not in html


def test_the_donut_sorts_largest_first():
    html = charts.donut([("Small", 1), ("Big", 99)])
    assert html.index("Big") < html.index("Small")


def test_an_empty_donut_says_so_rather_than_drawing_a_circle():
    html = charts.donut([], empty="No cars yet.")
    assert "No cars yet." in html
    assert "<svg" not in html


def test_a_trend_needs_two_points_to_be_a_trend():
    assert "polyline" not in charts.trend([("2026-01", 5.0)])
    assert "polyline" in charts.trend([("2026-01", 5.0), ("2026-02", 7.0)])


def test_only_the_last_point_on_a_trend_is_labelled():
    """A number on every point is chaos and goes unread."""
    svg = charts.trend([("2026-01", 11.0), ("2026-02", 22.0), ("2026-03", 33.0)])
    assert "33" in svg
    assert ">11<" not in svg and ">22<" not in svg


# ---------------------------------------------------------------------------
# The figures behind them
# ---------------------------------------------------------------------------


def test_what_you_are_owed_is_cumulative_not_the_months_movement(shop, read_web_db):
    """A per-month difference is the movement, and would be read as the balance."""
    from app import repository as repo

    for month, amount in (("01", "1000"), ("02", "500")):
        shop.post("/invoices/new", data={
            "customer_id": "1", "vehicle_id": "1",
            "issue_date": f"2026-{month}-10", "vat_rate": "0", "status": "issued",
            "item_catalog_id": [""], "item_description": ["Work"],
            "item_description_ar": [""], "item_kind": ["service"],
            "item_unit": ["pcs"], "item_qty": ["1"], "item_price": [amount],
        })

    with read_web_db() as c:
        rows = {r["ym"]: r for r in repo.monthly_money(c)}

    assert rows["2026-01"]["invoiced_minor"] == 100000
    assert rows["2026-02"]["invoiced_minor"] == 50000
    # January's 1,000 is still owed in February, so the balance is 1,500.
    assert rows["2026-02"]["outstanding_minor"] == 150000


def test_active_means_seen_recently_not_a_ticked_box(shop, read_web_db):
    """A stored flag is wrong the moment nobody updates it."""
    from app import repository as repo

    with read_web_db() as c:
        before = repo.customer_activity(c)
    assert before["active"] == 0
    assert before["dormant"] == before["total"]

    shop.post("/invoices/new", data={
        "customer_id": "1", "vehicle_id": "1", "issue_date": "2026-11-16",
        "vat_rate": "15", "status": "issued",
        "item_catalog_id": [""], "item_description": ["Work"],
        "item_description_ar": [""], "item_kind": ["service"],
        "item_unit": ["pcs"], "item_qty": ["1"], "item_price": ["100"],
    })

    with read_web_db() as c:
        after = repo.customer_activity(c)
    assert after["active"] == 1


def test_the_panel_arrives_closed(shop):
    """It is extra depth, not the first thing anyone needs."""
    page = shop.get("/").text
    # Asserted on the `open` attribute alone rather than on the whole tag:
    # the tag has since gained an id, and the first version of this test
    # broke on that while the behaviour it describes was untouched.
    assert 'class="analytics"' in page
    assert "analytics\" id=\"analytics\" open" not in page


# --- cars by model ---------------------------------------------------------

def test_cars_with_no_model_are_not_counted_as_a_model(conn):
    """They used to be, which put "BMW 979" at the top of a chart headed
    "Cars by model" -- 979 cars whose model nobody wrote down, reading as
    though they were all one model."""
    repo.create_customer(conn, {"name": "X"})
    for plate, make, model in (
        ("A", "BMW", "G12"), ("B", "BMW", ""), ("C", "BMW", ""), ("D", "BMW", None),
    ):
        conn.execute(
            "INSERT INTO vehicles (customer_id, plate_no, make, model)"
            " VALUES (1, ?, ?, COALESCE(?, ''))",
            (plate, make, model),
        )
    conn.commit()

    labels = [row["label"] for row in repo.cars_by_model(conn)]
    assert labels == ["BMW G12"]
    assert repo.cars_without_model(conn) == 3


def test_the_gap_is_reported_rather_than_hidden(shop, read_web_db):
    """How many cars have no model is worth knowing -- it is just a
    different fact from which models there are."""
    shop.post("/vehicles/new", data={
        "customer_id": "1", "plate_no": "NOMODEL 1", "make": "BMW", "model": "",
    })
    with read_web_db() as c:
        assert repo.cars_without_model(c) >= 1
    assert "no model recorded" in shop.get("/").text


# --- year and colour -------------------------------------------------------

def _fleet(conn, rows):
    repo.create_customer(conn, {"name": "X"})
    for plate, year, colour in rows:
        conn.execute(
            "INSERT INTO vehicles (customer_id, plate_no, make, model_year, colour)"
            " VALUES (1, ?, 'BMW', ?, ?)",
            (plate, year, colour),
        )
    conn.commit()


def test_colour_is_counted_case_insensitively(conn):
    """A register typed over years holds BLACK, Black and black, and they
    are one colour."""
    _fleet(conn, [("A", 2019, "BLACK"), ("B", 2019, "Black"), ("C", 2019, "black")])
    rows = repo.cars_by_colour(conn)
    assert len(rows) == 1
    assert rows[0]["cars"] == 3


def test_cars_with_no_colour_are_not_a_colour(conn):
    # The column is NOT NULL with a default of '', so a missing colour is
    # an empty string rather than NULL. Both are "not a colour".
    _fleet(conn, [("A", 2019, "BLACK"), ("B", 2019, ""), ("C", 2019, "   ")])
    assert [r["label"] for r in repo.cars_by_colour(conn)] == ["BLACK"]


def test_age_is_banded_rather_than_one_bar_per_year(conn):
    """One bar per year over twenty years is a picket fence nobody reads."""
    _fleet(conn, [("A", 2016, "x"), ("B", 2017, "x"), ("C", 2019, "x"), ("D", 2021, "x")])
    bands = {r["band"]: r["cars"] for r in repo.cars_by_decade(conn)}
    assert bands == {2015: 3, 2020: 1}


def test_an_impossible_year_is_left_out_of_the_bands(conn):
    """A typo like 20019 would stretch the chart to the year 20,000."""
    _fleet(conn, [("A", 2019, "x"), ("B", 20019, "x"), ("C", 12, "x")])
    bands = [r["band"] for r in repo.cars_by_decade(conn)]
    assert bands == [2015]


def test_model_codes_in_the_colour_box_are_counted_not_corrected(conn):
    """Somebody typed "320I" where the colour goes. Counting them is how a
    person who knows the cars finds out there is tidying to do -- moving
    the data silently would be a guess about their register."""
    _fleet(conn, [("A", 2019, "BLACK"), ("B", 2019, "320I"), ("C", 2019, "E300")])
    assert repo.colour_values_that_are_not_colours(conn) == 2
    # And they are still shown, as written.
    assert "320I" in [r["label"] for r in repo.cars_by_colour(conn)]


def test_the_dashboard_shows_both_new_charts(shop):
    page = shop.get("/").text
    assert "Cars by age" in page
    assert "Cars by colour" in page


# --- the chart filter ------------------------------------------------------

def test_the_car_charts_can_be_narrowed_to_one_make(conn):
    repo.create_customer(conn, {"name": "X"})
    for plate, make, model, colour, year in (
        ("A", "BMW", "G12", "BLACK", 2019),
        ("B", "BMW", "G30", "WHITE", 2021),
        ("C", "Mercedes-Benz", "E300", "BLUE", 2015),
    ):
        conn.execute(
            "INSERT INTO vehicles (customer_id, plate_no, make, model, colour, model_year)"
            " VALUES (1, ?, ?, ?, ?, ?)",
            (plate, make, model, colour, year),
        )
    conn.commit()

    assert len(repo.cars_by_model(conn, make="BMW")) == 2
    assert [r["label"] for r in repo.cars_by_colour(conn, make="Mercedes-Benz")] == ["BLUE"]
    assert sum(r["cars"] for r in repo.cars_by_decade(conn, make="BMW")) == 2


def test_the_make_filter_is_not_case_sensitive(conn):
    repo.create_customer(conn, {"name": "X"})
    conn.execute(
        "INSERT INTO vehicles (customer_id, plate_no, make, model)"
        " VALUES (1, 'A', 'BMW', 'G12')"
    )
    conn.commit()
    assert len(repo.cars_by_model(conn, make="bmw")) == 1


def test_an_unknown_make_shows_nothing_rather_than_everything(conn):
    repo.create_customer(conn, {"name": "X"})
    conn.execute(
        "INSERT INTO vehicles (customer_id, plate_no, make, model)"
        " VALUES (1, 'A', 'BMW', 'G12')"
    )
    conn.commit()
    assert repo.cars_by_model(conn, make="Lada") == []


def test_the_make_filter_cannot_be_injected(conn):
    repo.create_customer(conn, {"name": "X"})
    conn.execute("INSERT INTO vehicles (customer_id, plate_no, make) VALUES (1,'A','BMW')")
    conn.commit()
    repo.cars_by_make(conn, make="' OR 1=1 --")
    assert conn.execute("SELECT COUNT(*) AS n FROM vehicles").fetchone()["n"] == 1


def test_filtering_opens_the_section(shop):
    """A filtered section still folded away looks as though the filter did
    nothing at all."""
    page = shop.get("/?make=BMW").text
    assert 'id="analytics" open' in page


def test_the_fleet_charts_are_never_filtered(conn):
    """"Cars by make" is how somebody picks a make; filtered it is a single
    bar, which is no use for choosing anything.

    Asserted on what the panel contains, not on how the route is written.
    The first version of this test read the route's source for a particular
    call and broke the moment that call was refactored, while the behaviour
    it was meant to protect had not changed at all.
    """
    from app import main

    repo.create_customer(conn, {"name": "X"})
    for plate, mk in (("A", "BMW"), ("B", "BMW"), ("C", "Mercedes-Benz")):
        conn.execute(
            "INSERT INTO vehicles (customer_id, plate_no, make, model)"
            " VALUES (1, ?, ?, 'M1')",
            (plate, mk),
        )
    conn.commit()

    everything = main._analytics(conn, "en")
    filtered = main._analytics(conn, "en", make="BMW")

    # The chart you choose a make from, and the list you choose it in, both
    # keep every make whatever is selected.
    assert dict(filtered["by_make"]) == dict(everything["by_make"])
    assert "Mercedes-Benz" in filtered["makes"]
    # While the charts underneath it did narrow.
    assert sum(v for _, v in filtered["by_model"]) == 2


def test_the_colour_chart_counts_only_cars_that_have_one(conn):
    """The donut's centre is the slices' total, not the fleet's -- otherwise
    the percentages do not add up to what is in the middle."""
    repo.create_customer(conn, {"name": "X"})
    for plate, colour in (("A", "BLACK"), ("B", "WHITE"), ("C", "")):
        conn.execute(
            "INSERT INTO vehicles (customer_id, plate_no, make, colour)"
            " VALUES (1, ?, 'BMW', ?)",
            (plate, colour),
        )
    conn.commit()
    assert repo.cars_with_a_colour(conn) == 2
