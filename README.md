# Askboard

Upload CSVs, ask questions in plain language, get a dashboard built on the fly.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design and the roadmap.

**Status:** phase 5 (related CSVs) — all phases of the architecture plan are implemented. Natural-language questions are answered by a LangGraph
pipeline (plan → SQL → guard → run → auto-correct → summary) and rendered as a dashboard: KPIs,
line/bar/pie/stacked-bar/scatter charts or tables, chosen from the shape of each result, with a
written summary and follow-up questions. Several CSVs can be uploaded together; Askboard detects
how they join (e.g. `pedidos.cliente_id → clientes.id`) and the LLM uses those relationships.

Questions need an LLM: set `OPENROUTER_API_KEY` in `backend/.env` (local run) or in a `.env` next to
`docker-compose.yml` (Docker). Everything else works without it.

## Layout

```
backend/    FastAPI + psycopg 3 (Python 3.11+)
frontend/   React + Vite + TypeScript
docker/     Postgres init scripts (creates the askboard_test database)
docs/       Architecture
```

## Run

```bash
# Postgres (host port 5433) + backend (port 8000)
docker compose up -d --build --wait

# Frontend (port 5173)
cd frontend
npm install
npm run dev
```

### Backend without Docker

```bash
docker compose up -d --wait db
cd backend
python -m venv .venv
.venv/Scripts/activate          # Linux/macOS: source .venv/bin/activate
pip install -e ".[dev]"
cp .env.example .env
python -m askboard.main         # http://localhost:8000
```

> **Windows:** psycopg's async mode does not work on the default `ProactorEventLoop`.
> Always start uvicorn with `--loop askboard.runtime:new_selector_event_loop`
> (`python -m askboard.main` already does this).

## Endpoints

| Method | Path | Description |
|---|---|---|
| GET | `/healthz` | Liveness: always 200 while the process runs |
| GET | `/readyz` | Readiness: 200 if Postgres answers, 503 otherwise |
| POST | `/workspaces` | Create a workspace (`{"name": ...}`) and its `ws_<id>` schema |
| GET | `/workspaces`, `/workspaces/{id}` | List / get workspaces |
| POST | `/workspaces/{id}/datasets` | Upload a CSV (multipart `file`): returns the inferred schema + first rows |
| POST | `/workspaces/{id}/datasets/{ds}/confirm` | Load it, optionally overriding `table_name` and column `name`/`pg_type` |
| GET | `/workspaces/{id}/datasets[/{ds}]` | List / get datasets with column profiles |
| POST | `/workspaces/{id}/ask` | Answer `{"question": ...}`: title, summary, table panels (with SQL), follow-ups |
| GET | `/workspaces/{id}/questions` | Last 20 answers, newest first |
| GET | `/workspaces/{id}/relationships` | Detected join keys between the workspace tables |
| PATCH | `/workspaces/{id}/relationships/{rel}` | `{"status": "confirmed" \| "rejected" \| "suggested"}` |

### How relationships are detected

After each table is loaded, `askboard/ingestion/relationships.py` proposes candidates **by name**
against a **unique** column of a compatible type in another table (`cliente_id`, `id_cliente`,
`cliente` → `clientes.id`; `customer_id` on both sides; prefixed tables such as `loja_clientes`
match on their last word). Each candidate is then **checked against the data**: it is suggested only
when ≥ 90% of the distinct source values exist in the target. Confirmed and suggested (not rejected)
relationships are given to the LLM as the only allowed JOINs; user decisions survive new uploads.

### How questions are answered

1. **Context**: tables and column profiles of the workspace (types, ranges, sample values).
2. **Plan**: the LLM splits comparisons into up to 3 sub-questions (one panel each).
3. **SQL**: the LLM writes one PostgreSQL `SELECT` per sub-question.
4. **Guard** (`askboard/ask/sql_guard.py`, sqlglot): a single read-only query, only this
   workspace's tables, no dangerous functions (`pg_*`, `set_config`, `dblink`, ...).
5. **Run** as `askboard_reader` in a `READ ONLY` transaction, `search_path` = workspace,
   statement timeout, row limit.
6. **Correct**: guard or Postgres errors go back to the LLM (`MAX_CORRECTION_ATTEMPTS`).
7. **Chart** (`askboard/viz/rules.py`): rules pick the panel from the result shape and list the
   valid alternatives:

   | Result shape | Panel |
   |---|---|
   | 1 row of numbers | KPI figures |
   | date + numbers | line (bar when ≤ 3 points) |
   | date + category + number (≤ 8 series) | multi-line |
   | category + one additive, non-negative number, 2–6 categories | donut |
   | category + numbers (≤ 30 categories) | bar (horizontal for many/long labels) |
   | 2 categories + number | stacked bar |
   | 2 numbers | scatter |
   | anything else | table |

8. **Summary**: title, insight bullets, follow-ups, panel titles, number formats and currency,
   in the question's language. The LLM may only switch a panel to one of its listed alternatives.

Every chart can be switched to its alternatives (always including a table) in the UI. Colors use a
fixed, colorblind-validated categorical order with separate light/dark steps.

### How CSV ingestion works

1. **Detect** encoding (UTF-8, UTF-8 BOM, cp1252) and delimiter (`,` `;` tab `|`).
2. **Normalize** headers into snake_case ASCII identifiers (`Preço Unitário` → `preco_unitario`).
3. **Infer** a type per column from all values: `boolean`, `bigint`, `numeric`, `date`,
   `timestamp`, `timestamptz` or `text`. `;` files default to decimal comma; day-first dates
   unless values prove month-first. Leading-zero codes (CEP, ids) stay `text`.
4. **Review**: the raw file waits in `askboard.dataset_sources` until the user confirms.
5. **Load** with `COPY`; rows that do not fit (wrong column count, unparseable value for a
   forced type) are rejected and reported by line, never silently dropped.
6. **Profile** each column (nulls, distinct, min/max, most frequent values) for the LLM context.

## Tests

The project is developed test-first (red, then green, then refactor).

```bash
# Backend: unit tests always run; integration tests need Postgres and skip otherwise
cd backend
docker compose up -d --wait db
.venv/Scripts/python -m pytest              # all
.venv/Scripts/python -m pytest -m "not integration"

# Frontend
cd frontend
npm test
```

## Database

- `askboard` schema: metadata (workspaces, datasets, columns, relationships, questions)
  and `schema_migrations`.
- `ws_<id>` schemas: one per workspace, holding the uploaded tables (created in phase 2).
- `askboard_reader` role: used via `SET LOCAL ROLE` to run generated SQL. It has no access
  to `askboard` and cannot create objects.
- Migrations live in `backend/askboard/db/migrations/NNN_name.sql`. They run automatically
  on startup (`AUTO_MIGRATE=true`), under an advisory lock, each one in its own transaction.
