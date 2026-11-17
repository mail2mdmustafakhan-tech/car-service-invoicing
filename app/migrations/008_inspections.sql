-- ---------------------------------------------------------------------------
-- 008_inspections.sql  --  the check that happens before anyone quotes
-- ---------------------------------------------------------------------------
-- There was a gap at the front of the flow. A car arrives, somebody looks it
-- over, and only then is there anything to quote. Until now that looking-over
-- lived in a technician's head and arrived as a list of prices, which is the
-- point at which a customer asks "but what did you actually find?".
--
--   inspection  ->  estimate  ->  invoice
--                      ^
--   car arrives  ->  contract  ->  invoice
--
-- An inspection is deliberately not an estimate with a different name. It
-- records condition, not money: a tyre at 3mm is a finding whether or not
-- this workshop ends up selling the tyre, and half of what gets checked is
-- fine and will never appear on a bill. Keeping them separate means the
-- record of what was checked survives the customer saying no.
-- ---------------------------------------------------------------------------

CREATE TABLE inspections (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_no   TEXT    NOT NULL UNIQUE,
    customer_id     INTEGER NOT NULL REFERENCES customers (id),
    vehicle_id      INTEGER          REFERENCES vehicles (id),
    inspected_on    TEXT    NOT NULL,
    odometer        INTEGER,
    technician      TEXT    NOT NULL DEFAULT '',
    status          TEXT    NOT NULL DEFAULT 'draft'
                            CHECK (status IN ('draft', 'checked', 'quoted')),
    -- Set when findings are turned into a quote, so the inspection can say
    -- what came of it and the quote can say where it came from.
    estimate_id     INTEGER          REFERENCES estimates (id) ON DELETE SET NULL,
    summary         TEXT    NOT NULL DEFAULT '',
    notes           TEXT    NOT NULL DEFAULT '',
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at      TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_inspections_customer ON inspections (customer_id);
CREATE INDEX idx_inspections_vehicle  ON inspections (vehicle_id);
CREATE INDEX idx_inspections_date     ON inspections (inspected_on);

CREATE TABLE inspection_items (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    inspection_id   INTEGER NOT NULL REFERENCES inspections (id) ON DELETE CASCADE,
    line_no         INTEGER NOT NULL,
    area            TEXT    NOT NULL DEFAULT '',
    area_ar         TEXT    NOT NULL DEFAULT '',

    -- 'ok' is the common answer and the default. A checklist where every row
    -- starts blank gets filled in for the faults and left empty everywhere
    -- else, and an empty row is ambiguous forever after: not checked, or
    -- checked and fine?
    condition       TEXT    NOT NULL DEFAULT 'ok'
                            CHECK (condition IN ('ok', 'attention', 'urgent', 'na')),

    finding         TEXT    NOT NULL DEFAULT '',
    finding_ar      TEXT    NOT NULL DEFAULT '',
    known_issue_id  INTEGER          REFERENCES known_issues (id) ON DELETE SET NULL,

    -- What it would cost to put right. Optional: a finding is worth recording
    -- before anybody has priced it, and forcing a number here would mean
    -- invented numbers.
    catalog_item_id INTEGER          REFERENCES catalog_items (id) ON DELETE SET NULL,
    qty_milli       INTEGER NOT NULL DEFAULT 1000 CHECK (qty_milli > 0),
    unit_price_minor INTEGER NOT NULL DEFAULT 0 CHECK (unit_price_minor >= 0),

    -- Whether this finding goes into the quote. Not everything found needs
    -- quoting, and the customer may want the brakes now and the suspension
    -- in three months.
    quote_it        INTEGER NOT NULL DEFAULT 0 CHECK (quote_it IN (0, 1)),
    created_at      TEXT    NOT NULL DEFAULT (datetime('now')),

    UNIQUE (inspection_id, line_no)
);

CREATE INDEX idx_inspection_items_inspection ON inspection_items (inspection_id);


-- Its own number series, like contracts and estimates, so a check that never
-- turns into a quote leaves no gap in the quote numbering.
ALTER TABLE settings ADD COLUMN inspection_prefix TEXT NOT NULL DEFAULT 'INS-';
ALTER TABLE settings ADD COLUMN next_inspection_seq INTEGER NOT NULL DEFAULT 1;

-- Where an estimate came from, when it came from a check.
ALTER TABLE estimates ADD COLUMN inspection_id INTEGER
    REFERENCES inspections (id) ON DELETE SET NULL;


-- Reporting, with the money as decimals like every other v_ view.
CREATE VIEW v_inspections AS
SELECT
    i.id,
    i.inspection_no,
    i.inspected_on,
    i.status,
    c.name                AS customer,
    v.plate_no,
    v.make,
    v.model,
    v.model_year,
    i.odometer,
    i.technician,
    e.estimate_no,
    (SELECT COUNT(*) FROM inspection_items t
      WHERE t.inspection_id = i.id)                       AS checks,
    (SELECT COUNT(*) FROM inspection_items t
      WHERE t.inspection_id = i.id AND t.condition = 'urgent')   AS urgent,
    (SELECT COUNT(*) FROM inspection_items t
      WHERE t.inspection_id = i.id AND t.condition = 'attention') AS attention,
    (SELECT COALESCE(SUM(t.qty_milli * t.unit_price_minor / 1000), 0) / 100.0
       FROM inspection_items t
      WHERE t.inspection_id = i.id AND t.quote_it = 1)    AS quotable_value
FROM inspections i
JOIN customers c ON c.id = i.customer_id
LEFT JOIN vehicles  v ON v.id = i.vehicle_id
LEFT JOIN estimates e ON e.id = i.estimate_id;
