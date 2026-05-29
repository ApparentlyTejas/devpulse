-- Runs once on a fresh Postgres data volume.
-- Enables extensions DevPulse relies on. Idempotent.

CREATE EXTENSION IF NOT EXISTS "pgcrypto";   -- UUID generation, secure random
CREATE EXTENSION IF NOT EXISTS "vector";     -- pgvector for embeddings
CREATE EXTENSION IF NOT EXISTS "citext";     -- case-insensitive text (emails)
