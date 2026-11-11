-- ---------------------------------------------------------------------------
-- 001_initial.sql  --  Car Service Invoicing: initial schema
-- ---------------------------------------------------------------------------
-- MONEY: every money column is an INTEGER in *minor units* (halalas/cents).
--        1 SAR = 100 halalas. 150.75 SAR is stored as 15075.
--        This avoids floating-point rounding errors entirely. The app layer
--        converts to/from decimals for display (see app/money.py).
--
-- QUANTITY: qty_milli is an INTEGER = quantity x 1000.
--           1 unit = 1000, 0.5 hours = 500, 2.25 = 2250.
--
-- Convenience views at the bottom expose both as readable decimals so you can
-- query this file directly from any BI/SQL tool without doing the maths.
-- ---------------------------------------------------------------------------

-- Business details, tax rate and invoice numbering. Exactly one row, id = 1.
CREATE TABLE settings (
    id                 INTEGER PRIMARY KEY CHECK (id = 1),
    business_name_en   TEXT    NOT NULL DEFAULT 'My Auto Service',
    business_name_ar   TEXT    NOT NULL DEFAULT '',
    vat_number         TEXT    NOT NULL DEFAULT '',
    cr_number          TEXT    NOT NULL DEFAULT '',
    address_en         TEXT    NOT NULL DEFAULT '',
    address_ar         TEXT    NOT NULL DEFAULT '',
    phone              TEXT    NOT NULL DEFAULT '',
    email              TEXT    NOT NULL DEFAULT '',
    -- VAT percentage as an integer in hundredths of a percent.
    -- 15% is stored as 1500, 5% as 500, 0% as 0. Exact, no decimals needed.
    vat_rate_bp        INTEGER NOT NULL DEFAULT 1500 CHECK (vat_rate_bp >= 0),
    -- Are catalogue/entered prices VAT-inclusive or VAT-exclusive?
    prices_include_vat INTEGER NOT NULL DEFAULT 0 CHECK (prices_include_vat IN (0, 1)),
    currency_code      TEXT    NOT NULL DEFAULT 'SAR',
    invoice_prefix     TEXT    NOT NULL DEFAULT 'INV-',
    next_invoice_seq   INTEGER NOT NULL DEFAULT 1 CHECK (next_invoice_seq >= 1),
    default_language   TEXT    NOT NULL DEFAULT 'en' CHECK (default_language IN ('en', 'ar')),
    invoice_footer_en  TEXT    NOT NULL DEFAULT '',
    invoice_footer_ar  TEXT    NOT NULL DEFAULT '',
    updated_at         TEXT    NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO settings (id) VALUES (1);

-- ---------------------------------------------------------------------------

CREATE TABLE customers (
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
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_customers_name  ON customers (name);
CREATE INDEX idx_customers_phone ON customers (phone);

-- ---------------------------------------------------------------------------

CREATE TABLE vehicles (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id   INTEGER NOT NULL REFERENCES customers (id) ON DELETE CASCADE,
    plate_no      TEXT    NOT NULL,
    make          TEXT    NOT NULL DEFAULT '',
    model         TEXT    NOT NULL DEFAULT '',
    model_year    INTEGER,
    vin           TEXT    NOT NULL DEFAULT '',
    colour        TEXT    NOT NULL DEFAULT '',
    odometer      INTEGER,                      -- last known reading, km
    notes         TEXT    NOT NULL DEFAULT '',
    is_active     INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at    TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_vehicles_customer ON vehicles (customer_id);
CREATE INDEX idx_vehicles_plate    ON vehicles (plate_no);

-- ---------------------------------------------------------------------------
-- Reusable services and parts, so invoice lines are picked rather than typed.

CREATE TABLE catalog_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    code             TEXT    NOT NULL DEFAULT '',
    name_en          TEXT    NOT NULL,
    name_ar          TEXT    NOT NULL DEFAULT '',
    kind             TEXT    NOT NULL DEFAULT 'service' CHECK (kind IN ('service', 'part')),
    unit             TEXT    NOT NULL DEFAULT 'pcs',    -- pcs, hour, litre, set
    unit_price_minor INTEGER NOT NULL DEFAULT 0 CHECK (unit_price_minor >= 0),
    is_active        INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at       TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at       TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX        idx_catalog_kind ON catalog_items (kind);
CREATE UNIQUE INDEX idx_catalog_code ON catalog_items (code) WHERE code <> '';

-- ---------------------------------------------------------------------------

CREATE TABLE invoices (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_no          TEXT    NOT NULL UNIQUE,
    customer_id         INTEGER NOT NULL REFERENCES customers (id) ON DELETE RESTRICT,
    vehicle_id          INTEGER          REFERENCES vehicles  (id) ON DELETE SET NULL,
    issue_date          TEXT    NOT NULL,                  -- YYYY-MM-DD
    due_date            TEXT,                              -- YYYY-MM-DD, optional
    odometer            INTEGER,                           -- reading at service
    status              TEXT    NOT NULL DEFAULT 'draft'
                                CHECK (status IN ('draft', 'issued', 'void')),
    -- Snapshot of the tax setup at the moment of issue, so re-printing an old
    -- invoice after changing settings still shows the original numbers.
    vat_rate_bp         INTEGER NOT NULL DEFAULT 1500 CHECK (vat_rate_bp >= 0),
    prices_include_vat  INTEGER NOT NULL DEFAULT 0 CHECK (prices_include_vat IN (0, 1)),
    currency_code       TEXT    NOT NULL DEFAULT 'SAR',
    discount_minor      INTEGER NOT NULL DEFAULT 0 CHECK (discount_minor >= 0),
    notes               TEXT    NOT NULL DEFAULT '',
    -- Stored totals: computed by app/invoicing.py and written on every save.
    subtotal_minor      INTEGER NOT NULL DEFAULT 0,  -- lines, before discount
    taxable_minor       INTEGER NOT NULL DEFAULT 0,  -- after discount, ex-VAT
    vat_minor           INTEGER NOT NULL DEFAULT 0,
    total_minor         INTEGER NOT NULL DEFAULT 0,
    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_invoices_customer ON invoices (customer_id);
CREATE INDEX idx_invoices_vehicle  ON invoices (vehicle_id);
CREATE INDEX idx_invoices_date     ON invoices (issue_date);
CREATE INDEX idx_invoices_status   ON invoices (status);

-- ---------------------------------------------------------------------------

CREATE TABLE invoice_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id       INTEGER NOT NULL REFERENCES invoices (id) ON DELETE CASCADE,
    line_no          INTEGER NOT NULL,
    catalog_item_id  INTEGER          REFERENCES catalog_items (id) ON DELETE SET NULL,
    -- Description is copied from the catalogue at the time the line is added,
    -- so editing a catalogue price later never changes a historic invoice.
    description      TEXT    NOT NULL,
    description_ar   TEXT    NOT NULL DEFAULT '',
    kind             TEXT    NOT NULL DEFAULT 'service' CHECK (kind IN ('service', 'part')),
    unit             TEXT    NOT NULL DEFAULT 'pcs',
    qty_milli        INTEGER NOT NULL DEFAULT 1000 CHECK (qty_milli > 0),
    unit_price_minor INTEGER NOT NULL DEFAULT 0 CHECK (unit_price_minor >= 0),
    line_total_minor INTEGER NOT NULL DEFAULT 0 CHECK (line_total_minor >= 0)
);

CREATE INDEX        idx_items_invoice     ON invoice_items (invoice_id);
CREATE UNIQUE INDEX idx_items_invoice_seq ON invoice_items (invoice_id, line_no);

-- ---------------------------------------------------------------------------

CREATE TABLE payments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    invoice_id    INTEGER NOT NULL REFERENCES invoices (id) ON DELETE CASCADE,
    paid_on       TEXT    NOT NULL,                        -- YYYY-MM-DD
    amount_minor  INTEGER NOT NULL CHECK (amount_minor > 0),
    method        TEXT    NOT NULL DEFAULT 'cash'
                          CHECK (method IN ('cash', 'card', 'transfer', 'cheque', 'other')),
    reference     TEXT    NOT NULL DEFAULT '',
    notes         TEXT    NOT NULL DEFAULT '',
    created_at    TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_payments_invoice ON payments (invoice_id);
CREATE INDEX idx_payments_date    ON payments (paid_on);

-- ---------------------------------------------------------------------------
-- Reporting views. Money and quantity shown as ordinary decimals so you can
-- point any SQL or BI tool at the database file and query it directly.
-- ---------------------------------------------------------------------------

CREATE VIEW v_invoices AS
SELECT
    i.id,
    i.invoice_no,
    i.issue_date,
    i.due_date,
    i.status,
    c.name                           AS customer_name,
    c.phone                          AS customer_phone,
    v.plate_no                       AS vehicle_plate,
    TRIM(v.make || ' ' || v.model)   AS vehicle_description,
    i.currency_code,
    i.vat_rate_bp / 100.0            AS vat_rate_percent,
    i.subtotal_minor  / 100.0        AS subtotal,
    i.discount_minor  / 100.0        AS discount,
    i.taxable_minor   / 100.0        AS taxable_amount,
    i.vat_minor       / 100.0        AS vat_amount,
    i.total_minor     / 100.0        AS total,
    COALESCE(p.paid_minor, 0) / 100.0            AS amount_paid,
    (i.total_minor - COALESCE(p.paid_minor, 0)) / 100.0 AS balance_due,
    CASE
        WHEN i.status = 'void'                              THEN 'void'
        WHEN i.status = 'draft'                             THEN 'draft'
        WHEN COALESCE(p.paid_minor, 0) >= i.total_minor     THEN 'paid'
        WHEN COALESCE(p.paid_minor, 0) > 0                  THEN 'partially_paid'
        ELSE 'unpaid'
    END                              AS payment_state
FROM invoices i
JOIN customers c ON c.id = i.customer_id
LEFT JOIN vehicles v ON v.id = i.vehicle_id
LEFT JOIN (
    SELECT invoice_id, SUM(amount_minor) AS paid_minor
    FROM payments
    GROUP BY invoice_id
) p ON p.invoice_id = i.id;

CREATE VIEW v_invoice_lines AS
SELECT
    it.invoice_id,
    i.invoice_no,
    i.issue_date,
    it.line_no,
    it.description,
    it.kind,
    it.unit,
    it.qty_milli        / 1000.0 AS qty,
    it.unit_price_minor / 100.0  AS unit_price,
    it.line_total_minor / 100.0  AS line_total
FROM invoice_items it
JOIN invoices i ON i.id = it.invoice_id;

CREATE VIEW v_payments AS
SELECT
    p.id,
    p.invoice_id,
    i.invoice_no,
    c.name               AS customer_name,
    p.paid_on,
    p.method,
    p.reference,
    p.amount_minor / 100.0 AS amount
FROM payments p
JOIN invoices  i ON i.id = p.invoice_id
JOIN customers c ON c.id = i.customer_id;
