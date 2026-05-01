---
# ──────────────────────────────────────────────────────────────────────
# STEP 2 of Exercise 2 — Path-scoped rule with YAML frontmatter.
#
# The `globs:` field tells Claude Code: "only inject this rule into the
# context window when the files being edited match one of these patterns."
# That keeps the API rules out of the way when you're working on tests
# or DB code (which have their own rules), and prevents Claude Code's
# context from filling up with rules that don't apply.
#
# `description:` is a short summary that may be shown in tooling.
# ──────────────────────────────────────────────────────────────────────
description: HTTP API conventions for FastAPI handlers
globs:
  - "src/api/**/*.py"
---

# API conventions

These rules apply when editing anything under `src/api/`.

## Handler shape

Every endpoint handler MUST:

1. Use FastAPI's `APIRouter` (no module-level `@app.X` decorators).
2. Take a Pydantic v2 request model (or path/query params); never raw
   `dict`/`Request` unless there's a specific reason.
3. Return a Pydantic v2 response model, never a raw dict.
4. Be `async def` — the whole stack is async.
5. Delegate to a repository (`src/db/`) or service for any logic
   beyond request parsing and response shaping.

Example:

```python
from fastapi import APIRouter, Depends
from src.db.repository import TaskRepository
from src.api.schemas import TaskCreate, TaskRead

router = APIRouter(prefix="/tasks", tags=["tasks"])

@router.post("/", response_model=TaskRead)
async def create_task(
    body: TaskCreate,
    repo: TaskRepository = Depends(),
) -> TaskRead:
    task = await repo.create(body)
    return TaskRead.model_validate(task)
```

## Errors

Raise exceptions from `src/core/errors.py`. A FastAPI exception handler
converts them to HTTP responses — handlers do not call
`raise HTTPException(...)` directly.

## Status codes

- POST creating a resource → 201
- DELETE → 204 (no body)
- PUT/PATCH → 200 with the updated resource
- GET on a missing resource → raise `NotFoundError` (handler turns it
  into 404)
