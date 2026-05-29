# ADR-0001: Monorepo layout with domain-driven backend

- **Status:** Accepted
- **Date:** 2026-05-19
- **Deciders:** DevPulse engineering

## Context

DevPulse comprises a FastAPI backend, a React frontend, background workers,
an MCP server, and infrastructure-as-code. We need a repository structure
that supports:

1. Independent runtime processes (api, worker, mcp) that share Python code.
2. Cross-cutting changes that touch backend + frontend (e.g., adding a field).
3. A single CI pipeline that can lint/test/build everything.
4. Reviewability: a hiring manager opening the repo should grok the
   architecture within minutes.

## Decision

We use a **single Git repository** ("monorepo") with these top-level dirs:

```
backend/         FastAPI + workers + MCP — one Python package
frontend/        React app
infrastructure/  Terraform, Nginx, Postgres init scripts
docs/            Architecture, ADRs, runbooks
docker-compose.yml + Makefile at the root
```

Within `backend/app/` we use a **domain-driven (vertical slice) layout**:
each bounded context (auth, organizations, services, metrics, alerts,
incidents, ai) is a folder containing its own `models.py`, `schemas.py`,
`repository.py`, `service.py`, `router.py`.

The api, worker, and MCP server are separate process entrypoints under the
same Python package (`app/main.py`, `app/workers/`, `app/mcp_server/`).

## Alternatives considered

- **Polyrepo (one repo per service).** Rejected: too much overhead for a
  one-engineer project; cross-cutting changes become N PRs.
- **Monorepo with build orchestration (Turborepo, Nx, Bazel).** Rejected:
  the configuration tax doesn't pay off below ~5 engineers.
- **Flat layered backend layout (`models/`, `routers/`, `schemas/`).**
  Rejected: works at 5 endpoints, collapses at 50. Vertical slices scale.
- **Separate Python packages for api, worker, mcp.** Rejected: creates
  dependency drift between processes and a real chance of inconsistent
  behavior. Same package, different entrypoints, is simpler and safer.

## Consequences

**Positive**

- One PR can touch backend, frontend, and infra atomically.
- New domain features land as one self-contained folder.
- The api/worker/mcp split is enforced by entrypoint, not by package boundary,
  which keeps shared logic shared.

**Negative**

- Repo size grows over time. We accept this; GitHub handles repos of this
  size trivially.
- Frontend and backend test pipelines must be scoped (changed-files-aware)
  in CI to stay fast. Mitigated by GitHub Actions `paths:` filters.

## Follow-ups

- ADR-0002: dependency management (uv) — accepted.
- ADR-0003: background jobs (APScheduler + arq) — accepted.
- ADR-0004: multi-tenancy isolation model — pending (will document
  shared-DB-shared-schema + repository-enforced tenant scope).
