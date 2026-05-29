# ADR-0004: Async SQLAlchemy engine, pooling, and session-per-request

- **Status:** Accepted
- **Date:** 2026-05-20

## Context

DevPulse's API serves WebSockets, AI streaming responses, and ordinary REST
traffic from a single event loop. Any synchronous I/O — including DB calls —
blocks every other in-flight request on that loop.

We need a database access pattern that:

1. Doesn't block the event loop.
2. Maintains a connection pool with safe defaults under realistic load.
3. Gives route handlers a clean, declarative way to receive a session.
4. Plays well with Alembic for migrations.

## Decision

- **Driver:** `asyncpg`. Fastest Python Postgres driver, async-native.
- **ORM layer:** SQLAlchemy 2.0 with the asyncio extension. We use
  `create_async_engine` with these defaults:

  | Setting              | Value | Why |
  | -------------------- | ----- | --- |
  | `pool_size`          | 5     | Long-lived connections per process. |
  | `max_overflow`       | 10    | Burst capacity; closed after use. |
  | `pool_pre_ping`      | True  | ~1ms `SELECT 1` per checkout; kills stale-conn bugs. |
  | `pool_recycle`       | 1800  | Recycle after 30 min to avoid idle timeouts. |
  | `expire_on_commit`   | False (on session) | Prevents `MissingGreenlet` on attribute access after commit. |

- **Session pattern:** one `AsyncSession` per HTTP request, injected via
  the FastAPI `get_db_session` dependency. The dependency manages the
  begin / commit / rollback / close lifecycle.
- **Naming convention:** declared on `MetaData` (`uq_*`, `ix_*`, `ck_*`,
  `fk_*`, `pk_*`) so Alembic generates deterministic constraint names.
- **Alembic:** async-aware `env.py` using `async_engine_from_config` +
  `connection.run_sync(do_run_migrations)`. DSN is pulled from app
  settings, not from `alembic.ini`, so app and migrations share one
  source of truth.

## Alternatives considered

- **Sync `psycopg` + `sync_to_async`.** Works but pollutes async code with
  thread offloading. Loses the latency benefit of asyncpg.
- **databases / encode/databases.** Lightweight async driver-wrapper but
  no ORM and no migrations story. Would force us to maintain raw SQL +
  Alembic separately. Rejected.
- **Tortoise ORM / SQLModel.** Tortoise is async-native but smaller
  community and weaker migration tooling. SQLModel piggybacks on SQLAlchemy
  but the Pydantic-ORM crossover loses clarity at scale; we'd rather use
  SQLAlchemy ORM + separate Pydantic DTOs.

## Consequences

- Single source of truth for the DSN (`app.core.config`), used by both the
  app engine and Alembic. No two-config drift.
- Connection pooling is forgiving of network blips thanks to pre_ping; the
  cost is ~1ms per checkout.
- `expire_on_commit=False` means callers can read attributes from an ORM
  instance after `await session.commit()` without surprise lazy loads.
  They still cannot expect *fresh* values written by another session
  without an explicit `refresh`.
- Migration files have deterministic constraint names that survive being
  re-run against a fresh DB.

## Follow-ups

- Add an observability hook: emit per-query latency to structlog at DEBUG
  level once we have real traffic. SQLAlchemy's event API supports this
  via `before_cursor_execute` / `after_cursor_execute`.
- Consider `pool_size` autosizing per replica count when we move to
  Kubernetes (`pool_size = (worker_count * threads_per_worker) / replicas`).
- Add read replica routing if Phase 4 introduces an RDS read replica.
  SQLAlchemy supports per-bind routing via `Session(binds={Read: ..., Write: ...})`.
