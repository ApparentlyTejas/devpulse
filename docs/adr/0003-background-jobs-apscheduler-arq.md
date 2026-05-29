# ADR-0003: APScheduler for periodic jobs, arq for event-driven work

- **Status:** Accepted
- **Date:** 2026-05-19

## Context

DevPulse needs two distinct kinds of background work:

1. **Periodic, idempotent work.** Service health checks every N seconds,
   metric rollups every minute, alert evaluation on a fixed cadence.
2. **Event-driven work.** "An incident was created — enrich it with recent
   metrics." "A log batch arrived — generate embeddings and index it."

These have different semantics. Periodic work is a fan-out from a scheduler.
Event-driven work is a queue with retries and dead-letter behavior.

## Decision

- Use **APScheduler** for periodic work. Run it inside a dedicated
  `worker` container with a single replica (to avoid double-firing). Use
  the Redis or Postgres job store so jobs survive restarts.
- Use **arq** (async Redis-backed queue) for event-driven work. The API
  enqueues jobs; arq workers consume them. arq is async-native, lightweight,
  and integrates cleanly with FastAPI's existing event loop semantics.

## Alternatives considered

- **Celery.** The industry-standard distributed task queue. Battle-tested
  but heavy: separate broker, beat scheduler, result backend, and a sync
  worker model that doesn't compose well with our async stack. We can
  migrate later if scale demands it.
- **APScheduler alone.** Sufficient for periodic work but a poor fit for
  event-driven workloads (no retries, no DLQ, no native back-pressure).
- **Dramatiq, RQ.** Reasonable but sync-first; arq is the async-native
  option that minimizes friction with the FastAPI codebase.

## Consequences

- Two distinct mental models for jobs: cron-like (APScheduler) vs queued
  (arq). Documented in the worker module README.
- Horizontal scaling of event-driven workers is straightforward (run more
  arq replicas). Periodic worker stays at 1 replica unless we add
  leader-election.
- Future migration to Celery is contained: the service layer enqueues
  jobs through a thin abstraction so the underlying engine can be swapped.
