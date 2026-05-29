"""Database layer.

Owns the async SQLAlchemy engine, the per-request session, the Redis client,
and health-check helpers. The rest of the app talks to Postgres and Redis
exclusively through this package.
"""
