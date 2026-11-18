-- Indexes for the queries that were measured to need them.
--
-- Every index here was tried against EXPLAIN QUERY PLAN on a database of six
-- thousand cars and five thousand invoices, and kept only because the planner
-- actually chose it. Two more were written and thrown away: an index on
-- `vehicles(make)` alone, which the composite below covers, and one on
-- `model_year`, which cannot help a query that groups cars into five-year
-- bands because the band is computed per row. An index nothing chooses is not
-- free -- it is written on every insert and update, and it misleads the next
-- person into thinking the query it was named for is covered.

-- Sorting a list by its most-used column. The list pages sort case-
-- insensitively, so the existing plain indexes on `name` and `plate_no` could
-- not serve them: SQLite will not use an index whose collation differs from
-- the one in the ORDER BY. Paging made this matter -- "page 40" has to skip
-- 1,950 rows, and skipping them in index order costs nothing while sorting
-- the whole table to find them costs everything.
CREATE INDEX idx_customers_name_nocase ON customers (name COLLATE NOCASE);
CREATE INDEX idx_vehicles_plate_nocase ON vehicles (plate_no COLLATE NOCASE);

-- The analytics panel groups the fleet by make and model, almost always
-- among the active cars only. Leading with `is_active` lets one index serve
-- both the unfiltered charts and the ones narrowed to a single make.
CREATE INDEX idx_vehicles_active_make ON vehicles (is_active, make, model);

-- Cars by colour, which is a pie of the whole fleet rather than the active
-- part of it, so it needs its own.
CREATE INDEX idx_vehicles_colour ON vehicles (colour);

-- The invoice list filtered by status, newest first -- the single most common
-- thing anybody does on that page. The existing indexes covered status and
-- date separately, which let SQLite narrow by one and then sort by the other.
CREATE INDEX idx_invoices_status_date ON invoices (status, issue_date DESC);

-- Give the planner statistics to choose with. Without these it guesses from
-- table shape alone, and guesses wrong on exactly the queries above: it has
-- no way to know that 'issued' is most of the invoices table while a
-- particular make is a twentieth of the vehicles.
ANALYZE;
