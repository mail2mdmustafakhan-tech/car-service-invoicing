-- A warning on a customer's file.
--
-- The workshop's paper register marks certain customers in red, and the note
-- beside them says things like "PLEASE DO NOT RECEIVE THIS CAR". That is a
-- decision somebody made for a reason, and it is worth nothing at all unless
-- it reaches the person at the front desk at the moment the car arrives.
--
-- So this is not a tag or a category. It is a level and a reason, and the
-- level is what decides how hard the application interrupts.

ALTER TABLE customers ADD COLUMN alert_level TEXT NOT NULL DEFAULT ''
    CHECK (alert_level IN ('', 'note', 'check', 'refuse'));

-- Why. Shown with every warning, in the words whoever set it used, because
-- "do not accept" without a reason gets overridden by whoever is on the desk
-- that afternoon.
ALTER TABLE customers ADD COLUMN alert_note TEXT NOT NULL DEFAULT '';

-- When it was set, so an old warning can be recognised as old. A note from
-- four years ago about a dispute that was settled should not read with the
-- same force as one from last week.
ALTER TABLE customers ADD COLUMN alert_set_on TEXT NOT NULL DEFAULT '';

CREATE INDEX idx_customers_alert ON customers (alert_level) WHERE alert_level <> '';
