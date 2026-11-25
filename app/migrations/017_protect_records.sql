-- A switch that stops the application deleting records outright.
--
-- Anything with an invoice attached is already protected: the delete is
-- refused and the user is told to mark it inactive instead. The gap this
-- closes is everything else -- a customer with no invoices yet, a vehicle
-- entered twice, a draft invoice -- which today vanishes entirely.
--
-- Off by default on purpose. While the register is being imported and
-- tidied up, deleting a mistyped row is the right thing to do and having
-- to hunt down inactive duplicates afterwards would be worse. Switched on
-- once the data is clean, every delete becomes "make inactive" instead.

ALTER TABLE settings ADD COLUMN protect_records INTEGER NOT NULL DEFAULT 0;
