# Plan mode vs direct execution

> **STEP 5 of Exercise 2** — when to plan first, and when to just go.

Claude Code has two execution modes:

- **Direct execution** — Claude Code reads the request, decides what to
  do, and starts doing it (with your approval at the tool call level).
- **Plan mode** — Claude Code produces a written plan FIRST, you review
  and approve the plan, and only then does it execute. Tools that
  modify files / run code are gated until the plan is accepted.

Plan mode adds a confirmation step. That's friction. But for some
changes the friction is exactly what you want.

---

## When to use plan mode

Use plan mode when **any** of these is true:

| Signal | Why plan mode helps |
|---|---|
| The change spans 3+ files | A plan lets you spot wrong assumptions before any file is touched. |
| The change touches public API | Once you ship a wrong public API, you can't take it back without a deprecation. |
| You're not sure what files to touch | Asking the model "what's your plan?" surfaces gaps in YOUR understanding too. |
| Migration or schema change | Reverting a migration after the fact is painful. |
| The work is exploratory and you don't have a clear ask | Plan mode forces the model to articulate its understanding so you can correct it. |
| Junior teammate is reviewing — useful as a paper trail | Plans are great PR descriptions. |

## When NOT to use plan mode

Direct execution is fine when **all** of these are true:

| Signal | Why a plan would be overhead |
|---|---|
| Single-file, small change | A typo, a renamed variable, an obvious bug. |
| You've already done the design | You're just asking the model to type it out. |
| Test-only change | Even if it's wrong, the worst case is the test fails. |
| Throwaway script | The blast radius is one file you'll delete tomorrow. |

---

## Three concrete examples for this project

### Example A — "Fix the typo in the docstring of `tasks.py`"

**Decision: direct execution.** Single-file, zero blast radius. Plan
mode would be slower with no benefit.

### Example B — "Add a `due_date` field to tasks"

**Decision: plan mode.** Touches:

- `src/db/models.py` (Pydantic model)
- `src/db/repository.py` (queries)
- `src/api/schemas.py` (request/response models)
- `src/api/tasks.py` (handlers)
- `tests/test_tasks.py`
- a new `migrations/` file

Six files plus a schema change. You want a plan to confirm the model
has the right list before any edit lands.

### Example C — "Refactor the repository pattern to use SQLAlchemy"

**Decision: plan mode, mandatory.** Wide blast radius (everything
under `src/db/`). Touches every endpoint indirectly. You need to see
the plan AND consider whether you actually want to do this — the
plan itself is partly a forcing function for the conversation about
"is this even a good idea?"

---

## How to enter plan mode in Claude Code

The exact key/command depends on your client (terminal, Cursor,
VS Code extension, etc.). Generally:

- **Terminal Claude Code**: type `/plan` or use the in-session keybind
  shown by `/help`.
- **Editor integrations**: there's usually a toggle/button labeled
  "Plan" near the input box.

You can also pre-decide in your prompt: "First, propose a plan. Wait
for me to approve before executing." Even without entering plan mode
formally, that phrasing shifts the model into plan-first behavior.
