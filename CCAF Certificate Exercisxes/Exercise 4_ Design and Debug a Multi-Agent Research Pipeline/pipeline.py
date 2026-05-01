"""
============================================================================
 Exercise 4 — Design and Debug a Multi-Agent Research Pipeline
============================================================================

This single file implements all 5 steps of the exercise. Read top to bottom;
every step is wrapped in a banner comment.

    Step 1 — Build a coordinator that delegates to ≥2 subagents (web_search
             + document_analysis) via a Task tool. Each subagent receives
             its findings DIRECTLY in its prompt (no auto-context-inheritance).
    Step 2 — Parallel subagent execution: when the coordinator emits multiple
             Task tool calls in a single response, run them concurrently.
             Measure latency vs sequential.
    Step 3 — Structured output for subagents: each Finding has a claim,
             evidence excerpt, source URL/document name, and publication
             date. Synthesis preserves attribution.
    Step 4 — Error propagation: a simulated subagent timeout produces a
             structured error (failure_type, attempted_query, partial_results)
             that the coordinator can act on. Final report annotates the
             coverage gap.
    Step 5 — Conflicting source data: when two credible sources disagree,
             the synthesis preserves both values with attribution and
             distinguishes "well-established" from "contested" findings.

Run with:
    python pipeline.py                # runs every demo in order
    python pipeline.py 1               # runs only demo 1
    python pipeline.py 2 4             # runs demos 2 and 4

Requires:
    ANTHROPIC_API_KEY  environment variable (steps 1, 2)
    anthropic >= 0.40  installed

Demos 3, 4, 5 are deterministic and run without the API.
============================================================================
"""

from __future__ import annotations

import json
import os
import sys
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass, field, asdict
from datetime import date
from enum import Enum
from typing import Any, Callable

import anthropic


MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")


# ============================================================================
# STEP 3 — Structured Finding (defined first because everything uses it)
# ============================================================================
# The exam guide names four required fields per Finding:
#   - claim              : the short statement
#   - evidence_excerpt   : verbatim text from the source
#   - source             : URL or document name
#   - publication_date   : when the source was published
#
# Synthesis preserves these, so a final report says
#   "Acme grew 12% in 2024 (Reuters, 2025-02-18)"
# instead of an unattributed "Acme grew 12% in 2024".
# ============================================================================

@dataclass(frozen=True)
class Finding:
    """A single attributed claim from a subagent."""
    claim:            str
    evidence_excerpt: str
    source:           str        # URL or document name
    publication_date: date | None = None
    # `topic` is an optional disambiguator — used by Step 5's conflict
    # detection to group findings that talk about the same fact.
    topic:            str | None = None

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["publication_date"] = self.publication_date.isoformat() if self.publication_date else None
        return d


def findings_to_text(findings: list[Finding]) -> str:
    """Render findings as a text block for inclusion in subagent prompts.
    The coordinator (Step 1) uses this when it puts prior findings into
    the next subagent's brief — explicit context passing, not auto-inheritance.
    """
    if not findings:
        return "(no findings yet)"
    lines = []
    for i, f in enumerate(findings, start=1):
        date_str = f.publication_date.isoformat() if f.publication_date else "n/a"
        lines.append(
            f"[F{i}] CLAIM: {f.claim}\n"
            f"     EVIDENCE: \"{f.evidence_excerpt}\"\n"
            f"     SOURCE: {f.source}  (date: {date_str})"
        )
    return "\n\n".join(lines)


# ============================================================================
# STEP 4 — Structured error context for subagent failures
# ============================================================================
# When a subagent times out, errors, or refuses, the coordinator needs:
#   - failure_type       (timeout / api_error / malformed / refused)
#   - attempted_query    (so it can decide to retry with a narrower brief)
#   - partial_results    (any Findings produced before the failure)
#
# The synthesis subagent uses these to annotate "coverage gaps" in the
# final report — the user is told what we tried to find but couldn't.
# ============================================================================

class FailureType(str, Enum):
    TIMEOUT          = "timeout"
    API_ERROR        = "api_error"
    MALFORMED_OUTPUT = "malformed_output"
    REFUSED          = "refused"
    UNKNOWN          = "unknown"


@dataclass
class SubagentError:
    failure_type:    FailureType
    subagent_name:   str
    attempted_query: str
    partial_results: list[Finding] = field(default_factory=list)
    detail:          str | None = None
    missing_topics:  list[str]   = field(default_factory=list)

    def to_dict(self) -> dict[str, Any]:
        return {
            "failure_type":    self.failure_type.value,
            "subagent_name":   self.subagent_name,
            "attempted_query": self.attempted_query,
            "partial_results": [f.to_dict() for f in self.partial_results],
            "detail":          self.detail,
            "missing_topics":  self.missing_topics,
        }


# A success returns list[Finding]; a failure returns SubagentError.
SubagentResult = list[Finding] | SubagentError


# ============================================================================
# STEP 4 — timeout simulator (so we can FORCE timeouts in demo 4)
# ============================================================================

class TimeoutSimulator:
    """Per-subagent toggle for forced timeouts in demos."""
    def __init__(self) -> None:
        self._forced: dict[str, bool] = {}

    def force(self, subagent_name: str, value: bool = True) -> None:
        self._forced[subagent_name] = value

    def should_timeout(self, subagent_name: str) -> bool:
        return self._forced.get(subagent_name, False)

    def reset(self) -> None:
        self._forced.clear()


# Module-level singleton — convenient for demos.
TIMEOUTS = TimeoutSimulator()


# ============================================================================
# STEP 1 — Subagents
# ============================================================================
# We need ≥2 subagents. Per the exam guide: web_search and document_analysis.
# Each subagent is a callable: `def __call__(self, brief) -> SubagentResult`.
#
# Live mode would call the real model (and real web search / real document
# read). For deterministic demos we use canned data — the structure is what
# matters for studying.
# ============================================================================

# Small canned corpus. Real research pipelines would have a vector DB,
# document loader, web fetcher, etc.

# Web canned findings — keyword → Finding(s).
WEB_CANNED: list[tuple[str, Finding]] = [
    ("nx-217", Finding(
        claim="NX-217 is in Phase II trials with positive headline results",
        evidence_excerpt="An external coverage piece notes NX-217 is in mid-stage trials with positive headline results.",
        source="https://medsource.example/nx-217-phase-2",
        publication_date=date(2024, 8, 22),
        topic="nx217_phase",
    )),
    ("nx-217", Finding(
        claim="Industry analysts called the NX-217 result a competitive efficacy signal",
        evidence_excerpt="Industry analysts called the 42-point reduction a competitive efficacy signal.",
        source="https://biomedpress.example/nx-217-results",
        publication_date=date(2024, 9, 5),
        topic="nx217_efficacy",
    )),
]

# Document canned findings — document name → Finding(s).
DOCS_CANNED: dict[str, list[Finding]] = {
    "internal_trial_results.txt": [
        Finding(
            claim="NX-217 Phase II showed 42-point reduction in primary endpoint",
            evidence_excerpt="Active arm achieved a mean reduction of 42 points; placebo arm achieved 18 points (p<0.001).",
            source="internal_trial_results.txt",
            publication_date=date(2024, 8, 12),
            topic="nx217_efficacy",
        ),
        Finding(
            claim="NX-217 Phase II adverse events were mild, no serious AEs",
            evidence_excerpt="Adverse events: mild headache (12% active vs 9% placebo). No serious adverse events reported.",
            source="internal_trial_results.txt",
            publication_date=date(2024, 8, 12),
            topic="nx217_safety",
        ),
    ],
    "regulatory_status.txt": [
        Finding(
            claim="FDA granted Fast Track designation for NX-217 on 2024-06-14",
            evidence_excerpt="FDA: Fast Track designation granted 2024-06-14.",
            source="regulatory_status.txt",
            publication_date=date(2024, 9, 30),
            topic="nx217_regulatory",
        ),
    ],
}


def web_search_subagent(brief: str) -> SubagentResult:
    """Mock web search subagent. In live mode this would call the model
    with the web_search tool enabled and parse the result into Findings.

    Honors the TIMEOUT simulator (Step 4)."""
    if TIMEOUTS.should_timeout("web_search"):
        # Simulated timeout — return a structured error with no partial
        # results (we hadn't started yet).
        return SubagentError(
            failure_type=FailureType.TIMEOUT,
            subagent_name="web_search",
            attempted_query=brief,
            partial_results=[],
            detail="Forced timeout via TIMEOUTS.force() (demo).",
        )

    findings = [f for kw, f in WEB_CANNED if kw.lower() in brief.lower()]
    return findings


def document_analysis_subagent(brief: str) -> SubagentResult:
    """Mock document_analysis subagent. Looks up documents named in the
    brief and returns their canned Findings."""
    if TIMEOUTS.should_timeout("document_analysis"):
        # Imagine we processed one document before timing out.
        partial: list[Finding] = []
        for findings in DOCS_CANNED.values():
            if findings:
                partial = [findings[0]]
                break
        return SubagentError(
            failure_type=FailureType.TIMEOUT,
            subagent_name="document_analysis",
            attempted_query=brief,
            partial_results=partial,
            detail="Forced timeout via TIMEOUTS.force() (demo).",
            missing_topics=["nx217_safety", "nx217_regulatory"],
        )

    findings: list[Finding] = []
    brief_lower = brief.lower()
    for doc_name, doc_findings in DOCS_CANNED.items():
        # Match either by exact filename or by topic phrase.
        if doc_name.lower() in brief_lower or doc_name.replace("_", " ").replace(".txt", "").lower() in brief_lower:
            findings.extend(doc_findings)
    return findings


# Subagent registry — coordinator dispatches by name.
SUBAGENTS: dict[str, Callable[[str], SubagentResult]] = {
    "web_search":         web_search_subagent,
    "document_analysis":  document_analysis_subagent,
}


# ============================================================================
# STEP 1 — Task tool (the coordinator's only tool)
# ============================================================================
# Per the exam guide: "Ensure the coordinator's allowedTools includes 'Task'
# and that each subagent receives its research findings directly in its
# prompt rather than relying on automatic context inheritance."
#
# The Task tool's input_schema requires a `prompt` field. The coordinator
# is INSTRUCTED via the system prompt to put any prior findings IN THAT
# PROMPT — that's what "explicit context passing" means in practice.
# ============================================================================

TASK_TOOL = {
    "name": "Task",
    "description": (
        "Delegate a sub-job to a specialized subagent. The subagent runs in "
        "isolation — it sees ONLY the prompt you provide, NOT the conversation "
        "history. Include all context the subagent needs (prior findings, "
        "errors, etc.) directly in the prompt argument."
    ),
    "input_schema": {
        "type": "object",
        "properties": {
            "subagent_type": {
                "type": "string",
                "enum": ["web_search", "document_analysis"],
                "description": (
                    "Which subagent to invoke. "
                    "web_search: searches the web for general information. "
                    "document_analysis: reads internal corpus documents."
                ),
            },
            "prompt": {
                "type": "string",
                "description": (
                    "Complete brief for the subagent — what to look for, plus "
                    "ALL relevant context (prior findings, errors). The subagent "
                    "does NOT see the rest of the conversation."
                ),
            },
            "description": {
                "type": "string",
                "description": "Short 3-5 word label for logging (e.g. 'search NX-217 results').",
            },
        },
        "required": ["subagent_type", "prompt", "description"],
    },
}


COORDINATOR_PROMPT = """\
You are a research coordinator. Your only tool is `Task`, which delegates \
to a subagent.

Available subagent_types:
  - web_search          searches the web for industry coverage / external info
  - document_analysis   reads internal corpus documents

Rules:
1. EXPLICIT CONTEXT. Subagents see ONLY the `prompt` you give them. They do
   NOT see the conversation history. Include any prior findings the subagent
   needs directly in the prompt.
2. PARALLELIZE. If two Task calls are independent (different subagents on
   different topics), emit BOTH in the same response — the runtime will
   execute them concurrently.
3. HANDLE FAILURES. If a Task returns an error, decide whether to retry,
   work around with a different subagent, or proceed with partial results
   and annotate the gap.
4. WHEN DONE. After collecting findings, summarize them in plain text and
   end your turn. The synthesis step is performed by another routine.
"""


# ============================================================================
# STEP 1 + 2 — Coordinator (with parallel dispatch)
# ============================================================================

@dataclass
class CoordinatorRun:
    """Outcome of one coordinator run."""
    findings:                   list[Finding]      = field(default_factory=list)
    errors:                     list[SubagentError] = field(default_factory=list)
    iterations:                 int                = 0
    stop_reason:                str                = ""
    final_assistant_text:       str                = ""
    run_wall_time_seconds:      float              = 0.0
    subagent_total_wall_time:   float              = 0.0
    task_call_count:            int                = 0


def execute_one_task_call(block: Any) -> tuple[dict[str, Any], SubagentResult, float]:
    """Run a single Task tool_use block. Returns (tool_result, subagent_result, wall_time)."""
    inp = dict(block.input or {})
    subagent_type = inp.get("subagent_type", "")
    prompt        = inp.get("prompt", "")

    started = time.monotonic()
    fn = SUBAGENTS.get(subagent_type)
    if fn is None:
        result: SubagentResult = SubagentError(
            failure_type=FailureType.UNKNOWN,
            subagent_name=subagent_type or "(empty)",
            attempted_query=prompt,
            detail=f"Unknown subagent_type: {subagent_type!r}",
        )
    else:
        try:
            result = fn(prompt)
        except Exception as e:
            result = SubagentError(
                failure_type=FailureType.API_ERROR,
                subagent_name=subagent_type,
                attempted_query=prompt,
                detail=f"{type(e).__name__}: {e}",
            )
    wall = time.monotonic() - started

    # Build the tool_result block to send back to the model.
    if isinstance(result, list):
        payload = {"findings": [f.to_dict() for f in result]}
        tool_result = {
            "type":        "tool_result",
            "tool_use_id": block.id,
            "content":     json.dumps(payload),
        }
    else:
        tool_result = {
            "type":        "tool_result",
            "tool_use_id": block.id,
            "content":     json.dumps(result.to_dict()),
            "is_error":    True,
        }
    return tool_result, result, wall


def run_coordinator(question: str, *, parallel: bool = True, verbose: bool = True) -> CoordinatorRun:
    """Run the coordinator loop until end_turn or max iterations."""
    client = anthropic.Anthropic()
    messages: list[dict[str, Any]] = [{"role": "user", "content": question}]
    rec = CoordinatorRun()
    started = time.monotonic()

    if verbose:
        print(f"\n┃ USER: {question}")

    MAX_ITER = 8
    for iteration in range(1, MAX_ITER + 1):
        response = client.messages.create(
            model=MODEL,
            max_tokens=2048,
            system=COORDINATOR_PROMPT,
            tools=[TASK_TOOL],
            messages=messages,
        )
        messages.append({"role": "assistant", "content": response.content})

        for block in response.content:
            if getattr(block, "type", None) == "text" and verbose:
                print(f"┃ COORDINATOR: {block.text}")

        if response.stop_reason == "end_turn":
            rec.stop_reason = "end_turn"
            # Capture the last assistant text as the final report-ish output.
            for block in response.content:
                if getattr(block, "type", None) == "text":
                    rec.final_assistant_text += block.text + "\n"
            break

        if response.stop_reason != "tool_use":
            rec.stop_reason = response.stop_reason or "unknown"
            break

        # Collect every Task call in this turn (could be 1, 2, or more).
        tool_use_blocks = [
            b for b in response.content if getattr(b, "type", None) == "tool_use"
        ]
        rec.task_call_count += len(tool_use_blocks)
        if verbose:
            mode = "parallel" if (parallel and len(tool_use_blocks) > 1) else "sequential"
            print(f"  → {len(tool_use_blocks)} Task call(s) — running {mode}")

        # ── STEP 2 — parallel dispatch when 2+ calls in one turn ──────
        tool_results: list[dict[str, Any] | None]
        if parallel and len(tool_use_blocks) > 1:
            tool_results = [None] * len(tool_use_blocks)
            with ThreadPoolExecutor(max_workers=len(tool_use_blocks)) as pool:
                futures = {pool.submit(execute_one_task_call, b): i
                           for i, b in enumerate(tool_use_blocks)}
                for fut in as_completed(futures):
                    idx = futures[fut]
                    tr, sub_result, wall = fut.result()
                    tool_results[idx] = tr
                    rec.subagent_total_wall_time += wall
                    if isinstance(sub_result, list):
                        rec.findings.extend(sub_result)
                        if verbose:
                            print(f"    ✓ {tool_use_blocks[idx].input.get('subagent_type')}: "
                                  f"{len(sub_result)} finding(s)  [{wall:.2f}s]")
                    else:
                        rec.errors.append(sub_result)
                        if verbose:
                            print(f"    ✗ {sub_result.subagent_name}: "
                                  f"{sub_result.failure_type.value}  [{wall:.2f}s]")
        else:
            tool_results = []
            for b in tool_use_blocks:
                tr, sub_result, wall = execute_one_task_call(b)
                tool_results.append(tr)
                rec.subagent_total_wall_time += wall
                if isinstance(sub_result, list):
                    rec.findings.extend(sub_result)
                    if verbose:
                        print(f"    ✓ {b.input.get('subagent_type')}: "
                              f"{len(sub_result)} finding(s)  [{wall:.2f}s]")
                else:
                    rec.errors.append(sub_result)
                    if verbose:
                        print(f"    ✗ {sub_result.subagent_name}: "
                              f"{sub_result.failure_type.value}  [{wall:.2f}s]")

        messages.append({"role": "user", "content": [tr for tr in tool_results if tr]})

    rec.iterations = iteration
    rec.run_wall_time_seconds = time.monotonic() - started
    if verbose:
        print(f"  (loop: iterations={rec.iterations}, task_calls={rec.task_call_count}, "
              f"wall={rec.run_wall_time_seconds:.2f}s)")
    return rec


# ============================================================================
# STEP 5 — Conflict detection + synthesis report
# ============================================================================
# Two findings CONFLICT when they have the same `topic` but different claims.
# We split findings into:
#   - established  (single source, OR multiple sources with the same claim)
#   - contested    (multiple sources, different claims, same topic)
#
# The report preserves BOTH sides of contested findings — never picks one.
# ============================================================================

def synthesize_report(
    *,
    findings: list[Finding],
    errors: list[SubagentError],
) -> str:
    """Produce a markdown-style report with three sections."""
    # Group findings by topic.
    by_topic: dict[str, list[Finding]] = {}
    for f in findings:
        key = f.topic if f.topic else "(untagged)"
        by_topic.setdefault(key, []).append(f)

    established: list[tuple[str, list[Finding]]] = []
    contested:   list[tuple[str, list[Finding]]] = []

    for topic, fs in by_topic.items():
        unique_claims = {f.claim.strip().lower() for f in fs}
        if len(fs) >= 2 and len(unique_claims) > 1:
            contested.append((topic, fs))
        else:
            established.append((topic, fs))

    out = ["# Research report", ""]

    # ── Section 1: well-established ──────────────────────────────────
    out.append("## 1. Well-established findings")
    if not established:
        out.append("(None.)")
    else:
        for topic, fs in established:
            if len(fs) > 1:
                # Multiple sources, same claim → strongly established.
                claim = fs[0].claim
                sources = ", ".join(f.source for f in fs)
                out.append(f"- **{claim}**  (sources: {sources})")
            else:
                f = fs[0]
                out.append(f"- **{f.claim}**  (source: {f.source}; "
                           f"date: {f.publication_date})")
    out.append("")

    # ── Section 2: contested ─────────────────────────────────────────
    out.append("## 2. Contested findings")
    if not contested:
        out.append("(No conflicts detected.)")
    else:
        for topic, fs in contested:
            out.append(f"### Topic: `{topic}`")
            out.append("Reputable sources disagree. Both values preserved:")
            for f in fs:
                date_str = f.publication_date.isoformat() if f.publication_date else "n/a"
                out.append(f"- _{f.source}_ (date: {date_str}): {f.claim}")
                out.append(f"  > \"{f.evidence_excerpt}\"")
            out.append("")
    out.append("")

    # ── Section 3: coverage gaps (Step 4) ────────────────────────────
    out.append("## 3. Coverage gaps")
    if not errors:
        out.append("(No subagent failures.)")
    else:
        for err in errors:
            topics = ", ".join(err.missing_topics) if err.missing_topics else "(unknown)"
            out.append(f"- **{err.subagent_name}** failed: "
                       f"`{err.failure_type.value}`. "
                       f"Attempted: \"{err.attempted_query[:80]}...\". "
                       f"Missing topics: {topics}.")
            if err.partial_results:
                out.append(f"  - {len(err.partial_results)} partial result(s) "
                           f"recovered before failure.")
    out.append("")

    return "\n".join(out)


# ============================================================================
# DEMOS — one per concept the exercise calls out
# ============================================================================

def demo_1_simple_research():
    """Step 1 — coordinator + 2 subagents end-to-end."""
    print("\n" + "=" * 70)
    print(" Demo 1 — Coordinator + 2 subagents (Step 1)")
    print(" Coordinator delegates to web_search AND document_analysis.")
    print(" Each subagent receives its brief in the Task call's `prompt`.")
    print("=" * 70)
    TIMEOUTS.reset()
    rec = run_coordinator(
        "Summarize what we know about NX-217's Phase II results, both from "
        "internal documents (internal_trial_results.txt and regulatory_status.txt) "
        "and from web coverage. Use both subagents."
    )
    print(f"\n  → findings collected: {len(rec.findings)}")
    print(f"  → errors:             {len(rec.errors)}")
    print(f"  → task calls:         {rec.task_call_count}")


def demo_2_parallel_vs_sequential():
    """Step 2 — measure latency of parallel vs sequential dispatch.

    Identical question, run twice — once with parallel=False, once True.
    `subagent_total_wall_time` is identical (same work). `run_wall_time_seconds`
    is shorter under parallel (assuming the model emits 2+ Task calls in
    a single response).
    """
    print("\n" + "=" * 70)
    print(" Demo 2 — Parallel vs sequential (Step 2)")
    print("=" * 70)
    TIMEOUTS.reset()
    question = (
        "Get NX-217's Phase II results from internal_trial_results.txt AND "
        "search the web for industry analyst coverage. Issue both Task calls "
        "in the same response."
    )

    print("\nSEQUENTIAL run:")
    seq = run_coordinator(question, parallel=False, verbose=False)
    print(f"  run_wall_time:           {seq.run_wall_time_seconds:.2f}s")
    print(f"  subagent_total_wall_time: {seq.subagent_total_wall_time:.2f}s")
    print(f"  task_calls:              {seq.task_call_count}")

    print("\nPARALLEL run:")
    par = run_coordinator(question, parallel=True, verbose=False)
    print(f"  run_wall_time:           {par.run_wall_time_seconds:.2f}s")
    print(f"  subagent_total_wall_time: {par.subagent_total_wall_time:.2f}s")
    print(f"  task_calls:              {par.task_call_count}")

    if seq.run_wall_time_seconds > 0:
        print(f"\n  → speedup (sequential ÷ parallel): "
              f"{seq.run_wall_time_seconds / max(par.run_wall_time_seconds, 0.001):.2f}×")


def demo_3_findings_attribution():
    """Step 3 — synthesis preserves source attribution.

    No coordinator/API call — we feed canned Findings directly to the
    synthesis function and verify every claim has its source + date.
    """
    print("\n" + "=" * 70)
    print(" Demo 3 — Findings preserve attribution (Step 3)")
    print(" No API call — feeds canned Findings to synthesize_report().")
    print("=" * 70)

    findings: list[Finding] = []
    findings.extend(DOCS_CANNED["internal_trial_results.txt"])
    findings.extend(DOCS_CANNED["regulatory_status.txt"])
    findings.extend([f for _, f in WEB_CANNED])

    report = synthesize_report(findings=findings, errors=[])
    print(report)


def demo_4_simulated_timeout():
    """Step 4 — simulated subagent timeout, structured error, partial results.

    No API call — we exercise the subagents directly with the timeout
    simulator. The point is to show the SHAPE of the error and how the
    report annotates the gap.
    """
    print("\n" + "=" * 70)
    print(" Demo 4 — Simulated timeout & coverage gap (Step 4)")
    print(" No API call — invokes subagents directly with timeout forced.")
    print("=" * 70)

    TIMEOUTS.reset()
    TIMEOUTS.force("document_analysis", True)

    web_result = web_search_subagent("nx-217 industry coverage")
    doc_result = document_analysis_subagent(
        "Read internal_trial_results.txt for NX-217 efficacy data."
    )

    TIMEOUTS.reset()

    # web should succeed, doc should fail with structured error + partial.
    findings: list[Finding] = []
    errors: list[SubagentError] = []

    if isinstance(web_result, list):
        findings.extend(web_result)
        print(f"  ✓ web_search:        {len(web_result)} finding(s)")
    else:
        errors.append(web_result)

    if isinstance(doc_result, list):
        findings.extend(doc_result)
    else:
        # Include partial_results in the report
        findings.extend(doc_result.partial_results)
        errors.append(doc_result)
        print(f"  ✗ document_analysis: {doc_result.failure_type.value}")
        print(f"      attempted_query:  {doc_result.attempted_query[:70]}…")
        print(f"      partial_results:  {len(doc_result.partial_results)}")
        print(f"      missing_topics:   {doc_result.missing_topics}")

    report = synthesize_report(findings=findings, errors=errors)
    print("\n--- Final report ---")
    print(report)


def demo_5_conflicting_sources():
    """Step 5 — two credible sources disagree; synthesis preserves both.

    No API call — we construct a small conflict scenario directly.
    """
    print("\n" + "=" * 70)
    print(" Demo 5 — Conflicting sources preserved (Step 5)")
    print(" Reuters and WSJ disagree on Acme Corp's 2024 growth rate.")
    print(" Synthesis preserves BOTH numbers with attribution.")
    print("=" * 70)

    findings = [
        # Two sources agree on company size → established.
        Finding(
            claim="Acme Corp's 2024 revenue was $2.4B",
            evidence_excerpt="Acme Corp reported full-year 2024 revenue of $2.4 billion.",
            source="https://reuters.example/acme-2024-results",
            publication_date=date(2025, 2, 18),
            topic="acme_2024_revenue",
        ),
        Finding(
            claim="Acme Corp's 2024 revenue was $2.4B",
            evidence_excerpt="Industry sources put Acme's full-year 2024 revenue at $2.4 billion.",
            source="https://wsj.example/acme-results-2024",
            publication_date=date(2025, 2, 19),
            topic="acme_2024_revenue",
        ),
        # Two sources disagree on growth rate → contested.
        Finding(
            claim="Acme Corp grew 12.0% year-over-year in 2024",
            evidence_excerpt="The full-year audit confirmed 12.0% YoY growth, in line with management guidance.",
            source="https://reuters.example/acme-2024-results",
            publication_date=date(2025, 2, 18),
            topic="acme_2024_growth_rate",
        ),
        Finding(
            claim="Acme Corp grew 9.8% year-over-year in 2024",
            evidence_excerpt="Subscription analysis pegs Acme's 2024 growth rate at 9.8%, lower than guidance.",
            source="https://wsj.example/acme-results-2024",
            publication_date=date(2025, 2, 19),
            topic="acme_2024_growth_rate",
        ),
    ]

    report = synthesize_report(findings=findings, errors=[])
    print(report)
    print(
        "Notice that the synthesis did NOT pick 12% or 9.8%. Both numbers\n"
        "appear with their respective sources. That's the Step 5 requirement."
    )


DEMOS = {
    "1": demo_1_simple_research,
    "2": demo_2_parallel_vs_sequential,
    "3": demo_3_findings_attribution,
    "4": demo_4_simulated_timeout,
    "5": demo_5_conflicting_sources,
}

# Demos 1 and 2 use the API; 3, 4, 5 don't.
NEEDS_API = {"1", "2"}


def main():
    args = sys.argv[1:]
    needs_api = bool(set(args or DEMOS.keys()) & NEEDS_API)
    if needs_api and not os.getenv("ANTHROPIC_API_KEY"):
        sys.exit("ERROR: set ANTHROPIC_API_KEY first (see HOW_TO_RUN.md). "
                 "Demos 3, 4, 5 run without the API.")

    if args:
        for arg in args:
            if arg not in DEMOS:
                sys.exit(f"Unknown demo {arg!r}. Choose from: {list(DEMOS)}")
            DEMOS[arg]()
    else:
        for fn in DEMOS.values():
            fn()


if __name__ == "__main__":
    main()
