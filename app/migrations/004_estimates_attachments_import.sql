-- ---------------------------------------------------------------------------
-- 004  --  estimates, invoice types, attachments, import, messaging
-- ---------------------------------------------------------------------------
-- Five additions, in the order a job now moves through the system:
--
--   estimate  ->  customer approves  ->  invoice  (tax or plain)
--
--   * estimates, quoted before any work is agreed, with a draft/approved life
--   * a document type on invoices, so a plain bill and a tax invoice are the
--     same workflow producing different paper
--   * attachments on a customer, for scanning in the old paper invoices
--   * a staging table for spreadsheet imports, so nothing is written to the
--     real tables until the preview has been seen and confirmed
--   * the settings that messaging and estimate numbering need
--
-- Same conventions as before: money is INTEGER minor units, quantity is
-- INTEGER thousandths.
-- ---------------------------------------------------------------------------

-- --- Settings ---------------------------------------------------------------

ALTER TABLE settings ADD COLUMN estimate_prefix TEXT NOT NULL DEFAULT 'EST-';
ALTER TABLE settings ADD COLUMN next_estimate_seq INTEGER NOT NULL DEFAULT 1
    CHECK (next_estimate_seq >= 1);

-- How long a quoted price stands. Written onto each estimate as a date, so
-- changing this never moves the deadline on one already given to a customer.
ALTER TABLE settings ADD COLUMN estimate_validity_days INTEGER NOT NULL DEFAULT 14
    CHECK (estimate_validity_days >= 0);

-- Dialling code used to turn a local number such as 0551234567 into the
-- international form WhatsApp needs. 966 is Saudi Arabia.
ALTER TABLE settings ADD COLUMN default_country_code TEXT NOT NULL DEFAULT '966';

-- The message sent with an estimate. Placeholders are filled in when sending:
--   {customer} {business} {number} {total} {valid_until} {items}
ALTER TABLE settings ADD COLUMN message_template_en TEXT NOT NULL DEFAULT '';
ALTER TABLE settings ADD COLUMN message_template_ar TEXT NOT NULL DEFAULT '';

UPDATE settings SET
    message_template_en =
        'Hello {customer},' || char(10) || char(10) ||
        'Here is our estimate {number} from {business}:' || char(10) ||
        '{items}' || char(10) ||
        'Total: {total}' || char(10) ||
        'Valid until {valid_until}.' || char(10) || char(10) ||
        'Reply to this message to go ahead, or call us with any questions.',
    message_template_ar =
        'مرحباً {customer}،' || char(10) || char(10) ||
        'هذا عرض السعر رقم {number} من {business}:' || char(10) ||
        '{items}' || char(10) ||
        'الإجمالي: {total}' || char(10) ||
        'صالح حتى {valid_until}.' || char(10) || char(10) ||
        'للموافقة يرجى الرد على هذه الرسالة، أو الاتصال بنا لأي استفسار.'
WHERE id = 1;

-- --- Invoice document type --------------------------------------------------
-- 'tax'   : a tax invoice. VAT is charged and shown, and the printed copy
--           carries the tax-invoice wording.
-- 'plain' : a simple bill with no VAT line. Still a full record in this
--           system and still counted in the shop's own totals -- the only
--           difference is the document the customer is handed.
--
-- Existing invoices were all tax invoices, which is what the default gives
-- them, so nothing already issued changes.

ALTER TABLE invoices ADD COLUMN doc_type TEXT NOT NULL DEFAULT 'tax'
    CHECK (doc_type IN ('tax', 'plain'));

CREATE INDEX idx_invoices_doc_type ON invoices (doc_type);

-- --- Estimates --------------------------------------------------------------

CREATE TABLE estimates (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    estimate_no         TEXT    NOT NULL UNIQUE,
    customer_id         INTEGER NOT NULL REFERENCES customers (id) ON DELETE RESTRICT,
    vehicle_id          INTEGER          REFERENCES vehicles  (id) ON DELETE SET NULL,

    issue_date          TEXT    NOT NULL,
    valid_until         TEXT,

    -- draft    : being written, not yet shown to anyone
    -- sent      : given to the customer, waiting on them
    -- approved  : the customer said yes
    -- declined  : the customer said no
    -- invoiced  : an invoice has been raised from it
    status              TEXT    NOT NULL DEFAULT 'draft'
                                CHECK (status IN ('draft', 'sent', 'approved',
                                                  'declined', 'invoiced')),
    sent_on             TEXT,
    decided_on          TEXT,
    approved_by         TEXT    NOT NULL DEFAULT '',   -- who at the customer agreed

    -- Snapshot of the tax treatment, so re-printing an old estimate after
    -- changing settings still shows the figures that were quoted.
    vat_rate_bp         INTEGER NOT NULL DEFAULT 1500 CHECK (vat_rate_bp >= 0),
    prices_include_vat  INTEGER NOT NULL DEFAULT 0 CHECK (prices_include_vat IN (0, 1)),
    currency_code       TEXT    NOT NULL DEFAULT 'SAR',
    discount_minor      INTEGER NOT NULL DEFAULT 0 CHECK (discount_minor >= 0),
    notes               TEXT    NOT NULL DEFAULT '',

    subtotal_minor      INTEGER NOT NULL DEFAULT 0,
    taxable_minor       INTEGER NOT NULL DEFAULT 0,
    vat_minor           INTEGER NOT NULL DEFAULT 0,
    total_minor         INTEGER NOT NULL DEFAULT 0,

    invoice_id          INTEGER          REFERENCES invoices (id) ON DELETE SET NULL,

    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_estimates_customer ON estimates (customer_id);
CREATE INDEX idx_estimates_vehicle  ON estimates (vehicle_id);
CREATE INDEX idx_estimates_status   ON estimates (status);
CREATE INDEX idx_estimates_date     ON estimates (issue_date);
CREATE INDEX idx_estimates_invoice  ON estimates (invoice_id);

CREATE TABLE estimate_items (
    id               INTEGER PRIMARY KEY AUTOINCREMENT,
    estimate_id      INTEGER NOT NULL REFERENCES estimates (id) ON DELETE CASCADE,
    line_no          INTEGER NOT NULL,
    catalog_item_id  INTEGER          REFERENCES catalog_items (id) ON DELETE SET NULL,
    description      TEXT    NOT NULL,
    description_ar   TEXT    NOT NULL DEFAULT '',
    kind             TEXT    NOT NULL DEFAULT 'service' CHECK (kind IN ('service', 'part')),
    unit             TEXT    NOT NULL DEFAULT 'pcs',
    qty_milli        INTEGER NOT NULL DEFAULT 1000 CHECK (qty_milli > 0),
    unit_price_minor INTEGER NOT NULL DEFAULT 0 CHECK (unit_price_minor >= 0),
    line_total_minor INTEGER NOT NULL DEFAULT 0 CHECK (line_total_minor >= 0)
);

CREATE INDEX        idx_estimate_items     ON estimate_items (estimate_id);
CREATE UNIQUE INDEX idx_estimate_items_seq ON estimate_items (estimate_id, line_no);

-- --- Customer attachments ---------------------------------------------------
-- Scans of invoices written before this system existed, so there is one place
-- to look for a customer's history rather than two.
--
-- Unlike the logo, the file itself is NOT in the database: these are up to
-- 10 MB each and a workshop may scan in years of paperwork, which would turn
-- the database into something too big to open or copy comfortably. They live
-- under the data folder beside it, and the backup now produces a zip of both
-- so a backup is still one thing to keep.
--
-- `stored_name` is generated, never the name the file arrived with: an
-- uploaded filename is attacker-controlled text and must never be used to
-- decide where something lands on disk.

CREATE TABLE customer_attachments (
    id            INTEGER PRIMARY KEY AUTOINCREMENT,
    customer_id   INTEGER NOT NULL REFERENCES customers (id) ON DELETE CASCADE,
    stored_name   TEXT    NOT NULL UNIQUE,
    original_name TEXT    NOT NULL,
    mime          TEXT    NOT NULL,
    size_bytes    INTEGER NOT NULL CHECK (size_bytes > 0),
    kind          TEXT    NOT NULL DEFAULT 'invoice'
                          CHECK (kind IN ('invoice', 'document', 'photo', 'other')),
    description   TEXT    NOT NULL DEFAULT '',
    document_date TEXT,                      -- the date on the paper, if known
    uploaded_at   TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_attachments_customer ON customer_attachments (customer_id);
CREATE INDEX idx_attachments_date     ON customer_attachments (document_date);

-- --- Spreadsheet imports ----------------------------------------------------
-- A batch is parsed and checked first, shown as a preview, and only written
-- to `customers` once it is confirmed. Keeping the parsed rows here rather
-- than in a hidden form field means a large file does not have to make a
-- round trip through the browser, and a half-finished import can be
-- abandoned without leaving anything behind.

CREATE TABLE import_batches (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    filename    TEXT    NOT NULL,
    rows_json   TEXT    NOT NULL,            -- the parsed rows, with per-row notes
    row_count   INTEGER NOT NULL DEFAULT 0,
    status      TEXT    NOT NULL DEFAULT 'pending'
                        CHECK (status IN ('pending', 'imported', 'cancelled')),
    imported    INTEGER NOT NULL DEFAULT 0,
    skipped     INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now'))
);

-- --- Reporting --------------------------------------------------------------

-- v_invoices is rebuilt rather than extended, because SQLite has no
-- ALTER VIEW. The only change is doc_type: anything reading this view, in
-- the application or in a BI tool, can now tell a tax invoice from a plain
-- one, which is the whole point of having the column.
DROP VIEW v_invoices;

CREATE VIEW v_invoices AS
SELECT
    i.id,
    i.invoice_no,
    i.doc_type,
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
    COALESCE(p.paid_minor, 0) / 100.0                   AS amount_paid,
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

CREATE VIEW v_estimates AS
SELECT
    e.id,
    e.estimate_no,
    e.issue_date,
    e.valid_until,
    e.status,
    c.name                         AS customer_name,
    c.phone                        AS customer_phone,
    v.plate_no                     AS vehicle_plate,
    TRIM(v.make || ' ' || v.model) AS vehicle_description,
    e.currency_code,
    e.vat_rate_bp / 100.0          AS vat_rate_percent,
    e.subtotal_minor / 100.0       AS subtotal,
    e.vat_minor      / 100.0       AS vat_amount,
    e.total_minor    / 100.0       AS total,
    i.invoice_no,
    CASE
        WHEN e.status IN ('approved', 'invoiced', 'declined') THEN 0
        WHEN e.valid_until IS NULL                            THEN 0
        WHEN e.valid_until < date('now')                      THEN 1
        ELSE 0
    END AS is_expired
FROM estimates e
JOIN customers c ON c.id = e.customer_id
LEFT JOIN vehicles v ON v.id = e.vehicle_id
LEFT JOIN invoices i ON i.id = e.invoice_id;
