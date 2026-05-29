# Alembic migrations

This directory holds the Alembic environment and all migration scripts.

## Common commands

Run from the host:

```bash
make migrate                          # alembic upgrade head
make revision MSG="add users table"   # autogenerate a new migration
```

Or directly inside the api container:

```bash
docker compose exec api alembic current
docker compose exec api alembic history --verbose
docker compose exec api alembic upgrade head
docker compose exec api alembic downgrade -1
docker compose exec api alembic revision --autogenerate -m "add users table"
```

## Workflow

1. Add a SQLAlchemy model in `app/modules/<domain>/models.py`.
2. Import it in `alembic/env.py` (the `Import all model modules below` block).
3. `make revision MSG="add foo table"` — generates a new file under `versions/`.
4. **Read the generated file before committing.** Autogenerate is good, not
   perfect. Type changes, indexes on JSONB, and CHECK constraints sometimes
   need a manual touch.
5. `make migrate` to apply.
6. Commit the migration file with the model change in the same PR.

## Migration hygiene rules

- One logical change per migration. Don't bundle unrelated table edits.
- Migrations are append-only. Never edit a migration that has been applied
  to any shared environment — write a new one that fixes the issue.
- Downgrades should work. Test with `alembic downgrade -1` locally before merging.
- For destructive operations (DROP COLUMN, DROP TABLE) on a production DB,
  do a two-phase migration: first PR makes the change optional in code,
  second PR drops the column after a deploy cycle.
