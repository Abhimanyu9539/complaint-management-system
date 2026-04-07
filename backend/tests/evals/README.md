# Eval dataset

`.dataset.json` is the golden set for the complaint-drafting pipeline: one entry per question,
with the answer we expect and the corpus text it must be grounded in. It is generated from the
seed corpus by [deepeval](https://deepeval.com)'s golden synthesizer, then committed.

**deepeval is used here as a dataset generator only.** It is not the eval runner and provides no
metrics in this project — `backend/docs/steps.md` Step 6 specifies LangSmith `evaluate()` for
that, and it will read this file.

## Files

| File | What it is | Committed |
| --- | --- | --- |
| `contexts.json` | The corpus slices fed to the generator, built by `cms-evalset export-contexts` | yes |
| `generated.json` | Raw synthesizer output. Overwritten by every generation run | yes |
| `.dataset.json` | **The dataset.** `generated.json` + ground-truth metadata | yes |

All three are committed on purpose. Regenerating costs real OpenAI tokens, and a dataset that
changes should show up as a reviewable diff rather than appearing out of nowhere on someone's
machine.

## Schema

```jsonc
{
  "input": "My X200 stopped charging after three months...",   // the question to send the app
  "expected_output": "Covered under warranty §2.3 — free replacement...",
  "context": ["POLICY warranty-policy.md (warranty) — Product Warranty Policy\n\n..."],
  "source_file": "warranty-policy.md",                         // ground truth: what must be retrieved
  "additional_metadata": {
    "corpus": "policy",                 // "policy" | "case"
    "source_ref": "warranty-policy.md", // policy filename, or case id ("C-1001")
    "expected_department": "warranty",  // null = company-wide policy, not "unknown"
    "title": "Product Warranty Policy"
  }
}
```

`expected_department` and `source_ref` are what make retrieval measurable: routing accuracy is
"did the classifier pick `expected_department`", retrieval hit rate is "was `source_ref` among the
chunks we retrieved". Both are free to compute — no LLM judge needed.

A golden with `source_ref: null` is one whose source header could not be parsed. None are expected;
if you see one, `cms-evalset annotate` logged a WARNING naming it.

## Regenerating

Three steps. Only the middle one costs money.

```bash
cd backend

# 1. Corpus -> contexts.json. Offline and free. --dry-run prints the selection
#    and writes nothing.
uv run cms-evalset export-contexts

# 2. The generation step. A few minutes, real OpenAI spend.
#    The model here is deliberately NOT settings.openai_model_main: this is a
#    dataset-authoring choice, not the app's serving model, and they need not match.
uv run cms-deepeval generate \
  --method contexts --variation single-turn \
  --contexts-file ./tests/evals/contexts.json \
  --max-goldens-per-context 1 \
  --max-concurrent 3 \
  --scenario "Customers of an Indian D2C appliance brand raising complaints by email and chat, and support agents checking what they are allowed to approve before replying" \
  --task "Answer the complaint by grounding the reply in company policy and past resolved cases, stating the remedy, the money involved and the timeline" \
  --input-format "A complaint or an agent question in plain English, mentioning order numbers, products (X200 Cordless Vacuum, AV-450, ProBlend 300, SmartHub Pro), payment methods (UPI, card, COD) and Rupee amounts where relevant" \
  --expected-output-format "A grounded answer that cites the governing clause (for example 'warranty 2.3') and states Rupee amounts and turnaround times exactly as the policy defines them" \
  --model gpt-4.1-mini --cost-tracking \
  --output-dir ./tests/evals --file-name generated

# 3. generated.json -> .dataset.json, attaching ground truth. Offline and free.
uv run cms-evalset annotate
```

Then read a handful of the new goldens before committing. See "Reviewing a run" below.

### Four things that will bite you

- **`cms-deepeval`, not `deepeval`.** The plain CLI is a separate process, so it never imports
  `cms.config` and never gets the truststore injection. Behind this machine's TLS-intercepting
  proxy every OpenAI call then dies with `CERTIFICATE_VERIFY_FAILED`. `cms-deepeval` is deepeval's
  own Typer app with that bootstrap applied and `OPENAI_API_KEY` loaded from `.env` — same flags,
  same help, same exit codes.
- **`--file-name` must not contain a dot.** deepeval's `save_as` rejects any period in the name, so
  it cannot write `.dataset.json` itself. That is why step 2 writes `generated` and step 3 produces
  the dotted final name.
- **`--num-goldens` does nothing here.** It only applies to `--method scratch`. The count is
  `contexts × --max-goldens-per-context`, so the size is set by `cms-evalset export-contexts
  --policies N --cases N` (default 26 + 14 = 40).
- **Rate limits will kill the run, and you pay for it anyway.** Nothing is written to disk until
  the whole run finishes, so a 429 storm at golden 38 costs you all 37 before it. deepeval retries
  a 429 only ~4 times before the run dies with `RetryError[... RateLimitError]`. Two settings keep
  it alive on a low tier:
  - `--max-concurrent 3` (deepeval defaults to **100**, which is hopeless at 30k TPM)
  - `--model gpt-4.1-mini` rather than `gpt-4.1`. This is the one that actually matters — on this
    account `gpt-4.1` is capped at 30,000 TPM, and each context is ~2,400 tokens before evolution
    and expected-output generation multiply it. Both `gpt-4.1` attempts died on 429s at
    concurrency 100 *and* 3; `gpt-4.1-mini` ran the full 40 without a single retry.

## Why `--method contexts` and not `--method docs`

The 34 policies are markdown and deepeval can load markdown, so `--method docs` looks like the
natural fit. It is the wrong choice here for two reasons:

1. **The chunks would not exist.** deepeval re-chunks with its own `TokenTextSplitter` at 1024
   tokens / 0 overlap. This project indexes policies header-aware at 800/100 (`chunk_policy`). A
   golden written against a 1024-token slice corresponds to no Qdrant point, which makes it a poor
   ruler for the retrieval it is supposed to measure. Going through `contexts.json` means every
   golden is grounded in text the retriever can actually return.
2. **It needs chromadb.** The document path pulls chromadb + onnxruntime purely to re-embed a
   corpus that is already embedded in Qdrant.

`cases.json` settles it anyway — it is not a document deepeval can load, so the cases half of the
corpus needs the contexts route regardless.

## How the source header works

`--method contexts` has no `source_files` parameter, so a generated golden comes back with
`source_file: null` and no way home. `cms-evalset export-contexts` therefore writes the identity
into the first line of each context:

```
POLICY warranty-policy.md (warranty) — Product Warranty Policy
CASE C-1001 (warranty) — faulty_product
```

`cms-evalset annotate` parses that line back into `additional_metadata`. The header earns its
place twice: it is the ground-truth link, and it tells the generator which department and document
it is writing about, which is what keeps a §-citation in the expected output honest.

`(company-wide)` is how a policy with no `department` in its frontmatter is written; it round-trips
back to `expected_department: null`. That is 16 of the 34 policies, and null there means "applies
to every department", never "unknown".

## Selection

40 of the 54 seed documents, chosen round-robin across departments so every department gets a
golden before any department gets a second one — taking the first N of a sorted list would spend
the whole budget in the alphabetically early departments. The selection is deterministic: the same
corpus always yields the same 40, so a regenerated dataset diffs as changed content rather than a
reshuffle.

Policies and cases are stratified separately (26 + 14). A shared budget would let the 34 policies
crowd out the 20 cases, and the two corpora answer different questions — "what is the rule?" versus
"what did we do last time?".

Each policy context carries up to 3 chunks sampled *evenly across* the document rather than the
first 3: every policy opens with scope and definitions, so taking the head of each would produce 26
near-identical "what does this policy cover?" goldens. Each case context is a single chunk, because
`chunk_case` is identity by design — a resolved complaint is semantically atomic.

## Reviewing a run

Generated goldens are not automatically good. Before committing a regenerated dataset:

```bash
# Size and coverage
uv run python -c "import json,collections; g=json.load(open('tests/evals/.dataset.json',encoding='utf-8')); print(len(g),'goldens'); print(collections.Counter(x['additional_metadata']['corpus'] for x in g)); print(sorted({str(x['additional_metadata']['expected_department']) for x in g}))"

# Is the source actually retrievable? This is the point of the dataset.
uv run cms-retrieve "<paste a golden input>" --json
```

Then read about five inputs by hand. Reject the run if they read as corpus trivia ("what does §2.3
say?") rather than complaints a customer would plausibly send — that means the styling flags need
tightening, and it is much cheaper to catch here than after a metric is built on top of it.

## The committed run

Generated 2026-08-20 with `gpt-4.1-mini`, `--max-concurrent 3`. Cost **$0.081**, ~2.5 minutes,
zero rate-limit retries.

- **40 goldens** — 26 policy, 14 case
- **40 distinct `source_ref`s** — no document is asked about twice
- **13 department strata** — all 12 departments, plus 8 goldens on company-wide policies
- **0** goldens with an unresolved source or a missing `expected_output`
- Ground truth was retrievable in the top-k for **8 of 8** spot-checked goldens, using the same
  `retrieve()` the app calls — so a retrieval metric built on this dataset starts from a corpus
  it can actually find.
