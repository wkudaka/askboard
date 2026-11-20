# Askboard — Architecture

> Upload CSVs → load them into PostgreSQL → ask questions in natural language → get a dashboard
> assembled on the fly (KPIs, bar/line/pie charts, tables + a written summary).

Evolution of `../sales-analytics-agent-wk` (LangGraph NL→SQL over SQLite, prose answers).
Askboard is a new project; it reuses that project's graph design, LLM factory and SQL guardrails.

## Decisions

| Topic | Decision |
|---|---|
| Layout | Monorepo: `backend/` (Python) + `frontend/` (TS) + `docker-compose.yml` |
| Backend | FastAPI + LangGraph, psycopg 3 (async pool), sqlglot for SQL validation |
| Database | PostgreSQL 16 (docker compose) |
| LLM | Reuse `llm_factory` (OpenRouter / Bedrock) |
| Frontend | React + Vite + TypeScript, Recharts, TanStack Query, Tailwind |
| Datasets | **Workspace** = group of related CSVs; each CSV = one table; JOINs allowed between them |
| Viz choice | **Hybrid**: deterministic rules on result shape pick the chart; LLM writes title/summary and resolves ambiguous cases |

## High-level flow

```
            ┌──────────── frontend (React) ─────────────┐
            │ Upload/Schema review │  Ask → <Dashboard/> │
            └──────────┬───────────┴──────────┬──────────┘
                       │ multipart            │ POST /ask (SSE later)
            ┌──────────▼──────────────────────▼──────────┐
            │                FastAPI                      │
            │  ingestion service      LangGraph "ask"     │
            │  (sniff, infer types,   (plan → SQL → exec  │
            │   COPY, profile,         → correct → viz    │
            │   infer relationships)   → summary)         │
            └──────────┬──────────────────────┬──────────┘
                       │ owner role           │ read-only role
            ┌──────────▼──────────────────────▼──────────┐
            │ Postgres: schema `askboard` (metadata)      │
            │           schema `ws_<id>` per workspace    │
            └─────────────────────────────────────────────┘
```

## Data model

**Metadata schema `askboard`:**
- `workspaces(id, name, created_at)`
- `datasets(id, workspace_id, table_name, original_filename, row_count, created_at)`
- `columns(dataset_id, name, original_name, pg_type, semantic_type, null_ratio, distinct_count, min, max, sample_values jsonb, is_unique)`
  - `semantic_type`: `id | categorical | numeric | currency | temporal | boolean | text`
- `relationships(id, workspace_id, from_dataset, from_column, to_dataset, to_column, confidence, status)`
  - `status`: `suggested | confirmed | rejected`
- `questions(id, workspace_id, question, sql jsonb, dashboard jsonb, created_at)` (history)

**Data:** each workspace gets its own schema `ws_<short_id>`; each CSV becomes a table there.

## Ingestion pipeline (`backend/askboard/ingestion/`)

1. **Sniff**: detect encoding (utf-8 → latin-1 fallback), delimiter (`csv.Sniffer`) and header.
2. **Normalize names**: tables and columns become snake_case ASCII, deduplicated, and reserved words get escaped. The original names are kept in the metadata.
3. **Infer types** (pandas over a sample, then validated on the full file): int → bigint, float/decimal (handles `1.234,56` / `R$`) → numeric, dates (ISO, `dd/mm/yyyy`) → date/timestamp, bool, else text.
4. **Preview step**: the API returns the inferred schema; the user can fix types and names in the UI before confirming.
5. **Load**: `CREATE TABLE` + `COPY` with psycopg 3. Rows that fail to cast are counted and reported, never silently dropped.
6. **Profile**: compute null ratio, distinct count, min/max, top values and uniqueness, then store them in `columns`.
7. **Relationship inference** (for multiple CSVs):
   - candidates: name match (`customer_id` ↔ `customers.id`, same column name in two tables), compatible types, and a target column that is unique;
   - score: the share of distinct values on the FK side that exist on the PK side (≥ 0.9 → suggested);
   - the user confirms or rejects suggestions in the UI. Only confirmed (or high-confidence) relationships are sent to the LLM as join hints.

Limits for the MVP: 50 MB per file, synchronous ingestion. A background job comes later.

## Ask graph (`backend/askboard/graph/`)

Reuse the shape of `sales-analytics-agent-wk/src/graph/graph.py`, plus two new nodes:

```
extract_question → load_context → query_planner → sql_generator → sql_executor
                                                        ▲              │
                                                        └ sql_correction┘ (retry ≤ N)
                                    (multi-step loops back to sql_generator)
sql_executor → viz_planner → narrative → END
```

- **extract_question**: reused as is (sanitization, length limit).
- **load_context** (new): builds the LLM context from metadata (tables, columns with semantic type and sample values, confirmed relationships). It replaces the hard-coded `SALES_CONTEXT` and the SQLite DDL.
- **query_planner / sql_generator / sql_correction**: reused. Prompts switch to the Postgres dialect and the dynamic context. Multi-step sub-questions become multiple dashboard panels.
- **sql_executor**: reused logic, but runs on Postgres with these guardrails:
  - parse with `sqlglot` (dialect postgres): a single statement, `SELECT`/`WITH` only, and every referenced table must belong to the workspace schema;
  - runs as the `askboard_reader` role (USAGE/SELECT on `ws_*` only, no access to `askboard`), in a `READ ONLY` transaction with `SET LOCAL search_path = ws_<id>` and `SET LOCAL statement_timeout = '10s'`;
  - a wrapping `LIMIT` (as in `_enforce_result_limit`).
- **viz_planner** (new, hybrid):
  1. **Profile the result**: classify each column as temporal / categorical / numeric from the Postgres type, the metadata and the values.
  2. **Rules** pick the default panel:
     | Result shape | Panel |
     |---|---|
     | 1 row × 1 numeric (or several numerics) | `kpi` (one card per metric) |
     | temporal + 1..n numeric | `line` (bar if ≤ 3 points) |
     | categorical + 1 numeric, ≤ 6 categories, part-of-whole (sum/count) | `pie` (donut) |
     | categorical + 1 numeric, otherwise | `bar` (horizontal when labels are long; top 15 + "Others") |
     | categorical + categorical + numeric | `stacked_bar` / grouped bar |
     | 2 numeric (no category) | `scatter` |
     | anything else / many columns | `table` |
  3. **LLM refine** (structured output): it writes the title, axis labels and number format (currency, %, integer). It may switch the chart type only among the alternatives the rules flagged as valid, and gets no free-form choice.
- **narrative**: replaces `analytical_response`. It writes a short summary (2–4 bullets of insights) plus follow-up questions.

## API contract

```
POST /workspaces                                  → Workspace
POST /workspaces/{id}/datasets (multipart, n files) → InferredSchema[] (preview)
POST /workspaces/{id}/datasets/{ds}/confirm       → Dataset (after type/name edits)
GET  /workspaces/{id}/schema                      → tables, columns, relationships
PUT  /workspaces/{id}/relationships/{rel}         → confirm / reject
POST /workspaces/{id}/ask  {question}             → Dashboard
GET  /workspaces/{id}/questions                   → history
GET  /healthz, /readyz
```

**`Dashboard` (the key contract between backend and frontend; Pydantic models → generated TS types):**

```jsonc
{
  "title": "Revenue by payment method",
  "summary": ["Credit card is 52% of revenue", "..."],
  "panels": [
    {
      "id": "p1",
      "type": "kpi | bar | line | pie | stacked_bar | scatter | table",
      "title": "Total revenue",
      "data": [{ "payment_method": "credit_card", "revenue": 1234.5 }],
      "encoding": { "x": "payment_method", "y": ["revenue"], "series": null },
      "format": { "revenue": "currency" },
      "alternatives": ["bar", "table"],      // the UI can toggle between these
      "sql": "SELECT ..."
    }
  ],
  "follow_ups": ["..."]
}
```

The frontend never decides *what* to show. It renders whatever the spec says, which keeps it simple and testable.

## Frontend (`frontend/src/`)

- `pages/Workspaces`, `pages/Upload` (drag & drop several CSVs → preview table with editable types → relationship review), `pages/Ask` (question box + history of dashboards).
- `components/dashboard/Dashboard.tsx` lays the panels out in a responsive grid, with KPIs on top and charts below.
- `components/panels/registry.ts` maps `type → component` (`KpiPanel`, `BarPanel`, `LinePanel`, `PiePanel`, `StackedBarPanel`, `ScatterPanel`, `TablePanel`). Each panel has an "alternatives" toggle and a "show SQL" toggle.
- `api/` uses TanStack Query hooks. Types are generated from FastAPI's OpenAPI schema (`openapi-typescript`).

## Folder layout

```
askboard/
  docker-compose.yml        # postgres + backend + frontend
  backend/
    pyproject.toml
    askboard/
      config.py  logging_config.py  runtime.py  server.py  main.py
      db/          database.py, migrations/ (NNN_name.sql + discovery)
      ingestion/   sniff.py, infer_types.py, loader.py, profile.py, relationships.py
      graph/       graph.py, state.py, nodes/ (reused + load_context, viz_planner, narrative)
      viz/         result_profile.py, rules.py, spec.py (Pydantic Dashboard/Panel)
      prompts/v1/
      services/    llm_factory.py (copied), postgres_service.py, sql_guard.py (sqlglot)
    tests/
  frontend/
    package.json  vite.config.ts
    src/ api/ pages/ components/{dashboard,panels}/
  docs/ARCHITECTURE.md
```

## Implementation phases

1. **Scaffold**: monorepo, docker compose with Postgres, metadata schema and roles, FastAPI health checks, Vite app shell.
2. **Single-CSV ingestion**: sniff, infer types, preview, confirm, COPY, profile. Upload page with type preview.
3. **Ask graph on Postgres**: port the nodes, add `load_context` and the `sql_guard`. Return only `table` panels at first.
4. **Viz planner + dashboard**: rules, LLM refine, narrative, plus the panel registry and the alternatives toggle.
5. **Multiple related CSVs**: relationship inference, review UI, join hints in the context.
6. **Polish**: SSE progress per graph node, question history, background ingestion, LangSmith tracing.

## Testing

- Unit (no LLM, no DB): type inference (BR number and date formats), name normalization, relationship scoring, `sql_guard`, `viz/rules.py` (a table-driven test per result shape).
- Integration: pytest against the docker compose Postgres (upload sample CSVs → schema → executor with the read-only role, checking that writes and cross-schema access are blocked).
- Graph: mocked LLM, like the current `tests/test_graph_routing.py`.
- Frontend: Vitest + Testing Library, rendering every panel type from fixture `Dashboard` JSONs.
- E2E check: `docker compose up`, upload a sample `orders.csv` + `customers.csv`, then ask "revenue by city" (expect a bar chart), "share of revenue by payment method" (pie), "revenue per month" (line) and "total revenue" (KPI).
