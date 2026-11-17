"""The advanced analytics panel, and the charts it draws.

The charts are plain functions returning SVG, so they can be checked without
rendering a page or driving a browser. What is worth pinning is the arithmetic
behind them and the two things that have actually gone wrong: labels running
under bars, and a right-to-left page scrambling a chart.
"""

from __future__ import annotations

from app import charts

# ---------------------------------------------------------------------------
# The charts themselves
# ---------------------------------------------------------------------------


def test_the_biggest_bar_is_the_darkest():
    """More-is-darker, so the ranking survives grayscale and a bad screen."""
    svg = charts.meter_list([("Big", 100), ("Small", 5)])
    darkest, lightest = charts.RAMP[4], charts.RAMP[0]
    assert darkest in svg
    assert lightest in svg
    assert svg.index(darkest) < svg.index(lightest)


def test_every_bar_carries_its_own_figure():
    """The pale end of the ramp has no contrast; the numbers are the relief."""
    svg = charts.meter_list([("BMW", 59), ("Audi", 4)])
    assert "59" in svg and "4" in svg
    assert "BMW" in svg and "Audi" in svg


def test_a_long_name_is_cut_rather_than_drawn_over_the_bar():
    svg = charts.meter_list([("A name far too long for its column", 10)], label_width=100)
    assert "…" in svg
    assert "A name far too long for its column" not in svg


def test_a_wider_label_column_keeps_more_of_the_name():
    narrow = charts.meter_list([("Timing chain guide wear", 3)], label_width=100)
    wide = charts.meter_list([("Timing chain guide wear", 3)], label_width=250)
    assert "Timing chain guide wear" in wide
    assert "Timing chain guide wear" not in narrow


def test_charts_never_inherit_the_pages_direction():
    """An SVG that inherits rtl moves its text anchors but not its rectangles.

    That put every label off the canvas and left a page of unlabelled bars.
    """
    assert 'direction="ltr"' in charts.meter_list([("BMW", 1)])
    assert 'direction="ltr"' in charts.meter_list([("BMW", 1)], rtl=True)
    assert 'direction="ltr"' in charts.trend([("2026-01", 1.0), ("2026-02", 2.0)])


def test_mirroring_moves_the_zones_not_only_the_anchors():
    """Figure, bar and name each get their own band in both directions."""
    ltr = charts.meter_list([("BMW", 59)])
    rtl = charts.meter_list([("BMW", 59)], rtl=True)
    assert 'text-anchor="end"' in rtl      # the name, on the right
    assert ltr != rtl
    # The track does not start at the very edge in rtl, or it would sit on
    # top of the figure.
    assert 'x="80"' in rtl


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
    assert "<details class=\"analytics\">" in page
    assert "<details class=\"analytics\" open>" not in page
