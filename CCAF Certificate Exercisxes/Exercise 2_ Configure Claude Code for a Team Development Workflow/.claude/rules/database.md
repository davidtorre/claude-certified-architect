---
# ──────────────────────────────────────────────────────────────────────
# STEP 2 of Exercise 2 — A SECOND path-scoped rule.
#
# A different glob scope demonstrates that you can have multiple rules,
# each active only when the files being edited match. When Claude Code
# is editing src/api/tasks.py, only api-conventions.md activates.
# When it's editing src/db/repository.py, only THIS rule activates.
# ──────────────────────────────────────────────────────────────────────
description: Database layer conventions (repository pattern, asyncpg)
globs:
  - "src/db/**/*.py"
---

# Database conventions

These rules apply when editing anything under `src/db/`.

## Repository pattern

All data access goes through repository classes in `src/db/repository.py`.
Repositories:

- Take an asyncpg `Connection` or `Pool` via dependency injection
- Return ORM-free domain objects (Pydantic models from
  `src/db/models.py`), NOT asyncpg `Record` rows
- Use parameterized queries (`$1`, `$2`, ...) — never f-string
  interpolation into SQL
- Are stateless: no class-level mutable state

## Connection management

Endpoints get a connection from the pool via FastAPI dependency
injection — they NEVER call `asyncpg.connect()` directly. The pool
lives on `app.state.db_pool` and is created in `src/main.py`'s
lifespan.

## Migrations

Schema changes go in `migrations/` as numbered SQL files
(`001_create_tasks.sql`, etc.). Never edit a migration that's been
merged — write a new one.

## Forbidden patterns

- ❌ Raw `await connection.execute(f"SELECT ... {user_input}")`  (SQL injection)
- ❌ `cursor` (asyncpg doesn't have one — use `fetch`/`fetchrow`/`fetchval`)
- ❌ Returning asyncpg `Record` objects across the repository boundary
