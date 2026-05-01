# HOW TO RUN — Exercise 4

## 1. Install

```bash
cd "Exercise 4: Design and Debug a Multi-Agent Research Pipeline"
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
(Demos 3, 4, 5 run without the API; only 1 and 2 hit the model.)

## 3. Run

```bash
python pipeline.py            # runs all 5 demos in order
python pipeline.py 1          # just demo 1
python pipeline.py 5          # just the no-API conflict demo
python pipeline.py 3 4 5      # all three no-API demos
```

## 4. What to look for in each demo

| Demo | Watch for |
|---|---|
| **1** | The coordinator emits Task tool calls — at least one to `web_search`, at least one to `document_analysis`. Each Task's `prompt` argument is self-contained (it includes any context the subagent needs). At the end, `findings collected: N` should be > 0. |
| **2** | Two runs of the same question, sequential then parallel. `subagent_total_wall_time` is the same in both (same work). `run_wall_time` is shorter for parallel because the two Task calls overlap. The speedup factor is printed at the end. |
| **3** | A markdown report with each claim followed by `(source: ...)`. No claim appears without attribution. That's the Step-3 promise — synthesis never strips provenance. |
| **4** | `document_analysis: timeout` failure. The error message includes `attempted_query`, `partial_results: 1`, and `missing_topics: [...]`. The report has a populated "Coverage gaps" section naming the failed subagent. |
| **5** | Section "1. Well-established findings" lists `Acme's 2024 revenue was $2.4B` (two sources agreed). Section "2. Contested findings" shows BOTH `12.0%` (Reuters) and `9.8%` (WSJ) under the same topic — synthesis didn't pick one. |

## 5. Forcing a timeout in your own code

The `TIMEOUTS` singleton lives in `pipeline.py`. To force a subagent
to fail with a structured error:

```python
from pipeline import TIMEOUTS, web_search_subagent

TIMEOUTS.force("web_search", True)
result = web_search_subagent("anything")
# result is a SubagentError with failure_type=TIMEOUT
TIMEOUTS.reset()
```

This is what demo 4 does.

## 6. Replacing the canned subagents with live ones

The `web_search_subagent` and `document_analysis_subagent` functions
in `pipeline.py` use canned data (`WEB_CANNED` and `DOCS_CANNED`) so
demos are deterministic. To make them live:

- **web_search**: replace the body with `client.messages.create(...)`
  using the `web_search` tool. Parse the response into `Finding` objects.
- **document_analysis**: replace `DOCS_CANNED` with a real document
  loader (vector DB, file system, etc.) and use the model to extract
  Findings via a forced-tool-choice extraction call (similar to
  Exercise 3's pattern).

The rest of the pipeline (coordinator, synthesis, conflict detection)
doesn't change — it works against the `Finding` / `SubagentResult`
contract regardless of how those Findings were produced.

## 7. Troubleshooting

- **`ModuleNotFoundError: anthropic`** — run `pip install -r requirements.txt`.
- **`ANTHROPIC_API_KEY not set`** — set it (step 2). Or run only demos 3, 4, 5.
- **Demo 2 shows no speedup** — the model needs to actually emit 2+
  Task calls in ONE response for parallel to apply. If it issues them
  one at a time across separate turns (sequentially in the conversation),
  there's nothing to parallelize. Tweak the question to make the two
  Task calls more obviously independent (different subagents, different
  topics).
- **Demo 5 shows everything as "established"** — the conflict detector
  groups by `topic` field. If you change the canned findings to share
  a topic but agree on claims, no conflict will be detected. To force
  one, set the same `topic` on findings with different claim strings.
