# Historical database migrations

These scripts document schema changes that predate Alembic. They are retained
for archaeology only and must not be run against the current schema.

Use these commands for all active schema changes:

```bash
uv run alembic upgrade head
uv run alembic current
```

Create each future schema change as a new file under `alembic/versions/`.
