-- Read-only role used to run LLM-generated SQL.
-- The application user switches to it with `SET LOCAL ROLE askboard_reader` inside a
-- READ ONLY transaction. Per-workspace USAGE/SELECT grants are added when a workspace
-- schema is created; the reader never gets access to the `askboard` metadata schema.

DO $$
BEGIN
    IF NOT EXISTS (SELECT 1 FROM pg_roles WHERE rolname = 'askboard_reader') THEN
        CREATE ROLE askboard_reader NOLOGIN NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT;
    END IF;
END
$$;

-- Allow the application user (the migration runner) to SET ROLE to the reader.
DO $$
BEGIN
    EXECUTE format('GRANT askboard_reader TO %I', current_user);
END
$$;

REVOKE ALL ON SCHEMA askboard FROM PUBLIC;
REVOKE ALL ON ALL TABLES IN SCHEMA askboard FROM PUBLIC;
REVOKE ALL ON SCHEMA askboard FROM askboard_reader;
REVOKE ALL ON ALL TABLES IN SCHEMA askboard FROM askboard_reader;

-- Nobody but the owner may create objects in public (default since PG15, explicit here).
REVOKE CREATE ON SCHEMA public FROM PUBLIC;
REVOKE ALL ON SCHEMA public FROM askboard_reader;
