-- The item code, recorded on every line that quotes one.
--
-- Lines already snapshot their description, their kind, their unit and
-- their price, so that editing the catalogue never changes a document
-- that has already gone out. The code has to be snapshotted for exactly
-- the same reason: it is the reference the customer and the workshop
-- quote at each other afterwards, and an invoice reprinted a year later
-- must show the code it was raised under, not whatever that catalogue
-- row happens to say today.
--
-- Empty for lines written before this, and empty for custom lines that
-- name no catalogue item -- which stays an ordinary thing to want.

ALTER TABLE invoice_items ADD COLUMN code TEXT NOT NULL DEFAULT '';
ALTER TABLE estimate_items ADD COLUMN code TEXT NOT NULL DEFAULT '';
ALTER TABLE repair_order_items ADD COLUMN code TEXT NOT NULL DEFAULT '';

-- Backfill from the catalogue for lines that still point at an item.
-- This is the one moment it is right to copy the current code onto an
-- old line: before today nothing recorded one, so the catalogue's answer
-- is the only answer there is, and leaving them blank would lose a
-- reference that is still correct for almost all of them.
UPDATE invoice_items
   SET code = COALESCE((SELECT c.code FROM catalog_items c
                         WHERE c.id = invoice_items.catalog_item_id), '')
 WHERE catalog_item_id IS NOT NULL;

UPDATE estimate_items
   SET code = COALESCE((SELECT c.code FROM catalog_items c
                         WHERE c.id = estimate_items.catalog_item_id), '')
 WHERE catalog_item_id IS NOT NULL;

UPDATE repair_order_items
   SET code = COALESCE((SELECT c.code FROM catalog_items c
                         WHERE c.id = repair_order_items.catalog_item_id), '')
 WHERE catalog_item_id IS NOT NULL;
