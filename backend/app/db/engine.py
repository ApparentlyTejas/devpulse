"""Async SQLAlchemy engine factory.

A single engine instance is created at app startup and disposed at shutdown.
It is held on `app.state.db_engine` (see `app/main.py`). Nothing else in the
codebase constructs engines.

Why a factory function and not a module-level singleton: tests can build a
fresh engine pointed at a testcontainer Postgres without monkeypatching.
"""

from __future__ import annotations

from sqlalchemy.ext.asyncio import AsyncEngine, create_async_engine

from app.core.config import Settings
from app.core.logging import get_logger

logger = get_logger(__name__)


def create_engine(settings: Settings) -> AsyncEngine:
    """Build the application's async SQLAlchemy engine.

    Pool sizing rationale:
      - `pool_size=5`: number of long-lived connections kept open.
      - `max_overflow=10`: extra connections allowed under burst load,
        closed after use. Total max = 15 connections per app process.
      - `pool_pre_ping=True`: tiny SELECT 1 before handing a pooled conn
        to the requester. Costs ~1ms; eliminates stale-connection failures
        after a Postgres restart or network blip.
      - `pool_recycle=1800`: recycle connections every 30 min to avoid
        hitting Postgres `idle_in_transaction_session_timeout` or any
        upstream proxy that closes idle sockets.

    These defaults are sensible for a small-to-medium service. We'd tune
    upward (and add monitoring) once we have real load numbers.
    """
    is_debug = settings.app_env == "local" and settings.app_debug

    engine = create_async_engine(
        settings.postgres.dsn,
        echo=is_debug,  # log every SQL statement in local debug mode
        pool_size=5,
        max_overflow=10,
        pool_pre_ping=True,
        pool_recycle=1800,
        # `future=True` is the default in SQLA 2.0; spelled out for clarity.
        future=True,
    )

    logger.info(
        "db.engine.created",
        host=settings.postgres.host,
        port=settings.postgres.port,
        db=settings.postgres.db,
        echo=is_debug,
    )
    return engine
