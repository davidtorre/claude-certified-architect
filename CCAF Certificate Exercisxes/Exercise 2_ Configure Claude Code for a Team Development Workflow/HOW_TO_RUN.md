# HOW TO RUN — Exercise 2

This exercise is **configuration only** — there's no Python script to
execute. Instead, you verify each of the 5 steps by launching Claude
Code in this folder and checking that it picks up the configuration.

## 1. Prerequisites

- Claude Code installed and authenticated
  (https://docs.claude.com/en/docs/claude-code)

That's the only requirement. No `pip install` needed.

## 2. Launch Claude Code in this directory

```bash
cd "Exercise 2: Configure Claude Code for a Team Development Workflow"
claude   # or whatever your launch command is
```

## 3. Verify each step

### ✅ Step 1 — CLAUDE.md is loaded

Inside Claude Code, ask:

```
What kind of project is this, and what are the build commands?
```

Claude Code should answer using the content of `CLAUDE.md` (TaskFlow,
FastAPI, Python 3.11, the build commands listed). If it asks "what
project?" or guesses, `CLAUDE.md` isn't being loaded.

You can also type `/memory` to see exactly which memory files Claude
Code loaded.

### ✅ Step 2 — Path-scoped rules activate on matching paths

Ask Claude Code:

```
Suggest the structure for a new endpoint in src/api/projects.py.
```

The response should reference the rules from `.claude/rules/api-conventions.md`
(APIRouter, Pydantic models, async, repository delegation). Now ask:

```
Suggest the structure for a new repository class in src/db/projects_repo.py.
```

This time the response should reference `.claude/rules/database.md`
(parameterized queries, no asyncpg `Record` leak, repository pattern)
and NOT the API rule.

If both rules show up for both paths, the `globs:` patterns aren't
being honored — check the YAML frontmatter syntax (no tabs, correct
indentation).

### ✅ Step 3 — Skill is discoverable and runs in a forked context

Ask Claude Code:

```
Use the code-review skill to look at the changes in HEAD.
```

Or use the slash-command equivalent if your client exposes one.

What to verify:

- The skill is **discoverable** (Claude Code knows about it without
  you pasting the file path).
- The skill's argument-hint is shown when invoking it.
- After the skill returns, your main conversation context is NOT
  full of the dozens of file reads it did. That's `context: fork`
  working — exploration happened in a separate context, only the
  final answer came back.
- The skill cannot edit files — try asking it to fix a bug, and it
  should refuse (because `allowed-tools` denies Edit/Write).

### ✅ Step 4 — `.mcp.json` is recognized; env vars expand

In your shell BEFORE launching Claude Code, set placeholder values:

```bash
export GITHUB_TOKEN=ghp_test
export TASKFLOW_DEV_DATABASE_URL=postgresql://localhost/taskflow_dev
export TEAM_DOCS_URL=https://docs.example.com
export TEAM_DOCS_API_KEY=test_key
```

Launch Claude Code. The MCP servers should be visible (e.g. via
`/mcp` if your client supports it). The values in `.mcp.json` should
be the expanded values, not the literal `${...}` strings.

If you do NOT set the env vars, the servers may fail to start — and
the failure should be visible (Claude Code typically reports MCP
startup errors). That's the system telling you "this is a project
server; you need credentials to use it."

For the personal-MCP example, copy the `mcpServers` block from
`personal-mcp-example.json` into `~/.claude.json` (creating it if
needed) and re-launch — your personal server should now appear
alongside the project ones.

### ✅ Step 5 — Plan mode behavior

Two prompts to compare:

**Direct execution test** — type:

```
Fix the typo in the docstring of src/api/tasks.py, line 1.
```

Claude Code should just do it (single-file, trivial).

**Plan mode test** — enter plan mode (your client's `/plan` command or
the toggle), then type:

```
Add a `due_date` field to tasks across the whole stack.
```

Claude Code should respond with a written plan covering models,
schemas, handlers, repository, tests, and migration — and wait for
your approval before touching files.

If you're unsure whether plan mode is active, ask Claude Code to
make a trivial edit; it should refuse to actually edit until you
approve a plan.

## 4. Troubleshooting

- **CLAUDE.md ignored** — make sure you launched Claude Code from
  this directory, not a parent. Use `/memory` to see what got loaded.
- **A rule isn't firing** — open the rule file and verify the YAML
  frontmatter is valid (no tabs in YAML, correct `---` fences).
- **`.mcp.json` server doesn't start** — the env vars probably
  aren't set in your shell. The `${...}` syntax expands at startup,
  not lazily — missing vars produce an empty string, which the
  server then complains about.
- **Skill is not discoverable** — check that the directory name is
  exactly `code-review/` (matches the `name` field in the
  frontmatter) and that `SKILL.md` is the filename (capitalization
  matters on Linux).
