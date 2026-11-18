"""Daily backups, taken without anybody having to remember.

A backup that depends on somebody pressing a button is a backup that exists
until the week it is needed. So this takes one by itself, keeps a sensible
number of them, and says plainly on the Settings page when it last worked --
because the failure that matters is the silent one, where backups stopped in
March and nobody finds out until the disk dies in September.

Three decisions shape the whole file:

**It runs when the application runs, not on a schedule the computer keeps.**
Windows Task Scheduler would be the obvious home for this, and it is the
wrong one here: it is a separate thing to set up, a separate thing to get
wrong, and it is invisible from inside this application, so Settings could
never honestly say whether backups were still happening. Instead the
application takes one at startup if the day has none, and checks again every
hour while it is running. The workshop PC gets switched on in the morning and
off at night, so "on startup" is in practice "every working day", and a
machine left running over a date change is covered by the hourly check.

**Older copies thin out rather than piling up or vanishing.** Everything from
the last fortnight is kept, and before that one per month for a year. Fourteen
daily copies answer "undo what we did on Tuesday"; the monthly ones answer
"what did this customer's record say last spring", which is the question that
turns up in an argument about an invoice.

**A backup beside the database is not yet a backup.** If the disk fails it
takes both. This module cannot fix that -- it has no business reaching into
Google Drive or a USB stick on its own -- so Settings says so in as many
words, and the folder is somewhere easy to copy from.
"""

from __future__ import annotations

import os
import re
import threading
import time
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

from .db import backup_archive, db_path

#: Name of every automatic backup: the date is the identity, so a second run
#: on the same day replaces the first rather than making a near-duplicate.
PATTERN = "carservice-backup-{date}.zip"
_NAME = re.compile(r"carservice-backup-(\d{4}-\d{2}-\d{2})\.zip$")

#: Keep every backup from the last fortnight...
KEEP_DAYS = 14
#: ...and before that, the newest one from each of the twelve most recent
#: months that have a backup at all. Not the last twelve calendar months:
#: a workshop with one copy from years ago and nothing since should keep
#: it, not have it deleted for being old. The promise is twelve months of
#: history, not twelve months of freshness.
KEEP_MONTHS = 12

#: How often a running application looks at the calendar again.
CHECK_EVERY = timedelta(hours=1)

#: Set to 1 to turn the automatic backup off. Here for the test suite, which
#: must not write backups into whatever directory it happens to run in, and
#: for anyone running a second copy of the application against the same data.
OFF = "CARSERVICE_NO_AUTOBACKUP"

LOG_NAME = "backup-log.txt"


def backups_dir() -> Path:
    """Where backups are kept: ``backups`` beside the database.

    Beside it on purpose. The point of this folder is that somebody can find
    it, see files with dates on them, and drag the lot onto a USB stick
    without being told where to look.
    """
    return db_path().parent / "backups"


# ---------------------------------------------------------------------------
# What is already there
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Backup:
    path: Path
    day: date
    bytes: int

    @property
    def name(self) -> str:
        return self.path.name


def existing() -> list[Backup]:
    """Every automatic backup on disk, newest first."""
    folder = backups_dir()
    if not folder.is_dir():
        return []

    found = []
    for item in folder.iterdir():
        match = _NAME.search(item.name)
        if not match or not item.is_file():
            continue
        try:
            day = date.fromisoformat(match.group(1))
        except ValueError:          # a date-shaped name that is not a date
            continue
        found.append(Backup(item, day, item.stat().st_size))
    return sorted(found, key=lambda b: b.day, reverse=True)


def is_due(today: date | None = None) -> bool:
    """Whether today still needs one."""
    today = today or date.today()
    return not any(b.day >= today for b in existing())


# ---------------------------------------------------------------------------
# Keeping a sensible number of them
# ---------------------------------------------------------------------------

def _keepers(backups: list[Backup], today: date) -> set[Path]:
    """Which of *backups* to keep: a fortnight of days, then a year of months.

    Written as "which to keep" rather than "which to delete" deliberately.
    The two are not the same when the rules are wrong: a bug in a keep-list
    leaves extra files lying about, and a bug in a delete-list destroys
    somebody's only copy of last March.
    """
    # A date in the future counts as recent -- a wrong clock, or a file
    # copied back from another machine, is not evidence that a backup is
    # disposable.
    keep = {b.path for b in backups if (today - b.day).days < KEEP_DAYS}

    months: dict[tuple[int, int], Backup] = {}
    for b in backups:
        if b.path in keep:
            continue
        key = (b.day.year, b.day.month)
        if key not in months or b.day > months[key].day:
            months[key] = b

    for key in sorted(months, reverse=True)[:KEEP_MONTHS]:
        keep.add(months[key].path)
    return keep


def prune(today: date | None = None) -> list[Path]:
    """Delete the backups the rules above do not keep. Returns what went."""
    today = today or date.today()
    backups = existing()
    if not backups:
        return []

    keep = _keepers(backups, today)
    if not keep:
        # Nothing matched the rules at all. That should not be reachable --
        # the newest month is always among the months kept -- so if it
        # happens, the rules are wrong and this is not the moment to act on
        # them confidently. Keep the newest and delete nothing else.
        #
        # Worth being exact about what this protects: not "the last file",
        # which an earlier version checked and which is a different and much
        # weaker promise. It protects against ever emptying the folder,
        # however many are in it.
        keep = {backups[0].path}
    removed = []
    for b in backups:
        if b.path in keep:
            continue
        try:
            b.path.unlink()
            removed.append(b.path)
        except OSError:
            # A file held open by a virus scanner or a file manager. It will
            # be offered up again tomorrow; failing the whole backup over it
            # would be a poor trade.
            pass
    return removed


# ---------------------------------------------------------------------------
# Taking one
# ---------------------------------------------------------------------------

def _log(line: str) -> None:
    """Append one line to a log a person can read without any tooling."""
    folder = backups_dir()
    try:
        folder.mkdir(parents=True, exist_ok=True)
        with (folder / LOG_NAME).open("a", encoding="utf-8") as handle:
            handle.write(f"{datetime.now():%Y-%m-%d %H:%M}  {line}\n")
    except OSError:
        pass        # a backup that worked must not fail over its own log


def last_log_line() -> str:
    try:
        lines = [
            line.strip()
            for line in (backups_dir() / LOG_NAME).read_text(encoding="utf-8").splitlines()
            if line.strip()
        ]
    except OSError:
        return ""
    return lines[-1] if lines else ""


def run(today: date | None = None, *, force: bool = False) -> Backup | None:
    """Take today's backup if it is due. Returns it, or ``None`` if not due.

    Raises whatever went wrong if it went wrong -- the caller decides whether
    that is worth interrupting somebody for. The automatic path logs it and
    carries on; the button on the Settings page shows it.
    """
    today = today or date.today()
    if not force and not is_due(today):
        return None

    folder = backups_dir()
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / PATTERN.format(date=today.isoformat())

    # Written beside its final name and then moved, so an interrupted backup
    # cannot leave a half-written zip wearing today's date -- which would
    # look like a good backup and satisfy `is_due` for the rest of the day.
    working = folder / f".{target.name}.part"
    try:
        backup_archive(working)
        working.replace(target)
    except BaseException as exc:
        working.unlink(missing_ok=True)
        _log(f"FAILED  {type(exc).__name__}: {exc}")
        raise

    made = Backup(target, today, target.stat().st_size)
    gone = prune(today)
    _log(
        f"ok  {made.name}  {made.bytes / 1_000_000:.1f} MB"
        + (f"  (removed {len(gone)} older)" if gone else "")
    )
    return made


# ---------------------------------------------------------------------------
# Doing it by itself
# ---------------------------------------------------------------------------

def _try_once() -> None:
    try:
        run()
    except Exception:
        pass        # already logged, and a failed backup must not stop the app


def start(stop: threading.Event | None = None) -> threading.Thread | None:
    """Take one now if due, then keep an eye on the calendar.

    Returns the watching thread, or ``None`` when switched off.

    On a background thread because this must not hold up the first page: a
    backup of a large register takes a second or two, and the person starting
    the application is usually standing at the counter with a customer.
    """
    if os.environ.get(OFF) == "1":
        return None

    stop = stop or threading.Event()

    def loop() -> None:
        _try_once()
        while not stop.wait(CHECK_EVERY.total_seconds()):
            _try_once()

    thread = threading.Thread(target=loop, name="daily-backup", daemon=True)
    thread.start()
    return thread


# ---------------------------------------------------------------------------
# What Settings shows
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class Status:
    folder: Path
    backups: list[Backup]
    last_line: str
    enabled: bool

    @property
    def latest(self) -> Backup | None:
        return self.backups[0] if self.backups else None

    @property
    def count(self) -> int:
        return len(self.backups)

    @property
    def total_bytes(self) -> int:
        return sum(b.bytes for b in self.backups)

    @property
    def days_since(self) -> int | None:
        return None if not self.latest else (date.today() - self.latest.day).days

    @property
    def stale(self) -> bool:
        """Worth saying out loud on the page.

        Two days rather than one: a workshop closes on a Friday, and a page
        that cries about a missing backup every weekend is a page whose
        warnings stop being read.
        """
        if not self.enabled:
            return False
        return self.latest is None or (self.days_since or 0) > 2


def status() -> Status:
    return Status(
        folder=backups_dir(),
        backups=existing(),
        last_line=last_log_line(),
        enabled=os.environ.get(OFF) != "1",
    )


def wait_for_quiet(seconds: float = 2.0) -> None:
    """Only for tests: let a just-started backup thread finish its first run."""
    deadline = time.monotonic() + seconds
    while time.monotonic() < deadline and is_due():
        time.sleep(0.05)
