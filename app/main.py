"""The web application: URLs, and what happens when each one is visited.

Reading guide, if you are new to web applications:

* Each ``@app.get(...)`` or ``@app.post(...)`` below attaches a Python function
  to a URL. ``GET`` is a page being viewed, ``POST`` is a form being submitted.
* A ``GET`` handler gathers data and renders a template from
  ``app/templates/``. A ``POST`` handler validates the form, writes to the
  database, then redirects to a ``GET`` -- that redirect is what stops a
  browser refresh from saving the same invoice twice.
* The database is reached only through :mod:`app.repository`; the maths only
  through :mod:`app.invoicing`. Nothing in this file does either itself.

There is no login: this is built to run on one machine in the office, as a
single-user system. Everything else -- numbering, tax, language -- is driven by
the Settings page.
"""

from __future__ import annotations

import os
import threading
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date, timedelta
from pathlib import Path
from sqlite3 import Connection, IntegrityError
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urlencode

from fastapi import Depends, FastAPI, File, Form, Query, Request, UploadFile
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import backups, charts, exporting, forms, importing, messaging, register_import
from . import repository as repo
from .db import backup_archive, connect, db_path, migrate, session
from .forms import FormError
from .i18n import LANGUAGES, direction, localised, normalise, t
from .invoicing import balance_due, compute_totals, line_total, payment_state
from .money import format_money, format_qty, format_rate, from_milli, from_minor
from .pdf import PDF_AVAILABLE, html_to_pdf

BASE_DIR = Path(__file__).parent

#: Cookie the chosen interface language is remembered in.
LANG_COOKIE = "carservice_lang"
COOKIE_MAX_AGE = 60 * 60 * 24 * 365  # one year


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Bring the database schema up to date before serving the first request."""
    conn = connect()
    try:
        applied = migrate(conn, verbose=True)
        if applied:
            print(f"Database upgraded: {', '.join(applied)}")
        print(f"Database ready at {db_path().resolve()}")
    finally:
        conn.close()

    # Takes today's backup if the day has none, then checks hourly. On a
    # background thread: a backup of a large register takes a second or two,
    # and whoever started the application is usually at the counter with a
    # customer waiting.
    stop = threading.Event()
    watcher = backups.start(stop)
    if watcher:
        print(f"Daily backups in {backups.backups_dir().resolve()}")

    yield

    stop.set()


app = FastAPI(
    title="Car Service Invoicing",
    description="Lightweight on-premise invoicing for a car service centre.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")


def static_url(path: str) -> str:
    """A stylesheet or script URL that changes whenever the file does.

    Browsers cache by URL. With a fixed ``/static/css/app.css`` they keep an
    old copy for as long as they feel like it, so an update arrives as a
    half-new interface: new buttons from the templates, old styling for them.
    That happened, and from the outside it looks exactly like the update
    having failed -- the worst sort of bug, because it makes working code
    look broken and sends everyone hunting in the wrong place.

    Stamping the file's modification time into the URL makes the address of a
    changed file a different address, which no cache can confuse with the old
    one. A stat call per tag is nothing next to the page it is on.

    A missing file falls back to the plain path rather than raising: a broken
    stylesheet link is a bad page, but a stack trace is no page at all.
    """
    target = BASE_DIR / "static" / path.lstrip("/")
    try:
        return f"/static/{path}?v={int(target.stat().st_mtime)}"
    except OSError:
        return f"/static/{path}"


templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals.update(
    static=static_url,
    meter_list=charts.meter_list,
    donut=charts.donut,
    trend_chart=charts.trend,
    LANGUAGES=LANGUAGES,
    PDF_AVAILABLE=PDF_AVAILABLE,
    fmt_qty=format_qty,
    fmt_rate=format_rate,
    # "Cash / نقداً" -- for the printed invoice, which labels everything in
    # both languages regardless of the interface language.
    t2=lambda key: f"{t(key, 'en')} / {t(key, 'ar')}",
    # "2.4 MB" rather than "2516582 bytes".
    filesize=lambda n: (
        f"{n} B" if n < 1024
        else f"{n / 1024:.0f} KB" if n < 1024 * 1024
        else f"{n / 1024 / 1024:.1f} MB"
    ),
    from_minor=from_minor,
    from_milli=from_milli,
    payment_state=payment_state,
    balance_due=balance_due,
    today=lambda: date.today().isoformat(),
    page_url=lambda request, n: page_url(request, n),
)


def page_url(request: Request, number: int) -> str:
    """This page's address with ``page`` set to *number*.

    Built from the request's own query string so that every filter and the
    sort order survive the jump. Spelling out the parameters instead would
    mean each list's pager knowing that list's filters, and a pager that
    forgets one quietly sends people to page 2 of an unfiltered list.
    """
    params = [(k, v) for k, v in request.query_params.multi_items() if k != "page"]
    params.append(("page", str(number)))
    return f"{request.url.path}?{urlencode(params)}"


# --------------------------------------------------------------------------
# Per-request plumbing
# --------------------------------------------------------------------------

def get_conn() -> Iterator[Connection]:
    """Open a database connection for the duration of one request."""
    with session() as conn:
        yield conn


def current_lang(request: Request, settings: Any) -> str:
    """The language to render in: the cookie, else the configured default."""
    cookie = request.cookies.get(LANG_COOKIE)
    if cookie:
        return normalise(cookie)
    return normalise(settings["default_language"])


def ctx(
    request: Request, conn: Connection, **extra: Any
) -> dict[str, Any]:
    """Build the variables every template needs, plus whatever the page adds."""
    settings = repo.get_settings(conn)
    lang = current_lang(request, settings)
    currency = settings["currency_code"]

    logo = repo.logo_state(conn)

    # Every dropdown's choices, in one query. Templates reach them as
    # `options.units`, and `opt_label('payment_methods', 'cash')` turns a
    # stored value back into words for display.
    options, option_labels = repo.all_options(conn)

    def opt_label(list_name: str, value: str) -> str:
        """The words for a stored value, in the current language.

        Falls back to the value itself. A payment recorded as "cheque"
        before anyone edited the list, or a source typed in by hand, still
        has to show as something -- an empty cell would read as missing
        data rather than as an unlisted answer.
        """
        if not value:
            return ""
        row = option_labels.get((list_name, value))
        if row is None:
            return value
        return localised(row, "label_en", lang) or value

    def opt_label2(list_name: str, value: str) -> str:
        """Both languages, for the printed documents.

        The customer's copy labels everything in English and Arabic
        regardless of the interface language, so a payment method has to
        print as "Cash / نقداً". A value added by hand usually has only an
        English label, in which case it prints once rather than twice with
        the same words either side of a slash.
        """
        if not value:
            return ""
        row = option_labels.get((list_name, value))
        if row is None:
            return value
        english = row["label_en"] or value
        arabic = row["label_ar"]
        return f"{english} / {arabic}" if arabic else english

    def counts_for(section: str) -> dict[str, Any]:
        """The count line for one section, asked for only where it is shown.

        Deliberately a function rather than a value: computing every
        section's count on every render would put eight queries behind every
        page in the application, including the printed documents, to serve
        one line that most of them never show.
        """
        if section in repo.COUNTED_STATUSES:
            return repo.status_counts(conn, section)
        return repo.simple_counts(conn)[section]

    def _chosen_id(value: Any) -> int | None:
        """A record id out of whatever a template hands over.

        Templates pass an int on an edit form, ``None`` on a blank one, and
        Jinja's Undefined where the variable is not set on that page.
        ``forms.opt_int`` is for parsing what a person typed into a box and
        calls ``.strip()``, which an int does not have -- using it here turned
        "this invoice has no lines" into a 500 on the page that was supposed
        to say so.
        """
        if value is None or isinstance(value, bool):
            return None
        try:
            return int(value) or None
        except (TypeError, ValueError):
            return None

    def picker_customers(chosen: Any = None) -> list[Any]:
        """The customers to put in a form's dropdown.

        Not all of them. Rendering every customer as an ``<option>`` was 4,000
        of them on the real register and most of a megabyte on every form, for
        a list nobody could find anybody in anyway. What the page needs is the
        customer already chosen -- an edit form that loses its customer is a
        far worse bug than a short list -- plus enough recent ones to cover
        the ordinary case of adding somebody and immediately invoicing them.
        Everyone else arrives through the search box, from /api/customers.

        A function rather than a value, like the counts above: the forms that
        need it ask for it, and the forty-odd pages that do not pay nothing.
        """
        return repo.picker_customers(conn, _chosen_id(chosen))

    def cars_of(customer_id: Any = None) -> list[Any]:
        """One customer's cars, for the vehicle dropdown beside the picker.

        The forms used to carry every vehicle in the database and hide the
        ones that did not belong. Six thousand cars, to show the two that one
        customer owns.
        """
        customer_id = _chosen_id(customer_id)
        if not customer_id:
            return []
        return repo.list_vehicles(conn, customer_id=customer_id)

    base: dict[str, Any] = {
        "request": request,
        "settings": settings,
        "has_logo": bool(logo["logo_mime"]),
        # The margin watermark paints the logo's shape in a flat colour, so
        # it needs a logo whose background is transparent. One with a solid
        # background cannot be masked -- the mask is the whole rectangle,
        # which is how the dark theme ended up with a grey box in each
        # margin. Settings explains it rather than leaving it a mystery.
        "watermark_ok": bool(logo["logo_mime"]) and bool(logo["logo_has_alpha"]),
        # The timestamp makes the URL change when the logo does, so a
        # replaced logo is not served from the browser's cache.
        "logo_url": f"/logo?v={logo['updated_at'].replace(' ', '')}",
        "lang": lang,
        "dir": direction(lang),
        "rtl": lang == "ar",
        "currency": currency,
        # Shorthands used throughout the templates:
        #   t("nav.invoices")  -> translated text
        #   m(12345)           -> "123.45 SAR"
        #   loc(row, "name_en")-> Arabic or English variant of a column
        "t": lambda key: t(key, lang),
        "m": lambda minor: format_money(minor or 0, currency),
        "m_plain": lambda minor: format_money(minor or 0),
        "loc": lambda row, base_col: localised(row, base_col, lang),
        "options": options,
        "opt_label": opt_label,
        "opt_label2": opt_label2,
        "counts_for": counts_for,
        "picker_customers": picker_customers,
        "cars_of": cars_of,
        "ALERT_LEVELS": repo.ALERT_LEVELS,
        "flash": request.query_params.get("msg", ""),
        "flash_error": request.query_params.get("err", ""),
    }
    base.update(extra)
    return base


def render(
    request: Request, conn: Connection, template: str, **extra: Any
) -> HTMLResponse:
    return templates.TemplateResponse(request, template, ctx(request, conn, **extra))


def go(url: str, *, msg: str = "", err: str = "") -> RedirectResponse:
    """Redirect after a successful form submission.

    Status 303 tells the browser to follow up with a ``GET``, so refreshing
    the resulting page cannot re-submit the form.
    """
    params = []
    if msg:
        params.append(f"msg={msg}")
    if err:
        params.append(f"err={err}")
    if params:
        url += ("&" if "?" in url else "?") + "&".join(params)
    return RedirectResponse(url, status_code=303)


@app.exception_handler(repo.NotFound)
async def record_not_found(request: Request, exc: Any) -> Response:
    """A record that does not exist is a 404, not a crash.

    Without this, asking for an invoice, customer or attachment that has
    been deleted -- or following a stale link, or mistyping a number in the
    address bar -- produced a 500 and a stack trace in the log. Every lookup
    in the repository raises this one exception, so handling it here covers
    all of them rather than needing a try/except on every route.
    """
    with session() as conn:
        return templates.TemplateResponse(
            request,
            "error.html",
            ctx(request, conn, code=404, detail="msg.not_found"),
            status_code=404,
        )


@app.exception_handler(404)
async def not_found(request: Request, exc: Any) -> Response:
    with session() as conn:
        return templates.TemplateResponse(
            request, "error.html", ctx(request, conn, code=404, detail="msg.not_found"),
            status_code=404,
        )


# --------------------------------------------------------------------------
# Language
# --------------------------------------------------------------------------

@app.get("/lang/{code}")
def set_language(code: str, request: Request) -> RedirectResponse:
    """Switch language and return to the page the user was on."""
    target = request.headers.get("referer") or "/"
    response = RedirectResponse(target, status_code=303)
    response.set_cookie(
        LANG_COOKIE, normalise(code), max_age=COOKIE_MAX_AGE, samesite="lax"
    )
    return response


# --------------------------------------------------------------------------
# Dashboard
# --------------------------------------------------------------------------

@app.get("/", response_class=HTMLResponse)
def dashboard(
    request: Request,
    make: str = "",
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request,
        conn,
        "dashboard.html",
        stats=repo.dashboard_stats(conn),
        recent=repo.list_invoices(conn, limit=8),
        unpaid=repo.unpaid_invoices(conn, limit=6),
        revenue=repo.monthly_revenue(conn, months=6),
        in_workshop=repo.cars_in_workshop(conn, limit=8),
        waiting_estimates=repo.open_estimates(conn, limit=6),
        # The deeper figures. Gathered on every load rather than behind their
        # own request: these are a few thousand rows on one PC, and a second
        # round trip to open a panel would cost more than the queries do.
        analytics=_analytics(conn, current_lang(request, repo.get_settings(conn)), make=make),
        # The same counts the list pages show, from the same function. Two
        # counts of the same thing that disagree are worse than no count at
        # all: one of them would be quietly wrong and nobody could tell
        # which.
        counts=repo.all_counts(conn),
        alerts=repo.alert_counts(conn),
        # The flagged customers themselves, not just the number. A count
        # that cannot be opened is a number somebody has to go and look up,
        # and these are the ones worth looking at.
        flagged=repo.list_flagged_customers(conn),
    )


def _sort_state(listing: str, sort: str, direction: str) -> dict[str, Any]:
    """What the template needs to draw the column headings.

    The values come back from the repository rather than being echoed from
    the query string, so the arrow on a heading always shows what the list
    is really sorted by -- not what somebody asked for in a URL and did not
    get.
    """
    _, sort, direction = repo.order_clause(listing, sort, direction)
    # Deliberately not "dir": the templates already have a `dir` -- the
    # page's text direction, rtl or ltr -- and shadowing it rendered every
    # Arabic page as <html dir="asc">. The query parameter stays short;
    # only the template name is spelled out.
    return {"sort": sort, "sort_dir": direction}


def _analytics(conn: Connection, lang: str, make: str = "") -> dict[str, Any]:
    """Everything the advanced panel draws, worked out from the records.

    The rows arrive as plain ``(label, value)`` pairs. Shaping them here
    rather than in the template keeps the charts testable without rendering a
    page, and keeps the template to laying things out.
    """
    money = repo.monthly_money(conn, months=12)
    _, option_labels = repo.all_options(conn)
    # One query, two uses: the chart shows the common makes, the filter
    # offers all of them. Asking twice with different limits read every
    # vehicle row twice -- 16ms of the dashboard for one list of makes.
    makes = repo.cars_by_make(conn, limit=40)
    labels = {
        key: (row["label_ar"] or row["label_en"]) if lang == "ar" else (row["label_en"] or row["value"])
        for key, row in option_labels.items()
    }

    def pairs(rows, label_key, value_key):
        return [(row[label_key], row[value_key]) for row in rows]

    return {
        "activity": repo.customer_activity(conn),
        "by_make": pairs(makes[:8], "label", "cars"),
        "by_model": pairs(repo.cars_by_model(conn, make=make), "label", "cars"),
        # Labelled from the configured list rather than a translation key.
        # The types became editable in Settings, so a type added there had
        # no key and would have shown as "cust.cat_insurance" on the chart.
        "by_category": [
            (labels.get(("customer_types", row["label"]), row["label"]), row["customers"])
            for row in repo.customer_categories(conn)
        ],
        "without_model": repo.cars_without_model(conn, make=make),
        "by_colour": pairs(repo.cars_by_colour(conn, make=make), "label", "cars"),
        "by_age": [
            (f"{row['band']}\u2013{row['band'] + 4}", row["cars"])
            for row in repo.cars_by_decade(conn, make=make)
        ],
        "make": make,
        "makes": [row["label"] for row in makes],
        "odd_colours": repo.colour_values_that_are_not_colours(conn, make=make),
        # The donut's centre: how many cars the slices add up to, which is
        # not the whole fleet -- a car with no colour recorded is in neither.
        "coloured_cars": repo.cars_with_a_colour(conn, make=make),
        "faults": [
            (
                f"{row['make']} — "
                f"{row['title_ar'] if lang == 'ar' and row['title_ar'] else row['title_en']}",
                row["cases"],
            )
            for row in repo.issue_case_counts(conn)
        ],
        "top_customers": repo.top_customers(conn),
        "owed_trend": [(row["ym"], round(row["outstanding_minor"] / 100)) for row in money],
        "invoiced_trend": [(row["ym"], round(row["invoiced_minor"] / 100)) for row in money],
    }


# --------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------

@app.get("/customers", response_class=HTMLResponse)
def customers_list(
    request: Request,
    q: str = "",
    inactive: str = "",
    sort: str = "",
    dir: str = "asc",
    page: int = 1,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    customers = repo.page_customers(
        conn, search=q, include_inactive=forms.truthy(inactive),
        sort=sort, direction=dir, page=page,
    )
    return render(
        request,
        conn,
        "customers_list.html",
        customers=customers,
        page=customers,
        **_sort_state("customers", sort, dir),
        q=q,
        inactive=inactive,
    )


@app.get("/customers/new", response_class=HTMLResponse)
def customer_new(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    return render(request, conn, "customer_form.html", customer=None, error="")


def _customer_type_values(conn: Connection) -> tuple[str, ...]:
    """The customer types currently offered, for validating a posted one.

    Read from the configured list rather than written out here, so a type
    added in Settings is accepted by the form that offers it.
    """
    return tuple(row["value"] for row in repo.list_options(conn, "customer_types"))


@app.post("/customers/new")
def customer_create(
    request: Request,
    name: str = Form(""),
    name_ar: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    vat_number: str = Form(""),
    notes: str = Form(""),
    category: str = Form("regular"),
    alert_level: str = Form(""),
    alert_note: str = Form(""),
    conn: Connection = Depends(get_conn),
):
    try:
        data = {
            "name": forms.required_text(name, field="Name"),
            "name_ar": forms.text(name_ar),
            "phone": forms.text(phone),
            "email": forms.text(email),
            "address": forms.text(address),
            "vat_number": forms.text(vat_number),
            "notes": forms.text(notes),
            # The form has always offered this and the handler has always
            # thrown it away, so a customer added as VIP came back as
            # regular. Checked against the configured list rather than a
            # tuple written here, or a type added in Settings would be
            # silently refused by the one screen that offers it.
            "category": forms.one_of(
                category, _customer_type_values(conn), default="regular"
            ),
        }
    except FormError as exc:
        return render(request, conn, "customer_form.html", customer=None, error=str(exc))

    customer_id = repo.create_customer(conn, data)
    if forms.text(alert_level):
        repo.set_customer_alert(
            conn, customer_id, level=forms.text(alert_level), note=forms.text(alert_note)
        )
    return go(f"/customers/{customer_id}", msg="msg.created")


# --------------------------------------------------------------------------
# Bringing an existing customer list in from a spreadsheet
# --------------------------------------------------------------------------
# These are declared before /customers/{customer_id}: routes are matched in
# the order they appear, and "import" is not a number, so the other way round
# every one of these would be rejected before it was reached.

# --------------------------------------------------------------------------
# Bringing a car register in from a spreadsheet
# --------------------------------------------------------------------------
# Different from the customer import above: there, one row is one customer.
# A register has one row per *car*, with the owner repeated down the sheet --
# and the red somebody marked a row with is a warning, not formatting, so it
# has to be read along with the values.

@app.get("/vehicles/tidy", response_class=HTMLResponse)
def vehicle_tidy(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    """What a tidy-up would change, before anything is changed.

    Above /vehicles/{vehicle_id}: "tidy" is not a number.
    """
    fixes = repo.colour_model_mixups(conn)
    return render(
        request, conn, "vehicle_tidy.html",
        fixes=fixes,
        swaps=sum(1 for f in fixes if f["action"] == "swap"),
        moves=sum(1 for f in fixes if f["action"] != "swap"),
    )


@app.post("/vehicles/tidy")
def vehicle_tidy_apply(conn: Connection = Depends(get_conn)):
    changed = repo.apply_colour_model_fixes(conn)
    return go("/vehicles", msg="msg.saved" if changed else "msg.nothing_to_do")


@app.get("/vehicles/import/template")
def register_template() -> Response:
    """An empty register with the right headings and three example rows.

    Declared above /vehicles/import/{batch_id} -- "template" is not a
    number, and routes are matched in the order they appear.
    """
    return Response(
        content=register_import.template_xlsx(),
        media_type=(
            "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet"
        ),
        headers={
            "Content-Disposition": 'attachment; filename="car-register-template.xlsx"'
        },
    )


@app.get("/vehicles/import", response_class=HTMLResponse)
def register_start(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    return render(request, conn, "register_import.html",
                  batch=None, prepared=None, error="")


@app.post("/vehicles/import")
async def register_upload(
    request: Request,
    spreadsheet: UploadFile = File(...),
    conn: Connection = Depends(get_conn),
):
    """Read the file and stage what it would do. Nothing is written yet.

    Loading a few thousand records is not something anybody wants to undo by
    hand, so the preview comes first and is built by the same pass that the
    import will use. A preview assembled separately is a preview of
    something else.
    """
    data = await spreadsheet.read()
    try:
        rows, marked = register_import.read_xlsx(data)
        prepared = register_import.prepare(rows, marked)
    except register_import.RegisterImportError as exc:
        return render(request, conn, "register_import.html",
                      batch=None, prepared=None, error=str(exc))

    payload = {
        "customers": [vars(c) for c in prepared["customers"]],
        "vehicles": [vars(v) for v in prepared["vehicles"]],
        "summary": prepared["summary"],
        "ignored_columns": prepared["ignored_columns"],
    }
    batch_id = repo.create_import_batch(
        conn, spreadsheet.filename or "register", [payload]
    )
    return go(f"/vehicles/import/{batch_id}")


@app.get("/vehicles/import/{batch_id}", response_class=HTMLResponse)
def register_preview(
    batch_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    batch, rows = repo.get_import_batch(conn, batch_id)
    return render(request, conn, "register_import.html",
                  batch=batch, prepared=rows[0] if rows else None, error="")


@app.post("/vehicles/import/{batch_id}/confirm")
def register_confirm(batch_id: int, conn: Connection = Depends(get_conn)):
    batch, rows = repo.get_import_batch(conn, batch_id)
    if batch["status"] != "pending" or not rows:
        return go("/vehicles", err="This import has already been dealt with.")
    payload = rows[0]
    result = repo.commit_register_import(conn, payload["customers"], payload["vehicles"])
    repo.mark_import_batch_done(
        conn, batch_id,
        imported=result['vehicles'], skipped=result['skipped'],
    )
    return go(
        "/vehicles",
        msg="msg.imported" if result["vehicles"] else "msg.nothing_imported",
    )


@app.post("/vehicles/import/{batch_id}/cancel")
def register_cancel(batch_id: int, conn: Connection = Depends(get_conn)):
    repo.cancel_import_batch(conn, batch_id)
    return go("/vehicles")


@app.get("/customers/flagged", response_class=HTMLResponse)
def customers_flagged(
    request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    """Everyone carrying a warning, worst first.

    Declared above /customers/{customer_id} with the import routes, for the
    same reason: "flagged" is not a number.
    """
    return render(
        request,
        conn,
        "customers_flagged.html",
        flagged=repo.list_flagged_customers(conn),
        alerts=repo.alert_counts(conn),
    )


@app.get("/customers/import", response_class=HTMLResponse)
def import_start(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    return render(request, conn, "customer_import.html", batch=None, rows=[],
                  summary=None, error="")


@app.get("/customers/import/template")
def import_template() -> Response:
    """A CSV with the expected headings and two example rows."""
    return Response(
        content=importing.template_csv(),
        media_type="text/csv",
        headers={
            "Content-Disposition": 'attachment; filename="customer-import-template.csv"'
        },
    )


@app.post("/customers/import")
async def import_upload(
    request: Request,
    spreadsheet: UploadFile = File(...),
    conn: Connection = Depends(get_conn),
):
    """Parse an upload into a batch and show what it would do.

    Nothing is written to the customers table here. The batch is a staging
    area so the preview can be looked at first: importing several hundred
    records is not something anyone wants to undo by hand.
    """
    data = await spreadsheet.read()
    try:
        rows = importing.read_table(data, spreadsheet.filename or "")
        names, phones = repo.existing_customer_keys(conn)
        prepared, summary = importing.prepare(
            rows, existing_names=names, existing_phones=phones
        )
    except importing.ImportError_ as exc:
        return render(request, conn, "customer_import.html", batch=None, rows=[],
                      summary=None, error=str(exc))

    batch_id = repo.create_import_batch(conn, spreadsheet.filename or "upload", prepared)
    return go(f"/customers/import/{batch_id}")


@app.get("/customers/import/{batch_id}", response_class=HTMLResponse)
def import_preview(
    batch_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    batch, rows = repo.get_import_batch(conn, batch_id)
    ready = sum(1 for r in rows if not r.get("skip"))
    summary = {
        "total": len(rows),
        "ready": ready,
        "skipped": len(rows) - ready,
        "unmapped": [],
        "fields": sorted({k for r in rows for k in r if k not in {"line", "skip", "note"}}),
    }
    return render(request, conn, "customer_import.html", batch=batch, rows=rows,
                  summary=summary, error="")


@app.post("/customers/import/{batch_id}/confirm")
def import_confirm(batch_id: int, conn: Connection = Depends(get_conn)):
    try:
        result = repo.commit_import_batch(conn, batch_id)
    except repo.InUse as exc:
        return go("/customers", err=str(exc))
    return go(
        "/customers",
        msg="msg.imported" if result["imported"] else "msg.nothing_imported",
    )


@app.post("/customers/import/{batch_id}/cancel")
def import_cancel(batch_id: int, conn: Connection = Depends(get_conn)):
    repo.cancel_import_batch(conn, batch_id)
    return go("/customers")


# --------------------------------------------------------------------------
# Customer attachments
# --------------------------------------------------------------------------
# Scans of invoices written before this system existed, so a customer's whole
# history is in one place.

@app.post("/customers/{customer_id}/attachments")
async def attachment_upload(
    customer_id: int,
    document: UploadFile = File(...),
    kind: str = Form("invoice"),
    description: str = Form(""),
    document_date: str = Form(""),
    conn: Connection = Depends(get_conn),
):
    data = await document.read(repo.MAX_ATTACHMENT_BYTES + 1)
    try:
        repo.add_attachment(
            conn,
            customer_id,
            data,
            original_name=document.filename or "",
            kind=forms.one_of(
                kind, ("invoice", "document", "photo", "other"), default="invoice"
            ),
            description=forms.text(description),
            document_date=forms.iso_date(document_date),
        )
    except (ValueError, FormError) as exc:
        return go(f"/customers/{customer_id}", err=str(exc))
    return go(f"/customers/{customer_id}", msg="msg.attached")



# --------------------------------------------------------------------------
# Photographs of catalogue parts
# --------------------------------------------------------------------------


@app.post("/catalog/{item_id}/images")
async def item_image_upload(
    item_id: int,
    image: UploadFile = File(...),
    caption: str = Form(""),
    conn: Connection = Depends(get_conn),
):
    data = await image.read(repo.MAX_ITEM_IMAGE_BYTES + 1)
    try:
        repo.add_item_image(
            conn, item_id, data,
            original_name=image.filename or "",
            caption=forms.text(caption),
        )
    except (ValueError, FormError) as exc:
        return go(f"/catalog/{item_id}/edit", err=str(exc))
    return go(f"/catalog/{item_id}/edit", msg="msg.attached")


@app.get("/item-images/{image_id}")
def item_image_view(image_id: int, conn: Connection = Depends(get_conn)):
    """Serve a part photograph.

    Same headers as a customer attachment, for the same reason: this is a
    file somebody uploaded, served back from the application's own address.
    `nosniff` stops a browser deciding it is really HTML, and the content
    policy stops anything inside it reaching out.
    """
    row, path = repo.item_image_file(conn, image_id)
    if not path.is_file():
        return Response(status_code=404)
    return FileResponse(
        path,
        media_type=row["mime"],
        headers={
            "Content-Disposition": f'inline; filename="{_ascii_filename(row["original_name"])}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; img-src 'self'",
        },
    )


@app.post("/item-images/{image_id}/delete")
def item_image_delete(image_id: int, conn: Connection = Depends(get_conn)):
    item_id = repo.get_item_image(conn, image_id)["catalog_item_id"]
    repo.delete_item_image(conn, image_id)
    return go(f"/catalog/{item_id}/edit", msg="msg.deleted")


@app.get("/attachments/{attachment_id}")
def attachment_view(attachment_id: int, conn: Connection = Depends(get_conn)):
    """Serve an attachment for viewing in the browser.

    The headers matter here. These are files someone uploaded, served back
    from the application's own address: `nosniff` stops a browser deciding
    the file is really HTML, and the content policy stops anything embedded
    in a PDF reaching out or running.
    """
    path, row = repo.attachment_file(conn, attachment_id)
    if not path.is_file():
        return Response(status_code=404)
    return FileResponse(
        path,
        media_type=row["mime"],
        headers={
            "Content-Disposition": f'inline; filename="{_ascii_filename(row["original_name"])}"',
            "X-Content-Type-Options": "nosniff",
            "Content-Security-Policy": "default-src 'none'; img-src 'self'; style-src 'unsafe-inline'",
        },
    )


@app.get("/attachments/{attachment_id}/download")
def attachment_download(attachment_id: int, conn: Connection = Depends(get_conn)):
    path, row = repo.attachment_file(conn, attachment_id)
    if not path.is_file():
        return Response(status_code=404)
    return FileResponse(
        path,
        media_type="application/octet-stream",
        filename=_ascii_filename(row["original_name"]),
        headers={"X-Content-Type-Options": "nosniff"},
    )


@app.post("/attachments/{attachment_id}/delete")
def attachment_delete(attachment_id: int, conn: Connection = Depends(get_conn)):
    customer_id = repo.delete_attachment(conn, attachment_id)
    return go(f"/customers/{customer_id}", msg="msg.deleted")


def _ascii_filename(name: str) -> str:
    """A filename safe to put in a header.

    A Content-Disposition header is a header: a newline or a quote in the
    name an upload arrived with could end it early and start another one.
    """
    cleaned = "".join(ch for ch in name if ch.isprintable() and ch not in '"\\\r\n')
    return cleaned.encode("ascii", "replace").decode("ascii")[:120] or "attachment"


@app.get("/customers/{customer_id}", response_class=HTMLResponse)
def customer_detail(
    customer_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request,
        conn,
        "customer_detail.html",
        customer=repo.get_customer(conn, customer_id),
        vehicles=repo.list_vehicles(conn, customer_id=customer_id),
        invoices=repo.list_invoices(conn, customer_id=customer_id, limit=50),
        estimates=repo.list_estimates(conn, customer_id=customer_id, limit=20),
        attachments=repo.list_attachments(conn, customer_id),
    )


@app.get("/customers/{customer_id}/edit", response_class=HTMLResponse)
def customer_edit(
    customer_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request,
        conn,
        "customer_form.html",
        customer=repo.get_customer(conn, customer_id),
        error="",
    )


@app.post("/customers/{customer_id}/edit")
def customer_update(
    customer_id: int,
    request: Request,
    name: str = Form(""),
    name_ar: str = Form(""),
    phone: str = Form(""),
    email: str = Form(""),
    address: str = Form(""),
    vat_number: str = Form(""),
    notes: str = Form(""),
    category: str = Form("regular"),
    alert_level: str = Form(""),
    alert_note: str = Form(""),
    is_active: str = Form(None),
    conn: Connection = Depends(get_conn),
):
    try:
        data = {
            "name": forms.required_text(name, field="Name"),
            "name_ar": forms.text(name_ar),
            "phone": forms.text(phone),
            "email": forms.text(email),
            "address": forms.text(address),
            "vat_number": forms.text(vat_number),
            "notes": forms.text(notes),
            # Not "active": that is a question about when they last came in,
            # and a stored flag would be wrong the moment nobody updates it.
            "category": forms.one_of(
                category, _customer_type_values(conn), default="regular"
            ),
            "is_active": forms.checkbox(is_active),
        }
    except FormError as exc:
        return render(
            request,
            conn,
            "customer_form.html",
            customer=repo.get_customer(conn, customer_id),
            error=str(exc),
        )

    repo.update_customer(conn, customer_id, data)
    repo.set_customer_alert(
        conn, customer_id,
        level=forms.text(alert_level),
        note=forms.text(alert_note),
    )
    return go(f"/customers/{customer_id}", msg="msg.saved")


@app.post("/customers/{customer_id}/delete")
def customer_delete(customer_id: int, conn: Connection = Depends(get_conn)):
    try:
        repo.delete_customer(conn, customer_id)
    except repo.InUse as exc:
        return go(f"/customers/{customer_id}", err=str(exc))
    return go("/customers", msg="msg.deleted")


# --------------------------------------------------------------------------
# Vehicles
# --------------------------------------------------------------------------

@app.get("/vehicles", response_class=HTMLResponse)
def vehicles_list(
    request: Request,
    q: str = "",
    inactive: str = "",
    sort: str = "",
    dir: str = "asc",
    make: str = "",
    page: int = 1,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    vehicles = repo.page_vehicles(
        conn, search=q, include_inactive=forms.truthy(inactive),
        make=make, sort=sort, direction=dir, page=page,
    )
    return render(
        request,
        conn,
        "vehicles_list.html",
        vehicles=vehicles,
        page=vehicles,
        makes=[r["label"] for r in repo.cars_by_make(conn)],
        make=make,
        **_sort_state("vehicles", sort, dir),
        q=q,
        inactive=inactive,
    )


@app.get("/vehicles/new", response_class=HTMLResponse)
def vehicle_new(
    request: Request, customer_id: int | None = None, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request,
        conn,
        "vehicle_form.html",
        vehicle=None,
        preset_customer_id=customer_id,
        customers=repo.list_customers(conn),
        error="",
    )


def _vehicle_payload(
    customer_id: str,
    plate_no: str,
    make: str,
    model: str,
    model_year: str,
    vin: str,
    colour: str,
    odometer: str,
    notes: str,
    is_active: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "customer_id": forms.opt_int(customer_id),
        "plate_no": forms.required_text(plate_no, field="Plate number"),
        "make": forms.text(make),
        "model": forms.text(model),
        "model_year": forms.opt_int(model_year),
        "vin": forms.text(vin),
        "colour": forms.text(colour),
        "odometer": forms.opt_int(odometer),
        "notes": forms.text(notes),
    }
    if data["customer_id"] is None:
        raise FormError("Choose the customer who owns this vehicle.")
    if is_active is not None:
        data["is_active"] = forms.checkbox(is_active)
    return data


@app.post("/vehicles/new")
def vehicle_create(
    request: Request,
    customer_id: str = Form(""),
    plate_no: str = Form(""),
    make: str = Form(""),
    model: str = Form(""),
    model_year: str = Form(""),
    vin: str = Form(""),
    colour: str = Form(""),
    odometer: str = Form(""),
    notes: str = Form(""),
    conn: Connection = Depends(get_conn),
):
    try:
        data = _vehicle_payload(
            customer_id, plate_no, make, model, model_year, vin, colour, odometer, notes
        )
    except FormError as exc:
        return render(
            request,
            conn,
            "vehicle_form.html",
            vehicle=None,
            preset_customer_id=forms.opt_int(customer_id),
            customers=repo.list_customers(conn),
            error=str(exc),
        )

    vehicle_id = repo.create_vehicle(conn, data)
    return go(f"/vehicles/{vehicle_id}", msg="msg.created")


@app.get("/vehicles/{vehicle_id}", response_class=HTMLResponse)
def vehicle_detail(
    vehicle_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request,
        conn,
        "vehicle_detail.html",
        vehicle=repo.get_vehicle(conn, vehicle_id),
        history=repo.vehicle_history(conn, vehicle_id),
    )


@app.get("/vehicles/{vehicle_id}/edit", response_class=HTMLResponse)
def vehicle_edit(
    vehicle_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request,
        conn,
        "vehicle_form.html",
        vehicle=repo.get_vehicle(conn, vehicle_id),
        preset_customer_id=None,
        customers=repo.list_customers(conn, include_inactive=True),
        error="",
    )


@app.post("/vehicles/{vehicle_id}/edit")
def vehicle_update(
    vehicle_id: int,
    request: Request,
    customer_id: str = Form(""),
    plate_no: str = Form(""),
    make: str = Form(""),
    model: str = Form(""),
    model_year: str = Form(""),
    vin: str = Form(""),
    colour: str = Form(""),
    odometer: str = Form(""),
    notes: str = Form(""),
    is_active: str = Form(None),
    conn: Connection = Depends(get_conn),
):
    try:
        data = _vehicle_payload(
            customer_id, plate_no, make, model, model_year, vin, colour, odometer,
            notes, is_active,
        )
    except FormError as exc:
        return render(
            request,
            conn,
            "vehicle_form.html",
            vehicle=repo.get_vehicle(conn, vehicle_id),
            preset_customer_id=None,
            customers=repo.list_customers(conn, include_inactive=True),
            error=str(exc),
        )

    repo.update_vehicle(conn, vehicle_id, data)
    return go(f"/vehicles/{vehicle_id}", msg="msg.saved")


@app.post("/vehicles/{vehicle_id}/delete")
def vehicle_delete(vehicle_id: int, conn: Connection = Depends(get_conn)):
    vehicle = repo.get_vehicle(conn, vehicle_id)
    try:
        repo.delete_vehicle(conn, vehicle_id)
    except repo.InUse as exc:
        return go(f"/vehicles/{vehicle_id}", err=str(exc))
    return go(f"/customers/{vehicle['customer_id']}", msg="msg.deleted")


# --------------------------------------------------------------------------
# Service and parts catalogue
# --------------------------------------------------------------------------

@app.get("/catalog", response_class=HTMLResponse)
def catalog_list(
    request: Request,
    q: str = "",
    kind: str = "",
    sort: str = "",
    dir: str = "asc",
    inactive: str = "",
    page: int = 1,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    items = repo.page_catalog(
        conn, search=q, kind=kind, include_inactive=forms.truthy(inactive),
        sort=sort, direction=dir, page=page,
    )
    return render(
        request,
        conn,
        "catalog_list.html",
        **_sort_state("catalog", sort, dir),
        items=items,
        page=items,
        q=q,
        kind=kind,
        inactive=inactive,
    )


@app.get("/catalog/new", response_class=HTMLResponse)
def catalog_new(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    return render(request, conn, "catalog_form.html", item=None, error="")


def _catalog_payload(
    code: str,
    name_en: str,
    name_ar: str,
    kind: str,
    unit: str,
    unit_price: str,
    is_active: str | None = None,
    manufacturer: str = "",
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "code": forms.text(code),
        "name_en": forms.required_text(name_en, field="Name"),
        "name_ar": forms.text(name_ar),
        "kind": forms.one_of(kind, ("service", "part"), default="service"),
        "unit": forms.text(unit, default="pcs"),
        "unit_price_minor": forms.money(unit_price, field="Unit price"),
        # Free text, from a suggested list. Not validated against it: the
        # part in the box may be made by somebody the list has never heard of.
        "manufacturer": forms.text(manufacturer),
    }
    if is_active is not None:
        data["is_active"] = forms.checkbox(is_active)
    return data


@app.post("/catalog/new")
def catalog_create(
    request: Request,
    code: str = Form(""),
    name_en: str = Form(""),
    name_ar: str = Form(""),
    kind: str = Form("service"),
    unit: str = Form("pcs"),
    unit_price: str = Form(""),
    manufacturer: str = Form(""),
    conn: Connection = Depends(get_conn),
):
    try:
        data = _catalog_payload(code, name_en, name_ar, kind, unit, unit_price,
                                 manufacturer=manufacturer)
        repo.create_catalog_item(conn, data)
    except FormError as exc:
        return render(request, conn, "catalog_form.html", item=None, error=str(exc))
    except IntegrityError:
        return render(
            request,
            conn,
            "catalog_form.html",
            item=None,
            error=f"The code {code!r} is already used by another item.",
        )
    return go("/catalog", msg="msg.created")


@app.get("/catalog/{item_id}/edit", response_class=HTMLResponse)
def catalog_edit(
    item_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request, conn, "catalog_form.html",
        item=repo.get_catalog_item(conn, item_id),
        images=repo.list_item_images(conn, item_id),
        error="",
    )


@app.post("/catalog/{item_id}/edit")
def catalog_update(
    item_id: int,
    request: Request,
    code: str = Form(""),
    name_en: str = Form(""),
    name_ar: str = Form(""),
    kind: str = Form("service"),
    unit: str = Form("pcs"),
    unit_price: str = Form(""),
    manufacturer: str = Form(""),
    is_active: str = Form(None),
    conn: Connection = Depends(get_conn),
):
    try:
        data = _catalog_payload(code, name_en, name_ar, kind, unit, unit_price,
                                 is_active, manufacturer=manufacturer)
        repo.update_catalog_item(conn, item_id, data)
    except FormError as exc:
        return render(
            request,
            conn,
            "catalog_form.html",
            item=repo.get_catalog_item(conn, item_id),
            error=str(exc),
        )
    except IntegrityError:
        return render(
            request,
            conn,
            "catalog_form.html",
            item=repo.get_catalog_item(conn, item_id),
            error=f"The code {code!r} is already used by another item.",
        )
    return go("/catalog", msg="msg.saved")


@app.post("/catalog/{item_id}/delete")
def catalog_delete(item_id: int, conn: Connection = Depends(get_conn)):
    repo.delete_catalog_item(conn, item_id)
    return go("/catalog", msg="msg.deleted")


# --------------------------------------------------------------------------
# Invoices
# --------------------------------------------------------------------------

@app.get("/invoices", response_class=HTMLResponse)
def invoices_list(
    request: Request,
    q: str = "",
    status: str = "",
    state: str = "",
    date_from: str = "",
    date_to: str = "",
    page: int = 1,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    invoices = repo.page_invoices(
        conn,
        search=q,
        status=status,
        payment_state=state,
        date_from=date_from,
        date_to=date_to,
        page=page,
    )
    return render(
        request,
        conn,
        "invoices_list.html",
        invoices=invoices,
        page=invoices,
        q=q,
        status=status,
        state=state,
        date_from=date_from,
        date_to=date_to,
    )


def _invoice_form_context(
    conn: Connection, *, invoice: Any = None, items: Any = None, error: str = ""
) -> dict[str, Any]:
    settings = repo.get_settings(conn)
    catalog = repo.list_catalog(conn)
    return {
        "invoice": invoice,
        "items": items or [],
        "customers": repo.list_customers(conn),
        "vehicles": repo.list_vehicles(conn),
        "catalog": catalog,
        # Plain dictionaries, embedded in the page as JSON so picking a
        # catalogue item on a line fills it in with no network round-trip.
        "catalog_json": [
            {
                "id": i["id"],
                "name_en": i["name_en"],
                "name_ar": i["name_ar"],
                "kind": i["kind"],
                "unit": i["unit"],
                "price": str(from_minor(i["unit_price_minor"])),
            }
            for i in catalog
        ],
        "default_vat_bp": settings["vat_rate_bp"],
        "default_include_vat": settings["prices_include_vat"],
        "error": error,
    }


@app.get("/invoices/new", response_class=HTMLResponse)
def invoice_new(
    request: Request,
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request,
        conn,
        "invoice_form.html",
        preset_customer_id=customer_id,
        preset_vehicle_id=vehicle_id,
        **_invoice_form_context(conn),
    )


def _invoice_payload(
    *,
    settings: Any,
    customer_id: str,
    vehicle_id: str,
    issue_date: str,
    due_date: str,
    odometer: str,
    notes: str,
    discount: str,
    vat_rate: str,
    prices_include_vat: str | None,
    doc_type: str = "tax",
    status: str | None = None,
    lines: list[dict[str, Any]] | None = None,
    discount_mode: str = "amount",
) -> dict[str, Any]:
    kind = forms.one_of(doc_type, ("tax", "plain"), default="tax")
    # A percentage only becomes money once the lines are known, so the
    # discount is settled here rather than alongside the simpler fields.
    subtotal = sum(
        line_total(line["qty_milli"], line["unit_price_minor"])
        for line in (lines or [])
    )
    discount_minor, mode, rate_bp = forms.discount(
        discount, discount_mode, subtotal_minor=subtotal
    )
    data: dict[str, Any] = {
        "customer_id": forms.opt_int(customer_id),
        "vehicle_id": forms.opt_int(vehicle_id),
        "issue_date": forms.iso_date(issue_date, default_today=True),
        "due_date": forms.iso_date(due_date),
        "odometer": forms.opt_int(odometer),
        "notes": forms.text(notes),
        "discount_minor": discount_minor,
        "discount_mode": mode,
        "discount_rate_bp": rate_bp,
        "doc_type": kind,
        # A plain invoice charges no VAT. Enforced here rather than trusted
        # to the form, so the document and the arithmetic can never disagree
        # about whether tax was charged.
        "vat_rate_bp": (
            forms.vat_rate(vat_rate, default=settings["vat_rate_bp"])
            if kind == "tax" else 0
        ),
        "prices_include_vat": forms.checkbox(prices_include_vat) if kind == "tax" else 0,
        "currency_code": settings["currency_code"],
    }
    if data["customer_id"] is None:
        raise FormError("Choose a customer for this invoice.")
    if status is not None:
        data["status"] = forms.one_of(
            status, ("draft", "issued", "void"), default="draft"
        )
    return data


@app.post("/invoices/new")
def invoice_create(
    request: Request,
    customer_id: str = Form(""),
    vehicle_id: str = Form(""),
    issue_date: str = Form(""),
    due_date: str = Form(""),
    odometer: str = Form(""),
    notes: str = Form(""),
    discount: str = Form(""),
    discount_mode: str = Form("amount"),
    vat_rate: str = Form(""),
    prices_include_vat: str = Form(None),
    doc_type: str = Form("tax"),
    status: str = Form("draft"),
    item_catalog_id: list[str] = Form([]),
    item_description: list[str] = Form([]),
    item_description_ar: list[str] = Form([]),
    item_kind: list[str] = Form([]),
    item_unit: list[str] = Form([]),
    item_qty: list[str] = Form([]),
    item_price: list[str] = Form([]),
    conn: Connection = Depends(get_conn),
):
    settings = repo.get_settings(conn)
    try:
        lines = forms.parse_invoice_lines(
            descriptions=item_description,
            descriptions_ar=item_description_ar,
            kinds=item_kind,
            units=item_unit,
            quantities=item_qty,
            prices=item_price,
            catalog_ids=item_catalog_id,
        )
        header = _invoice_payload(
            settings=settings,
            customer_id=customer_id,
            vehicle_id=vehicle_id,
            issue_date=issue_date,
            due_date=due_date,
            odometer=odometer,
            notes=notes,
            discount=discount,
            vat_rate=vat_rate,
            prices_include_vat=prices_include_vat,
            doc_type=doc_type,
            status=status,
            lines=lines,
            discount_mode=discount_mode,
        )

    except FormError as exc:
        return render(
            request,
            conn,
            "invoice_form.html",
            preset_customer_id=forms.opt_int(customer_id),
            preset_vehicle_id=forms.opt_int(vehicle_id),
            **_invoice_form_context(conn, error=str(exc)),
        )

    invoice_id = repo.create_invoice(conn, header, lines)
    return go(f"/invoices/{invoice_id}", msg="msg.created")


# ---------------------------------------------------------------------------
# The quick invoice — a wiper blade, a bulb, a litre of oil
# ---------------------------------------------------------------------------
# The full invoice screen asks for a vehicle, a due date, an odometer reading
# and a VAT rate before it will take a 25-riyal sale, which is why that sale
# ends up written on a pad instead. This is the same invoice with everything
# optional left out: who, what, how much, done.
#
# It still creates a customer rather than booking the sale to nobody. The man
# who bought the bulb is someone the workshop may need to find again, and an
# invoice with no customer behind it is a hole in the records that shows up
# later as "who was this?".


@app.get("/invoices/quick", response_class=HTMLResponse)
def quick_invoice_new(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    settings = repo.get_settings(conn)
    catalog = repo.list_catalog(conn)
    return render(
        request, conn, "invoice_quick.html",
        customers=repo.list_customers(conn),
        catalog=catalog,
        catalog_json=_catalog_json(catalog),
        default_vat_bp=settings["vat_rate_bp"],
        error="",
    )


@app.post("/invoices/quick")
def quick_invoice_create(
    request: Request,
    customer_id: str = Form(""),
    customer_name: str = Form(""),
    customer_phone: str = Form(""),
    doc_type: str = Form("tax"),
    item_description: list[str] = Form([]),
    item_qty: list[str] = Form([]),
    item_price: list[str] = Form([]),
    item_catalog_id: list[str] = Form([]),
    paid_now: str = Form(""),
    payment_method: str = Form("cash"),
    conn: Connection = Depends(get_conn),
):
    settings = repo.get_settings(conn)

    def back(message: str):
        catalog = repo.list_catalog(conn)
        return render(
            request, conn, "invoice_quick.html",
            customers=repo.list_customers(conn),
            catalog=catalog,
            catalog_json=_catalog_json(catalog),
            default_vat_bp=settings["vat_rate_bp"],
            error=message,
        )

    try:
        # The three rows arrive with a quantity already in them, which is
        # what makes the screen quick to use and also what makes an untouched
        # row look half-filled to the line parser. Rows with neither a
        # description nor a price were never typed in; they are dropped here
        # rather than reported as mistakes.
        def at(values: list[str], index: int) -> str:
            return values[index] if index < len(values) else ""

        used = [
            i
            for i in range(len(item_description))
            if forms.text(item_description[i]) or forms.text(at(item_price, i))
        ]
        if not used:
            raise FormError("Add at least one line.")

        lines = forms.parse_invoice_lines(
            descriptions=[item_description[i] for i in used],
            descriptions_ar=[""] * len(used),
            kinds=["service"] * len(used),
            units=["pcs"] * len(used),
            quantities=[at(item_qty, i) for i in used],
            prices=[at(item_price, i) for i in used],
            catalog_ids=[at(item_catalog_id, i) for i in used],
        )

        # An existing customer if one was chosen, otherwise a new one from the
        # name typed in. Creating it here is the whole point: stopping to fill
        # in a customer form is what makes people reach for a paper pad.
        chosen = forms.opt_int(customer_id)
        if chosen is None:
            name = forms.required_text(customer_name, field="Customer")
            chosen = repo.create_customer(conn, {
                "name": name,
                "phone": forms.text(customer_phone),
                "notes": "Added from a quick invoice.",
            })

        kind = forms.one_of(doc_type, ("tax", "plain"), default="tax")
        invoice_id = repo.create_invoice(
            conn,
            {
                "customer_id": chosen,
                "vehicle_id": None,
                "issue_date": date.today().isoformat(),
                "due_date": None,
                "odometer": None,
                "status": "issued",
                "vat_rate_bp": settings["vat_rate_bp"] if kind == "tax" else 0,
                "prices_include_vat": settings["prices_include_vat"],
                "currency_code": settings["currency_code"],
                "discount_minor": 0,
                "discount_mode": "amount",
                "discount_rate_bp": 0,
                "notes": "",
                "doc_type": kind,
            },
            lines,
        )
    except FormError as exc:
        return back(str(exc))

    # Counter sales are usually paid on the spot, so the money can be recorded
    # in the same breath rather than needing a second visit to the screen.
    if forms.checkbox(paid_now):
        invoice = repo.get_invoice(conn, invoice_id)
        repo.add_payment(conn, {
            "invoice_id": invoice_id,
            "paid_on": date.today().isoformat(),
            "amount_minor": invoice["total_minor"],
            "method": forms.one_of(
                payment_method, ("cash", "card", "transfer", "cheque", "other"),
                default="cash",
            ),
            "reference": "",
            "notes": "",
        })

    return go(f"/invoices/{invoice_id}/print")


# NOTE ON ORDER: this has to be declared before /invoices/{invoice_id}.
# FastAPI matches routes in the order they are defined, so a later
# "/invoices/quick" would be read as an invoice whose id is "quick"
# and rejected before it ever reached this function.
@app.get("/invoices/{invoice_id}", response_class=HTMLResponse)
def invoice_detail(
    invoice_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    invoice = repo.get_invoice(conn, invoice_id)
    return render(
        request,
        conn,
        "invoice_detail.html",
        invoice=invoice,
        items=repo.get_invoice_items(conn, invoice_id),
        payments=repo.list_payments(conn, invoice_id),
        state=payment_state(
            invoice["status"], invoice["total_minor"], invoice["paid_minor"]
        ),
        balance=balance_due(invoice["total_minor"], invoice["paid_minor"]),
        # Shown as a link back to the signed paperwork, when this invoice
        # came from a repair contract.
        contract=repo.order_for_invoice(conn, invoice_id),
        estimate=repo.estimate_for_invoice(conn, invoice_id),
    )


@app.get("/invoices/{invoice_id}/edit", response_class=HTMLResponse)
def invoice_edit(
    invoice_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request,
        conn,
        "invoice_form.html",
        preset_customer_id=None,
        preset_vehicle_id=None,
        **_invoice_form_context(
            conn,
            invoice=repo.get_invoice(conn, invoice_id),
            items=repo.get_invoice_items(conn, invoice_id),
        ),
    )


@app.post("/invoices/{invoice_id}/edit")
def invoice_update(
    invoice_id: int,
    request: Request,
    customer_id: str = Form(""),
    vehicle_id: str = Form(""),
    issue_date: str = Form(""),
    due_date: str = Form(""),
    odometer: str = Form(""),
    notes: str = Form(""),
    discount: str = Form(""),
    discount_mode: str = Form("amount"),
    vat_rate: str = Form(""),
    prices_include_vat: str = Form(None),
    doc_type: str = Form("tax"),
    status: str = Form("draft"),
    item_catalog_id: list[str] = Form([]),
    item_description: list[str] = Form([]),
    item_description_ar: list[str] = Form([]),
    item_kind: list[str] = Form([]),
    item_unit: list[str] = Form([]),
    item_qty: list[str] = Form([]),
    item_price: list[str] = Form([]),
    conn: Connection = Depends(get_conn),
):
    settings = repo.get_settings(conn)
    try:
        lines = forms.parse_invoice_lines(
            descriptions=item_description,
            descriptions_ar=item_description_ar,
            kinds=item_kind,
            units=item_unit,
            quantities=item_qty,
            prices=item_price,
            catalog_ids=item_catalog_id,
        )
        header = _invoice_payload(
            settings=settings,
            customer_id=customer_id,
            vehicle_id=vehicle_id,
            issue_date=issue_date,
            due_date=due_date,
            odometer=odometer,
            notes=notes,
            discount=discount,
            vat_rate=vat_rate,
            prices_include_vat=prices_include_vat,
            doc_type=doc_type,
            status=status,
            lines=lines,
            discount_mode=discount_mode,
        )

    except FormError as exc:
        return render(
            request,
            conn,
            "invoice_form.html",
            preset_customer_id=None,
            preset_vehicle_id=None,
            **_invoice_form_context(
                conn,
                invoice=repo.get_invoice(conn, invoice_id),
                items=repo.get_invoice_items(conn, invoice_id),
                error=str(exc),
            ),
        )

    repo.update_invoice(conn, invoice_id, header, lines)
    return go(f"/invoices/{invoice_id}", msg="msg.saved")


@app.post("/invoices/{invoice_id}/status")
def invoice_status(
    invoice_id: int, status: str = Form(...), conn: Connection = Depends(get_conn)
):
    try:
        repo.set_invoice_status(conn, invoice_id, status)
    except ValueError as exc:
        return go(f"/invoices/{invoice_id}", err=str(exc))
    msg = "msg.invoice_issued" if status == "issued" else "msg.saved"
    return go(f"/invoices/{invoice_id}", msg=msg)


@app.post("/invoices/{invoice_id}/delete")
def invoice_delete(invoice_id: int, conn: Connection = Depends(get_conn)):
    try:
        repo.delete_invoice(conn, invoice_id)
    except repo.InUse as exc:
        return go(f"/invoices/{invoice_id}", err=str(exc))
    return go("/invoices", msg="msg.deleted")


@app.get("/invoices/{invoice_id}/print", response_class=HTMLResponse)
def invoice_print(
    invoice_id: int,
    request: Request,
    conn: Connection = Depends(get_conn),
    autoprint: int = 1,
) -> HTMLResponse:
    """The customer-facing invoice, laid out for A4 paper.

    Opens the browser's print dialogue automatically, from which any browser
    can also "Save as PDF" -- that is the no-dependency route to a PDF file.
    """
    invoice = repo.get_invoice(conn, invoice_id)
    return render(
        request,
        conn,
        "invoice_print.html",
        invoice=invoice,
        items=repo.get_invoice_items(conn, invoice_id),
        payments=repo.list_payments(conn, invoice_id),
        balance=balance_due(invoice["total_minor"], invoice["paid_minor"]),
        autoprint=bool(autoprint),
        logo_uri=repo.logo_data_uri(conn),
    )


@app.get("/invoices/{invoice_id}/pdf")
def invoice_pdf(
    invoice_id: int, request: Request, conn: Connection = Depends(get_conn)
):
    """Download the invoice as a real PDF file.

    Needs the optional WeasyPrint dependency (it is installed in the Docker
    image). Without it, this falls back to the print view, which still gets
    the user a PDF through the browser's own "Save as PDF".
    """
    invoice = repo.get_invoice(conn, invoice_id)
    if not PDF_AVAILABLE:
        return go(f"/invoices/{invoice_id}/print")

    html = render(
        request,
        conn,
        "invoice_print.html",
        invoice=invoice,
        items=repo.get_invoice_items(conn, invoice_id),
        payments=repo.list_payments(conn, invoice_id),
        balance=balance_due(invoice["total_minor"], invoice["paid_minor"]),
        autoprint=False,
        pdf=True,
        logo_uri=repo.logo_data_uri(conn),
    ).body.decode("utf-8")

    pdf_bytes = html_to_pdf(
        html,
        base_url=str(BASE_DIR),
        stylesheets=[BASE_DIR / "static" / "css" / "print.css"],
    )
    filename = f"{invoice['invoice_no']}.pdf"
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={"Content-Disposition": f'inline; filename="{filename}"'},
    )


# --------------------------------------------------------------------------
# Payments
# --------------------------------------------------------------------------

@app.post("/invoices/{invoice_id}/payments")
def payment_create(
    invoice_id: int,
    amount: str = Form(""),
    paid_on: str = Form(""),
    method: str = Form("cash"),
    reference: str = Form(""),
    notes: str = Form(""),
    conn: Connection = Depends(get_conn),
):
    invoice = repo.get_invoice(conn, invoice_id)
    try:
        amount_minor = forms.money(amount, field="Amount")
        if amount_minor <= 0:
            raise FormError("Enter an amount greater than zero.")
        data = {
            "invoice_id": invoice_id,
            "amount_minor": amount_minor,
            "paid_on": forms.iso_date(paid_on, default_today=True),
            "method": forms.one_of(
                method, ("cash", "card", "transfer", "cheque", "other"), default="cash"
            ),
            "reference": forms.text(reference),
            "notes": forms.text(notes),
        }
    except FormError as exc:
        return go(f"/invoices/{invoice_id}", err=str(exc))

    if invoice["status"] != "issued":
        return go(
            f"/invoices/{invoice_id}",
            err="Issue the invoice before recording a payment against it.",
        )

    repo.add_payment(conn, data)
    return go(f"/invoices/{invoice_id}", msg="msg.payment_recorded")


@app.post("/payments/{payment_id}/delete")
def payment_delete(payment_id: int, conn: Connection = Depends(get_conn)):
    invoice_id = repo.delete_payment(conn, payment_id)
    return go(f"/invoices/{invoice_id}", msg="msg.deleted")


# --------------------------------------------------------------------------
# Estimates
# --------------------------------------------------------------------------
# What a customer is quoted before anything is agreed. Written, sent,
# approved or declined, and only then turned into an invoice.

@app.get("/estimates", response_class=HTMLResponse)
def estimates_list(
    request: Request,
    q: str = "",
    status: str = "",
    page: int = 1,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    estimates = repo.page_estimates(conn, search=q, status=status, page=page)
    return render(
        request,
        conn,
        "estimates_list.html",
        estimates=estimates,
        page=estimates,
        q=q,
        status=status,
    )


def _estimate_form_context(
    conn: Connection, *, estimate: Any = None, items: Any = None, error: str = ""
) -> dict[str, Any]:
    settings = repo.get_settings(conn)
    catalog = repo.list_catalog(conn)
    return {
        "estimate": estimate,
        "items": items or [],
        "customers": repo.list_customers(conn),
        "vehicles": repo.list_vehicles(conn),
        "catalog": catalog,
        "catalog_json": [
            {
                "id": i["id"],
                "name_en": i["name_en"],
                "name_ar": i["name_ar"],
                "kind": i["kind"],
                "unit": i["unit"],
                "price": str(from_minor(i["unit_price_minor"])),
            }
            for i in catalog
        ],
        "default_vat_bp": settings["vat_rate_bp"],
        "default_include_vat": settings["prices_include_vat"],
        "validity_days": settings["estimate_validity_days"],
        "error": error,
    }


@app.get("/estimates/new", response_class=HTMLResponse)
def estimate_new(
    request: Request,
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request,
        conn,
        "estimate_form.html",
        preset_customer_id=customer_id,
        preset_vehicle_id=vehicle_id,
        **_estimate_form_context(conn),
    )


def _estimate_payload(
    *,
    settings: Any,
    customer_id: str,
    vehicle_id: str,
    issue_date: str,
    valid_until: str,
    notes: str,
    discount: str,
    vat_rate: str,
    prices_include_vat: str | None,
    lines: list[dict[str, Any]] | None = None,
    discount_mode: str = "amount",
) -> dict[str, Any]:
    issued = forms.iso_date(issue_date, default_today=True)
    expires = forms.iso_date(valid_until)
    if expires is None and settings["estimate_validity_days"]:
        expires = (
            date.fromisoformat(issued)
            + timedelta(days=int(settings["estimate_validity_days"]))
        ).isoformat()

    data: dict[str, Any] = {
        "customer_id": forms.opt_int(customer_id),
        "vehicle_id": forms.opt_int(vehicle_id),
        "issue_date": issued,
        "valid_until": expires,
        "notes": forms.text(notes),
        **dict(zip(
            ("discount_minor", "discount_mode", "discount_rate_bp"),
            forms.discount(
                discount, discount_mode,
                subtotal_minor=sum(
                    line_total(line["qty_milli"], line["unit_price_minor"])
                    for line in (lines or [])
                ),
            ),
            strict=True,
        )),
        "vat_rate_bp": forms.vat_rate(vat_rate, default=settings["vat_rate_bp"]),
        "prices_include_vat": forms.checkbox(prices_include_vat),
        "currency_code": settings["currency_code"],
    }
    if data["customer_id"] is None:
        raise FormError("Choose a customer for this estimate.")
    return data


@app.post("/estimates/new")
def estimate_create(
    request: Request,
    customer_id: str = Form(""),
    vehicle_id: str = Form(""),
    issue_date: str = Form(""),
    valid_until: str = Form(""),
    notes: str = Form(""),
    discount: str = Form(""),
    discount_mode: str = Form("amount"),
    vat_rate: str = Form(""),
    prices_include_vat: str = Form(None),
    item_catalog_id: list[str] = Form([]),
    item_description: list[str] = Form([]),
    item_description_ar: list[str] = Form([]),
    item_kind: list[str] = Form([]),
    item_unit: list[str] = Form([]),
    item_qty: list[str] = Form([]),
    item_price: list[str] = Form([]),
    conn: Connection = Depends(get_conn),
):
    settings = repo.get_settings(conn)
    try:
        lines = forms.parse_invoice_lines(
            descriptions=item_description,
            descriptions_ar=item_description_ar,
            kinds=item_kind,
            units=item_unit,
            quantities=item_qty,
            prices=item_price,
            catalog_ids=item_catalog_id,
        )
        header = _estimate_payload(
            settings=settings, customer_id=customer_id, vehicle_id=vehicle_id,
            issue_date=issue_date, valid_until=valid_until, notes=notes,
            discount=discount, vat_rate=vat_rate,
            prices_include_vat=prices_include_vat,
            lines=lines, discount_mode=discount_mode,
        )
    except FormError as exc:
        return render(
            request,
            conn,
            "estimate_form.html",
            preset_customer_id=forms.opt_int(customer_id),
            preset_vehicle_id=forms.opt_int(vehicle_id),
            **_estimate_form_context(conn, error=str(exc)),
        )

    estimate_id = repo.create_estimate(conn, header, lines)
    return go(f"/estimates/{estimate_id}", msg="msg.created")


def _estimate_message(conn: Connection, estimate: Any, items: Any, lang: str) -> str:
    """The message body sent with an estimate, from the Settings template.

    ``lang`` is the language of the *message*, which is not necessarily the
    language of the interface: the person sending it reads Arabic, the
    customer may not, and the customer is the one who has to understand it.
    """
    settings = repo.get_settings(conn)
    template = settings["message_template_ar"] if lang == "ar" else settings["message_template_en"]
    currency = settings["currency_code"]

    # Formatted here rather than inside messaging.py, so the message agrees
    # with the printed estimate down to the decimal place.
    lines = [
        {
            "description": localised(item, "description", lang),
            "qty": format_qty(item["qty_milli"]),
            "price": format_money(item["unit_price_minor"], ""),
            "amount": format_money(item["line_total_minor"], ""),
        }
        for item in items
    ]
    more = "و{n} أخرى" if lang == "ar" else "and {n} more"

    return messaging.render_template(
        template,
        {
            "customer": localised(estimate, "customer_name", lang),
            "business": localised(settings, "business_name_en", lang),
            "number": estimate["estimate_no"],
            "subtotal": format_money(estimate["subtotal_minor"], currency),
            "vat": format_money(estimate["vat_minor"], currency),
            "total": format_money(estimate["total_minor"], currency),
            "valid_until": estimate["valid_until"] or "",
            "items": messaging.itemise(lines, more=more),
        },
    )


@app.get("/estimates/{estimate_id}", response_class=HTMLResponse)
def estimate_detail(
    estimate_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    estimate = repo.get_estimate(conn, estimate_id)
    items = repo.get_estimate_items(conn, estimate_id)
    settings = repo.get_settings(conn)
    lang = current_lang(request, settings)
    country = settings["default_country_code"]

    # Both languages are built here and the page switches between them, rather
    # than the message following the interface language. Which language the
    # customer reads has nothing to do with which one the workshop works in,
    # and changing the whole interface to send one message in Arabic is a
    # silly thing to make somebody do.
    messages = {
        code: _estimate_message(conn, estimate, items, code) for code in ("en", "ar")
    }
    phone = estimate["customer_phone"]

    return render(
        request,
        conn,
        "estimate_detail.html",
        estimate=estimate,
        items=items,
        message_lang=lang,
        messages=messages,
        whatsapp_urls={
            code: messaging.whatsapp_link(phone, body, country)
            for code, body in messages.items()
        },
        sms_urls={
            code: messaging.sms_link(phone, body, country)
            for code, body in messages.items()
        },
        has_phone=bool(messaging.normalise_phone(phone, country)),
        provider_note=messaging.provider_note(lang),
    )


@app.get("/estimates/{estimate_id}/edit", response_class=HTMLResponse)
def estimate_edit(
    estimate_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request,
        conn,
        "estimate_form.html",
        preset_customer_id=None,
        preset_vehicle_id=None,
        **_estimate_form_context(
            conn,
            estimate=repo.get_estimate(conn, estimate_id),
            items=repo.get_estimate_items(conn, estimate_id),
        ),
    )


@app.post("/estimates/{estimate_id}/edit")
def estimate_update(
    estimate_id: int,
    request: Request,
    customer_id: str = Form(""),
    vehicle_id: str = Form(""),
    issue_date: str = Form(""),
    valid_until: str = Form(""),
    notes: str = Form(""),
    discount: str = Form(""),
    discount_mode: str = Form("amount"),
    vat_rate: str = Form(""),
    prices_include_vat: str = Form(None),
    item_catalog_id: list[str] = Form([]),
    item_description: list[str] = Form([]),
    item_description_ar: list[str] = Form([]),
    item_kind: list[str] = Form([]),
    item_unit: list[str] = Form([]),
    item_qty: list[str] = Form([]),
    item_price: list[str] = Form([]),
    conn: Connection = Depends(get_conn),
):
    settings = repo.get_settings(conn)
    try:
        lines = forms.parse_invoice_lines(
            descriptions=item_description,
            descriptions_ar=item_description_ar,
            kinds=item_kind,
            units=item_unit,
            quantities=item_qty,
            prices=item_price,
            catalog_ids=item_catalog_id,
        )
        header = _estimate_payload(
            settings=settings, customer_id=customer_id, vehicle_id=vehicle_id,
            issue_date=issue_date, valid_until=valid_until, notes=notes,
            discount=discount, vat_rate=vat_rate,
            prices_include_vat=prices_include_vat,
            lines=lines, discount_mode=discount_mode,
        )
        repo.update_estimate(conn, estimate_id, header, lines)
    except FormError as exc:
        return render(
            request,
            conn,
            "estimate_form.html",
            preset_customer_id=None,
            preset_vehicle_id=None,
            **_estimate_form_context(
                conn,
                estimate=repo.get_estimate(conn, estimate_id),
                items=repo.get_estimate_items(conn, estimate_id),
                error=str(exc),
            ),
        )
    except repo.InUse as exc:
        return go(f"/estimates/{estimate_id}", err=str(exc))

    return go(f"/estimates/{estimate_id}", msg="msg.saved")


@app.post("/estimates/{estimate_id}/status")
def estimate_status(
    estimate_id: int,
    status: str = Form(...),
    approved_by: str = Form(""),
    conn: Connection = Depends(get_conn),
):
    try:
        repo.set_estimate_status(
            conn, estimate_id, status, approved_by=forms.text(approved_by)
        )
    except (ValueError, repo.InUse) as exc:
        return go(f"/estimates/{estimate_id}", err=str(exc))
    messages = {
        "sent": "msg.estimate_sent",
        "approved": "msg.estimate_approved",
        "declined": "msg.saved",
    }
    return go(f"/estimates/{estimate_id}", msg=messages.get(status, "msg.saved"))


@app.post("/estimates/{estimate_id}/delete")
def estimate_delete(estimate_id: int, conn: Connection = Depends(get_conn)):
    try:
        repo.delete_estimate(conn, estimate_id)
    except repo.InUse as exc:
        return go(f"/estimates/{estimate_id}", err=str(exc))
    return go("/estimates", msg="msg.deleted")


@app.post("/estimates/{estimate_id}/invoice")
def estimate_to_invoice(
    estimate_id: int,
    doc_type: str = Form("tax"),
    conn: Connection = Depends(get_conn),
):
    """Turn an approved estimate into a draft invoice."""
    try:
        invoice_id = repo.convert_estimate_to_invoice(
            conn,
            estimate_id,
            doc_type=forms.one_of(doc_type, ("tax", "plain"), default="tax"),
        )
    except repo.InUse as exc:
        return go(f"/estimates/{estimate_id}", err=str(exc))
    return go(f"/invoices/{invoice_id}", msg="msg.invoice_from_estimate")


@app.get("/estimates/{estimate_id}/print", response_class=HTMLResponse)
def estimate_print(
    estimate_id: int,
    request: Request,
    conn: Connection = Depends(get_conn),
    autoprint: int = 1,
) -> HTMLResponse:
    return render(
        request,
        conn,
        "estimate_print.html",
        estimate=repo.get_estimate(conn, estimate_id),
        items=repo.get_estimate_items(conn, estimate_id),
        autoprint=bool(autoprint),
        logo_uri=repo.logo_data_uri(conn),
    )


@app.get("/estimates/{estimate_id}/pdf")
def estimate_pdf(
    estimate_id: int, request: Request, conn: Connection = Depends(get_conn)
):
    estimate = repo.get_estimate(conn, estimate_id)
    if not PDF_AVAILABLE:
        return go(f"/estimates/{estimate_id}/print")

    html = render(
        request,
        conn,
        "estimate_print.html",
        estimate=estimate,
        items=repo.get_estimate_items(conn, estimate_id),
        autoprint=False,
        pdf=True,
        logo_uri=repo.logo_data_uri(conn),
    ).body.decode("utf-8")

    pdf_bytes = html_to_pdf(
        html,
        base_url=str(BASE_DIR),
        stylesheets=[BASE_DIR / "static" / "css" / "print.css"],
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{estimate["estimate_no"]}.pdf"'
        },
    )


# --------------------------------------------------------------------------
# Repair contracts
# --------------------------------------------------------------------------
# The paper the customer signs when the car is booked in. It records what was
# asked for, what the technician found and which parts went on, and is later
# converted into an invoice.

@app.get("/contracts", response_class=HTMLResponse)
def contracts_list(
    request: Request,
    q: str = "",
    status: str = "",
    page: int = 1,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    contracts = repo.page_repair_orders(conn, search=q, status=status, page=page)
    return render(
        request,
        conn,
        "contracts_list.html",
        contracts=contracts,
        page=contracts,
        q=q,
        status=status,
    )


def _contract_form_context(
    conn: Connection, *, order: Any = None, items: Any = None, parts: Any = None,
    error: str = "",
) -> dict[str, Any]:
    settings = repo.get_settings(conn)
    catalog = repo.list_catalog(conn)
    return {
        "order": order,
        "items": items or [],
        "parts": parts or [],
        "customers": repo.list_customers(conn),
        "vehicles": repo.list_vehicles(conn),
        "catalog": catalog,
        "services": [c for c in catalog if c["kind"] == "service"],
        "catalog_json": [
            {
                "id": i["id"],
                "name_en": i["name_en"],
                "name_ar": i["name_ar"],
                "kind": i["kind"],
                "unit": i["unit"],
                "price": str(from_minor(i["unit_price_minor"])),
            }
            for i in catalog
        ],
        "parts_markup_bp": settings["parts_markup_bp"],
        "error": error,
    }


@app.get("/contracts/new", response_class=HTMLResponse)
def contract_new(
    request: Request,
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request,
        conn,
        "contract_form.html",
        preset_customer_id=customer_id,
        preset_vehicle_id=vehicle_id,
        **_contract_form_context(conn),
    )


def _contract_payload(
    *,
    customer_id: str,
    vehicle_id: str,
    date_in: str,
    expected_date_out: str,
    odometer: str,
    car_code: str,
    technician_name: str,
    damage_notes: str,
    notes: str,
    status: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "customer_id": forms.opt_int(customer_id),
        "vehicle_id": forms.opt_int(vehicle_id),
        "date_in": forms.iso_date(date_in, default_today=True),
        "expected_date_out": forms.iso_date(expected_date_out),
        "odometer": forms.opt_int(odometer),
        "car_code": forms.text(car_code),
        "technician_name": forms.text(technician_name),
        "damage_notes": forms.text(damage_notes),
        "notes": forms.text(notes),
    }
    if data["customer_id"] is None:
        raise FormError("Choose the customer this contract is for.")
    if status is not None:
        data["status"] = forms.one_of(
            status, ("open", "completed", "invoiced", "cancelled"), default="open"
        )
    return data


def _contract_lines(
    item_description: list[str],
    item_description_ar: list[str],
    item_expense: list[str],
    item_remarks: list[str],
    item_catalog_id: list[str],
    part_number: list[str],
    part_description: list[str],
    part_description_ar: list[str],
    part_qty: list[str],
    part_price: list[str],
    part_sourced: list[str],
    part_catalog_id: list[str],
) -> tuple[list[dict[str, Any]], list[dict[str, Any]]]:
    items = forms.parse_contract_items(
        descriptions=item_description,
        descriptions_ar=item_description_ar,
        expenses=item_expense,
        remarks=item_remarks,
        catalog_ids=item_catalog_id,
    )
    parts = forms.parse_contract_parts(
        part_numbers=part_number,
        descriptions=part_description,
        descriptions_ar=part_description_ar,
        quantities=part_qty,
        prices=part_price,
        sourced=part_sourced,
        catalog_ids=part_catalog_id,
    )
    return items, parts


@app.post("/contracts/new")
def contract_create(
    request: Request,
    customer_id: str = Form(""),
    vehicle_id: str = Form(""),
    date_in: str = Form(""),
    expected_date_out: str = Form(""),
    odometer: str = Form(""),
    car_code: str = Form(""),
    technician_name: str = Form(""),
    damage_notes: str = Form(""),
    notes: str = Form(""),
    status: str = Form("open"),
    item_catalog_id: list[str] = Form([]),
    item_description: list[str] = Form([]),
    item_description_ar: list[str] = Form([]),
    item_expense: list[str] = Form([]),
    item_remarks: list[str] = Form([]),
    part_catalog_id: list[str] = Form([]),
    part_number: list[str] = Form([]),
    part_description: list[str] = Form([]),
    part_description_ar: list[str] = Form([]),
    part_qty: list[str] = Form([]),
    part_price: list[str] = Form([]),
    part_sourced: list[str] = Form([]),
    conn: Connection = Depends(get_conn),
):
    try:
        header = _contract_payload(
            customer_id=customer_id, vehicle_id=vehicle_id, date_in=date_in,
            expected_date_out=expected_date_out, odometer=odometer,
            car_code=car_code, technician_name=technician_name,
            damage_notes=damage_notes, notes=notes, status=status,
        )
        items, parts = _contract_lines(
            item_description, item_description_ar, item_expense, item_remarks,
            item_catalog_id, part_number, part_description, part_description_ar,
            part_qty, part_price, part_sourced, part_catalog_id,
        )
    except FormError as exc:
        return render(
            request,
            conn,
            "contract_form.html",
            preset_customer_id=forms.opt_int(customer_id),
            preset_vehicle_id=forms.opt_int(vehicle_id),
            **_contract_form_context(conn, error=str(exc)),
        )

    order_id = repo.create_repair_order(conn, header, items, parts)
    return go(f"/contracts/{order_id}", msg="msg.created")


@app.get("/contracts/{order_id}", response_class=HTMLResponse)
def contract_detail(
    order_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request,
        conn,
        "contract_detail.html",
        order=repo.get_repair_order(conn, order_id),
        items=repo.get_order_items(conn, order_id),
        parts=repo.get_order_parts(conn, order_id),
        totals=repo.order_totals(conn, order_id),
        order_issues=repo.list_order_issues(conn, order_id),
        known_issues=repo.list_known_issues(conn),
    )


@app.get("/contracts/{order_id}/edit", response_class=HTMLResponse)
def contract_edit(
    order_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request,
        conn,
        "contract_form.html",
        preset_customer_id=None,
        preset_vehicle_id=None,
        **_contract_form_context(
            conn,
            order=repo.get_repair_order(conn, order_id),
            items=repo.get_order_items(conn, order_id),
            parts=repo.get_order_parts(conn, order_id),
        ),
    )


@app.post("/contracts/{order_id}/edit")
def contract_update(
    order_id: int,
    request: Request,
    customer_id: str = Form(""),
    vehicle_id: str = Form(""),
    date_in: str = Form(""),
    expected_date_out: str = Form(""),
    odometer: str = Form(""),
    car_code: str = Form(""),
    technician_name: str = Form(""),
    damage_notes: str = Form(""),
    notes: str = Form(""),
    status: str = Form("open"),
    item_catalog_id: list[str] = Form([]),
    item_description: list[str] = Form([]),
    item_description_ar: list[str] = Form([]),
    item_expense: list[str] = Form([]),
    item_remarks: list[str] = Form([]),
    part_catalog_id: list[str] = Form([]),
    part_number: list[str] = Form([]),
    part_description: list[str] = Form([]),
    part_description_ar: list[str] = Form([]),
    part_qty: list[str] = Form([]),
    part_price: list[str] = Form([]),
    part_sourced: list[str] = Form([]),
    conn: Connection = Depends(get_conn),
):
    try:
        header = _contract_payload(
            customer_id=customer_id, vehicle_id=vehicle_id, date_in=date_in,
            expected_date_out=expected_date_out, odometer=odometer,
            car_code=car_code, technician_name=technician_name,
            damage_notes=damage_notes, notes=notes, status=status,
        )
        items, parts = _contract_lines(
            item_description, item_description_ar, item_expense, item_remarks,
            item_catalog_id, part_number, part_description, part_description_ar,
            part_qty, part_price, part_sourced, part_catalog_id,
        )
        repo.update_repair_order(conn, order_id, header, items, parts)
    except FormError as exc:
        return render(
            request,
            conn,
            "contract_form.html",
            preset_customer_id=None,
            preset_vehicle_id=None,
            **_contract_form_context(
                conn,
                order=repo.get_repair_order(conn, order_id),
                items=repo.get_order_items(conn, order_id),
                parts=repo.get_order_parts(conn, order_id),
                error=str(exc),
            ),
        )
    except repo.InUse as exc:
        return go(f"/contracts/{order_id}", err=str(exc))

    return go(f"/contracts/{order_id}", msg="msg.saved")


@app.post("/contracts/{order_id}/status")
def contract_status(
    order_id: int, status: str = Form(...), conn: Connection = Depends(get_conn)
):
    try:
        repo.set_order_status(conn, order_id, status)
    except ValueError as exc:
        return go(f"/contracts/{order_id}", err=str(exc))
    return go(f"/contracts/{order_id}", msg="msg.saved")


@app.post("/contracts/{order_id}/sign")
def contract_sign(
    order_id: int, signed: str = Form("1"), conn: Connection = Depends(get_conn)
):
    repo.sign_repair_order(conn, order_id, signed == "1")
    return go(f"/contracts/{order_id}", msg="msg.saved")


@app.post("/contracts/{order_id}/delete")
def contract_delete(order_id: int, conn: Connection = Depends(get_conn)):
    try:
        repo.delete_repair_order(conn, order_id)
    except repo.InUse as exc:
        return go(f"/contracts/{order_id}", err=str(exc))
    return go("/contracts", msg="msg.deleted")


@app.post("/contracts/{order_id}/invoice")
def contract_to_invoice(order_id: int, conn: Connection = Depends(get_conn)):
    """Turn a signed, finished contract into a draft invoice."""
    try:
        invoice_id = repo.convert_order_to_invoice(conn, order_id)
    except repo.InUse as exc:
        return go(f"/contracts/{order_id}", err=str(exc))
    return go(f"/invoices/{invoice_id}", msg="msg.invoice_from_contract")


@app.get("/contracts/{order_id}/print", response_class=HTMLResponse)
def contract_print(
    order_id: int,
    request: Request,
    conn: Connection = Depends(get_conn),
    autoprint: int = 1,
) -> HTMLResponse:
    """The contract as it is printed for the customer to sign."""
    return render(
        request,
        conn,
        "contract_print.html",
        order=repo.get_repair_order(conn, order_id),
        items=repo.get_order_items(conn, order_id),
        parts=repo.get_order_parts(conn, order_id),
        totals=repo.order_totals(conn, order_id),
        # Only the ones ticked to be shown. Recording that a fault was ruled
        # out is useful internally and is not necessarily the customer's
        # business, which is what that tick decides.
        order_issues=[
            link for link in repo.list_order_issues(conn, order_id)
            if link["show_on_print"]
        ],
        autoprint=bool(autoprint),
        logo_uri=repo.logo_data_uri(conn),
    )


@app.get("/contracts/{order_id}/pdf")
def contract_pdf(
    order_id: int, request: Request, conn: Connection = Depends(get_conn)
):
    order = repo.get_repair_order(conn, order_id)
    if not PDF_AVAILABLE:
        return go(f"/contracts/{order_id}/print")

    html = render(
        request,
        conn,
        "contract_print.html",
        order=order,
        items=repo.get_order_items(conn, order_id),
        parts=repo.get_order_parts(conn, order_id),
        totals=repo.order_totals(conn, order_id),
        order_issues=[
            link for link in repo.list_order_issues(conn, order_id)
            if link["show_on_print"]
        ],
        autoprint=False,
        pdf=True,
        logo_uri=repo.logo_data_uri(conn),
    ).body.decode("utf-8")

    pdf_bytes = html_to_pdf(
        html,
        base_url=str(BASE_DIR),
        stylesheets=[BASE_DIR / "static" / "css" / "print.css"],
    )
    return Response(
        content=pdf_bytes,
        media_type="application/pdf",
        headers={
            "Content-Disposition": f'inline; filename="{order["contract_no"]}.pdf"'
        },
    )


# --------------------------------------------------------------------------
# Settings
# --------------------------------------------------------------------------


# ==========================================================================
# Known faults
# ==========================================================================


def _issue_payload(
    make: str, model: str, engine: str, year_from: str, year_to: str,
    title_en: str, title_ar: str, symptoms_en: str, symptoms_ar: str,
    check_en: str, check_ar: str, severity: str, notes: str,
    is_active: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "make": forms.required_text(make, field="Make"),
        "model": forms.text(model),
        "engine": forms.text(engine),
        "year_from": forms.opt_int(year_from),
        "year_to": forms.opt_int(year_to),
        "title_en": forms.required_text(title_en, field="Title"),
        "title_ar": forms.text(title_ar),
        "symptoms_en": forms.text(symptoms_en),
        "symptoms_ar": forms.text(symptoms_ar),
        "check_en": forms.text(check_en),
        "check_ar": forms.text(check_ar),
        "severity": forms.one_of(severity, ("low", "medium", "high"), default="medium"),
        "notes": forms.text(notes),
    }
    if is_active is not None:
        data["is_active"] = forms.checkbox(is_active)
    return data


@app.get("/issues", response_class=HTMLResponse)
def issues_list(
    request: Request,
    make: str = Query(""),
    q: str = Query(""),
    inactive: str = Query(""),
    sort: str = Query(""),
    dir: str = Query("asc"),
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request,
        conn,
        "issues_list.html",
        **_sort_state("issues", sort, dir),
        issues=repo.list_known_issues(
            conn, make=make, search=q, include_inactive=forms.truthy(inactive),
            sort=sort, direction=dir
        ),
        makes=repo.known_issue_makes(conn),
        make=make,
        q=q,
        inactive=bool(inactive),
    )


@app.get("/issues/new", response_class=HTMLResponse)
def issue_new(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    return render(request, conn, "issue_form.html", issue=None, error="")


@app.post("/issues/new")
def issue_create(
    request: Request,
    make: str = Form(""), model: str = Form(""), engine: str = Form(""),
    year_from: str = Form(""), year_to: str = Form(""),
    title_en: str = Form(""), title_ar: str = Form(""),
    symptoms_en: str = Form(""), symptoms_ar: str = Form(""),
    check_en: str = Form(""), check_ar: str = Form(""),
    severity: str = Form("medium"), notes: str = Form(""),
    conn: Connection = Depends(get_conn),
):
    try:
        data = _issue_payload(make, model, engine, year_from, year_to,
                              title_en, title_ar, symptoms_en, symptoms_ar,
                              check_en, check_ar, severity, notes)
        repo.create_known_issue(conn, data)
    except FormError as exc:
        return render(request, conn, "issue_form.html", issue=None, error=str(exc))
    return go("/issues", msg="msg.created")


@app.get("/issues/{issue_id}/edit", response_class=HTMLResponse)
def issue_edit(
    issue_id: int, request: Request, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request, conn, "issue_form.html",
        issue=repo.get_known_issue(conn, issue_id), error="",
    )


@app.post("/issues/{issue_id}/edit")
def issue_update(
    issue_id: int,
    request: Request,
    make: str = Form(""), model: str = Form(""), engine: str = Form(""),
    year_from: str = Form(""), year_to: str = Form(""),
    title_en: str = Form(""), title_ar: str = Form(""),
    symptoms_en: str = Form(""), symptoms_ar: str = Form(""),
    check_en: str = Form(""), check_ar: str = Form(""),
    severity: str = Form("medium"), notes: str = Form(""),
    is_active: str = Form(None),
    conn: Connection = Depends(get_conn),
):
    try:
        data = _issue_payload(make, model, engine, year_from, year_to,
                              title_en, title_ar, symptoms_en, symptoms_ar,
                              check_en, check_ar, severity, notes)
        # The edit form always draws this box, so its absence is the box
        # being cleared, not a field that was never offered. Written
        # unconditionally here for that reason -- the shared payload builder
        # leaves it alone so creating a fault does not have to mention it.
        data["is_active"] = forms.checkbox(is_active)
        repo.update_known_issue(conn, issue_id, data)
    except FormError as exc:
        return render(
            request, conn, "issue_form.html",
            issue=repo.get_known_issue(conn, issue_id), error=str(exc),
        )
    return go("/issues", msg="msg.saved")


@app.post("/issues/{issue_id}/delete")
def issue_delete(issue_id: int, conn: Connection = Depends(get_conn)):
    repo.delete_known_issue(conn, issue_id)
    return go("/issues", msg="msg.deleted")


# -- attaching a fault to a job --------------------------------------------


@app.post("/contracts/{order_id}/issues")
def contract_attach_issue(
    order_id: int,
    known_issue_id: str = Form(""),
    outcome: str = Form("suspected"),
    show_on_print: str = Form(None),
    note: str = Form(""),
    conn: Connection = Depends(get_conn),
):
    issue_id = forms.opt_int(known_issue_id)
    if issue_id is None:
        return go(f"/contracts/{order_id}", err="Choose a fault to attach.")
    repo.attach_issue(
        conn, order_id, issue_id,
        outcome=forms.one_of(
            outcome, ("suspected", "confirmed", "ruled_out", "repaired"),
            default="suspected",
        ),
        show_on_print=bool(forms.checkbox(show_on_print)),
        note=forms.text(note),
    )
    return go(f"/contracts/{order_id}", msg="msg.saved")


@app.post("/contract-issues/{link_id}/delete")
def contract_detach_issue(link_id: int, conn: Connection = Depends(get_conn)):
    order_id = repo.detach_issue(conn, link_id)
    return go(f"/contracts/{order_id}", msg="msg.deleted")


@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    return render(request, conn, "settings.html", error="", backup=backups.status())


# NOTE: these sit above /settings/{...} style paths for the same reason the
# quick invoice sits above /invoices/{invoice_id} -- FastAPI matches routes in
# the order they are declared.
@app.get("/settings/lists", response_class=HTMLResponse)
def lists_page(
    request: Request,
    list_name: str = "sources",
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    if list_name not in repo.OPTION_LISTS:
        list_name = "sources"
    return render(
        request,
        conn,
        "settings_lists.html",
        list_name=list_name,
        # Switched-off values are shown here, greyed, because this is the one
        # screen where their existence matters: it explains why re-adding
        # something says it is already there.
        rows=repo.list_options(conn, list_name, include_inactive=True),
        lists=repo.OPTION_LISTS,
    )


@app.post("/settings/lists/add")
def lists_add(
    list_name: str = Form(...),
    value: str = Form(""),
    label_en: str = Form(""),
    label_ar: str = Form(""),
    conn: Connection = Depends(get_conn),
):
    try:
        repo.create_option(
            conn,
            list_name=list_name,
            value=value,
            label_en=label_en,
            label_ar=label_ar,
        )
    except ValueError as exc:
        return go(f"/settings/lists?list_name={list_name}", err=str(exc))
    return go(f"/settings/lists?list_name={list_name}", msg="msg.saved")


@app.post("/settings/lists/save")
def lists_save(
    list_name: str = Form(...),
    option_id: list[int] = Form(default=[]),
    label_en: list[str] = Form(default=[]),
    label_ar: list[str] = Form(default=[]),
    sort_order: list[str] = Form(default=[]),
    active: list[str] = Form(default=[]),
    conn: Connection = Depends(get_conn),
):
    """Save every row of one list at once.

    `active` is a select rather than a checkbox on purpose: an unticked
    checkbox is not submitted at all, which would shift these parallel lists
    out of step with each other and switch off the wrong value.
    """
    for i, option_id_value in enumerate(option_id):
        repo.update_option(
            conn,
            option_id_value,
            label_en=label_en[i] if i < len(label_en) else None,
            label_ar=label_ar[i] if i < len(label_ar) else None,
            sort_order=int(sort_order[i]) if i < len(sort_order) and sort_order[i].strip() else None,
            is_active=(active[i] == "1") if i < len(active) else None,
        )
    return go(f"/settings/lists?list_name={list_name}", msg="msg.saved")


@app.post("/settings/lists/{option_id}/delete")
def lists_delete(
    option_id: int,
    list_name: str = Form(...),
    conn: Connection = Depends(get_conn),
):
    repo.delete_option(conn, option_id)
    return go(f"/settings/lists?list_name={list_name}", msg="msg.deleted")


@app.post("/settings")
def settings_save(
    request: Request,
    # Every field defaults to None rather than "" so the handler can tell a
    # box the user cleared (which arrives as "") from one the submission did
    # not contain at all. Only what was actually sent is written, so posting
    # part of this form can never silently wipe the rest of the settings.
    business_name_en: str = Form(None),
    business_name_ar: str = Form(None),
    vat_number: str = Form(None),
    cr_number: str = Form(None),
    address_en: str = Form(None),
    address_ar: str = Form(None),
    phone: str = Form(None),
    email: str = Form(None),
    vat_rate: str = Form(None),
    prices_include_vat: str = Form(None),
    currency_code: str = Form(None),
    invoice_prefix: str = Form(None),
    next_invoice_seq: str = Form(None),
    default_language: str = Form(None),
    invoice_footer_en: str = Form(None),
    invoice_footer_ar: str = Form(None),
    business_tagline_en: str = Form(None),
    business_tagline_ar: str = Form(None),
    contract_terms_en: str = Form(None),
    contract_terms_ar: str = Form(None),
    contract_authorization_en: str = Form(None),
    contract_authorization_ar: str = Form(None),
    contract_prefix: str = Form(None),
    next_contract_seq: str = Form(None),
    parts_markup: str = Form(None),
    estimate_prefix: str = Form(None),
    next_estimate_seq: str = Form(None),
    estimate_validity_days: str = Form(None),
    default_country_code: str = Form(None),
    message_template_en: str = Form(None),
    message_template_ar: str = Form(None),
    conn: Connection = Depends(get_conn),
):
    current = repo.get_settings(conn)
    data: dict[str, Any] = {}

    def submitted(column: str, raw: str | None, convert) -> None:
        """Record a column only when the form actually carried that field."""
        if raw is not None:
            data[column] = convert(raw)

    try:
        submitted(
            "business_name_en", business_name_en,
            lambda v: forms.required_text(v, field="Business name"),
        )
        submitted("business_name_ar", business_name_ar, forms.text)
        submitted("vat_number", vat_number, forms.text)
        submitted("cr_number", cr_number, forms.text)
        submitted("address_en", address_en, forms.text)
        submitted("address_ar", address_ar, forms.text)
        submitted("phone", phone, forms.text)
        submitted("email", email, forms.text)
        submitted(
            "vat_rate_bp", vat_rate,
            lambda v: forms.vat_rate(v, default=current["vat_rate_bp"]),
        )
        submitted("currency_code", currency_code,
                  lambda v: forms.text(v, default="SAR").upper()[:5])
        submitted("invoice_prefix", invoice_prefix, forms.text)
        submitted("invoice_footer_en", invoice_footer_en, forms.text)
        submitted("invoice_footer_ar", invoice_footer_ar, forms.text)
        submitted("business_tagline_en", business_tagline_en, forms.text)
        submitted("business_tagline_ar", business_tagline_ar, forms.text)
        submitted("contract_terms_en", contract_terms_en, forms.text)
        submitted("contract_terms_ar", contract_terms_ar, forms.text)
        submitted("contract_authorization_en", contract_authorization_en, forms.text)
        submitted("contract_authorization_ar", contract_authorization_ar, forms.text)
        submitted("contract_prefix", contract_prefix, forms.text)
        submitted(
            "default_language", default_language,
            lambda v: forms.one_of(v, tuple(LANGUAGES), default="en"),
        )
        submitted(
            "parts_markup_bp", parts_markup,
            lambda v: forms.vat_rate(v, default=current["parts_markup_bp"]),
        )
        submitted("estimate_prefix", estimate_prefix, forms.text)
        submitted("message_template_en", message_template_en, forms.text)
        submitted("message_template_ar", message_template_ar, forms.text)
        submitted(
            "default_country_code", default_country_code,
            # Digits only: it is pasted straight into a wa.me link.
            lambda v: "".join(ch for ch in forms.text(v) if ch.isdigit())[:4] or "966",
        )
        submitted(
            "estimate_validity_days", estimate_validity_days,
            lambda v: max(0, forms.opt_int(v) or 0),
        )

        # The checkbox is the exception: unticked means absent, so it can only
        # be read when the form it belongs to was the one submitted.
        if business_name_en is not None:
            data["prices_include_vat"] = forms.checkbox(prices_include_vat)

        if next_invoice_seq is not None:
            seq = forms.opt_int(next_invoice_seq) or current["next_invoice_seq"]
            if seq < 1:
                raise FormError("The next invoice number must be 1 or higher.")
            data["next_invoice_seq"] = seq

        if next_contract_seq is not None:
            contract_seq = (
                forms.opt_int(next_contract_seq) or current["next_contract_seq"]
            )
            if contract_seq < 1:
                raise FormError("The next contract number must be 1 or higher.")
            data["next_contract_seq"] = contract_seq

        if next_estimate_seq is not None:
            estimate_seq = (
                forms.opt_int(next_estimate_seq) or current["next_estimate_seq"]
            )
            if estimate_seq < 1:
                raise FormError("The next estimate number must be 1 or higher.")
            data["next_estimate_seq"] = estimate_seq
    except FormError as exc:
        return render(request, conn, "settings.html", error=str(exc),
                      backup=backups.status())

    repo.update_settings(conn, data)
    return go("/settings", msg="set.saved")


@app.get("/logo")
def logo_image(conn: Connection = Depends(get_conn)) -> Response:
    """Serve the business logo for the screen.

    The printed documents embed the image instead (see `logo_data_uri`);
    this is for the top bar, where a cacheable URL is the better fit.
    """
    stored = repo.get_logo(conn)
    if stored is None:
        return Response(status_code=404)
    data, mime = stored
    return Response(
        content=data,
        media_type=mime,
        headers={
            # The URL carries the logo's timestamp, so a replaced logo gets a
            # new URL and appears at once rather than being served from cache.
            "Cache-Control": "public, max-age=86400",
            "X-Content-Type-Options": "nosniff",
        },
    )


@app.post("/settings/logo")
async def logo_upload(
    logo: UploadFile = File(...), conn: Connection = Depends(get_conn)
):
    """Store an uploaded logo.

    One byte past the limit is read deliberately: it is enough to know the
    file is too big, without pulling a huge upload into memory to find out.
    """
    data = await logo.read(repo.MAX_LOGO_BYTES + 1)
    try:
        repo.set_logo(conn, data, filename=logo.filename or "")
    except ValueError as exc:
        return go("/settings", err=str(exc))
    return go("/settings", msg="set.logo_saved")


@app.post("/settings/logo/remove")
def logo_remove(conn: Connection = Depends(get_conn)):
    repo.clear_logo(conn)
    return go("/settings", msg="msg.deleted")


@app.post("/settings/backup/now")
def settings_backup_now():
    """Take a backup right now, whether or not the day already has one.

    Here because somebody about to do something they are nervous about --
    importing a file, deleting a batch, letting a new member of staff loose
    on it -- wants a copy from *this minute*, not from whenever the program
    happened to start.
    """
    try:
        backups.run(force=True)
    except OSError as exc:
        return go("/settings", err=f"{exc}")
    return go("/settings", msg="set.backup_done")


@app.get("/settings/backup")
def settings_backup() -> FileResponse:
    """Download a snapshot of everything: the database and the attachments.

    This used to be the bare database file. Attachments are stored beside it
    rather than inside it, so that download would have quietly left out every
    scanned invoice -- and the gap would only have shown up during a restore.
    """
    stamp = date.today().isoformat()
    tmp = TemporaryDirectory()
    target = Path(tmp.name) / f"carservice-backup-{stamp}.zip"
    backup_archive(target)
    # The temporary directory is kept alive by the response's background task
    # so the file still exists while it is being streamed to the browser.
    response = FileResponse(
        target,
        media_type="application/octet-stream",
        filename=target.name,
    )
    response.background = _cleanup(tmp)
    return response


@app.get("/settings/backup.xlsx")
def settings_backup_excel(request: Request, conn: Connection = Depends(get_conn)):
    """Download every record as an Excel workbook.

    Not a backup, and the file says so on its first sheet. This is the copy
    that stays readable when the software is not: an accountant, an auditor
    or a buyer can open it, and so can you in five years when none of this is
    installed anywhere.
    """
    stamp = date.today().isoformat()
    tmp = TemporaryDirectory()
    target = Path(tmp.name) / f"carservice-records-{stamp}.xlsx"

    try:
        exporting.write_workbook(target, conn)
    except ModuleNotFoundError:
        # Shipped as a dependency, but an old virtual environment may predate
        # it. Say what is missing rather than returning a broken download.
        tmp.cleanup()
        lang = current_lang(request, repo.get_settings(conn))
        return go("/settings", err=t("set.excel_unavailable", lang))

    response = FileResponse(
        target,
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        filename=target.name,
    )
    response.background = _cleanup(tmp)
    return response


def _cleanup(tmp: TemporaryDirectory):
    from starlette.background import BackgroundTask

    return BackgroundTask(tmp.cleanup)


# --------------------------------------------------------------------------
# Small JSON endpoints used by the invoice form
# --------------------------------------------------------------------------

@app.get("/api/customers")
def api_customers(
    request: Request,
    q: str = "",
    limit: int = 50,
    conn: Connection = Depends(get_conn),
) -> JSONResponse:
    """Customers matching what somebody has typed, for the picker on the forms.

    The forms used to render every customer as an ``<option>``: four thousand
    of them, 1.7 MB of HTML on a page with two fields worth filling in, and a
    dropdown nobody could find anybody in. Now the page carries the fifty most
    recent and asks here for the rest as the name is typed.

    The alert fields come along so that choosing a flagged customer still
    raises the warning dialog immediately, with no second request at the one
    moment it matters.
    """
    lang = current_lang(request, repo.get_settings(conn))
    rows = repo.list_customers(conn, search=q.strip(), limit=max(1, min(limit, 200)))
    return JSONResponse(
        [
            {
                "id": c["id"],
                "label": _customer_label(c),
                "alert_level": c["alert_level"] or "",
                "alert_label": t(f"alert.{c['alert_level']}", lang) if c["alert_level"] else "",
                "alert_note": c["alert_note"] or "",
                "alert_when": c["alert_set_on"] or "",
            }
            for c in rows
        ]
    )


def _customer_label(c: Any) -> str:
    """"Name — phone", the same shape the template writes into an option."""
    name = c["name"] or ""
    return f"{name} — {c['phone']}" if c["phone"] else name


@app.get("/api/customers/{customer_id}/vehicles")
def api_customer_vehicles(
    customer_id: int, conn: Connection = Depends(get_conn)
) -> JSONResponse:
    """Vehicles belonging to one customer, so choosing a customer on the
    invoice form narrows the vehicle list without reloading the page."""
    vehicles = repo.list_vehicles(conn, customer_id=customer_id)
    return JSONResponse(
        [
            {
                "id": v["id"],
                "label": " — ".join(
                    part for part in [v["plate_no"], f"{v['make']} {v['model']}".strip()]
                    if part
                ),
                "odometer": v["odometer"],
            }
            for v in vehicles
        ]
    )


@app.get("/api/catalog")
def api_catalog(conn: Connection = Depends(get_conn)) -> JSONResponse:
    """The catalogue, for the item picker on each invoice line."""
    items = repo.list_catalog(conn)
    return JSONResponse(
        [
            {
                "id": i["id"],
                "code": i["code"],
                "name_en": i["name_en"],
                "name_ar": i["name_ar"],
                "kind": i["kind"],
                "unit": i["unit"],
                "price": str(from_minor(i["unit_price_minor"])),
            }
            for i in items
        ]
    )


@app.get("/api/preview-totals")
def api_preview_totals(
    qty: list[str] = Query(default=[]),
    price: list[str] = Query(default=[]),
    discount: str = "0",
    vat_rate: str = "15",
    include_vat: int = 0,
) -> JSONResponse:
    """Server-side totals, used by the automated tests to confirm that the
    figures the browser shows match the figures the server will store."""
    lines = []
    for q, p in zip(qty, price, strict=False):
        try:
            lines.append((forms.quantity(q), forms.money(p)))
        except FormError:
            continue
    totals = compute_totals(
        lines,
        vat_rate_bp=forms.vat_rate(vat_rate),
        discount_minor=forms.money(discount),
        prices_include_vat=bool(include_vat),
    )
    return JSONResponse(totals.as_dict())


@app.get("/healthz")
def healthz() -> JSONResponse:
    """Liveness check, used by Docker and by the deployment scripts."""
    return JSONResponse({"status": "ok", "database": str(db_path())})


def run() -> None:
    """Entry point for ``python -m app.main`` and the run scripts."""
    import uvicorn

    host = os.environ.get("CARSERVICE_HOST", "127.0.0.1")
    port = int(os.environ.get("CARSERVICE_PORT", "8000"))
    uvicorn.run("app.main:app", host=host, port=port, reload=False)


if __name__ == "__main__":
    run()


# ---------------------------------------------------------------------------
# Inspections — the check that happens before anyone quotes
# ---------------------------------------------------------------------------


def _catalog_json(catalog: Any) -> list[dict[str, Any]]:
    """The catalogue as plain dictionaries, for embedding in a page.

    Shared so every line editor sees the same shape; a second copy of this
    drifting from the first is how one screen starts filling prices in and
    another stops.
    """
    return [
        {
            "id": i["id"],
            "name_en": i["name_en"],
            "name_ar": i["name_ar"],
            "kind": i["kind"],
            "unit": i["unit"],
            "price": str(from_minor(i["unit_price_minor"])),
        }
        for i in catalog
    ]


def _inspection_form_context(
    conn: Connection, *, inspection: Any = None, items: Any = None, error: str = ""
) -> dict[str, Any]:
    return {
        "inspection": inspection,
        "items": items or [],
        "customers": repo.list_customers(conn),
        "vehicles": repo.list_vehicles(conn),
        "catalog": repo.list_catalog(conn),
        "issues": repo.list_known_issues(conn),
        "checklist": repo.DEFAULT_CHECKLIST,
        "error": error,
    }


def _inspection_payload(
    *,
    customer_id: str,
    vehicle_id: str,
    inspected_on: str,
    odometer: str,
    technician: str,
    summary: str,
    notes: str,
    status: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "customer_id": forms.opt_int(customer_id),
        "vehicle_id": forms.opt_int(vehicle_id),
        "inspected_on": forms.iso_date(inspected_on, default_today=True),
        "odometer": forms.opt_int(odometer),
        "technician": forms.text(technician),
        "summary": forms.text(summary),
        "notes": forms.text(notes),
    }
    if status is not None:
        data["status"] = forms.one_of(
            status, ("draft", "checked"), default="draft"
        )
    if data["customer_id"] is None:
        raise FormError("Choose a customer for this check.")
    return data


@app.get("/inspections", response_class=HTMLResponse)
def inspections_list(
    request: Request,
    q: str = "",
    status: str = "",
    page: int = 1,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    inspections = repo.page_inspections(conn, search=q, status=status, page=page)
    return render(
        request, conn, "inspections_list.html",
        inspections=inspections,
        page=inspections,
        q=q, status=status,
    )


@app.get("/inspections/new", response_class=HTMLResponse)
def inspection_new(
    request: Request,
    customer_id: int | None = None,
    vehicle_id: int | None = None,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request, conn, "inspection_form.html",
        preset_customer_id=customer_id,
        preset_vehicle_id=vehicle_id,
        **_inspection_form_context(conn),
    )


@app.post("/inspections/new")
def inspection_create(
    request: Request,
    customer_id: str = Form(""),
    vehicle_id: str = Form(""),
    inspected_on: str = Form(""),
    odometer: str = Form(""),
    technician: str = Form(""),
    summary: str = Form(""),
    notes: str = Form(""),
    status: str = Form("draft"),
    item_area: list[str] = Form([]),
    item_area_ar: list[str] = Form([]),
    item_condition: list[str] = Form([]),
    item_finding: list[str] = Form([]),
    item_finding_ar: list[str] = Form([]),
    item_issue_id: list[str] = Form([]),
    item_catalog_id: list[str] = Form([]),
    item_qty: list[str] = Form([]),
    item_price: list[str] = Form([]),
    item_quote: list[str] = Form([]),
    conn: Connection = Depends(get_conn),
):
    try:
        header = _inspection_payload(
            customer_id=customer_id, vehicle_id=vehicle_id,
            inspected_on=inspected_on, odometer=odometer, technician=technician,
            summary=summary, notes=notes, status=status,
        )
        items = forms.parse_inspection_items(
            areas=item_area, areas_ar=item_area_ar, conditions=item_condition,
            findings=item_finding, findings_ar=item_finding_ar,
            issue_ids=item_issue_id, catalog_ids=item_catalog_id,
            quantities=item_qty, prices=item_price, quote_flags=item_quote,
        )
    except FormError as exc:
        return render(
            request, conn, "inspection_form.html",
            preset_customer_id=forms.opt_int(customer_id),
            preset_vehicle_id=forms.opt_int(vehicle_id),
            **_inspection_form_context(conn, error=str(exc)),
        )

    inspection_id = repo.create_inspection(conn, header, items)
    return go(f"/inspections/{inspection_id}")


@app.get("/inspections/{inspection_id}", response_class=HTMLResponse)
def inspection_detail(
    request: Request, inspection_id: int, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request, conn, "inspection_detail.html",
        inspection=repo.get_inspection(conn, inspection_id),
        items=repo.get_inspection_items(conn, inspection_id),
    )


@app.get("/inspections/{inspection_id}/edit", response_class=HTMLResponse)
def inspection_edit(
    request: Request, inspection_id: int, conn: Connection = Depends(get_conn)
) -> HTMLResponse:
    return render(
        request, conn, "inspection_form.html",
        preset_customer_id=None, preset_vehicle_id=None,
        **_inspection_form_context(
            conn,
            inspection=repo.get_inspection(conn, inspection_id),
            items=repo.get_inspection_items(conn, inspection_id),
        ),
    )


@app.post("/inspections/{inspection_id}/edit")
def inspection_save(
    request: Request,
    inspection_id: int,
    customer_id: str = Form(""),
    vehicle_id: str = Form(""),
    inspected_on: str = Form(""),
    odometer: str = Form(""),
    technician: str = Form(""),
    summary: str = Form(""),
    notes: str = Form(""),
    status: str = Form("draft"),
    item_area: list[str] = Form([]),
    item_area_ar: list[str] = Form([]),
    item_condition: list[str] = Form([]),
    item_finding: list[str] = Form([]),
    item_finding_ar: list[str] = Form([]),
    item_issue_id: list[str] = Form([]),
    item_catalog_id: list[str] = Form([]),
    item_qty: list[str] = Form([]),
    item_price: list[str] = Form([]),
    item_quote: list[str] = Form([]),
    conn: Connection = Depends(get_conn),
):
    try:
        header = _inspection_payload(
            customer_id=customer_id, vehicle_id=vehicle_id,
            inspected_on=inspected_on, odometer=odometer, technician=technician,
            summary=summary, notes=notes, status=status,
        )
        items = forms.parse_inspection_items(
            areas=item_area, areas_ar=item_area_ar, conditions=item_condition,
            findings=item_finding, findings_ar=item_finding_ar,
            issue_ids=item_issue_id, catalog_ids=item_catalog_id,
            quantities=item_qty, prices=item_price, quote_flags=item_quote,
        )
        repo.update_inspection(conn, inspection_id, header, items)
    except (FormError, repo.InUse) as exc:
        return render(
            request, conn, "inspection_form.html",
            preset_customer_id=None, preset_vehicle_id=None,
            **_inspection_form_context(
                conn,
                inspection=repo.get_inspection(conn, inspection_id),
                items=repo.get_inspection_items(conn, inspection_id),
                error=str(exc),
            ),
        )
    return go(f"/inspections/{inspection_id}")


@app.post("/inspections/{inspection_id}/estimate")
def inspection_to_estimate(
    request: Request, inspection_id: int, conn: Connection = Depends(get_conn)
):
    try:
        estimate_id = repo.convert_inspection_to_estimate(conn, inspection_id)
    except repo.InUse as exc:
        return go(f"/inspections/{inspection_id}", err=str(exc))
    return go(f"/estimates/{estimate_id}/edit")


@app.get("/inspections/{inspection_id}/print", response_class=HTMLResponse)
def inspection_print(
    inspection_id: int,
    request: Request,
    conn: Connection = Depends(get_conn),
    autoprint: int = 1,
) -> HTMLResponse:
    return render(
        request,
        conn,
        "inspection_print.html",
        inspection=repo.get_inspection(conn, inspection_id),
        items=repo.get_inspection_items(conn, inspection_id),
        autoprint=bool(autoprint),
        logo_uri=repo.logo_data_uri(conn),
    )
