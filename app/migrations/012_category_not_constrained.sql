-- Let the customer types in Settings actually be the customer types.
--
-- `category` was created with CHECK (category IN ('regular','vip','family',
-- 'fleet')). That was right when those four were written in the code. They
-- are rows in `list_options` now, editable in Settings -- so adding
-- "Insurance company" there offered a choice the database then refused to
-- store. A list you can edit that silently rejects what you add is worse
-- than no list.
--
-- The rule has not gone away; it has moved to where the data now lives. The
-- form validates a posted category against the configured list, which is the
-- only place that knows what the current answer is.
--
-- SQLite cannot drop a CHECK constraint, so the table is rebuilt. The
-- documented procedure, in order:
--
--   * foreign keys are turned off for the duration. Other tables reference
--     customers(id), and dropping the old table with them on would either
--     fail or cascade. Ids are carried across unchanged and the new table
--     takes the same name, so every one of those references still resolves
--     when they are turned back on.
--   * views are NOT recreated. A SQLite view is stored as text and is
--     resolved when it runs, so a view over `customers` keeps working as
--     long as the replacement has the same columns -- which this does, in
--     the same order.
--   * indexes ARE recreated. Those are dropped with the table.
--   * AUTOINCREMENT is kept, so a deleted customer's id is never handed to
--     somebody else later. Invoices refer to these ids.

-- runner: self-managed
--
-- (The line above tells the migration runner not to wrap this file in its
-- own transaction. The pragmas below are ignored inside one, silently,
-- which would leave this rebuild running with foreign keys still on.)

PRAGMA foreign_keys = OFF;

-- And this one stops ALTER TABLE ... RENAME from re-parsing every view in
-- the database as it goes. Six views select from `customers`, and halfway
-- through this rebuild that name briefly belongs to nothing -- with the
-- modern behaviour the rename fails with "error in view v_payments: no such
-- table: main.customers". The views themselves need no changes: they are
-- stored as text and resolved when they run, and the replacement table has
-- the same columns in the same order.
PRAGMA legacy_alter_table = ON;

BEGIN;

CREATE TABLE customers_rebuilt (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL,
    name_ar     TEXT    NOT NULL DEFAULT '',
    phone       TEXT    NOT NULL DEFAULT '',
    email       TEXT    NOT NULL DEFAULT '',
    address     TEXT    NOT NULL DEFAULT '',
    vat_number  TEXT    NOT NULL DEFAULT '',   -- for business customers
    notes       TEXT    NOT NULL DEFAULT '',
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    -- No CHECK. What is offered is decided by list_options; what is accepted
    -- is decided by the form against that same list.
    category    TEXT    NOT NULL DEFAULT 'regular',
    -- This one keeps its CHECK. These three values are not configurable and
    -- are not meant to be: each one means a different amount of interruption,
    -- written into the templates and the script that shows them.
    alert_level TEXT    NOT NULL DEFAULT ''
        CHECK (alert_level IN ('', 'note', 'check', 'refuse')),
    alert_note   TEXT   NOT NULL DEFAULT '',
    alert_set_on TEXT   NOT NULL DEFAULT ''
);

INSERT INTO customers_rebuilt
    (id, name, name_ar, phone, email, address, vat_number, notes,
     is_active, created_at, updated_at, category,
     alert_level, alert_note, alert_set_on)
SELECT
     id, name, name_ar, phone, email, address, vat_number, notes,
     is_active, created_at, updated_at, category,
     alert_level, alert_note, alert_set_on
  FROM customers;

DROP TABLE customers;

ALTER TABLE customers_rebuilt RENAME TO customers;

CREATE INDEX idx_customers_name     ON customers (name);
CREATE INDEX idx_customers_phone    ON customers (phone);
CREATE INDEX idx_customers_category ON customers (category) WHERE category <> 'regular';
CREATE INDEX idx_customers_alert    ON customers (alert_level) WHERE alert_level <> '';

COMMIT;

PRAGMA legacy_alter_table = OFF;
PRAGMA foreign_keys = ON;
