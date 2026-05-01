# Exercise 4 — Design and Debug a Multi-Agent Research Pipeline

A single Python file (`pipeline.py`) implementing all 5 steps of the
exercise.

## What each step asks for, and where it lives in `pipeline.py`

| Step | What the exam guide asks for | Where it lives |
|---|---|---|
| 1 | Coordinator with ≥2 subagents (web_search + document_analysis). Coordinator's allowedTools includes `Task`. Each subagent receives findings DIRECTLY in its prompt. | `web_search_subagent`, `document_analysis_subagent`, `SUBAGENTS` registry, `TASK_TOOL` spec, `COORDINATOR_PROMPT`, `run_coordinator()`. Demo 1. |
| 2 | Parallel subagent execution: multiple Task calls in one response. Measure latency vs sequential. | `run_coordinator(parallel=True/False)` — uses `ThreadPoolExecutor` when 2+ Task calls in one turn. Demo 2 measures both runs. |
| 3 | Structured Findings (claim, evidence excerpt, source URL/document name, publication date). Synthesis preserves attribution. | `Finding` dataclass + `synthesize_report()`. Demo 3 (no API). |
| 4 | Error propagation: simulated timeout → structured error context (failure type, attempted query, partial results). Coordinator continues; report annotates gap. | `FailureType` enum, `SubagentError` dataclass, `TimeoutSimulator` (TIMEOUTS singleton), the report's "Coverage gaps" section. Demo 4 (no API). |
| 5 | Conflicting sources: synthesis preserves both with attribution; report distinguishes well-established from contested. | `synthesize_report()` groups by `topic`; multi-claim same-topic groups go to "Contested findings". Demo 5 (no API). |

## File creation sequence (build order)

The file is structured so you can read top-to-bottom and each section
makes sense given what came before:

1. **Imports + `MODEL` constant.**
2. **Step 3 — `Finding` dataclass.** Defined first because everything
   else uses it (subagents return Findings; reports format Findings).
3. **Step 4 — `FailureType`, `SubagentError`, `SubagentResult` alias.**
4. **`TimeoutSimulator` + `TIMEOUTS` singleton.** Lets demos force
   timeouts deterministically.
5. **Step 1 — Subagents.** Canned corpora (`WEB_CANNED`, `DOCS_CANNED`)
   + the two subagent functions + `SUBAGENTS` registry.
6. **Step 1 — `TASK_TOOL` spec + `COORDINATOR_PROMPT`.** What the
   coordinator can do and how it's instructed to behave.
7. **Steps 1+2 — `CoordinatorRun`, `execute_one_task_call()`,
   `run_coordinator()`.** The agentic loop, with parallel dispatch for
   multi-Task turns.
8. **Step 5 — `synthesize_report()`.** Groups findings by topic, splits
   established vs contested, appends gaps.
9. **5 demos**, one per step.
10. **`main()` CLI.**

## Demo → step mapping

| Demo | Step it shows | Needs API? |
|---|---|---|
| 1 | Step 1 — coordinator + 2 subagents end-to-end | yes |
| 2 | Step 2 — parallel vs sequential (with wall-time comparison) | yes |
| 3 | Step 3 — synthesis preserves attribution | NO |
| 4 | Step 4 — simulated timeout → structured error → coverage gap | NO |
| 5 | Step 5 — Reuters vs WSJ disagree on Acme growth → both preserved | NO |

## Run it

See [HOW_TO_RUN.md](./HOW_TO_RUN.md) for setup. Quick version:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python pipeline.py            # all 5 demos
python pipeline.py 5          # just the conflict-preservation demo (no API)
python pipeline.py 3 4 5      # all three no-API demos
```
