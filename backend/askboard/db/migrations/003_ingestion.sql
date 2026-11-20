-- CSV ingestion: keep the raw upload between preview and confirm, plus parse metadata.

ALTER TABLE askboard.datasets
    ADD COLUMN IF NOT EXISTS source_format jsonb NOT NULL DEFAULT '{}'::jsonb,
    ADD COLUMN IF NOT EXISTS load_errors   jsonb NOT NULL DEFAULT '[]'::jsonb;

ALTER TABLE askboard.columns
    ADD COLUMN IF NOT EXISTS parse_options jsonb NOT NULL DEFAULT '{}'::jsonb;

-- Raw bytes of an upload awaiting confirmation; deleted once the table is loaded.
CREATE TABLE IF NOT EXISTS askboard.dataset_sources (
    dataset_id uuid PRIMARY KEY REFERENCES askboard.datasets(id) ON DELETE CASCADE,
    content    bytea NOT NULL,
    created_at timestamptz NOT NULL DEFAULT now()
);

REVOKE ALL ON askboard.dataset_sources FROM PUBLIC;
