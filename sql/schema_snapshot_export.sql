-- Schema snapshot export: one query on any warehouse produces the JSON
-- rows ddr diffs against. Run before and after applying the migration to
-- a disposable CI database to get both snapshots for migration mode.

-- Generic information_schema (Postgres, DuckDB, SQL Server, MySQL 8+)
SELECT table_name  AS "table",
       column_name AS "column",
       data_type   AS "type"
FROM information_schema.columns
WHERE table_schema = 'ANALYTICS';

-- Snowflake variant (account-level view, filter to the reporting schema)
SELECT table_name  AS "table",
       column_name AS "column",
       data_type   AS "type"
FROM snowflake.account_usage.columns
WHERE table_schema = 'ANALYTICS' AND deleted IS NULL;
