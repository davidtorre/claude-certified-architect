# HOW TO RUN — Exercise 1

## 1. Install

```bash
cd "Exercise 1: Build a Multi-Tool Agent with Escalation Logic"
pip install -r requirements.txt
```

That installs the Anthropic SDK (the only dependency).

## 2. Set your API key

```bash
# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-...

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Get a key at https://console.anthropic.com.

## 3. Run

```bash
python agent.py            # runs all 7 demos in order
python agent.py 1          # runs just demo 1
python agent.py 6 7        # runs demos 6 and 7
```

## 4. What to look for in each demo

| Demo | Watch for |
|---|---|
| **1** | A single `tool_use: get_customer_info(...)` call. The model picked the ACCOUNT tool, not the ORDER tool — that's the disambiguation working. |
| **2** | One call to `get_customer_info(99999)` → `INVALID_INPUT (retryable=False)`. The model then explains the error to the user instead of trying again. |
| **3** | `get_customer_info(CUS-FLAKY)` → `TEMPORARY_FAILURE (retryable=True)`. The model tries again. (The fake handler always returns the error, so the second try also fails — but you'll see the model attempt the retry, which is the whole point.) |
| **4** | `get_customer_info(CUS-MISSING)` → `NOT_FOUND (retryable=False)`. Model reports gracefully. |
| **5** | `process_refund(... amount=50)` → ✓ ok. The hook ran, returned `None`, the tool executed normally. |
| **6** | `process_refund(... amount=750)` → ⛔ blocked by hook. Then watch for `escalate_to_human(...)` in the next assistant turn. The hook's error message tells the model exactly what to do next. |
| **7** | Multiple `tool_use:` lines bunched together in a single assistant turn. The agent decomposed the 3 concerns into (likely) 3 parallel tool calls. |

## 5. Troubleshooting

- **`ModuleNotFoundError: anthropic`** — run `pip install -r requirements.txt`.
- **`ANTHROPIC_API_KEY not set`** — set the env var (step 2).
- **The model picks the wrong tool in demo 1** — the tool descriptions
  in `agent.py` are the entire defense against this. If you tweak them
  and break the disambiguation, demo 1 is your canary.
- **Model doesn't escalate after the hook blocks (demo 6)** — make
  sure the hook's error message in `pre_tool_hook()` explicitly says
  "call escalate_to_human" — without that hint, the model sometimes
  apologizes and stops instead of switching tools.
