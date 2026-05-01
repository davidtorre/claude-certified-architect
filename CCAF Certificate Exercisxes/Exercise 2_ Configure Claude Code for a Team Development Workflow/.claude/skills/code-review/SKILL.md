---
# ──────────────────────────────────────────────────────────────────────
# STEP 3 of Exercise 2 — A skill with the three frontmatter fields the
# exercise asks for: `context: fork`, `allowed-tools`, and `argument-hint`.
#
#   context: fork    The skill runs in a FORKED context window — it sees
#                    the conversation up to this point but its work
#                    (reading lots of files, exploring) does NOT pollute
#                    the parent conversation. When the skill returns,
#                    only its final answer comes back to the parent.
#                    Use fork for any skill that does heavy reading or
#                    exploration. Without fork, the parent context fills
#                    up fast.
#
#   allowed-tools    Restricts what tools the skill can call. This skill
#                    only NEEDS to read code, so we deny Edit/Write/Bash.
#                    That makes the skill safe to invoke without prompting
#                    the user for tool approvals.
#
#   argument-hint    A short string Claude Code shows when invoking the
#                    skill, so the user knows what to provide.
# ──────────────────────────────────────────────────────────────────────
name: code-review
description: |
  Review the changes in the current diff against project conventions.
  Reports findings without modifying files. Run before opening a PR.
context: fork
allowed-tools:
  - Read
  - Grep
  - Glob
argument-hint: "(optional) path or PR number to focus on"
---

# Code-review skill

You are a code reviewer for the TaskFlow project. Your job: read the
changed files in the current diff, check them against the project's
conventions, and report findings.

## What to check

1. **Path-scoped rules.** For each changed file, look at the
   corresponding rule in `.claude/rules/` (matched by `globs:`). Flag
   violations.

2. **Type hints.** `mypy --strict` must pass — every public function
   needs full annotations. Flag missing or imprecise annotations
   (`Any`, untyped `dict`).

3. **Tests.** Every code change in `src/` must have either a new test
   or an updated test in `tests/`. Flag changes to `src/` with no
   corresponding test changes.

4. **Forbidden patterns** (CLAUDE.md):
   - `print()` calls in `src/`
   - Business logic in API handlers
   - Raw SQL string interpolation in `src/db/`

5. **Public API stability.** Anything exported from `src/__init__.py`
   or `src/api/` that's renamed or removed is a breaking change —
   call it out explicitly.

## Output format

Produce a markdown report with three sections:

- **Blockers** — must fix before merging
- **Suggestions** — nice to address but not blocking
- **Compliments** — things the change does well

Be specific: cite file paths and line numbers. Don't restate the diff;
the reviewer can already see it.

## What you do NOT do

- You do NOT modify files. (Your `allowed-tools` doesn't include
  Edit/Write — even if you tried, the call would be denied.)
- You do NOT run tests. (Bash is also denied.)
- You do NOT push, merge, or comment on a PR.
