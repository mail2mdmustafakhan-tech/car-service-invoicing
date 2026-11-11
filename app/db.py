"""Database connection and schema migrations.

The whole application stores its data in **one SQLite file**. There is no
database server to install, configure, start or patch -- backing up the system
means copying that one file. For a single service centre this is not a
compromise; SQLite comfortably handles far more invoices than a workshop will
ever write.

Schema changes are applied by dropping a numbered ``.sql`` file into
``app/migrations/``. On every start-up the application runs any file it has
not run before, in filename order, and records it in ``schema_migrations``.
That means upgrading is just "pull the new code and restart" -- never a manual
database step.
"""

from __future__ import annotations

import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

#: Where the migration ``.sql`` files live.
MIGRATIONS_DIR = Path(__file__).parent / "migrations"

#: Default location of the database file, overridable with the
#: ``CARSERVICE_DB`` environment variable (the Docker setup points it at a
#: mounted volume so the data outlives the container).
DEFAULT_DB_PATH = Path("data") / "carservice.db"


def db_path() -> Path:
    """Resolve the database file location."""
    return Path(os.environ.get("CARSERVICE_DB", DEFAULT_DB_PATH))


def connect(path: Path | str | None = None) -> sqlite3.Connection:
    """Open a configured connection.

    Three settings matter and are applied to every connection:

    ``row_factory``
        Rows come back as mappings, so templates can say ``invoice["total"]``
        instead of counting columns.
    ``foreign_keys``
        SQLite leaves these *off* by default. Without it, deleting a customer
        would silently orphan their vehicles and invoices.
    ``journal_mode = WAL``
        Lets the printable-invoice view be read while another page is being
        saved, instead of briefly locking.

    ``check_same_thread=False``
        SQLite's Python driver refuses by default to let a connection be
        touched from a thread other than the one that opened it. The web
        framework runs each request's handler on a worker thread, and the
        thread that opens the connection is not guaranteed to be the one that
        closes it -- which made this fail intermittently. Turning the check
        off is safe *because of how connections are used here*: one
        connection is opened per request, used by that request alone, and
        closed when it ends. No connection is ever shared between requests,
        so there is nothing for two threads to race over.
    """
    target = Path(path) if path is not None else db_path()
    if str(target) != ":memory:":
        target.parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target, timeout=15.0, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA synchronous = NORMAL")
    return conn


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[sqlite3.Connection]:
    """Run a block of statements as one all-or-nothing unit.

    If the block raises, every change inside it is rolled back. Used wherever
    more than one table is written together -- saving an invoice writes the
    header, replaces its lines and recalculates the totals, and a half-written
    invoice would be worse than no invoice.
    """
    try:
        yield conn
    except Exception:
        conn.rollback()
        raise
    else:
        conn.commit()


# --------------------------------------------------------------------------
# Migrations
# --------------------------------------------------------------------------

def _ensure_migrations_table(conn: sqlite3.Connection) -> None:
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS schema_migrations (
            filename   TEXT PRIMARY KEY,
            applied_at TEXT NOT NULL DEFAULT (datetime('now'))
        )
        """
    )
    conn.commit()


def applied_migrations(conn: sqlite3.Connection) -> set[str]:
    """Filenames of migrations already run against this database."""
    _ensure_migrations_table(conn)
    rows = conn.execute("SELECT filename FROM schema_migrations").fetchall()
    return {row["filename"] for row in rows}


def pending_migrations(conn: sqlite3.Connection) -> list[Path]:
    """Migration files not yet applied, in the order they should run."""
    done = applied_migrations(conn)
    files = sorted(MIGRATIONS_DIR.glob("*.sql"), key=lambda p: p.name)
    return [f for f in files if f.name not in done]


def migrate(conn: sqlite3.Connection, *, verbose: bool = False) -> list[str]:
    """Apply every pending migration. Returns the filenames that ran.

    Safe to call on every start-up: already-applied files are skipped.
    """
    ran: list[str] = []
    for sql_file in pending_migrations(conn):
        script = sql_file.read_text(encoding="utf-8")
        # Each migration is one transaction: if statement 9 of 10 fails, the
        # database is left exactly as it was rather than half-upgraded.
        try:
            conn.executescript(f"BEGIN;\n{script}\nCOMMIT;")
        except Exception:
            conn.rollback()
            raise RuntimeError(f"Migration failed: {sql_file.name}") from None
        conn.execute(
            "INSERT INTO schema_migrations (filename) VALUES (?)", (sql_file.name,)
        )
        conn.commit()
        ran.append(sql_file.name)
        if verbose:
            print(f"  applied {sql_file.name}")
    return ran


def init_db(path: Path | str | None = None, *, verbose: bool = False) -> sqlite3.Connection:
    """Open the database and bring the schema up to date."""
    conn = connect(path)
    migrate(conn, verbose=verbose)
    return conn


@contextmanager
def session(path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Open a connection for one unit of work and close it afterwards.

    Used as the FastAPI request dependency. Opening a SQLite connection costs
    microseconds, so a connection per request keeps things simple and avoids
    any cross-thread sharing problems.
    """
    conn = connect(path)
    try:
        yield conn
    finally:
        conn.close()


def backup_to(destination: Path | str, source: Path | str | None = None) -> Path:
    """Make a consistent copy of the database, safe to run while in use.

    Uses SQLite's own online backup, which copies a coherent snapshot even if
    an invoice is being saved at that moment -- unlike copying the file by
    hand, which can catch it mid-write.
    """
    dest = Path(destination)
    dest.parent.mkdir(parents=True, exist_ok=True)
    src = connect(source)
    try:
        out = sqlite3.connect(dest)
        try:
            src.backup(out)
        finally:
            out.close()
    finally:
        src.close()
    return dest
