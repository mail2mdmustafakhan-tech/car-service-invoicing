-- ---------------------------------------------------------------------------
-- 006_sources_issues_analytics.sql
-- ---------------------------------------------------------------------------
-- Seven things at once, which is more than a migration should usually carry.
-- They go together because they land in one release and because several of
-- them touch the same views: splitting them would mean dropping and
-- recreating v_repair_order_parts three times for no gain.
--
--   1. Where a part came from, as a list rather than a yes/no
--   2. Who made it, on the price list
--   3. Photographs of parts
--   4. Discounts as a percentage as well as an amount
--   5. What kind of customer this is
--   6. Known faults by make, and the repairs they are attached to
-- ---------------------------------------------------------------------------


-- ---------------------------------------------------------------------------
-- 1. Where a part came from
-- ---------------------------------------------------------------------------
-- `sourced_externally` answered one question: did we buy this in for the
-- customer, and therefore does the handling percentage apply? That question
-- still matters and the column stays, because the printed contract and the
-- markup both depend on it.
--
-- What it could not answer is where the part actually came from, which is
-- what anyone asks three months later when the part fails: agency, used
-- market, or shipped from Germany are three very different conversations
-- about the same line on an invoice.
--
-- Free text rather than a CHECK list. A workshop finds a new supplier more
-- often than anyone edits a database constraint, and a part whose origin is
-- recorded as something unexpected is still better than one recorded wrong.

ALTER TABLE repair_order_parts ADD COLUMN source TEXT NOT NULL DEFAULT 'own_stock';

-- Carry the old answer across so no history is lost.
UPDATE repair_order_parts SET source = 'outside' WHERE sourced_externally = 1;
UPDATE repair_order_parts SET source = 'own_stock' WHERE sourced_externally = 0;


-- ---------------------------------------------------------------------------
-- 2. Who made the part
-- ---------------------------------------------------------------------------
-- Same list as the source, same reasoning for leaving it open: "BMW" and
-- "used market" are the common answers, but neither is the only one.

ALTER TABLE catalog_items ADD COLUMN manufacturer TEXT NOT NULL DEFAULT '';

CREATE INDEX idx_catalog_manufacturer ON catalog_items (manufacturer)
    WHERE manufacturer <> '';


-- ---------------------------------------------------------------------------
-- 3. Photographs of parts
-- ---------------------------------------------------------------------------
-- Same shape as customer_attachments, and for the same reason: the bytes
-- live beside the database rather than inside it, so years of photographs
-- never make the database itself awkward to copy.

CREATE TABLE catalog_item_images (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    catalog_item_id INTEGER NOT NULL REFERENCES catalog_items (id) ON DELETE CASCADE,
    stored_name     TEXT    NOT NULL UNIQUE,
    original_name   TEXT    NOT NULL,
    mime            TEXT    NOT NULL,
    size_bytes      INTEGER NOT NULL CHECK (size_bytes > 0),
    caption         TEXT    NOT NULL DEFAULT '',
    uploaded_at     TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_item_images_item ON catalog_item_images (catalog_item_id);


-- ---------------------------------------------------------------------------
-- 4. Discounts: a percentage or an amount
-- ---------------------------------------------------------------------------
-- `discount_minor` stays the single source of truth for the arithmetic -- the
-- money taken off, in halalas. The percentage is remembered alongside it so
-- the form can show what was typed and recalculate if the lines change, but
-- every total still comes from the amount.
--
-- Storing only the percentage would mean an issued invoice's discount could
-- move when a line was edited, and a document that has gone to a customer
-- must not change its mind about what it says.

ALTER TABLE invoices ADD COLUMN discount_mode TEXT NOT NULL DEFAULT 'amount'
    CHECK (discount_mode IN ('amount', 'percent'));
ALTER TABLE invoices ADD COLUMN discount_rate_bp INTEGER NOT NULL DEFAULT 0
    CHECK (discount_rate_bp >= 0 AND discount_rate_bp <= 1000000);

ALTER TABLE estimates ADD COLUMN discount_mode TEXT NOT NULL DEFAULT 'amount'
    CHECK (discount_mode IN ('amount', 'percent'));
ALTER TABLE estimates ADD COLUMN discount_rate_bp INTEGER NOT NULL DEFAULT 0
    CHECK (discount_rate_bp >= 0 AND discount_rate_bp <= 1000000);


-- ---------------------------------------------------------------------------
-- 5. What kind of customer this is
-- ---------------------------------------------------------------------------
-- 'regular' covers almost everyone. The rest exist because the workshop
-- already treats them differently and the software should be able to say so:
-- a fleet is invoiced with a VAT number, family and friends are often cash
-- without a tax invoice, and VIP is who you ring first when a part arrives.
--
-- Note what is NOT here: "active". Whether a customer is active is a question
-- about when they last came in, and storing it would mean a flag that is
-- wrong the moment nobody updates it. It is worked out from the records.

ALTER TABLE customers ADD COLUMN category TEXT NOT NULL DEFAULT 'regular'
    CHECK (category IN ('regular', 'vip', 'family', 'fleet'));

CREATE INDEX idx_customers_category ON customers (category) WHERE category <> 'regular';


-- ---------------------------------------------------------------------------
-- 6. Known faults
-- ---------------------------------------------------------------------------
-- A reference list of the faults that come through the door often enough to
-- be worth naming, so a technician can attach one to a job instead of
-- describing it again, and so the dashboard can answer "how many 7 Series
-- have we had in with water in the boot?".
--
-- `make` is required and everything else optional: half of what a workshop
-- knows is "BMW, around 2013, the chain guides" and a schema that demands a
-- model and a year range would only get fiction typed into it.

CREATE TABLE known_issues (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    make          TEXT    NOT NULL,
    model         TEXT    NOT NULL DEFAULT '',   -- '3 Series (F30)', 'X5'
    engine        TEXT    NOT NULL DEFAULT '',   -- 'N20', 'EA888', 'M276'
    year_from     INTEGER,
    year_to       INTEGER,
    title_en      TEXT    NOT NULL,
    title_ar      TEXT    NOT NULL DEFAULT '',
    symptoms_en   TEXT    NOT NULL DEFAULT '',
    symptoms_ar   TEXT    NOT NULL DEFAULT '',
    check_en      TEXT    NOT NULL DEFAULT '',   -- what to look at first
    check_ar      TEXT    NOT NULL DEFAULT '',
    severity      TEXT    NOT NULL DEFAULT 'medium'
                          CHECK (severity IN ('low', 'medium', 'high')),
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    is_builtin    INTEGER NOT NULL DEFAULT 0 CHECK (is_builtin IN (0, 1)),
    notes         TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_issues_make ON known_issues (make);
CREATE INDEX idx_issues_active ON known_issues (is_active);

-- A fault attached to a job. `show_on_print` is the include-or-exclude: the
-- workshop may want to record that it checked for a known fault without
-- putting it on the customer's copy, and may equally want it printed as the
-- reason a bill is what it is.
CREATE TABLE repair_order_issues (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id INTEGER NOT NULL REFERENCES repair_orders (id) ON DELETE CASCADE,
    known_issue_id  INTEGER NOT NULL REFERENCES known_issues (id) ON DELETE CASCADE,
    outcome         TEXT    NOT NULL DEFAULT 'suspected'
                            CHECK (outcome IN ('suspected', 'confirmed', 'ruled_out', 'repaired')),
    show_on_print   INTEGER NOT NULL DEFAULT 1 CHECK (show_on_print IN (0, 1)),
    note            TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (repair_order_id, known_issue_id)
);

CREATE INDEX idx_order_issues_order ON repair_order_issues (repair_order_id);
CREATE INDEX idx_order_issues_issue ON repair_order_issues (known_issue_id);


-- ---------------------------------------------------------------------------
-- Views: SQLite has no ALTER VIEW, so a changed column means DROP and CREATE
-- ---------------------------------------------------------------------------

DROP VIEW IF EXISTS v_repair_order_parts;
CREATE VIEW v_repair_order_parts AS
SELECT
    p.repair_order_id,
    ro.contract_no,
    ro.date_in,
    p.line_no,
    p.part_number,
    p.description,
    p.source,
    p.sourced_externally,
    p.qty_milli        / 1000.0 AS qty,
    p.unit_price_minor / 100.0  AS unit_price,
    p.line_total_minor / 100.0  AS line_total
FROM repair_order_parts p
JOIN repair_orders ro ON ro.id = p.repair_order_id;

-- Faults as they have actually been seen, which is the view the dashboard
-- counts from and the one worth exporting to a spreadsheet.
CREATE VIEW v_known_issue_cases AS
SELECT
    k.id            AS issue_id,
    k.make,
    k.model,
    k.engine,
    k.title_en      AS issue,
    k.severity,
    ro.contract_no,
    ro.date_in,
    v.plate_no,
    v.make          AS car_make,
    v.model         AS car_model,
    v.model_year,
    c.name          AS customer,
    oi.outcome,
    oi.note
FROM repair_order_issues oi
JOIN known_issues  k  ON k.id  = oi.known_issue_id
JOIN repair_orders ro ON ro.id = oi.repair_order_id
LEFT JOIN vehicles  v ON v.id  = ro.vehicle_id
LEFT JOIN customers c ON c.id  = ro.customer_id;
