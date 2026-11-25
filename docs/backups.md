# Backups

Everything about the automatic daily backup: what it does, how to stop it,
what can be changed, and what to do when it stops working.

If you read one paragraph, read this one: **the backups sit on the same disk
as your data. If that disk fails, it takes both.** Copy the `backups` folder
onto a USB stick or a cloud drive from time to time. Nothing in this software
can do that step for you, and it is the step that makes the rest worth
having.

---

## What happens on its own

You do not start backups. They start with the application.

- A backup is taken **when the program starts**, if that day does not already
  have one.
- While the program is open, it **checks again every hour**, so a computer
  left running past midnight still gets the new day's backup.
- One per day. Starting the program five times in a morning makes one
  backup, not five.

The workshop PC is switched on in the morning and off at night, so "when the
program starts" is in practice "every working day". That is the whole design:
no scheduled task to set up in Windows, nothing separate to remember, and
nothing that can be running or not running without the application knowing
about it.

### Where they go

```
D:\Mini Project\car-service-invoicing\data\backups\
    carservice-backup-2026-11-22.zip
    carservice-backup-2026-11-21.zip
    backup-log.txt
```

Each zip holds the **database and every scanned attachment** together. That
is why it is a zip and not a single file — restoring only the database would
silently lose the photographs and documents attached to jobs.

At the register's current size each one is about 2.5 MB.

### How many are kept

- **Every backup from the last 14 days.**
- Before that, **the newest one from each of the twelve most recent months
  that have a backup.**

Note the wording of the second rule: twelve months *that have one*, not the
last twelve months on the calendar. A workshop with a copy from three years
ago and nothing since keeps it. The promise is twelve months of history, not
twelve months of freshness.

Older ones are deleted. Anything in that folder whose name is not in the
`carservice-backup-DATE.zip` form is left alone, so a copy you made yourself
and named something else is safe there.

---

## Checking it is actually working

**Settings → Backup** is the page. It shows:

| | |
| --- | --- |
| **Last backup** | the date, and its size |
| **Backups kept** | how many, and what they come to in total |
| **Folder** | the full path, for copying elsewhere |

If more than **two days** pass with no backup, the page says so in amber.
Two days rather than one is deliberate — a workshop closed on Friday should
not come back to a warning every Saturday, because a warning that cries wolf
stops being read.

There is also **`backup-log.txt`** in the backups folder, one line per
attempt, in plain English:

```
2026-11-22 08:14  ok  carservice-backup-2026-11-22.zip  2.4 MB
2026-11-21 08:02  ok  carservice-backup-2026-11-21.zip  2.4 MB  (removed 1 older)
2026-11-20 09:31  FAILED  OSError: [Errno 28] No space left on device
```

### Taking one by hand

**Settings → Backup → Back up now.** Worth pressing before anything that
makes you nervous — a large import, deleting a batch, letting somebody new
loose on it. It replaces the day's backup rather than adding a second one.

**Settings → Backup → Download backup (.zip)** gives you the same thing
through the browser, which is how you get a copy onto a tablet or straight
into a cloud folder.

**Settings → Backup → Download as Excel (.xlsx)** is a different thing and
worth knowing about: every record in a workbook anyone can open. It is not a
backup you can restore from, but it is readable in twenty years without this
software, which no `.zip` of a database can promise.

---

## Restoring

1. **Stop the application** — close the black window, or press Ctrl+C in it.
2. Open `D:\Mini Project\car-service-invoicing\data`.
3. Rename the existing `carservice.db` to `carservice-before-restore.db`,
   and rename `attachments` to `attachments-before-restore`. Do not delete
   them. If the restore turns out to be the wrong backup, these are what you
   go back to.
4. Open the backup zip and extract `carservice.db` and the `attachments`
   folder into `data`, so they sit where the originals were.
5. Start the application again.

Check a few recent invoices look right before deleting the renamed copies.

### Checking a backup before you need it

Worth doing once, so you find out now rather than on the worst day:

1. Copy a backup zip somewhere else — the Desktop will do.
2. Open it. It should contain `carservice.db` and, if you have attachments,
   an `attachments` folder.
3. If `carservice.db` is there and is not zero bytes, the backup is sound.

---

## Changing how it behaves

### Turning it off

Rarely the right answer, but documented because it exists. Backups are
switched off by an environment variable, `CARSERVICE_NO_AUTOBACKUP=1`.

For one session, open a Command Prompt in the application folder and run:

```
set CARSERVICE_NO_AUTOBACKUP=1
run.bat
```

It applies only to that window. Starting the program normally brings backups
back.

To turn them off permanently, add this line near the top of `run.bat`, after
the other `set` lines:

```
set CARSERVICE_NO_AUTOBACKUP=1
```

When backups are off, **Settings → Backup** says so, and stops warning that
no backup has been taken — it cannot be behind on a job it is not doing.

Backups are also off during the automated tests, which is why the test suite
does not scatter zip files across the project folder.

### Changing how many are kept

Both numbers live at the top of `app/backups.py`:

```python
KEEP_DAYS = 14      # every backup from the last fortnight
KEEP_MONTHS = 12    # then one a month, going back
```

Raising them costs disk space and nothing else — at 2.5 MB each, a year of
daily backups is under a gigabyte. Lowering them throws history away the
next time the application starts, so take a copy first.

### Changing where they go

The folder is always `backups` beside the database, and is not configurable
on purpose: a backup folder somebody has to be told the location of is a
backup folder nobody copies.

To keep them somewhere else as well — which you should — copy the folder, or
point your cloud drive's sync at it. Do not move it.

### Changing how often

`CHECK_EVERY` in `app/backups.py`, an hour by default. There is little point
making it shorter: the rule is one backup a day, so checking more often only
means noticing a new day sooner.

---

## When something is wrong

### "No backup has been taken for more than two days"

Work through these in order.

**Has the program been opened?** Backups happen when it runs. A week's
holiday means a week with no backups, and that is the message working
correctly rather than a fault.

**Is the disk full?** Look at `backup-log.txt` for a `FAILED` line — it names
the reason. "No space left on device" means exactly that.

**Can the folder be written to?** Try creating a text file in
`data\backups` yourself. If Windows refuses, the application will be refused
too. This happens when a cloud drive marks the folder read-only while it
syncs.

**Is an antivirus holding the files?** Some scanners lock a zip while they
inspect it. The log will show a backup that failed and then succeeded later.
If it happens daily, add the `data` folder to the scanner's exclusions.

### A `.part` file in the backups folder

A backup that was interrupted. It is harmless and the next one will overwrite
it. The file is written under a temporary name and only given its real name
once it is complete, precisely so that a half-written zip never sits there
wearing today's date and looking like a good backup.

### The folder is getting large

Check how many are in it against the rules above. If there are far more than
about 26, the tidy-up is failing — look in `backup-log.txt`. Deleting the
extras by hand is safe.

### Nothing in the folder at all, and no log

The application has not started successfully since backups were added. Start
it and watch the black window — it prints `Daily backups in ...` once they
are running.

---

## What this does not protect you from

Being clear about the edges, because a backup you trust for the wrong thing
is worse than none:

- **A failed disk**, unless you have copied the folder elsewhere. This is the
  big one.
- **Theft or fire.** Same answer: a copy somewhere else.
- **A mistake you do not notice for a month.** You have twelve monthly
  backups, so there is something to go back to, but the closest copy will be
  weeks old.
- **Ransomware**, which encrypts the backups folder along with everything
  else. An offline copy — a USB stick in a drawer — is the only answer to
  that one.
