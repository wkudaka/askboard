-- Metadata about workspaces, uploaded datasets, their columns and relationships.
-- User data itself lives in one schema per workspace (ws_<id>), created at runtime.

CREATE SCHEMA IF NOT EXISTS askboard;

CREATE TABLE IF NOT EXISTS askboard.workspaces (
    id          uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    name        text NOT NULL CHECK (length(trim(name)) > 0),
    schema_name text NOT NULL UNIQUE,
    created_at  timestamptz NOT NULL DEFAULT now()
);

CREATE TABLE IF NOT EXISTS askboard.datasets (
    id                uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id      uuid NOT NULL REFERENCES askboard.workspaces(id) ON DELETE CASCADE,
    table_name        text NOT NULL,
    original_filename text NOT NULL,
    status            text NOT NULL DEFAULT 'pending'
                      CHECK (status IN ('pending', 'loaded', 'failed')),
    row_count         bigint,
    rejected_rows     bigint NOT NULL DEFAULT 0,
    created_at        timestamptz NOT NULL DEFAULT now(),
    UNIQUE (workspace_id, table_name)
);

CREATE TABLE IF NOT EXISTS askboard.columns (
    dataset_id     uuid NOT NULL REFERENCES askboard.datasets(id) ON DELETE CASCADE,
    position       int  NOT NULL,
    name           text NOT NULL,
    original_name  text NOT NULL,
    pg_type        text NOT NULL,
    semantic_type  text NOT NULL
                   CHECK (semantic_type IN ('id', 'categorical', 'numeric', 'currency',
                                            'temporal', 'boolean', 'text')),
    null_ratio     double precision,
    distinct_count bigint,
    min_value      text,
    max_value      text,
    sample_values  jsonb NOT NULL DEFAULT '[]'::jsonb,
    is_unique      boolean NOT NULL DEFAULT false,
    PRIMARY KEY (dataset_id, name),
    UNIQUE (dataset_id, position)
);

CREATE TABLE IF NOT EXISTS askboard.relationships (
    id              uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id    uuid NOT NULL REFERENCES askboard.workspaces(id) ON DELETE CASCADE,
    from_dataset_id uuid NOT NULL REFERENCES askboard.datasets(id) ON DELETE CASCADE,
    from_column     text NOT NULL,
    to_dataset_id   uuid NOT NULL REFERENCES askboard.datasets(id) ON DELETE CASCADE,
    to_column       text NOT NULL,
    confidence      double precision NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    status          text NOT NULL DEFAULT 'suggested'
                    CHECK (status IN ('suggested', 'confirmed', 'rejected')),
    created_at      timestamptz NOT NULL DEFAULT now(),
    UNIQUE (from_dataset_id, from_column, to_dataset_id, to_column)
);

CREATE TABLE IF NOT EXISTS askboard.questions (
    id           uuid PRIMARY KEY DEFAULT gen_random_uuid(),
    workspace_id uuid NOT NULL REFERENCES askboard.workspaces(id) ON DELETE CASCADE,
    question     text NOT NULL,
    queries      jsonb NOT NULL DEFAULT '[]'::jsonb,
    dashboard    jsonb,
    error        text,
    created_at   timestamptz NOT NULL DEFAULT now()
);

CREATE INDEX IF NOT EXISTS questions_workspace_created_idx
    ON askboard.questions (workspace_id, created_at DESC);
