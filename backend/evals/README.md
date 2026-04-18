# Evals

Retrieval quality for the **policy** retriever, scored with [deepeval](https://deepeval.com).

```
evals/
├── conftest.py              # truststore + OPENAI_API_KEY, applies to every suite here
├── datasets/
│   ├── policies.json        # the golden set (2 goldens)
│   └── cases.json           # moved into place; no suite reads it yet
└── retriever/
    ├── adapters.py          # each leg -> retrieved chunk texts, in rank order
    ├── metrics.py           # the shared judge and thresholds
    ├── test_dense.py
    ├── test_sparse.py
    └── test_hybrid.py
```

There is no `generate` node in the graph yet, so retrieval is the only stage that can be
evaluated end to end today — and none of the three metrics need an `actual_output`.

## The metrics

| Metric                        | What it asks                                                      | Threshold |
| ----------------------------- | ----------------------------------------------------------------- | --------- |
| `ContextualPrecisionMetric` | Are the relevant chunks ranked*above* the irrelevant ones?      | 0.7       |
| `ContextualRecallMetric`    | Does the retrieved set cover everything`expected_output` needs? | 0.7       |
| `ContextualRelevancyMetric` | How much of what came back is actually on topic?                  | 0.5       |

Relevancy sits lower on purpose: it penalises every irrelevant *sentence* inside an
otherwise-correct chunk, and `chunk_policy` cuts policies at 800 tokens. A 0.7 bar there would
fail retrievals that are in fact correct.

## Three files, three legs

One file per leg, because the comparison *is* the result:

- `test_dense.py` — the semantic leg alone (OpenAI embeddings, cosine)
- `test_sparse.py` — the lexical leg alone (local BM25, exact terms)
- `test_hybrid.py` — what production uses: both legs, fused by Qdrant (RRF)

All three are driven by the raw `golden.input` — no query rewriting, no department filter — and
all three take the same `k` from `policy_retriever.DEFAULT_K`, which is what makes the numbers
comparable. If hybrid is not beating `max(dense, sparse)` on recall, RRF is not earning its keep.

## Running them

Qdrant must be up and the policies collection populated first, or every score is zero for
reasons that have nothing to do with retrieval quality:

```bash
uv run cms-retrieve "warranty claim for a unit that stopped charging" --json
```

Then, from `backend/`:

```bash
uv run deepeval test run evals/retriever/test_dense.py  --ignore-errors --identifier policy-dense-round-1
uv run deepeval test run evals/retriever/test_sparse.py --ignore-errors --identifier policy-sparse-round-1
uv run deepeval test run evals/retriever/test_hybrid.py --ignore-errors --identifier policy-hybrid-round-1
```

Worth knowing:

- **`uv run pytest` will not run these.** `testpaths = ["tests"]` keeps `evals/` out of the
  ordinary suite, so nobody spends judge tokens on a normal test run. Explicit paths still collect.
- **Budget scales with the dataset.** Three LLM-judged metrics per golden. The cost is printed at
  the end of every run.
- **Read the reasons, not just the scores.** `include_reason=True` is on, and with two goldens the
  numbers are anecdotes — the judge's written reasons are the signal.
- **Add `--num-processes 4`** once the dataset is big enough to be worth it.

## The judge

`gpt-5.4-mini`, pinned in `retriever/metrics.py`. deepeval has that id in its model registry,
which buys three things a newer or dated id would not: it forces `temperature=1` instead of the
`0.0` the gpt-5 reasoning endpoint rejects, it uses native structured outputs for the verdicts
rather than reparsing JSON, and its prices are registered so the cost line is real.

## The baseline run

2026-08-27, `gpt-5.4-mini`, `k=4`, 2 goldens per leg. ~$0.03 and ~25s per leg.

| Leg    | Precision      | Recall         | Relevancy      | Passed |
| ------ | -------------- | -------------- | -------------- | ------ |
| dense  | **1.00** | **0.72** | **0.73** | 1/2    |
| sparse | 0.67           | 0.35           | 0.38           | 0/2    |
| hybrid | 0.75           | 0.72           | 0.53           | 1/2    |

**Dense beats hybrid on every metric.** Hybrid matches dense on recall but loses precision and
relevancy, which is what it looks like when RRF pulls sparse's noise into the top 4 without
adding anything dense missed. Sparse alone is weak — the goldens are paraphrased customer
complaints, so there is little exact-term overlap for BM25 to work with.

Two caveats before acting on this:

- **Two goldens is an anecdote, not a measurement.** Re-running dense gave 2/2 once and 1/2 the
  next time with no code change — that is judge variance on a sample this small.
- **Recall is capped by `k=4`.** Every failure was recall: the goldens' `expected_output` cites
  ~5 policy sections across 2 documents, and at 800-token chunks four slots cannot always hold
  them. Re-run at a larger `k` before concluding the ranking is at fault.

The obvious next steps are widening the dataset (34 policy docs are sitting in
`data/seed/policies/`, and `deepeval generate --method docs` is the documented path) and sweeping
`k` — in that order.
