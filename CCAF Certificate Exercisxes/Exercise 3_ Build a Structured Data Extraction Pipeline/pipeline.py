"""
============================================================================
 Exercise 3 — Build a Structured Data Extraction Pipeline
============================================================================

This single file implements all 5 steps of the exercise. Read top to bottom;
every step is wrapped in a banner comment.

    Step 1 — Define an extraction tool with a JSON schema containing
             required fields, optional fields, an enum-with-"other"+detail
             pattern, and nullable fields. Verify on a sparse document
             that the model returns null rather than fabricating values.
    Step 2 — Validation-retry loop: when Pydantic validation fails, send
             the document, the failed extraction, and the specific error
             back to the model. Track which errors are resolvable
             (format) versus unresolvable (info absent from source).
    Step 3 — Few-shot examples for varied formats (narrative vs tabular
             vs bibliographic).
    Step 4 — Batch processing via the Message Batches API: submit many
             documents at once, handle failures by custom_id, resubmit
             failed ones (e.g. chunking oversized docs).
    Step 5 — Field-level confidence scores → human-review routing.
             Plus a small accuracy report by document type and field.

Run with:
    python pipeline.py                # runs every demo in order
    python pipeline.py 1               # runs only demo 1
    python pipeline.py 2 5             # runs demos 2 and 5

Requires:
    ANTHROPIC_API_KEY   environment variable (steps 1, 2, 3, 5)
    pydantic >= 2       installed
    anthropic >= 0.40   installed

Domain: research-paper metadata extraction. The schema captures fields
most papers expose; sample documents vary in format to exercise step 3.
============================================================================
"""

from __future__ import annotations

import json
import os
import sys
import time
from enum import Enum
from typing import Any

import anthropic
from pydantic import BaseModel, Field, ValidationError, model_validator


MODEL = os.getenv("ANTHROPIC_MODEL", "claude-sonnet-4-5")


# ============================================================================
# STEP 1 — Schema with the four field-shape patterns
# ============================================================================
# The exam guide names four patterns; we define them below using Pydantic v2.
# Pydantic gives us:
#   - in-Python validation (raises ValidationError on bad data)
#   - model_json_schema() that we hand to the SDK as the tool's input_schema
#
# The four patterns:
#   - REQUIRED          : title, authors             — must be present
#   - OPTIONAL          : doi, venue, abstract       — may be omitted
#   - ENUM-WITH-"other" : study_type + study_type_other — when value is
#                          "other", the detail string must be supplied
#   - NULLABLE          : publication_year, sample_size — explicitly null
#                          when the source doesn't state it (NOT guessed)
# ============================================================================


class StudyType(str, Enum):
    """Study type — an enum with an OTHER escape hatch."""
    EXPERIMENTAL  = "experimental"
    OBSERVATIONAL = "observational"
    REVIEW        = "review"
    META_ANALYSIS = "meta_analysis"
    OTHER         = "other"   # when used, study_type_other must be filled


class Author(BaseModel):
    """A single author. Required: name. Optional: affiliation."""
    name:        str       = Field(description="Full name as printed.")
    affiliation: str | None = Field(default=None, description="Institution; null if unstated.")


class ExtractedPaper(BaseModel):
    """Target schema for paper-metadata extraction.

    Each field's description ends up in the JSON schema we hand the model.
    The wording matters: "return null if not stated" is the nudge that
    keeps the model honest about absent information (Step 1).
    """

    # ── REQUIRED ──────────────────────────────────────────────────────
    title:   str          = Field(description="Title exactly as printed.")
    authors: list[Author] = Field(min_length=1, description="At least one author.")

    # ── ENUM WITH "OTHER" + DETAIL ────────────────────────────────────
    study_type: StudyType = Field(
        description=(
            "Type of study. Use 'other' only when none of the listed "
            "categories applies, AND set study_type_other to a description."
        ),
    )
    study_type_other: str | None = Field(
        default=None,
        description="REQUIRED when study_type='other'; otherwise null.",
    )

    # ── OPTIONAL ──────────────────────────────────────────────────────
    doi:      str | None = Field(default=None, description="DOI; null if not stated.")
    venue:    str | None = Field(default=None, description="Journal/conference; null if not stated.")
    abstract: str | None = Field(default=None, description="Abstract text; null if not present.")

    # ── NULLABLE — return null when the source doesn't state these,
    # don't guess from filenames or context ─────────────────────────────
    publication_year: int | None = Field(
        default=None, ge=1900, le=2100,
        description="4-digit year. Null if not stated. DO NOT guess.",
    )
    sample_size: int | None = Field(
        default=None, ge=1,
        description=(
            "Number of participants. Null for review/meta-analysis "
            "papers, or when the source does not state it."
        ),
    )

    # ── CONFIDENCE (Step 5 — populated below) ────────────────────────
    field_confidences: dict[str, float] = Field(
        default_factory=dict,
        description=(
            "Per-field confidence scores in [0,1]. Be calibrated — "
            ">0.9 only when the field is verbatim in the document; "
            "lower for inferred or partial information."
        ),
    )

    # ── Cross-field validation: enum-with-other consistency ──────────
    @model_validator(mode="after")
    def _enforce_other_detail(self) -> "ExtractedPaper":
        """If study_type is OTHER, study_type_other must be non-empty."""
        if self.study_type == StudyType.OTHER:
            if not self.study_type_other or not self.study_type_other.strip():
                raise ValueError(
                    "study_type_other is required (and non-empty) when "
                    "study_type='other'. Either set study_type_other to "
                    "describe the type, or pick a more specific study_type."
                )
        return self


# Tool spec the SDK consumes. We DERIVE input_schema from Pydantic so
# the validator and the schema can never drift apart.
EXTRACT_TOOL_NAME = "extract_paper_metadata"

EXTRACT_TOOL = {
    "name": EXTRACT_TOOL_NAME,
    "description": (
        "Extract structured metadata from a research paper. Return null "
        "for fields the document does not state — DO NOT guess from "
        "filenames, dates, or context. For study_type, pick the most "
        "specific value; only use 'other' (with study_type_other filled) "
        "when none of the listed categories applies. Provide a calibrated "
        "confidence per field in field_confidences (0.0–1.0)."
    ),
    "input_schema": ExtractedPaper.model_json_schema(),
}


# ============================================================================
# STEP 1 helper — single extraction call, no retry yet
# ============================================================================

SYSTEM_PROMPT_BASIC = """\
You are a research-paper metadata extractor. Call the \
extract_paper_metadata tool with the structured fields it requires.

Rules:
- For fields not stated in the document: return null. Do NOT guess.
- For funding_sources / keywords-style lists: empty list, never null.
- For study_type: pick the most specific value. Use 'other' (with
  study_type_other) only when nothing fits.
- For field_confidences: be calibrated. >0.9 only when the field is
  verbatim in the document.
"""


def call_model_once(
    *,
    client: anthropic.Anthropic,
    system_prompt: str,
    document: str,
    extra_messages: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    """Call Claude with forced tool_choice. Return the raw tool_use input
    dict. Forced tool_choice means we get a guaranteed tool call, no prose.
    """
    messages: list[dict[str, Any]] = [{
        "role": "user",
        "content": (
            f"Extract structured metadata from the following document.\n\n"
            f"--- DOCUMENT ---\n{document}"
        ),
    }]
    if extra_messages:
        messages.extend(extra_messages)

    response = client.messages.create(
        model=MODEL,
        max_tokens=4096,
        system=system_prompt,
        tools=[EXTRACT_TOOL],
        # Force the model to call our extraction tool — guaranteed JSON.
        tool_choice={"type": "tool", "name": EXTRACT_TOOL_NAME},
        messages=messages,
    )
    for block in response.content:
        if getattr(block, "type", None) == "tool_use":
            return dict(block.input or {})
    raise RuntimeError("Model did not call the extraction tool (unexpected with forced tool_choice).")


# ============================================================================
# STEP 2 — Validation-retry loop with resolvable/unresolvable classification
# ============================================================================
# When Pydantic validation fails, we:
#   1. Classify each error as RESOLVABLE (format/type) or UNRESOLVABLE
#      (info absent from the source).
#   2. Send a follow-up message including the document, the failed
#      extraction, and the specific errors. The model corrects and tries
#      again.
#   3. Stop when (a) extraction validates, (b) every error is unresolvable,
#      or (c) we've used our retry budget.
# ============================================================================

# Pydantic error type tags we know how to classify.
_RESOLVABLE_TAGS = {
    "string_type", "int_type", "float_type", "bool_type",
    "list_type", "dict_type",
    "enum",                     # picked a value not in the enum
    "value_error",              # raised by our model_validator
    "greater_than_equal", "less_than_equal",
    "string_too_long", "string_too_short",
}
# 'missing' is ambiguous — could be format issue or info-truly-absent.
# We treat it as UNRESOLVABLE after one retry to avoid loops.


def classify_error(error: dict[str, Any]) -> str:
    """Return 'resolvable' or 'unresolvable' for one Pydantic error dict."""
    return "resolvable" if error.get("type", "") in _RESOLVABLE_TAGS else "unresolvable"


def format_retry_feedback(errors: list[dict[str, Any]], prior: dict[str, Any]) -> str:
    """Build the feedback message for the retry. Tells the model
    EXACTLY which fields failed, why, and what to do."""
    lines = [
        "Your previous extraction failed schema validation. Please correct "
        "the following issues and call the tool again:",
        "",
    ]
    for e in errors:
        loc = ".".join(str(p) for p in e.get("loc", ()))
        kind = classify_error(e)
        tag = "[FORMAT — fix and retry]" if kind == "resolvable" else "[INFO MAY BE ABSENT — re-check the document]"
        lines.append(f"  • {loc}: {e.get('msg', '')} {tag}")
    lines += [
        "",
        "Your previous attempt was:",
        "```json",
        json.dumps(prior, indent=2, default=str),
        "```",
        "",
        "Re-read the document. For any field whose information is GENUINELY "
        "ABSENT, return null — do not fabricate. For format errors, fix the "
        "value to match the schema and call the tool again.",
    ]
    return "\n".join(lines)


def extract_with_retry(
    *,
    client: anthropic.Anthropic,
    system_prompt: str,
    document: str,
    max_attempts: int = 3,
) -> tuple[ExtractedPaper | None, list[dict[str, Any]]]:
    """Try extraction up to `max_attempts` times, feeding errors back
    on failure. Returns (validated_paper or None, attempt_log).

    The attempt log is a list of dicts so callers can see what happened
    on each try.
    """
    extra: list[dict[str, Any]] = []
    log: list[dict[str, Any]] = []

    for attempt in range(1, max_attempts + 1):
        raw = call_model_once(
            client=client,
            system_prompt=system_prompt,
            document=document,
            extra_messages=extra,
        )
        try:
            paper = ExtractedPaper.model_validate(raw)
            log.append({"attempt": attempt, "outcome": "validated"})
            return paper, log
        except ValidationError as e:
            errors = e.errors()
            categories = {classify_error(err) for err in errors}
            log.append({
                "attempt": attempt,
                "outcome": "validation_failed",
                "errors": errors,
                "categories": sorted(categories),
            })

            # Bail early if every error is unresolvable.
            if categories == {"unresolvable"}:
                log[-1]["bailed"] = "all_unresolvable"
                return None, log

            # Otherwise: build feedback and retry.
            feedback = format_retry_feedback(errors, raw)
            extra = [{"role": "user", "content": feedback}]

    return None, log


# ============================================================================
# STEP 3 — Few-shot examples for varied document formats
# ============================================================================
# The exam guide names two structural varieties to handle:
#   - inline citations vs explicit bibliographies
#   - narrative descriptions vs structured tables
# We provide one few-shot per variety. Each is a (document, ideal-extraction)
# pair. They get rendered into the system prompt below.
# ============================================================================

FEW_SHOT_EXAMPLES = [
    {
        "label": "Narrative-style preprint",
        "document": (
            "Title: Sleep Restriction and Working Memory in Young Adults\n"
            "Authors: Sara Chen (Stanford)*, Marcus Lee (MIT)\n"
            "*Corresponding: schen@stanford.edu\n"
            "Posted on bioRxiv, March 14, 2024. doi:10.1101/2024.03.12.584321\n\n"
            "Abstract\n"
            "We conducted a randomized controlled trial with 84 healthy adults..."
        ),
        "extraction": {
            "title": "Sleep Restriction and Working Memory in Young Adults",
            "authors": [
                {"name": "Sara Chen",  "affiliation": "Stanford"},
                {"name": "Marcus Lee", "affiliation": "MIT"},
            ],
            "study_type": "experimental",
            "study_type_other": None,
            "doi": "10.1101/2024.03.12.584321",
            "venue": "bioRxiv",
            "publication_year": 2024,
            "sample_size": 84,
            "field_confidences": {
                "title": 0.99, "authors": 0.95, "doi": 0.99,
                "venue": 0.95, "publication_year": 0.95, "sample_size": 0.95,
            },
        },
    },
    {
        "label": "Tabular journal cover page",
        "document": (
            "================================================\n"
            " J. Cognitive Neuroscience  Vol 35  Issue 7  2023\n"
            "================================================\n\n"
            "  Default-Mode Network and Memory Consolidation\n\n"
            "  | Author              | Affiliation   |\n"
            "  |---------------------|---------------|\n"
            "  | Hannah Kowalski (*) | UC San Diego  |\n"
            "  | Jacob Weiss         | UC San Diego  |\n\n"
            "  (*) corresponding author\n\n"
            "  Synopsis. We followed 47 participants over 18 months..."
        ),
        "extraction": {
            "title": "Default-Mode Network and Memory Consolidation",
            "authors": [
                {"name": "Hannah Kowalski", "affiliation": "UC San Diego"},
                {"name": "Jacob Weiss",     "affiliation": "UC San Diego"},
            ],
            "study_type": "observational",
            "study_type_other": None,
            "doi": None,
            "venue": "J. Cognitive Neuroscience",
            "publication_year": 2023,
            "sample_size": 47,
            "field_confidences": {
                "title": 0.99, "authors": 0.95, "doi": 0.95,
                "venue": 0.95, "publication_year": 0.95, "sample_size": 0.9,
            },
        },
    },
    {
        "label": "Review article with bibliography",
        "document": (
            "TRENDS IN MOLECULAR MEDICINE\n"
            "Review article — https://doi.org/10.1016/j.molmed.2024.02.008\n\n"
            "GLP-1 Receptor Agonists Beyond Diabetes: A Decade in Review\n"
            "Olawale Adebayo[1,*], Karin Mueller[2]\n"
            "[1] Imperial College London, [2] Karolinska Institutet\n"
            "* o.adebayo@imperial.ac.uk\n\n"
            "We review evidence from 2014-2024 on the use of GLP-1 RAs..."
        ),
        "extraction": {
            "title": "GLP-1 Receptor Agonists Beyond Diabetes: A Decade in Review",
            "authors": [
                {"name": "Olawale Adebayo", "affiliation": "Imperial College London"},
                {"name": "Karin Mueller",   "affiliation": "Karolinska Institutet"},
            ],
            "study_type": "review",
            "study_type_other": None,
            "doi": "10.1016/j.molmed.2024.02.008",
            "venue": "Trends in Molecular Medicine",
            "publication_year": 2024,
            "sample_size": None,    # review papers don't have one
            "field_confidences": {
                "title": 0.99, "authors": 0.95, "doi": 0.99,
                "venue": 0.99, "publication_year": 0.99, "sample_size": 0.99,
            },
        },
    },
]


def build_few_shot_prompt() -> str:
    """Render the 3 examples into the system prompt."""
    parts = [SYSTEM_PROMPT_BASIC, "\nFEW-SHOT EXAMPLES — varied formats:\n"]
    for i, ex in enumerate(FEW_SHOT_EXAMPLES, start=1):
        parts.append(
            f"\n--- Example {i}: {ex['label']} ---\n"
            f"\nDOCUMENT:\n{ex['document']}\n"
            f"\nIDEAL EXTRACTION (call extract_paper_metadata with):\n"
            f"{json.dumps(ex['extraction'], indent=2)}\n"
        )
    parts.append("\n--- End of examples. Apply the same patterns to user input. ---\n")
    return "".join(parts)


SYSTEM_PROMPT_FEW_SHOT = build_few_shot_prompt()


# ============================================================================
# STEP 4 — Batch processing via the Message Batches API
# ============================================================================
# Submit many documents in one batch (50% cheaper, up to 24h processing
# window). Failures come back keyed by custom_id, so YOU never lose track
# of which document failed. Common failure: oversized inputs — the recovery
# strategy is to chunk and resubmit.
# ============================================================================

# A conservative size threshold for "oversized". Real models accept much
# more, but we use a small number so the demo can show chunking without
# generating megabyte-sized docs.
MAX_CHARS_PER_DOC = 80_000


def build_batch_request(custom_id: str, document: str) -> dict[str, Any]:
    """One entry for client.messages.batches.create(requests=[...])."""
    return {
        "custom_id": custom_id,
        "params": {
            "model":       MODEL,
            "max_tokens":  4096,
            "system":      SYSTEM_PROMPT_FEW_SHOT,
            "tools":       [EXTRACT_TOOL],
            "tool_choice": {"type": "tool", "name": EXTRACT_TOOL_NAME},
            "messages": [{
                "role": "user",
                "content": f"Extract metadata from:\n\n{document}",
            }],
        },
    }


def chunk_oversized(custom_id: str, document: str) -> list[tuple[str, str]]:
    """Split a too-long document into overlapping chunks. Each chunk gets
    a custom_id like 'paper-007::chunk-0' so we can stitch results later.
    """
    if len(document) <= MAX_CHARS_PER_DOC:
        return [(custom_id, document)]
    chunks: list[tuple[str, str]] = []
    overlap = 2000
    start = 0
    idx = 0
    while start < len(document):
        end = min(start + MAX_CHARS_PER_DOC, len(document))
        chunks.append((f"{custom_id}::chunk-{idx}", document[start:end]))
        if end >= len(document):
            break
        start = end - overlap
        idx += 1
    return chunks


def submit_batch_demo(documents: dict[str, str]) -> None:
    """End-to-end batch demo with size-based failure recovery.

    `documents` is custom_id → document_text. We:
      1. Build the initial batch (chunking nothing — submit as-is).
      2. (In a real run) submit, poll, collect.
      3. For any custom_id that came back failed AND whose original
         document was oversized, chunk + resubmit.

    Because the sandbox can't actually submit batches, this function
    PRINTS the calls it would make and SHOWS the recovery flow on a
    fabricated set of "failure" custom_ids.
    """
    print("\n  → Submitting initial batch:")
    initial = [build_batch_request(cid, doc) for cid, doc in documents.items()]
    print(f"    requests in batch: {len(initial)}")
    print(f"    sample request keys: {sorted(initial[0].keys())}")
    print(f"    sample params keys:  {sorted(initial[0]['params'].keys())}")
    print()
    print("  In a real run you would now do:")
    print("    batch = client.messages.batches.create(requests=initial)")
    print("    # poll batch.id until status='ended'")
    print("    results = client.messages.batches.results(batch.id)")
    print()

    # Pretend two custom_ids failed — one for size, one for transient reasons.
    pretend_failed_for_size: list[str] = [
        cid for cid, doc in documents.items() if len(doc) > MAX_CHARS_PER_DOC
    ]
    pretend_failed_other: list[str] = []  # add any to demonstrate

    print(f"  → (simulated) failures by custom_id: {pretend_failed_for_size + pretend_failed_other}")

    # Recovery: chunk size-failures, resubmit; others would resubmit as-is
    # (or escalate after N retries).
    recovery: list[dict[str, Any]] = []
    for cid in pretend_failed_for_size:
        for chunk_id, chunk_text in chunk_oversized(cid, documents[cid]):
            recovery.append(build_batch_request(chunk_id, chunk_text))

    if recovery:
        print(f"\n  → Built recovery batch: {len(recovery)} requests "
              f"(chunked from {len(pretend_failed_for_size)} oversized docs)")
        print(f"    chunk custom_ids: {[r['custom_id'] for r in recovery]}")
    else:
        print("\n  → No recovery batch needed.")


# ============================================================================
# STEP 5 — Confidence-based human-review routing + accuracy by type/field
# ============================================================================
# The schema already has `field_confidences`. Here we turn those numbers
# into a routing decision and (separately) an accuracy report against
# hand-curated ground truth.
# ============================================================================


def route_for_review(paper: ExtractedPaper) -> tuple[str, str]:
    """Decide whether the extraction needs human review.

    Three outcomes:
      AUTO_ACCEPT   — every confidence above threshold
      HUMAN_REVIEW  — at least one important field below threshold
      REJECT        — no usable extraction (caller passes None)
    """
    high_stakes = {"title", "authors", "doi"}
    threshold = 0.7

    confs = paper.field_confidences or {}
    if not confs:
        # No confidence emitted at all — be conservative.
        return "HUMAN_REVIEW", "no field_confidences emitted by the model"

    low_overall = [k for k, v in confs.items() if v < threshold]
    low_high_stakes = [k for k in low_overall if k in high_stakes]

    if low_high_stakes:
        return "HUMAN_REVIEW", f"high-stakes field(s) below {threshold}: {low_high_stakes}"

    mean = sum(confs.values()) / len(confs)
    if mean < 0.75:
        return "HUMAN_REVIEW", f"mean confidence {mean:.2f} below 0.75"

    return "AUTO_ACCEPT", "all confidences above thresholds"


def accuracy_by_format_and_field(
    samples: list[tuple[str, ExtractedPaper, dict[str, Any]]],
) -> dict[str, dict[str, dict[str, int]]]:
    """Compare extractions against ground truth, group by format AND field.

    `samples` is a list of (format_label, extracted_paper, ground_truth).
    Returns: { format: { field: {"matches": int, "total": int } } }

    Use case: if extractions on tabular documents are 60% accurate while
    narrative docs hit 95%, that's a signal you need more tabular
    few-shots — exactly the kind of signal the exam asks for.
    """
    report: dict[str, dict[str, dict[str, int]]] = {}
    for fmt, paper, truth in samples:
        extracted = paper.model_dump(mode="json")
        for field, expected in truth.items():
            actual = extracted.get(field)
            matched = _values_equal(actual, expected)
            report.setdefault(fmt, {}).setdefault(field, {"matches": 0, "total": 0})
            report[fmt][field]["total"] += 1
            if matched:
                report[fmt][field]["matches"] += 1
    return report


def _values_equal(a: Any, b: Any) -> bool:
    if isinstance(a, str) and isinstance(b, str):
        return a.strip() == b.strip()
    return a == b


# ============================================================================
# Sample documents for the demos
# ============================================================================

# A normal narrative-style document (used for the happy path + retry).
SAMPLE_NORMAL = (
    "Caffeine Dosage and Simple Reaction Time: A Double-Blind RCT\n\n"
    "Authors: Maya Holloway*, Diego Rivera, Anna Petrov\n"
    "*Corresponding (m.holloway@upenn.edu)\n"
    "All authors: University of Pennsylvania, Department of Psychology\n\n"
    "Published in Psychopharmacology, June 2023.\n"
    "DOI: 10.1007/s00213-023-06401-z\n\n"
    "ABSTRACT\n"
    "We conducted a double-blind, placebo-controlled trial with 120 college "
    "students (mean age 20.4) measuring simple-reaction-time differences "
    "across 0mg, 100mg, and 200mg caffeine doses. Dose-dependent reduction "
    "in reaction time observed."
)

# Deliberately sparse — for the null-vs-hallucination test (Step 1).
SAMPLE_SPARSE = (
    "Behavioral Effects of Intermittent Light Exposure in Mice\n\n"
    "[Authors withheld for blind peer review]\n"
    "[Affiliation suppressed]\n\n"
    "We exposed C57BL/6J mice to intermittent light cycles and "
    "measured anxiety-like behavior in the open-field test.\n\n"
    "[Funding and acknowledgments will be added on revision]"
)


# ============================================================================
# DEMOS — one per concept the exercise calls out
# ============================================================================

def demo_1_basic_and_nulls():
    """Step 1 — basic extraction + null-vs-hallucination on a sparse doc."""
    print("\n" + "=" * 70)
    print(" Demo 1 — Schema + null-vs-hallucination (Step 1)")
    print("=" * 70)
    client = anthropic.Anthropic()

    print("\n--- Normal document ---")
    raw = call_model_once(
        client=client,
        system_prompt=SYSTEM_PROMPT_BASIC,
        document=SAMPLE_NORMAL,
    )
    paper = ExtractedPaper.model_validate(raw)
    print(f"  title:            {paper.title!r}")
    print(f"  publication_year: {paper.publication_year}")
    print(f"  doi:              {paper.doi}")
    print(f"  sample_size:      {paper.sample_size}")
    print(f"  study_type:       {paper.study_type.value}")

    print("\n--- Sparse document (most fields absent) ---")
    raw_sparse = call_model_once(
        client=client,
        system_prompt=SYSTEM_PROMPT_BASIC,
        document=SAMPLE_SPARSE,
    )
    print("  Raw tool input:")
    print("  " + json.dumps(raw_sparse, indent=2).replace("\n", "\n  "))
    print(
        "\n  ↑ Watch that publication_year / doi / sample_size are null,\n"
        "    not fabricated. That's the schema descriptions doing their job."
    )


def demo_2_validation_retry():
    """Step 2 — validation-retry loop. We attempt extraction with a
    deliberately weak prompt to provoke an error and watch the retry."""
    print("\n" + "=" * 70)
    print(" Demo 2 — Validation-retry loop (Step 2)")
    print("=" * 70)
    client = anthropic.Anthropic()

    paper, log = extract_with_retry(
        client=client,
        system_prompt=SYSTEM_PROMPT_BASIC,
        document=SAMPLE_NORMAL,
        max_attempts=3,
    )

    print(f"\n  attempts: {len(log)}")
    for entry in log:
        outcome = entry["outcome"]
        if outcome == "validation_failed":
            print(f"    attempt {entry['attempt']}: FAILED  "
                  f"categories={entry['categories']}")
            for err in entry["errors"][:3]:
                print(f"       - {err.get('loc')}: {err.get('msg')}")
        else:
            print(f"    attempt {entry['attempt']}: {outcome}")

    if paper:
        print(f"  → final extraction succeeded: {paper.title!r}")
    else:
        print("  → final extraction FAILED (escalate to human)")


def demo_3_format_variety():
    """Step 3 — compare zero-shot vs few-shot on a varied-format document.

    We extract the tabular sample with both prompts and print both
    titles. With few-shots, the model handles the tabular layout cleanly;
    without them, it sometimes misses author affiliations or treats the
    'Synopsis' label as something other than the abstract.
    """
    print("\n" + "=" * 70)
    print(" Demo 3 — Few-shots improve format variety (Step 3)")
    print("=" * 70)
    client = anthropic.Anthropic()

    tabular_doc = FEW_SHOT_EXAMPLES[1]["document"]   # the tabular one

    print("\n--- ZERO-SHOT (basic prompt) ---")
    raw0 = call_model_once(
        client=client,
        system_prompt=SYSTEM_PROMPT_BASIC,
        document=tabular_doc,
    )
    print(f"  authors: {[a.get('name') for a in raw0.get('authors', [])]}")
    print(f"  venue:   {raw0.get('venue')!r}")

    print("\n--- FEW-SHOT (prompt with 3 varied examples) ---")
    raw1 = call_model_once(
        client=client,
        system_prompt=SYSTEM_PROMPT_FEW_SHOT,
        document=tabular_doc,
    )
    print(f"  authors: {[a.get('name') for a in raw1.get('authors', [])]}")
    print(f"  venue:   {raw1.get('venue')!r}")


def demo_4_batch_processing():
    """Step 4 — batch submission shape + size-based recovery (no API call)."""
    print("\n" + "=" * 70)
    print(" Demo 4 — Batch processing & failure recovery (Step 4)")
    print("=" * 70)
    documents = {
        "paper-001": SAMPLE_NORMAL,
        "paper-002": SAMPLE_SPARSE,
        # Synthetic oversized doc to demonstrate chunking
        "paper-003-big": SAMPLE_NORMAL * 1000,
    }
    submit_batch_demo(documents)


def demo_5_confidence_routing():
    """Step 5 — confidence routing + per-format accuracy report."""
    print("\n" + "=" * 70)
    print(" Demo 5 — Confidence routing + accuracy report (Step 5)")
    print("=" * 70)
    client = anthropic.Anthropic()

    # Run extraction across 3 different document formats.
    results: list[tuple[str, ExtractedPaper, dict[str, Any]]] = []
    for ex in FEW_SHOT_EXAMPLES:
        raw = call_model_once(
            client=client,
            system_prompt=SYSTEM_PROMPT_FEW_SHOT,
            document=ex["document"],
        )
        try:
            paper = ExtractedPaper.model_validate(raw)
        except ValidationError as e:
            print(f"  {ex['label']}: extraction failed validation; skipping ({e})")
            continue

        decision, reason = route_for_review(paper)
        print(f"\n  [{ex['label']}]")
        print(f"    routing decision: {decision} — {reason}")
        # Use the few-shot's "ideal extraction" as our ground truth.
        results.append((ex["label"], paper, ex["extraction"]))

    print("\n  Accuracy by format and field:")
    report = accuracy_by_format_and_field(results)
    for fmt, fields in report.items():
        print(f"    {fmt}:")
        for fname, stats in sorted(fields.items()):
            rate = stats["matches"] / stats["total"] if stats["total"] else 0.0
            print(f"      {fname:20s}  {stats['matches']}/{stats['total']}  ({rate:.0%})")


DEMOS = {
    "1": demo_1_basic_and_nulls,
    "2": demo_2_validation_retry,
    "3": demo_3_format_variety,
    "4": demo_4_batch_processing,
    "5": demo_5_confidence_routing,
}


def main():
    if not os.getenv("ANTHROPIC_API_KEY"):
        # Demo 4 doesn't actually call the API, but everything else does.
        if not (sys.argv[1:] and sys.argv[1:] == ["4"]):
            sys.exit("ERROR: set ANTHROPIC_API_KEY first (see HOW_TO_RUN.md). "
                     "(Demo 4 alone runs without the API.)")

    args = sys.argv[1:]
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
