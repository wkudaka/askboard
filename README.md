# Askboard

Upload CSVs, ask questions in plain language, get a dashboard built on the fly.

See [`docs/ARCHITECTURE.md`](docs/ARCHITECTURE.md) for the design and the roadmap.

**Status:** phase 1 (scaffold): PostgreSQL + metadata schema and read-only role, FastAPI with
health checks and auto-migrations, React app shell showing API status.

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
