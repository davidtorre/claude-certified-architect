# Exercise 3 — Build a Structured Data Extraction Pipeline

A single Python file (`pipeline.py`) implementing all 5 steps of the
exercise. Domain: research-paper metadata extraction.

## What each step asks for, and where it lives in `pipeline.py`

| Step | What the exam guide asks for | Where it lives |
|---|---|---|
| 1 | Define an extraction tool with a JSON schema containing required fields, optional fields, an enum-with-"other" + detail string pattern, and nullable fields. Verify the model returns `null` rather than fabricating values on a sparse document. | `StudyType`, `Author`, `ExtractedPaper` Pydantic models + `EXTRACT_TOOL` dict. Demo 1 runs the sparse-doc test. |
| 2 | Validation-retry loop: when validation fails, send the document, the failed extraction, and the validation error back. Track resolvable (format) vs unresolvable (info absent) errors. | `_RESOLVABLE_TAGS`, `classify_error()`, `format_retry_feedback()`, `extract_with_retry()`. Demo 2. |
| 3 | Few-shot examples for varied document formats (inline citations vs bibliographies, narrative vs structured tables). Verify improved handling. | `FEW_SHOT_EXAMPLES` list (3 varieties), `build_few_shot_prompt()`. Demo 3 compares zero-shot vs few-shot on the tabular doc. |
| 4 | Batch processing via the Message Batches API: submit many documents, handle failures by `custom_id`, resubmit (e.g. chunking oversized). | `build_batch_request()`, `chunk_oversized()`, `submit_batch_demo()`. Demo 4 (no real submission — prints the call shape and the recovery flow). |
| 5 | Field-level confidence scores → human-review routing. Accuracy analysis by document type and field. | `field_confidences` field on `ExtractedPaper`, `route_for_review()`, `accuracy_by_format_and_field()`. Demo 5. |

## File creation sequence (build order)

The file is structured so you can read top-to-bottom and each section
makes sense given what came before:

1. **Imports + `MODEL` constant.**
2. **Step 1 — Pydantic schema.** `StudyType` enum, `Author`, `ExtractedPaper`.
   The model_validator on `ExtractedPaper` enforces the enum-with-other
   constraint.
3. **`EXTRACT_TOOL` dict.** Derived from the Pydantic schema via
   `model_json_schema()` so the SDK gets the same constraints as the
   in-Python validator.
4. **Step 1 helper — `call_model_once()`.** Forced `tool_choice` for
   guaranteed JSON output.
5. **Step 2 — validation-retry.** Error classification, feedback
   formatter, the retry loop.
6. **Step 3 — few-shots.** 3 examples + prompt builder.
7. **Step 4 — batch helpers.** Build a batch request, chunk an
   oversized document, simulate the recovery flow.
8. **Step 5 — confidence routing + accuracy.** `route_for_review()`,
   `accuracy_by_format_and_field()`.
9. **Sample documents.** `SAMPLE_NORMAL`, `SAMPLE_SPARSE`.
10. **5 demos**, one per step.
11. **`main()` CLI.**

## Demo → step mapping

| Demo | Step it shows | Needs API? |
|---|---|---|
| 1 | Step 1 — schema + null-vs-hallucination on a sparse doc | yes |
| 2 | Step 2 — validation-retry loop | yes |
| 3 | Step 3 — zero-shot vs few-shot on a tabular doc | yes |
| 4 | Step 4 — batch shape + chunked recovery (prints the calls; doesn't submit) | NO |
| 5 | Step 5 — confidence routing + per-format accuracy report | yes |

## Run it

See [HOW_TO_RUN.md](./HOW_TO_RUN.md) for setup. Quick version:

```bash
pip install -r requirements.txt
export ANTHROPIC_API_KEY=sk-ant-...
python pipeline.py        # all 5 demos
python pipeline.py 4      # the no-API one
python pipeline.py 1 2    # just steps 1 and 2
```
