"""The performance page, and the counting behind it.

The page exists to answer "has it got slower, and where". That makes its
own correctness load-bearing in an unusual way: a dashboard that quietly
mismeasures is worse than no dashboard, because it sends somebody tuning
the wrong page. So these tests are mostly about the counting being
attributed to the right place, not about the markup.
"""

from __future__ import annotations

from app import charts, telemetry


def _fresh() -> telemetry.Telemetry:
    return telemetry.Telemetry()


# --- what gets counted, and under what name ---------------------------------


def test_requests_are_grouped_by_route_not_by_address(client):
    """One invoice screen is one row, however many invoices are opened.

    Grouped by address instead, a workshop with five thousand invoices gets
    five thousand rows of one visit each, and the median of each is
    meaningless.
    """
    telemetry.stats.reset()
    inv = client.get("/invoices").text
    assert "/invoices" in inv

    client.get("/customers/new")
    client.get("/customers/new")

    names = {route.name for route in telemetry.stats.snapshot()["routes"]}
    assert "/customers/new" in names
    # The path template, not a rendered address with an id in it.
    assert not any(name.rstrip("/").split("/")[-1].isdigit() for name in names)


def test_unmatched_addresses_all_share_one_row(client):
    """Otherwise the dictionary grows by one key per address guessed at.

    This is the leak-shaped bug on the page whose purpose is finding leaks:
    a bot probing for /wp-login.php, /admin.php and so on would add a row
    each, forever, and never be evicted.
    """
    telemetry.stats.reset()
    for guess in ("/wp-login.php", "/admin", "/.env", "/phpmyadmin"):
        assert client.get(guess).status_code == 404

    names = [route.name for route in telemetry.stats.snapshot()["routes"]]
    assert names.count(telemetry.UNMATCHED) == 1
    assert "/wp-login.php" not in names
    row = next(r for r in telemetry.stats.snapshot()["routes"]
               if r.name == telemetry.UNMATCHED)
    assert row.count == 4


def test_static_files_are_not_counted(client):
    """They are most of the requests and none of the interesting ones.

    Counted, they bury the pages that matter: every page load fetches the
    stylesheet, so /static would sit at the top of the table forever.
    """
    telemetry.stats.reset()
    assert client.get("/static/css/app.css").status_code == 200

    assert telemetry.stats.snapshot()["requests"] == 0


def test_a_mistyped_address_is_not_an_application_failure(client):
    """404 is the application working. Only 5xx is the application failing.

    If 404s counted as failures the figure would never be zero, and a figure
    that is never zero is one nobody looks at.
    """
    telemetry.stats.reset()
    client.get("/no-such-page")

    snap = telemetry.stats.snapshot()
    assert snap["requests"] == 1
    assert snap["errors"] == 0


def test_a_server_error_is_counted_as_one():
    stats = _fresh()
    stats.record("/x", 5.0, status=500)
    stats.record("/x", 5.0, status=200)

    snap = stats.snapshot()
    assert snap["errors"] == 1
    assert snap["requests"] == 2


def test_queries_are_counted_per_request(client):
    """A page's query count is the number that finds an N+1 loop.

    A page that is slow because it runs one query per row looks identical to
    a page that is slow for any other reason, until this column.
    """
    telemetry.stats.reset()
    client.get("/invoices")

    row = next(r for r in telemetry.stats.snapshot()["routes"]
               if r.name == "/invoices")
    assert row.queries_each > 0


# --- the figures themselves -------------------------------------------------


def test_slow_runs_is_the_slow_end_not_the_average():
    """p95 and the mean answer different questions.

    Nineteen fast visits and one awful one average out to "fine", which is
    exactly the shape of the complaint "it's usually quick but sometimes it
    hangs". The slow end has to be reported separately or that complaint
    cannot be seen in the numbers at all.
    """
    stats = _fresh()
    for _ in range(90):
        stats.record("/x", 10.0, status=200)
    for _ in range(10):
        stats.record("/x", 2000.0, status=200)

    row = next(r for r in stats.snapshot()["routes"] if r.name == "/x")
    assert row.percentile(0.5) == 10  # the usual experience is fine
    assert row.percentile(0.95) >= 1000  # one visit in ten is not
    assert row.max_ms == 2000
    # And the mean hides it: 209 ms reads as "a bit slow", not as "it hangs".
    assert 150 < row.mean_ms < 300


def test_only_the_recent_sample_is_kept_so_memory_does_not_grow():
    """The point of a bounded sample: this page must not itself leak.

    Totals are kept exactly; individual timings are kept only for the recent
    window, because an application left open for a month would otherwise
    hold every timing it ever took.
    """
    stats = _fresh()
    for _ in range(telemetry.SAMPLE * 3):
        stats.record("/x", 1.0, status=200)

    row = next(r for r in stats.snapshot()["routes"] if r.name == "/x")
    assert row.count == telemetry.SAMPLE * 3  # the total is exact
    assert len(stats.routes["/x"].recent) <= telemetry.SAMPLE


def test_the_slowest_list_is_capped_too():
    stats = _fresh()
    for n in range(telemetry.SLOWEST * 5):
        stats.record("/x", float(n), status=200)

    assert len(stats.snapshot()["slowest"]) <= telemetry.SLOWEST


def test_the_slowest_list_holds_the_slowest_ones():
    """Not merely the most recent ones.

    Kept by recency, the list empties itself of the interesting entries
    every time somebody clicks around the quick pages.
    """
    stats = _fresh()
    stats.record("/slow", 900.0, status=200, path="/slow?x=1")
    for _ in range(telemetry.SLOWEST * 2):
        stats.record("/fast", 1.0, status=200)

    slowest = stats.snapshot()["slowest"]
    assert slowest[0]["ms"] == 900.0
    assert slowest[0]["path"] == "/slow?x=1"


def test_reset_clears_the_figures_but_keeps_counting(client):
    """After a change, the old numbers would drag the new average."""
    telemetry.stats.reset()
    client.get("/invoices")
    assert telemetry.stats.snapshot()["requests"] >= 1

    client.post("/settings/performance/reset", follow_redirects=False)
    after = telemetry.stats.snapshot()
    # The reset request itself is the only thing counted since.
    assert after["requests"] <= 1
    assert after["routes"] == [] or after["requests"] <= 1

    client.get("/invoices")
    assert telemetry.stats.snapshot()["requests"] >= 1


def test_memory_reading_is_a_plausible_number():
    """Reads /proc on Linux and the Windows API otherwise; both can fail.

    A wrong reading here is worse than none, because the whole point of the
    memory section is spotting a trend -- so a zero or a nonsense figure
    would read as "no leak" just as convincingly as the truth.
    """
    mb = telemetry.memory_mb()
    assert mb is None or 1 < mb < 100_000


# --- the shape drawn from the readings --------------------------------------


def test_the_memory_shape_is_scaled_from_zero():
    """Scaled from the lowest reading instead, a 2 MB wobble looks a cliff.

    That is how a chart lies without a single wrong number in it, and this
    one is read specifically to judge whether a line is climbing.
    """
    bars = charts.sparkline([(0.0, 100.0), (1.0, 102.0)])
    heights = [float(part.split("--h: ")[1].split("%")[0])
               for part in bars.split("spark-bar")[1:]]

    assert heights[0] > 90  # not a flattened near-zero bar
    assert abs(heights[0] - heights[1]) < 10  # a small change looks small


def test_the_memory_shape_is_empty_when_there_is_nothing_to_draw():
    assert charts.sparkline([]) == ""


# --- the page ---------------------------------------------------------------


def test_the_page_opens_and_names_the_pages_it_measured(client):
    telemetry.stats.reset()
    client.get("/invoices")
    client.get("/customers")

    page = client.get("/settings/performance")
    assert page.status_code == 200
    assert "/invoices" in page.text
    assert "/customers" in page.text


def test_the_page_opens_in_arabic(client):
    """Every page has to, and this one has the most invented vocabulary."""
    client.get("/invoices")
    client.get("/lang/ar")
    page = client.get("/settings/performance")

    assert page.status_code == 200
    assert "الأداء" in page.text
    assert 'dir="rtl"' in page.text


def test_the_page_opens_before_anything_has_been_measured(client):
    """The first thing a new install does is open Settings."""
    telemetry.stats.reset()

    page = client.get("/settings/performance")
    assert page.status_code == 200


def test_settings_links_to_the_page(client):
    """Unreachable, it may as well not exist -- nobody types a URL."""
    assert "/settings/performance" in client.get("/settings").text


# --- not claiming more than the sample supports ------------------------------


def test_one_visit_gives_no_typical_and_no_slow_end():
    """Otherwise the same number is printed three times across the row.

    With a single timing the median, the 95th percentile and the worst are
    all that one reading, and a row showing "189 / 189 / 189" reads as
    three measurements agreeing rather than as one measurement repeated.
    """
    stats = _fresh()
    stats.record("/x", 189.0, status=200)

    row = next(r for r in stats.snapshot()["routes"] if r.name == "/x")
    assert row.median_ms is None
    assert row.p95_ms is None
    assert row.max_ms == 189.0  # what we do know is still shown


def test_a_typical_appears_once_there_is_a_middle_to_point_at():
    stats = _fresh()
    for ms in (10.0, 20.0, 30.0):
        stats.record("/x", ms, status=200)

    row = next(r for r in stats.snapshot()["routes"] if r.name == "/x")
    assert row.median_ms == 20.0


def test_a_slow_end_waits_for_enough_visits_to_have_one():
    """The slowest one in twenty needs twenty before it is an observation
    rather than an extrapolation."""
    stats = _fresh()
    for _ in range(telemetry.MIN_FOR_P95 - 1):
        stats.record("/x", 10.0, status=200)
    row = next(r for r in stats.snapshot()["routes"] if r.name == "/x")
    assert row.p95_ms is None

    stats.record("/x", 10.0, status=200)
    row = next(r for r in stats.snapshot()["routes"] if r.name == "/x")
    assert row.p95_ms is not None


def test_the_page_shows_a_dash_rather_than_a_made_up_figure(client):
    telemetry.stats.reset()
    client.get("/invoices")  # exactly one visit

    page = client.get("/settings/performance")
    assert page.status_code == 200
    assert "&mdash;" in page.text or "—" in page.text


def test_uptime_is_said_in_words_in_both_languages(client):
    from app.main import _uptime_words

    assert _uptime_words(10) == "just started"  # not "0 min"
    assert "5" in _uptime_words(300)
    assert _uptime_words(300, "ar") != _uptime_words(300, "en")


def test_a_size_keeps_its_number_and_unit_together_in_arabic(client):
    """Left to the bidirectional algorithm, "0.6 MB" displays as "MB 0.6".

    The number and the unit resolve as separate runs in a right-to-left
    paragraph and get laid out right-to-left, so the reader sees the unit
    first. Isolating the pair is what keeps it readable, and this applies
    to Settings as much as to this page.
    """
    from app.main import _megabytes

    rendered = _megabytes(612_345)
    assert "0.6 MB" in rendered
    assert 'dir="ltr"' in rendered

    client.get("/lang/ar")
    for page in ("/settings", "/settings/performance"):
        assert 'dir="ltr"' in client.get(page).text
