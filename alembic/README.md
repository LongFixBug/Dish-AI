# FoodAI database migrations

Alembic is the only supported owner of schema changes.

## Fresh database

```bash
uv run alembic upgrade head
```

This runs the baseline and every later revision.

## Existing database created before Alembic

First confirm that both `vn_ingredients` and `vn_dishes` already exist. Then
record the baseline without replaying it, and apply later changes:

```bash
uv run alembic stamp 0001_existing_schema
uv run alembic upgrade head
```

## Development checks

```bash
uv run alembic current
uv run alembic check
```

Never edit a revision that has already been applied. Add a new linear revision
under `alembic/versions/` instead.
