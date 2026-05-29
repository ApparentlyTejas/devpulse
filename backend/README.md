# DevPulse Backend

FastAPI + SQLAlchemy async + Postgres + Redis. Single Python package backs
three runtime entrypoints: the API, the worker, and the MCP server.

## Layout

```
backend/
├── app/
│   ├── main.py               FastAPI app factory
│   ├── api.py                Mounts module routers under /api/v1
│   ├── core/                 Config, logging, security, exceptions
│   ├── db/                   Async engine, session, base
│   ├── modules/<domain>/     Vertical slices: model, schema, repo, service, router
│   ├── workers/              APScheduler + arq background work
│   └── mcp_server/           MCP entrypoint + tools
├── alembic/                  Migrations
├── tests/                    unit / integration / e2e
└── pyproject.toml            uv-managed deps, ruff, mypy, pytest config
```

## Dev workflow (inside the backend container or with local uv)

```bash
uv sync --extra dev
uv run uvicorn app.main:app --reload
uv run pytest
uv run ruff check .
uv run mypy app
```
