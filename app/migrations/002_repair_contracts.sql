-- ---------------------------------------------------------------------------
-- 002_repair_contracts.sql
--
-- The repair contract (عقد اصلاح سيارة) is the document the workshop actually
-- runs on. It is written and signed when the car arrives, long before an
-- invoice exists: it records what the owner asked for, what the technician
-- found, which parts were fitted, and the customer's authorisation to carry
-- out the work.
--
-- The flow this models:
--
--     car arrives -> contract written -> customer signs -> work done
--                 -> parts recorded   -> contract converted to an invoice
--
-- A contract is therefore NOT an invoice. It carries estimates, remarks and a
-- signature; the invoice carries the money that is owed. Converting a
-- contract copies its lines into a new invoice and links the two, so the
-- paperwork for one job can always be traced end to end.
--
-- Same conventions as 001: money is INTEGER minor units, quantity is
-- INTEGER thousandths.
-- ---------------------------------------------------------------------------

-- --- Settings the printed contract needs -----------------------------------

-- Shown under the business name on the contract masthead,
-- e.g. "Mechanical - Electrical - Denting - Painting".
ALTER TABLE settings ADD COLUMN business_tagline_en TEXT NOT NULL DEFAULT '';
ALTER TABLE settings ADD COLUMN business_tagline_ar TEXT NOT NULL DEFAULT '';

-- The numbered notice printed at the top of the contract, one point per line.
-- Edited on the Settings page; blank lines are ignored when printing.
ALTER TABLE settings ADD COLUMN contract_terms_en TEXT NOT NULL DEFAULT '';
ALTER TABLE settings ADD COLUMN contract_terms_ar TEXT NOT NULL DEFAULT '';

-- The paragraph the customer signs under. {business} is replaced with the
-- business name when printing, so the wording stays correct if the centre is
-- ever renamed, and so this ships without one shop's name baked into it.
ALTER TABLE settings ADD COLUMN contract_authorization_en TEXT NOT NULL DEFAULT '';
ALTER TABLE settings ADD COLUMN contract_authorization_ar TEXT NOT NULL DEFAULT '';

-- Contracts are numbered separately from invoices: a car can come in and be
-- turned away, and the invoice series should not have gaps where that happened.
ALTER TABLE settings ADD COLUMN contract_prefix TEXT NOT NULL DEFAULT 'RC-';
ALTER TABLE settings ADD COLUMN next_contract_seq INTEGER NOT NULL DEFAULT 1;

-- Point 5 of the printed notice: a percentage added to parts the centre
-- sources from an agency on the customer's behalf. Stored in hundredths of a
-- percent, as vat_rate_bp is. 10% is 1000. Applied only when a parts line is
-- marked as sourced, and never silently.
ALTER TABLE settings ADD COLUMN parts_markup_bp INTEGER NOT NULL DEFAULT 0
    CHECK (parts_markup_bp >= 0);

UPDATE settings SET
    business_tagline_en = 'Mechanical  -  Electrical  -  Denting  -  Painting',
    business_tagline_ar = 'ميكانيكا  -  كهرباء  -  سمكرة  -  بوية',
    contract_terms_en =
        'Center is not responsible for any personal things left in the car.' || char(10) ||
        'The Owner should take out the phone when the car is in repair.' || char(10) ||
        'The Center is not responsible for any repairs not mentioned as done in the maintenance center.' || char(10) ||
        'The Owner of car should know the charges before putting his signature.' || char(10) ||
        'The Center will charge 10% over the spare part price for obtaining these from agencies and companies.' || char(10) ||
        'The invoice issued from the center is considered complete and official. It includes spare parts and labour charges, so the customer should not ask for another one.',
    contract_terms_ar =
        'المركز غير مسؤول عن أي أشياء شخصية تُفقد داخل السيارة.' || char(10) ||
        'يجب على المالك سحب جهاز التلفون عند إصلاح السيارة.' || char(10) ||
        'المركز غير مسؤول عن أي إصلاحات لم يتم إبلاغها أو إجراؤها من قبل المركز.' || char(10) ||
        'يجب على صاحب السيارة معرفة الأجور وتكاليف الإصلاح قبل التوقيع على عقد الإصلاح.' || char(10) ||
        'المركز يستوفي ١٠٪ من قيمة القطع التي يتم تأمينها من الشركات أو المؤسسات لصالح السيارة مقابل خدمة إتعاب تأمين القطع.' || char(10) ||
        'يُكتفى بالفاتورة الصادرة من المركز وتشمل قطع الغيار والأجور، فهي رسمية وشاملة وليس للعميل أي حق بطلب فاتورة أخرى.',
    contract_authorization_en =
        'I, the undersigned, the above mentioned car owner, authorize {business} to carry out the repairs shown above on my car, and undertake to pay all resulting labour charges and the value of any spare parts required. I further undertake to collect the car on the date determined above, and in case of delay I discharge {business} from any responsibility whatsoever towards the car. The centre has the full right to test the car inside and outside the workshop.',
    contract_authorization_ar =
        'أنا الموقع اسمي أدناه صاحب السيارة الموضحة أعلاه أفوض {business} بعمل الإصلاحات الموضحة أعلاه لسيارتي، ومستعد بدفع ما يترتب على ذلك من نفقات أجور الإصلاح أو قيمة قطع الغيار، كما أنني متعهد باستلام السيارة في الوقت المحدد أعلاه، وفي حالة تأخري في ذلك فأنا أتعهد بإخلاء ساحة مركز الصيانة من أية مسؤولية تجاه السيارة، كما أن للمركز حق الفحص داخل وخارج الورشة دون أدنى مسؤولية.',
    parts_markup_bp = 1000
WHERE id = 1;

-- --- The contract itself ---------------------------------------------------

CREATE TABLE repair_orders (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    contract_no         TEXT    NOT NULL UNIQUE,
    customer_id         INTEGER NOT NULL REFERENCES customers (id) ON DELETE RESTRICT,
    vehicle_id          INTEGER          REFERENCES vehicles  (id) ON DELETE SET NULL,

    date_in             TEXT    NOT NULL,          -- تاريخ إدخال السيارة الورشة
    expected_date_out   TEXT,                      -- التاريخ المتوقع لإستلام السيارة
    odometer            INTEGER,                   -- رقم عداد السيارة
    car_code            TEXT    NOT NULL DEFAULT '',  -- رمز السيارة

    -- open      : written up, car in the workshop
    -- completed : work finished, car ready to collect
    -- invoiced  : an invoice has been raised from it
    -- cancelled : the job was not carried out
    status              TEXT    NOT NULL DEFAULT 'open'
                                CHECK (status IN ('open', 'completed', 'invoiced', 'cancelled')),

    technician_name     TEXT    NOT NULL DEFAULT '',
    -- Whether the customer has signed the printed contract. The signature
    -- itself lives on paper; this records that it was obtained.
    customer_signed     INTEGER NOT NULL DEFAULT 0 CHECK (customer_signed IN (0, 1)),
    signed_on           TEXT,

    -- Existing damage marked on the car diagram, written out in words.
    damage_notes        TEXT    NOT NULL DEFAULT '',
    notes               TEXT    NOT NULL DEFAULT '',

    -- Set once this contract has been turned into an invoice.
    invoice_id          INTEGER          REFERENCES invoices (id) ON DELETE SET NULL,

    created_at          TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at          TEXT    NOT NULL DEFAULT (datetime('now'))
);

CREATE INDEX idx_orders_customer ON repair_orders (customer_id);
CREATE INDEX idx_orders_vehicle  ON repair_orders (vehicle_id);
CREATE INDEX idx_orders_status   ON repair_orders (status);
CREATE INDEX idx_orders_date     ON repair_orders (date_in);
CREATE INDEX idx_orders_invoice  ON repair_orders (invoice_id);

-- --- Work requested, and what the technician found --------------------------
-- The three columns of the main table on the paper contract.

CREATE TABLE repair_order_items (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id    INTEGER NOT NULL REFERENCES repair_orders (id) ON DELETE CASCADE,
    line_no            INTEGER NOT NULL,
    catalog_item_id    INTEGER          REFERENCES catalog_items (id) ON DELETE SET NULL,

    description        TEXT    NOT NULL,              -- الاصلاحات المطلوبة
    description_ar     TEXT    NOT NULL DEFAULT '',
    -- Labour estimate for this repair (ر.س تكلفة الأجور). An estimate on the
    -- contract; it becomes a real charge only when the invoice is raised.
    expense_minor      INTEGER NOT NULL DEFAULT 0 CHECK (expense_minor >= 0),
    technician_remarks TEXT    NOT NULL DEFAULT ''    -- ملاحظات الميكانيكي
);

CREATE INDEX        idx_order_items          ON repair_order_items (repair_order_id);
CREATE UNIQUE INDEX idx_order_items_sequence ON repair_order_items (repair_order_id, line_no);

-- --- Spare parts ------------------------------------------------------------
-- The second sheet: Part Number / Type of Spare / Qty / Price.

CREATE TABLE repair_order_parts (
    id                 INTEGER PRIMARY KEY AUTOINCREMENT,
    repair_order_id    INTEGER NOT NULL REFERENCES repair_orders (id) ON DELETE CASCADE,
    line_no            INTEGER NOT NULL,
    catalog_item_id    INTEGER          REFERENCES catalog_items (id) ON DELETE SET NULL,

    part_number        TEXT    NOT NULL DEFAULT '',   -- رقم القطعة الأصلي
    description        TEXT    NOT NULL,              -- مسمى القطعة
    description_ar     TEXT    NOT NULL DEFAULT '',
    qty_milli          INTEGER NOT NULL DEFAULT 1000 CHECK (qty_milli > 0),
    unit_price_minor   INTEGER NOT NULL DEFAULT 0 CHECK (unit_price_minor >= 0),
    line_total_minor   INTEGER NOT NULL DEFAULT 0 CHECK (line_total_minor >= 0),

    -- Marks a part the centre obtained from an agency on the customer's
    -- behalf, which the printed notice says carries a handling percentage.
    -- The markup is applied to the price when set, never behind the counter.
    sourced_externally INTEGER NOT NULL DEFAULT 0 CHECK (sourced_externally IN (0, 1))
);

CREATE INDEX        idx_order_parts          ON repair_order_parts (repair_order_id);
CREATE UNIQUE INDEX idx_order_parts_sequence ON repair_order_parts (repair_order_id, line_no);

-- --- Reporting --------------------------------------------------------------

CREATE VIEW v_repair_orders AS
SELECT
    ro.id,
    ro.contract_no,
    ro.date_in,
    ro.expected_date_out,
    ro.status,
    ro.customer_signed,
    c.name                         AS customer_name,
    c.phone                        AS customer_phone,
    v.plate_no                     AS vehicle_plate,
    TRIM(v.make || ' ' || v.model) AS vehicle_description,
    ro.odometer,
    ro.technician_name,
    COALESCE(labour.total, 0) / 100.0             AS labour_estimate,
    COALESCE(parts.total, 0)  / 100.0             AS parts_estimate,
    (COALESCE(labour.total, 0) + COALESCE(parts.total, 0)) / 100.0 AS estimate_total,
    i.invoice_no,
    -- How long the car has been in, in days. Open contracts measure to today.
    CAST(julianday(COALESCE(ro.expected_date_out, date('now'))) - julianday(ro.date_in) AS INTEGER)
                                   AS days_in_workshop
FROM repair_orders ro
JOIN customers c ON c.id = ro.customer_id
LEFT JOIN vehicles v ON v.id = ro.vehicle_id
LEFT JOIN invoices i ON i.id = ro.invoice_id
LEFT JOIN (
    SELECT repair_order_id, SUM(expense_minor) AS total
    FROM repair_order_items GROUP BY repair_order_id
) labour ON labour.repair_order_id = ro.id
LEFT JOIN (
    SELECT repair_order_id, SUM(line_total_minor) AS total
    FROM repair_order_parts GROUP BY repair_order_id
) parts ON parts.repair_order_id = ro.id;

CREATE VIEW v_repair_order_parts AS
SELECT
    p.repair_order_id,
    ro.contract_no,
    ro.date_in,
    p.line_no,
    p.part_number,
    p.description,
    p.sourced_externally,
    p.qty_milli        / 1000.0 AS qty,
    p.unit_price_minor / 100.0  AS unit_price,
    p.line_total_minor / 100.0  AS line_total
FROM repair_order_parts p
JOIN repair_orders ro ON ro.id = p.repair_order_id;
