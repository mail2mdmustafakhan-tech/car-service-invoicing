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
from collections.abc import Iterator
from contextlib import asynccontextmanager
from datetime import date
from pathlib import Path
from sqlite3 import Connection, IntegrityError
from tempfile import TemporaryDirectory
from typing import Any

from fastapi import Depends, FastAPI, Form, Query, Request
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse, RedirectResponse, Response
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from . import forms
from . import repository as repo
from .db import backup_to, connect, db_path, migrate, session
from .forms import FormError
from .i18n import LANGUAGES, direction, localised, normalise, t
from .invoicing import balance_due, compute_totals, payment_state
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
    yield


app = FastAPI(
    title="Car Service Invoicing",
    description="Lightweight on-premise invoicing for a car service centre.",
    version="1.0.0",
    lifespan=lifespan,
    docs_url="/api/docs",
    redoc_url=None,
)

app.mount("/static", StaticFiles(directory=BASE_DIR / "static"), name="static")

templates = Jinja2Templates(directory=str(BASE_DIR / "templates"))
templates.env.globals.update(
    LANGUAGES=LANGUAGES,
    PDF_AVAILABLE=PDF_AVAILABLE,
    fmt_qty=format_qty,
    fmt_rate=format_rate,
    # "Cash / نقداً" -- for the printed invoice, which labels everything in
    # both languages regardless of the interface language.
    t2=lambda key: f"{t(key, 'en')} / {t(key, 'ar')}",
    from_minor=from_minor,
    from_milli=from_milli,
    payment_state=payment_state,
    balance_due=balance_due,
    today=lambda: date.today().isoformat(),
)


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

    base: dict[str, Any] = {
        "request": request,
        "settings": settings,
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
def dashboard(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    return render(
        request,
        conn,
        "dashboard.html",
        stats=repo.dashboard_stats(conn),
        recent=repo.list_invoices(conn, limit=8),
        unpaid=repo.unpaid_invoices(conn, limit=6),
        revenue=repo.monthly_revenue(conn, months=6),
        in_workshop=repo.cars_in_workshop(conn, limit=8),
    )


# --------------------------------------------------------------------------
# Customers
# --------------------------------------------------------------------------

@app.get("/customers", response_class=HTMLResponse)
def customers_list(
    request: Request,
    q: str = "",
    inactive: int = 0,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request,
        conn,
        "customers_list.html",
        customers=repo.list_customers(conn, search=q, include_inactive=bool(inactive)),
        q=q,
        inactive=inactive,
    )


@app.get("/customers/new", response_class=HTMLResponse)
def customer_new(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    return render(request, conn, "customer_form.html", customer=None, error="")


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
        }
    except FormError as exc:
        return render(request, conn, "customer_form.html", customer=None, error=str(exc))

    customer_id = repo.create_customer(conn, data)
    return go(f"/customers/{customer_id}", msg="msg.created")


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
    inactive: int = 0,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request,
        conn,
        "vehicles_list.html",
        vehicles=repo.list_vehicles(conn, search=q, include_inactive=bool(inactive)),
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
    inactive: int = 0,
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request,
        conn,
        "catalog_list.html",
        items=repo.list_catalog(
            conn, search=q, kind=kind, include_inactive=bool(inactive)
        ),
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
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "code": forms.text(code),
        "name_en": forms.required_text(name_en, field="Name"),
        "name_ar": forms.text(name_ar),
        "kind": forms.one_of(kind, ("service", "part"), default="service"),
        "unit": forms.text(unit, default="pcs"),
        "unit_price_minor": forms.money(unit_price, field="Unit price"),
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
    conn: Connection = Depends(get_conn),
):
    try:
        data = _catalog_payload(code, name_en, name_ar, kind, unit, unit_price)
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
        request, conn, "catalog_form.html", item=repo.get_catalog_item(conn, item_id), error=""
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
    is_active: str = Form(None),
    conn: Connection = Depends(get_conn),
):
    try:
        data = _catalog_payload(code, name_en, name_ar, kind, unit, unit_price, is_active)
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
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request,
        conn,
        "invoices_list.html",
        invoices=repo.list_invoices(
            conn,
            search=q,
            status=status,
            payment_state=state,
            date_from=date_from,
            date_to=date_to,
        ),
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
    status: str | None = None,
) -> dict[str, Any]:
    data: dict[str, Any] = {
        "customer_id": forms.opt_int(customer_id),
        "vehicle_id": forms.opt_int(vehicle_id),
        "issue_date": forms.iso_date(issue_date, default_today=True),
        "due_date": forms.iso_date(due_date),
        "odometer": forms.opt_int(odometer),
        "notes": forms.text(notes),
        "discount_minor": forms.money(discount, field="Discount"),
        "vat_rate_bp": forms.vat_rate(vat_rate, default=settings["vat_rate_bp"]),
        "prices_include_vat": forms.checkbox(prices_include_vat),
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
    vat_rate: str = Form(""),
    prices_include_vat: str = Form(None),
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
            status=status,
        )
        lines = forms.parse_invoice_lines(
            descriptions=item_description,
            descriptions_ar=item_description_ar,
            kinds=item_kind,
            units=item_unit,
            quantities=item_qty,
            prices=item_price,
            catalog_ids=item_catalog_id,
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
    vat_rate: str = Form(""),
    prices_include_vat: str = Form(None),
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
            status=status,
        )
        lines = forms.parse_invoice_lines(
            descriptions=item_description,
            descriptions_ar=item_description_ar,
            kinds=item_kind,
            units=item_unit,
            quantities=item_qty,
            prices=item_price,
            catalog_ids=item_catalog_id,
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
    conn: Connection = Depends(get_conn),
) -> HTMLResponse:
    return render(
        request,
        conn,
        "contracts_list.html",
        contracts=repo.list_repair_orders(conn, search=q, status=status),
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
        autoprint=bool(autoprint),
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
        autoprint=False,
        pdf=True,
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

@app.get("/settings", response_class=HTMLResponse)
def settings_page(request: Request, conn: Connection = Depends(get_conn)) -> HTMLResponse:
    return render(request, conn, "settings.html", error="")


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
    except FormError as exc:
        return render(request, conn, "settings.html", error=str(exc))

    repo.update_settings(conn, data)
    return go("/settings", msg="set.saved")


@app.get("/settings/backup")
def settings_backup() -> FileResponse:
    """Download a consistent snapshot of the database file."""
    stamp = date.today().isoformat()
    tmp = TemporaryDirectory()
    target = Path(tmp.name) / f"carservice-backup-{stamp}.db"
    backup_to(target)
    # The temporary directory is kept alive by the response's background task
    # so the file still exists while it is being streamed to the browser.
    response = FileResponse(
        target,
        media_type="application/octet-stream",
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
