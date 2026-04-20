# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Commands

```bash
python main.py              # Run the interactive agent (menu with test queries)
python manage.py restart    # Restore all files to starter state (TODOs intact, .env preserved)
python manage.py solve      # Apply completed solutions for all TODOs
pip install -r requirements.txt  # anthropic, python-dotenv, rich
```

## Architecture

Single-agent customer support system using the Anthropic Client SDK with a manual agentic loop (not the Agent SDK). The loop checks `stop_reason`: `"tool_use"` means execute the tool and continue, `"end_turn"` means stop and print the final response.

**Control flow in `main.py`:**
1. `run_agent()` sends messages to Claude with 4 tools available
2. On `tool_use` stop_reason, each tool_use block goes through `execute_tool()`:
   - `check_prerequisite()` — **prerequisite gate** blocks `process_refund` unless `get_customer` is in `tool_history`
   - Tool function executes via `TOOL_FUNCTIONS` dispatch
   - `post_tool_use_hook()` — **PostToolUse hook** intercepts results; blocks refunds > `MAX_REFUND_AMOUNT` ($500) with a policy_violation error and `escalate_to_human` action hint
3. Tool results append to `messages` as `tool_result` blocks; loop continues
4. On `end_turn` stop_reason, agent prints final text response and exits

**Tool pattern in `tools.py`:** Each tool is a plain function + a companion `_schema` dict (not decorators). `ALL_TOOLS` is the list of schemas passed to the API; `TOOL_FUNCTIONS` maps names to callables.

**Error response convention:** All tool errors return `{"error": True, "errorCategory": "<type>", "isRetryable": <bool>, "message": "..."}`. Categories: `validation`, `business`, `policy_violation`.

**System prompt:** Loaded from `system_prompt.txt` with `.format(case_facts=case_facts)`. The `{case_facts}` template variable injects verified transactional facts into an XML-tagged section so they survive context summarization.

## Coding conventions

- **No inline return structures** — assign to a variable first, then return it.
- **No function calls as arguments** — assign the result first, then pass it.
- **Mock data in separate files** — never inline mock data in Python code. Import from `data.py`.
- **Use the Anthropic SDK** — `import anthropic`. Never make manual REST calls.
- **Tool definitions follow the companion `_schema` dict pattern** — define the Python function separately, then define a `_schema` dict with `name`, `description`, and `input_schema`.
- **Prompt templates in `.txt` files** — load system prompts from `system_prompt.txt`. Use `.format()` with template variables for dynamic content. Dynamic sections use XML tags (e.g., `<case_facts>{case_facts}</case_facts>`). Never use string concatenation or f-strings to build prompts.
- **Constants in `config.py`** — model name, thresholds, policy values, console colors.
- **File headers** — every Python file starts with `# filename.py - Short description`.
- Functions over classes.
- Comments only where they clarify an exam concept.
- `.env` for API keys — never hardcoded.
