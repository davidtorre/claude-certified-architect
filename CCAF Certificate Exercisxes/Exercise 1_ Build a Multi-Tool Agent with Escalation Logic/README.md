# Exercise 1 — Build a Multi-Tool Agent with Escalation Logic

A single Python file (`agent.py`) implementing all 5 steps of the exercise.

## What each step asks for, and where it lives in `agent.py`

| Step | What the exam guide asks for | Where it lives in `agent.py` |
|---|---|---|
| 1 | Define 3-4 MCP tools with detailed descriptions, including 2 with similar functionality whose descriptions disambiguate them. | The `TOOLS` list (4 tools). `get_customer_info` and `lookup_order` are the deliberately-similar pair; their descriptions emphasize ACCOUNT-level vs ORDER-level data and include a "USE THIS WHEN..." line. |

| 2 | Implement the agentic loop: handle `stop_reason='tool_use'` by executing tools and appending results, terminate on `stop_reason='end_turn'`. | The `run_agent()` function. |

| 3 | Structured error responses with `errorCategory`, `isRetryable`, and `description`. Test with INVALID_INPUT, TEMPORARY_FAILURE, NOT_FOUND. | `_structured_error()` helper + the three error categories returned by the fake tool handlers. Demos 2, 3, 4. |

| 4 | A programmatic hook that intercepts `process_refund`: when amount > $500, block the tool execution and force the agent to call `escalate_to_human` instead. | `pre_tool_hook()` function, called from inside the agent loop BEFORE every tool execution. Demos 5, 6. |

| 5 | Test with a multi-concern user message; verify the agent decomposes into multiple tool calls. | Demo 7. The agent loop already handles N tool_use blocks per turn — no extra code needed. |

## File creation sequence (build order)

The file is structured so you can read top-to-bottom and each section
makes sense given what came before:

1. **Imports** — `anthropic`, stdlib.
2. **Step 1 — `TOOLS` list.** Tool definitions with descriptions. This is
   pure data, no logic; the agent loop will hand it to the SDK as `tools=`.
3. **Step 3 — `_structured_error()` + tool implementations.** We
   intentionally put the error helper BEFORE the tool implementations so
   the implementations can use it as soon as you see them.
4. **`execute_tool()` dispatcher.** Routes a tool call by name to its
   implementation. Catches uncaught exceptions and wraps them as
   structured errors.
5. **Step 4 — `pre_tool_hook()`.** The refund-threshold check.
6. **Step 2 — `run_agent()`.** The agentic loop. Calls the hook, calls
   the dispatcher, builds tool_result blocks, repeats.
7. **Demos 1–7.** One demo per concept the exercise calls out.
8. **`main()`.** Tiny CLI: `python agent.py` runs all demos;
   `python agent.py 5 6` runs only demos 5 and 6.

If you're rebuilding from scratch, the same order works as a
file-creation sequence — though here it's all one file, so just write
it top-down.

## Internal structure of `agent.py`

```
agent.py
├── module docstring (the 5 steps + how to run)
├── imports
├── TOOLS list                          ← Step 1
├── _structured_error()                 ← Step 3 helper
├── _do_get_customer_info()             ← tool impl + Step 3 errors
├── _do_lookup_order()                  ← tool impl + Step 3 errors
├── _do_process_refund()                ← tool impl
├── _do_escalate_to_human()             ← tool impl
├── execute_tool()                      ← dispatch
├── AUTONOMOUS_REFUND_LIMIT
├── pre_tool_hook()                     ← Step 4
├── DEFAULT_SYSTEM_PROMPT, MODEL, MAX_ITERATIONS
├── run_agent()                         ← Step 2
├── demo_1_tool_selection()             ← Step 1 in action
├── demo_2_invalid_input()              ← Step 3
├── demo_3_temporary_failure()          ← Step 3
├── demo_4_not_found()                  ← Step 3
├── demo_5_refund_under_limit()         ← Step 4
├── demo_6_refund_over_limit()          ← Step 4
├── demo_7_multi_concern()              ← Step 5
├── DEMOS dict + main()
```

## Demo → step mapping

| Demo | Step it shows |
|---|---|
| 1 | Step 1 — model picks the right tool of two similar ones |
| 2 | Step 3 — INVALID_INPUT (model does NOT retry) |
| 3 | Step 3 — TEMPORARY_FAILURE (model retries) |
| 4 | Step 3 — NOT_FOUND (model reports gracefully) |
| 5 | Step 4 — refund **under** $500 (hook lets it through) |
| 6 | Step 4 — refund **over** $500 (hook blocks → escalation) |
| 7 | Step 5 — multi-concern message decomposed |

## Run it

See [HOW_TO_RUN.md](./HOW_TO_RUN.md) for setup. Quick version:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python agent.py        # all demos
python agent.py 6 7    # just the interesting ones
```
