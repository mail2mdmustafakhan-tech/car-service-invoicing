-- Every dropdown in the application, as data rather than as code.
--
-- Until now the choices behind a dropdown lived in three different places:
-- Python constants for part sources and manufacturers, a literal list inside
-- three templates for units, and translation keys for payment methods and
-- customer types. Adding a supplier meant editing Python; adding a unit meant
-- editing the same list in three files and hoping none was missed.
--
-- They are all rows here now, editable in Settings. A workshop finds a new
-- supplier far more often than anyone edits a constant.
--
-- Nothing here is enforced against the columns that use it. These remain
-- suggestions: a source typed in unexpected words is still worth more than
-- one recorded wrongly because the list had no room for the truth. What the
-- list decides is what is offered, not what is allowed.

CREATE TABLE list_options (
    id          INTEGER PRIMARY KEY,
    -- Which dropdown this belongs to: sources, manufacturers, units,
    -- payment_methods, customer_types.
    list_name   TEXT    NOT NULL,
    -- What lands in the database when this is chosen. Deliberately the
    -- readable name rather than a code, so a spreadsheet of this data reads
    -- without a lookup table.
    value       TEXT    NOT NULL,
    label_en    TEXT    NOT NULL DEFAULT '',
    label_ar    TEXT    NOT NULL DEFAULT '',
    sort_order  INTEGER NOT NULL DEFAULT 0,
    is_active   INTEGER NOT NULL DEFAULT 1,
    -- A built-in cannot be deleted, only switched off. Deleting one would
    -- not remove it from the invoices that already record it -- it would
    -- just leave those invoices referring to something with no label.
    is_builtin  INTEGER NOT NULL DEFAULT 0,
    created_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    updated_at  TEXT    NOT NULL DEFAULT (datetime('now')),
    UNIQUE (list_name, value)
);

CREATE INDEX idx_list_options_list ON list_options (list_name, sort_order);

-- ---------------------------------------------------------------------------
-- Where a part came from. The first two keep short codes because rows written
-- before this list existed already hold them.
-- ---------------------------------------------------------------------------
INSERT INTO list_options (list_name, value, label_en, label_ar, sort_order, is_builtin) VALUES
    ('sources', 'own_stock',     'Own stock',             'مخزوننا',            10, 1),
    ('sources', 'BMW',           'BMW agency',            'وكالة BMW',          20, 1),
    ('sources', 'Mercedes-Benz', 'Mercedes-Benz agency',  'وكالة مرسيدس',       30, 1),
    ('sources', 'Audi',          'Audi agency',           'وكالة أودي',          40, 1),
    ('sources', 'Volkswagen',    'Volkswagen agency',     'وكالة فولكس واجن',    50, 1),
    ('sources', 'Rolls-Royce',   'Rolls-Royce agency',    'وكالة رولز رويس',     60, 1),
    ('sources', 'Used market',   'Used market',           'السوق المستعمل',      70, 1),
    ('sources', 'Germany',       'Imported from Germany', 'مستورد من ألمانيا',   80, 1),
    ('sources', 'outside',       'Other supplier',        'مورد آخر',           90, 1);

-- ---------------------------------------------------------------------------
-- Who made the part. The same names without the word "agency": a part is made
-- by BMW whoever you bought it from.
-- ---------------------------------------------------------------------------
INSERT INTO list_options (list_name, value, label_en, label_ar, sort_order, is_builtin) VALUES
    ('manufacturers', 'BMW',           'BMW',                   'BMW',               10, 1),
    ('manufacturers', 'Mercedes-Benz', 'Mercedes-Benz',         'مرسيدس بنز',        20, 1),
    ('manufacturers', 'Audi',          'Audi',                  'أودي',               30, 1),
    ('manufacturers', 'Volkswagen',    'Volkswagen',            'فولكس واجن',         40, 1),
    ('manufacturers', 'Rolls-Royce',   'Rolls-Royce',           'رولز رويس',          50, 1),
    ('manufacturers', 'Porsche',       'Porsche',               'بورشه',              60, 1),
    ('manufacturers', 'Volvo',         'Volvo',                 'فولفو',              70, 1),
    ('manufacturers', 'Used market',   'Used market',           'السوق المستعمل',     80, 1),
    ('manufacturers', 'Germany',       'Imported from Germany', 'مستورد من ألمانيا',  90, 1),
    ('manufacturers', 'Other',         'Other',                 'أخرى',              100, 1);

-- ---------------------------------------------------------------------------
-- How a line is counted. These were a literal list inside three templates.
-- ---------------------------------------------------------------------------
INSERT INTO list_options (list_name, value, label_en, label_ar, sort_order, is_builtin) VALUES
    ('units', 'pcs',   'pcs',   'حبة',  10, 1),
    ('units', 'hour',  'hour',  'ساعة', 20, 1),
    ('units', 'litre', 'litre', 'لتر',  30, 1),
    ('units', 'set',   'set',   'طقم',  40, 1),
    ('units', 'km',    'km',    'كم',   50, 1);

-- ---------------------------------------------------------------------------
-- How the customer paid.
-- ---------------------------------------------------------------------------
INSERT INTO list_options (list_name, value, label_en, label_ar, sort_order, is_builtin) VALUES
    ('payment_methods', 'cash',     'Cash',          'نقداً',      10, 1),
    ('payment_methods', 'card',     'Card',          'بطاقة',      20, 1),
    ('payment_methods', 'transfer', 'Bank transfer', 'تحويل بنكي', 30, 1),
    ('payment_methods', 'cheque',   'Cheque',        'شيك',        40, 1),
    ('payment_methods', 'other',    'Other',         'أخرى',       50, 1);

-- ---------------------------------------------------------------------------
-- What kind of customer this is. Changes nothing about how they are billed;
-- it is there so the analytics can tell a fleet from a friend.
-- ---------------------------------------------------------------------------
INSERT INTO list_options (list_name, value, label_en, label_ar, sort_order, is_builtin) VALUES
    ('customer_types', 'regular', 'Regular',            'عادي',          10, 1),
    ('customer_types', 'vip',     'VIP',                'عميل مميز',      20, 1),
    ('customer_types', 'family',  'Family and friends', 'أهل وأصدقاء',    30, 1),
    ('customer_types', 'fleet',   'Fleet or business',  'أسطول أو منشأة', 40, 1);
