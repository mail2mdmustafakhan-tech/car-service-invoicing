-- The marques the workshop services, for the ribbon along the bottom of the
-- screen.
--
-- A sixth entry in the same `list_options` table rather than a new setting
-- of its own, so it is edited on the screen that already exists for exactly
-- this: Settings -> Dropdown lists. Take one off the list and it leaves the
-- ribbon.
--
-- Deliberately separate from the `manufacturers` list, which answers a
-- different question. That one includes "Used market", "Imported from
-- Germany" and "Other", because those are real answers to "who made this
-- part". They are not marques, and they have no business in a line that
-- says what the workshop works on.
--
-- These are names set in the application's own typeface. The manufacturers'
-- logos are their trademarks and are not reproduced here -- and a workshop
-- that is not an authorised dealer has its own reason to want names rather
-- than badges on its paperwork.

INSERT INTO list_options (list_name, value, label_en, label_ar, sort_order, is_builtin) VALUES
    ('marques', 'BMW',           'BMW',           'BMW',         10, 1),
    ('marques', 'M Sport',       'M Sport',       'إم سبورت',    20, 1),
    ('marques', 'Mercedes-Benz', 'Mercedes-Benz', 'مرسيدس بنز',  30, 1),
    ('marques', 'AMG',           'AMG',           'AMG',         40, 1),
    ('marques', 'Audi',          'Audi',          'أودي',         50, 1),
    ('marques', 'Volkswagen',    'Volkswagen',    'فولكس واجن',   60, 1),
    ('marques', 'Porsche',       'Porsche',       'بورشه',        70, 1),
    ('marques', 'Volvo',         'Volvo',         'فولفو',        80, 1),
    ('marques', 'Rolls-Royce',   'Rolls-Royce',   'رولز رويس',    90, 1);
