# Exercise 2 — Configure Claude Code for a Team Development Workflow

This exercise is configuration, not code. Each of the 5 steps maps to
one (or two) actual files Claude Code will read.

## What each step asks for, and where it lives

| Step | What the exam guide asks for | File |
|---|---|---|
| 1 | Project-level `CLAUDE.md` describing the project, conventions, and pointers. | [`CLAUDE.md`](./CLAUDE.md) |
| 2 | `.claude/rules/` files with YAML frontmatter (`globs:`) so each rule activates only on matching paths. | [`.claude/rules/api-conventions.md`](./.claude/rules/api-conventions.md), [`.claude/rules/database.md`](./.claude/rules/database.md) |
| 3 | A skill in `.claude/skills/<name>/SKILL.md` with `context: fork`, `allowed-tools`, and `argument-hint` in its frontmatter. | [`.claude/skills/code-review/SKILL.md`](./.claude/skills/code-review/SKILL.md) |
| 4 | `.mcp.json` (project-level, in repo) with `${ENV_VAR}` expansion. Plus an example of the personal config that goes in `~/.claude.json` (NOT in the repo). | [`.mcp.json`](./.mcp.json) and [`personal-mcp-example.json`](./personal-mcp-example.json) |
| 5 | A doc explaining when to use plan mode vs direct execution. | [`plan-mode.md`](./plan-mode.md) |

## File creation sequence (build order)

1. **`CLAUDE.md`** — start with the project-wide context. Everything
   else builds on the conventions stated here.
2. **`.claude/rules/api-conventions.md`** — first path-scoped rule.
   Pick the part of the codebase you care about most (HTTP API).
3. **`.claude/rules/database.md`** — second rule, with a different
   glob, to demonstrate that multiple rules can coexist without
   colliding.
4. **`.claude/skills/code-review/SKILL.md`** — the skill with the
   three frontmatter fields the exercise calls out.
5. **`.mcp.json`** — project MCP servers (with env-var expansion).
6. **`personal-mcp-example.json`** — the personal-config example
   (kept here only for reference; in real life it would live in
   `~/.claude.json`).
7. **`plan-mode.md`** — the plan-mode-vs-direct-execution decision
   guide.

## How the four configuration surfaces interact

When Claude Code opens this directory, it loads (in roughly this order):

```
~/.claude/CLAUDE.md             ← user-level (your global preferences)
+ this CLAUDE.md                ← project-level (in this repo)
+ matching .claude/rules/*.md   ← path-scoped (only when editing matching files)
+ ~/.claude.json (mcpServers)   ← personal MCP servers
+ ./.mcp.json (mcpServers)      ← project MCP servers
```

Skills are NOT auto-loaded; they're invoked on demand by name.

## What the exercise does NOT ask for (and why this folder doesn't have it)

- **A working FastAPI service.** The exercise is about Claude Code
  configuration, not implementation. The CLAUDE.md and rules
  describe a hypothetical project — that's enough for Claude Code
  to act on the configuration.
- **Tests, examples, scaffolds.** Out of scope.

If you want a real project to point Claude Code at, drop these files
into any existing FastAPI project; the rules' globs will match
whatever you have under `src/api/` and `src/db/`.

## Run / verify

See [HOW_TO_RUN.md](./HOW_TO_RUN.md) for the verification walk-through.
