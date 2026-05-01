# Project memory — TaskFlow service

<!--
================================================================================
 STEP 1 of Exercise 2 — Project-level CLAUDE.md.
 This file is loaded automatically by Claude Code when it's launched in
 this directory. It's the place to put information that applies to the
 WHOLE project (every file Claude Code might touch).

 Use it for:
   - Project conventions that don't fit a single subdirectory
   - The tech stack and build commands
   - "Always do X / never do Y" team norms
   - Pointers to other docs

 Do NOT use it for:
   - Path-specific rules (those go in .claude/rules/, see Step 2)
   - Skills (those go in .claude/skills/, see Step 3)
   - Personal preferences (those belong in your user-level CLAUDE.md
     at ~/.claude/CLAUDE.md, NOT here in the repo)
================================================================================
-->

## What this project is

TaskFlow is a small task-management HTTP API built on FastAPI with a
PostgreSQL backend. It uses the repository pattern to separate the
HTTP layer from the data layer.

## Tech stack

- Python 3.11+, FastAPI, Pydantic v2
- PostgreSQL (asyncpg driver)
- pytest for tests, ruff for linting, mypy --strict for typing

## Project conventions (apply everywhere)

- **Type hints are mandatory** on every public function. `mypy --strict`
  must pass before merging.
- **Errors are raised, not returned.** Custom exception classes live in
  `src/core/errors.py`. The API layer turns exceptions into HTTP
  responses.
- **No `print()` calls in `src/`**. Use the `logging` module.
- **No business logic in API handlers.** Handlers parse the request,
  delegate to a repository or service, and serialize the response.

## Build / run commands

```bash
pip install -e ".[dev]"         # install with dev extras
pytest -q                       # run tests
ruff check src/ tests/          # lint
mypy --strict src/              # typecheck
uvicorn src.main:app --reload   # run the dev server on :8000
```

## When making changes, please

- Read the rule file under `.claude/rules/` that matches the path
  you're editing — those rules are MANDATORY for that subtree.
- For multi-file or risky changes, use plan mode FIRST. See
  `plan-mode.md`.
- For code review, the `/review-pr` slash command applies our project
  review checklist.
