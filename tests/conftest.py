"""Shared test fixtures.

Each test gets its own throwaway database in a temporary directory, so tests
never see each other's data and never touch the real ``data/carservice.db``.
"""

from __future__ import annotations

import os
import sqlite3
import tempfile
from collections.abc import Iterator
from pathlib import Path

import pytest

# The application reads this when it opens a connection, so it has to be set
# before `app.main` is imported anywhere.
_TMP = tempfile.TemporaryDirectory()
os.environ.setdefault("CARSERVICE_DB", str(Path(_TMP.name) / "test.db"))

from app.db import init_db  # noqa: E402  (import after the env var is set)


@pytest.fixture()
def conn(tmp_path: Path) -> Iterator[sqlite3.Connection]:
    """A migrated, empty database for one test."""
    connection = init_db(tmp_path / "unit.db")
    try:
        yield connection
    finally:
        connection.close()


@pytest.fixture()
def client(tmp_path, monkeypatch) -> Iterator:
    """A test client wired to its own fresh database."""
    from fastapi.testclient import TestClient

    db_file = tmp_path / "web.db"
    monkeypatch.setenv("CARSERVICE_DB", str(db_file))

    import app.db as db_module

    monkeypatch.setattr(db_module, "DEFAULT_DB_PATH", db_file)

    from app.main import app as fastapi_app

    with TestClient(fastapi_app) as test_client:
        yield test_client


@pytest.fixture()
def web_db(tmp_path) -> Path:
    """The database the `client` fixture is wired to.

    `conn` is a *different* database, which catches people out: data created
    through it is invisible to the web client and vice versa. When a test
    needs to look at what the application actually stored, it opens this one.
    """
    return tmp_path / "web.db"


@pytest.fixture()
def read_web_db(web_db):
    """Open the web client's database read-only, for checking what was saved.

    Returns a callable so the connection is opened at the moment of asking --
    the file does not exist until the client has started.
    """
    import contextlib

    @contextlib.contextmanager
    def _open() -> Iterator[sqlite3.Connection]:
        connection = sqlite3.connect(web_db)
        connection.row_factory = sqlite3.Row
        try:
            yield connection
        finally:
            connection.close()

    return _open


@pytest.fixture()
def shop(client):
    """A client with a customer, a vehicle and a catalogue item already set up.

    Most web tests need all three before they can do anything interesting, so
    creating them once here keeps the tests themselves about one thing each.
    """
    client.post(
        "/settings",
        data={
            "business_name_en": "Test Auto Service",
            "vat_rate": "15",
            "currency_code": "SAR",
            "invoice_prefix": "T-",
            "next_invoice_seq": "1",
            "default_language": "en",
        },
    )
    client.post("/customers/new", data={"name": "Test Customer", "phone": "0500000000"})
    client.post(
        "/vehicles/new",
        data={"customer_id": "1", "plate_no": "TEST 1", "make": "Toyota", "model": "Hilux"},
    )
    client.post(
        "/catalog/new",
        data={
            "name_en": "Oil change",
            "name_ar": "تغيير زيت",
            "kind": "service",
            "unit": "pcs",
            "unit_price": "150",
            "code": "OIL",
        },
    )
    return client
