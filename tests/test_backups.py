"""The automatic daily backup.

Two things are being guarded here and they are not equally dangerous.

That a backup gets taken is the obvious one, and the easy one: if it does not
happen, the Settings page says so in large letters.

That the *pruning* is right is the dangerous one. A mistake in which files to
keep deletes somebody's only copy of last March, silently, and is discovered
only when they go looking for it. So most of this file is about which files
survive, including the cases nobody plans for: a clock set wrongly, a single
backup, a folder somebody has put their own files in.
"""

from __future__ import annotations

import os
import zipfile
from datetime import date, timedelta
from pathlib import Path

import pytest

from app import backups, db


@pytest.fixture()
def shop_data(tmp_path, monkeypatch):
    """A database with a row in it, and a backups folder beside it."""
    data = tmp_path / "data"
    data.mkdir()
    monkeypatch.setenv("CARSERVICE_DB", str(data / "carservice.db"))
    monkeypatch.delenv(backups.OFF, raising=False)

    conn = db.init_db(data / "carservice.db")
    conn.execute("INSERT INTO customers (name, phone) VALUES ('Findable', '0500')")
    conn.commit()
    conn.close()
    return data


def _place(folder: Path, *days: date, size: int = 40) -> None:
    """Put backup-shaped files on disk without the cost of making real ones."""
    folder.mkdir(parents=True, exist_ok=True)
    for day in days:
        (folder / backups.PATTERN.format(date=day.isoformat())).write_bytes(b"x" * size)


# ---------------------------------------------------------------------------
# Taking one
# ---------------------------------------------------------------------------

def test_a_backup_holds_the_database_and_the_attachments(shop_data):
    (shop_data / "attachments").mkdir()
    (shop_data / "attachments" / "scan.pdf").write_bytes(b"%PDF-1.4 pretend")

    made = backups.run()

    assert made is not None
    assert made.path.parent == shop_data / "backups"
    with zipfile.ZipFile(made.path) as archive:
        names = archive.namelist()
    assert "carservice.db" in names
    assert "attachments/scan.pdf" in names, (
        "a backup without the scans is the kind you only discover while restoring"
    )


def test_the_backup_can_actually_be_opened_as_a_database(shop_data):
    """The point of the whole exercise. A zip that holds a corrupt file is
    not a backup, it is a reassuring noise."""
    import sqlite3

    made = backups.run()
    restored = shop_data / "restored"
    with zipfile.ZipFile(made.path) as archive:
        archive.extractall(restored)

    conn = sqlite3.connect(restored / "carservice.db")
    assert conn.execute("SELECT name FROM customers").fetchone()[0] == "Findable"
    conn.close()


def test_one_a_day_and_not_more(shop_data):
    assert backups.run() is not None
    assert backups.run() is None, "a second start on the same day made a second copy"
    assert len(backups.existing()) == 1


def test_but_it_can_always_be_asked_for(shop_data):
    """The button on the Settings page, for somebody about to do something
    they are nervous about."""
    backups.run()
    assert backups.run(force=True) is not None
    assert len(backups.existing()) == 1, "forcing should replace today's, not pile up"


def test_a_failed_backup_leaves_no_file_wearing_todays_date(shop_data, monkeypatch):
    """The nastiest failure available here: a half-written zip dated today
    looks like a good backup, satisfies "already done" for the rest of the
    day, and is worthless. So the file is written under a temporary name and
    moved into place only once it is whole.

    The failure has to happen *after* some bytes are on disk, or this proves
    nothing -- the first version of this test raised before writing anything,
    which a backup written straight to its final name passes just as happily.
    """
    def fail_midway(destination, *_args, **_kwargs):
        Path(destination).write_bytes(b"PK\x03\x04 half a zip")
        raise OSError("disk full")

    monkeypatch.setattr(backups, "backup_archive", fail_midway)
    with pytest.raises(OSError):
        backups.run()

    assert backups.existing() == [], "a broken zip is sitting there wearing today's date"
    assert backups.is_due() is True, "and the day now counts as backed up"
    assert "FAILED" in backups.last_log_line()
    assert list(backups.backups_dir().glob("*.part")) == [], "the scrap was left behind"


def test_what_happened_is_written_down(shop_data):
    backups.run()
    line = backups.last_log_line()
    assert "ok" in line
    assert date.today().isoformat() in line


# ---------------------------------------------------------------------------
# Which ones survive -- the dangerous half
# ---------------------------------------------------------------------------

def test_the_last_fortnight_is_kept_in_full(shop_data):
    today = date.today()
    _place(backups.backups_dir(), *(today - timedelta(days=n) for n in range(14)))

    backups.prune(today)

    assert len(backups.existing()) == 14


def test_an_old_backup_is_not_deleted_merely_for_being_old(shop_data):
    """The monthly rule keeps the twelve most recent months that *have* a
    backup, not the last twelve calendar months.

    The difference matters for exactly the case where it would hurt: a
    workshop with one copy from years ago and nothing since. A calendar rule
    would delete it for being older than a year. This keeps it, because
    twelve months of history is the promise -- not twelve months of
    freshness.
    """
    today = date(2026, 11, 18)
    _place(backups.backups_dir(), today, date(2019, 1, 1))

    backups.prune(today)

    assert date(2019, 1, 1) in {b.day for b in backups.existing()}


def test_older_than_a_fortnight_thins_to_one_a_month(shop_data):
    today = date(2026, 11, 18)
    folder = backups.backups_dir()
    _place(folder, *(today - timedelta(days=n) for n in range(14)))       # daily
    _place(folder, date(2026, 9, 2), date(2026, 9, 14), date(2026, 9, 28))
    _place(folder, date(2026, 8, 3), date(2026, 8, 30))

    backups.prune(today)

    kept = {b.day for b in backups.existing()}
    assert date(2026, 9, 28) in kept, "the newest of a month is the one to keep"
    assert date(2026, 9, 2) not in kept
    assert date(2026, 9, 14) not in kept
    assert date(2026, 8, 30) in kept
    assert date(2026, 8, 3) not in kept


def test_a_year_of_months_is_kept_and_no_more(shop_data):
    today = date(2026, 11, 18)
    folder = backups.backups_dir()
    # One on the first of every month, from three years back up to today.
    months = [
        date(y, m, 1)
        for y in (2024, 2025, 2026)
        for m in range(1, 13)
        if date(y, m, 1) <= today
    ]
    _place(folder, *months)

    backups.prune(today)
    kept = sorted(b.day for b in backups.existing())

    assert len(kept) == backups.KEEP_MONTHS
    assert kept[0] == date(2025, 12, 1)
    assert kept[-1] == date(2026, 11, 1)


def test_a_backup_dated_in_the_future_is_kept(shop_data):
    """A machine whose clock is wrong, or a file copied back from one.

    Found by accident: the test above originally placed a December file
    while pretending it was November, passed for that reason rather than the
    one it claimed, and had to be asked what it was really testing. The
    behaviour it stumbled into is the right one -- a date ahead of today is
    not evidence that a backup is disposable -- so it is pinned here on
    purpose instead.
    """
    today = date(2026, 11, 18)
    _place(backups.backups_dir(), today, date(2027, 3, 1))

    backups.prune(today)

    assert date(2027, 3, 1) in {b.day for b in backups.existing()}


def test_the_last_backup_is_never_deleted(shop_data, monkeypatch):
    """A backstop under the keep rules, tested by defeating them.

    With the rules as they stand this cannot trigger: the newest month is
    always among the months kept, so something always survives. That is
    exactly why it is worth having and worth testing deliberately -- the
    guard is insurance against a future change to those rules, and a test
    that only exercises the rules would pass with the guard deleted. This
    one was written that way first, and did.
    """
    _place(backups.backups_dir(), date(2026, 1, 1), date(2026, 2, 1))
    monkeypatch.setattr(backups, "_keepers", lambda *_: set())

    backups.prune(date(2026, 6, 1))

    remaining = backups.existing()
    assert len(remaining) == 1, (
        "with nothing marked for keeping, the folder was emptied"
    )
    assert remaining[0].day == date(2026, 2, 1), "and it kept the newest"


def test_pruning_leaves_other_peoples_files_alone(shop_data):
    """Somebody will put something in this folder. It is a folder."""
    folder = backups.backups_dir()
    _place(folder, date.today(), date(2019, 1, 1))
    (folder / "notes.txt").write_text("the Tuesday we lost the VAT number")
    (folder / "carservice-backup-before-the-import.zip").write_bytes(b"mine")

    backups.prune(date.today())

    assert (folder / "notes.txt").exists()
    assert (folder / "carservice-backup-before-the-import.zip").exists(), (
        "a name that is not a date is somebody's own copy, kept on purpose"
    )


def test_a_date_shaped_name_that_is_not_a_date_is_ignored(shop_data):
    folder = backups.backups_dir()
    folder.mkdir(parents=True, exist_ok=True)
    (folder / "carservice-backup-2026-13-45.zip").write_bytes(b"x")

    assert backups.existing() == []


# ---------------------------------------------------------------------------
# What the Settings page is told
# ---------------------------------------------------------------------------

def test_status_reports_what_is_there(shop_data):
    backups.run()
    state = backups.status()

    assert state.count == 1
    assert state.days_since == 0
    assert state.total_bytes > 0
    assert state.folder == shop_data / "backups"
    assert not state.stale


def test_a_gap_of_more_than_two_days_is_called_out(shop_data):
    _place(backups.backups_dir(), date.today() - timedelta(days=5))
    assert backups.status().stale is True


def test_a_weekend_is_not_called_out(shop_data):
    """A page that complains every Monday is a page whose warnings get
    ignored by Tuesday."""
    _place(backups.backups_dir(), date.today() - timedelta(days=2))
    assert backups.status().stale is False


def test_nothing_at_all_is_called_out(shop_data):
    assert backups.status().stale is True


def test_switched_off_means_switched_off(shop_data, monkeypatch):
    monkeypatch.setenv(backups.OFF, "1")
    assert backups.start() is None
    assert backups.status().enabled is False
    assert backups.status().stale is False, (
        "it cannot be behind on a job it is not doing"
    )


# ---------------------------------------------------------------------------
# Doing it by itself
# ---------------------------------------------------------------------------

def test_starting_the_program_takes_the_day_s_backup(shop_data):
    import threading

    stop = threading.Event()
    thread = backups.start(stop)
    try:
        backups.wait_for_quiet()
        assert len(backups.existing()) == 1
    finally:
        stop.set()
        thread.join(timeout=2)


def test_the_watcher_never_brings_the_application_down(shop_data, monkeypatch):
    """A backup that cannot be written is a problem to report, not a reason
    the workshop cannot invoice anybody."""
    import threading

    def explode(*_args, **_kwargs):
        raise OSError("disk full")

    monkeypatch.setattr(backups, "backup_archive", explode)
    stop = threading.Event()
    thread = backups.start(stop)
    try:
        thread.join(timeout=2)
        assert thread.is_alive(), "the watcher died on a failed backup"
    finally:
        stop.set()
        thread.join(timeout=2)


def test_the_settings_page_shows_the_state(shop, web_db, monkeypatch):
    page = shop.get("/settings").text
    assert "Automatic daily backup" in page
    assert "backups" in page


def test_the_button_takes_one(shop, web_db, monkeypatch):
    monkeypatch.delenv(backups.OFF, raising=False)
    monkeypatch.setenv("CARSERVICE_DB", str(web_db))

    response = shop.post("/settings/backup/now", follow_redirects=False)

    assert response.status_code in (302, 303)
    assert len(backups.existing()) == 1
    for made in backups.existing():
        os.unlink(made.path)


def test_the_page_says_so_when_backups_have_stopped(shop, monkeypatch):
    """The whole point of showing any of this. A backup that quietly stopped
    in March is discovered in September, on the day it was needed."""
    stale = backups.Status(
        folder=Path("/somewhere/backups"),
        backups=[],
        last_line="",
        enabled=True,
    )
    monkeypatch.setattr(backups, "status", lambda: stale)

    page = shop.get("/settings").text
    assert "No backup has been taken for more than two days" in page
    assert "hint warn" in page


def test_the_page_does_not_cry_wolf_when_all_is_well(shop, monkeypatch):
    fine = backups.Status(
        folder=Path("/somewhere/backups"),
        backups=[backups.Backup(Path("/somewhere/backups/x.zip"), date.today(), 1000)],
        last_line="ok",
        enabled=True,
    )
    monkeypatch.setattr(backups, "status", lambda: fine)

    assert "No backup has been taken" not in shop.get("/settings").text
