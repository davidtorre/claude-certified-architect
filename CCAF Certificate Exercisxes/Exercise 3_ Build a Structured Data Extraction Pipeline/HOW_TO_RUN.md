# HOW TO RUN — Exercise 3

## 1. Install

```bash
cd "Exercise 3: Build a Structured Data Extraction Pipeline"
pip install -r requirements.txt
```

That installs `anthropic` (the SDK) and `pydantic` (the schema layer).

## 2. Set your API key

```bash
# macOS / Linux
export ANTHROPIC_API_KEY=sk-ant-...

# Windows PowerShell
$env:ANTHROPIC_API_KEY = "sk-ant-..."
```

Get a key at https://console.anthropic.com.
(Demo 4 — batch — runs without the API; everything else needs it.)

## 3. Run

```bash
python pipeline.py            # runs all 5 demos in order
python pipeline.py 1          # just demo 1
python pipeline.py 4          # the no-API one
python pipeline.py 1 5        # demos 1 and 5
```

## 4. What to look for in each demo

| Demo | Watch for |
|---|---|
| **1** | First the normal doc gets extracted cleanly. Then on the sparse doc — make sure `publication_year`, `doi`, `sample_size` come back as `null`. The schema descriptions tell the model "DO NOT guess"; this demo verifies the rule sticks. |
| **2** | Up to 3 attempts. Each attempt prints its outcome. If validation fails, the script logs the error categories (`resolvable` / `unresolvable`) and feeds the error message back to the model. Most runs succeed on attempt 1 with the basic prompt; if not, the retry should fix it. |
| **3** | Two extractions on the same tabular document — first with the basic prompt, second with the few-shot prompt. With few-shots, both author names + the venue should be recognized cleanly; without, you may see one author missed or the venue empty. |
| **4** | Prints the shape of a batch request (the dict you'd pass to `client.messages.batches.create`). Then simulates an oversized-doc failure and prints the chunked recovery batch. No real network call. |
| **5** | For each of 3 document formats, prints a routing decision: `AUTO_ACCEPT` or `HUMAN_REVIEW` with a reason. Then a per-format-and-field accuracy table. Lower-confidence fields tend to be the same ones (e.g. `sample_size` on review papers) — that's the signal you'd act on in production. |

## 5. Real batch submission (beyond the demo)

Demo 4 prints the call shape but doesn't submit. To actually submit:

```python
client = anthropic.Anthropic()
requests = [build_batch_request(cid, doc) for cid, doc in documents.items()]
batch = client.messages.batches.create(requests=requests)
print(batch.id)

# Poll until done:
while True:
    status = client.messages.batches.retrieve(batch.id)
    if status.processing_status == "ended":
        break
    time.sleep(30)

# Stream results:
for entry in client.messages.batches.results(batch.id):
    print(entry.custom_id, entry.result.type)
```

Batches:
- 50% cheaper than synchronous calls
- Up to 24-hour processing window
- Use only for non-urgent batch work

## 6. Troubleshooting

- **`ModuleNotFoundError: pydantic`** — run `pip install -r requirements.txt`.
  Pydantic v2 is required (the schema uses `model_validator`).
- **`ANTHROPIC_API_KEY not set`** — set the env var (step 2).
- **Demo 1 sparse doc DOES fabricate values** — re-read the description
  on each `Field(...)` in `ExtractedPaper`. The "DO NOT guess" wording
  is what nudges the model. If you weaken it, fabrication returns.
- **Demo 2 always succeeds on attempt 1** — that's actually the
  expected outcome with a clean document. To force a retry,
  temporarily tighten a constraint (e.g. `min_length=2` on `authors`)
  and try the sparse doc.
