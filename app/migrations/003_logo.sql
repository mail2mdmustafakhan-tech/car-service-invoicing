-- ---------------------------------------------------------------------------
-- 003_logo.sql  --  the business logo, printed on contracts and invoices
-- ---------------------------------------------------------------------------
-- Stored in the database rather than as a file on disk. That looks like the
-- odd choice until you consider backups: the whole system is promised to be
-- one file you can copy, and the Settings page's backup button copies exactly
-- that. A logo sitting beside the database would be left out of every backup
-- and quietly lost on the first restore.
--
-- It gets a table of its own rather than another column on `settings`,
-- because every page load reads the settings row. Keeping the image out of
-- that row means a megabyte of PNG is not dragged through the application
-- each time someone opens a list of invoices; it is read only when the logo
-- is actually being served or printed.
-- ---------------------------------------------------------------------------

CREATE TABLE branding (
    id            INTEGER PRIMARY KEY CHECK (id = 1),
    logo_blob     BLOB,
    logo_mime     TEXT NOT NULL DEFAULT '',
    logo_filename TEXT NOT NULL DEFAULT '',
    updated_at    TEXT NOT NULL DEFAULT (datetime('now'))
);

INSERT INTO branding (id) VALUES (1);
