# Evals

Retrieval quality for the **policy** and **case** retrievers, scored with
[deepeval](https://deepeval.com).

```
evals/
├── conftest.py              # truststore, stdout/stderr encoding, telemetry opt-out
├── datasets/
│   ├── policies.json        # 30 goldens
│   └── cases.json           # 30 goldens
└── retriever/
    ├── adapters.py          # each leg -> retrieved chunk texts, in rank order
    ├── aggregate.py         # one leg -> the aggregate table (all 9 legs live here)
    ├── metrics.py           # the shared judge and thresholds
    ├── test_policy_dense.py         test_policy_dense_rerank.py
    ├── test_policy_sparse.py        test_policy_hybrid_rerank.py
    ├── test_policy_hybrid.py
    ├── test_case_dense.py
    ├── test_case_sparse.py
    └── test_case_hybrid.py
```

There is no `generate` node in the graph yet, so retrieval is the last stage that can be
evaluated end to end — and neither metric needs an `actual_output`.

## The metrics


| Metric                      | What it asks                                                    | Threshold |
| ----------------------------- | ----------------------------------------------------------------- | ----------- |
| `ContextualPrecisionMetric` | Are the relevant chunks ranked*above* the irrelevant ones?      | 0.7       |
| `ContextualRecallMetric`    | Does the retrieved set cover everything`expected_output` needs? | 0.7       |

### Precision is a ranking metric, not a noise metric

This one has misled us once, so it is worth stating plainly. `ContextualPrecisionMetric` averages
precision@k **only over the positions holding a relevant chunk** — it is MAP, not "what fraction of
the context is useful."

Two consequences:

- **Irrelevant chunks below the last relevant one are free.** Verified on a real top-20 run:
  deleting the ~4 trailing junk chunks left the score at 0.7831, unchanged to four decimals.
- **The score falls as `top_n` rises, mechanically.** A relevant chunk newly recovered at rank 13
  contributes 7/13 = 0.54 to the average. Those are exactly the chunks that earn the recall, so the
  metric charges you for the recall you gained.

**Never compare precision across different `top_n`.** At a *fixed* chunk count it is a fine signal;
across chunk counts it is close to meaningless. Judge the cost of a bigger context by tokens and by
relevant-chunk density instead.

`ContextualRelevancyMetric` is in `metrics.py` but **commented out**: it penalises every irrelevant
*sentence* inside an otherwise-correct chunk, which over 800-token policy chunks marks correct
retrievals down for boilerplate they cannot avoid carrying. Its threshold constant is left in place
so re-enabling it is a one-line change.

## The legs

`aggregate.py` is the full list; the `test_*.py` files cover the plain legs only.


| Leg                          | What it is                                   |
| ------------------------------ | ---------------------------------------------- |
| `policy-dense`               | semantic only (embeddings, cosine), raw pool |
| `policy-sparse`              | lexical only (local BM25), raw pool          |
| `policy-hybrid`              | both, fused by Qdrant (RRF), raw pool        |
| `policy-dense-rerank`        | dense candidates, reranked to`POLICY_TOP_N`  |
| `policy-hybrid-rerank`       | hybrid candidates, reranked to`POLICY_TOP_N` |
| **`policy-graph-rerank`**    | **the production path — see below**         |
| `case-{dense,sparse,hybrid}` | the same three legs over the case corpus     |

Every leg except `policy-graph-rerank` is driven by the raw `golden.input` — no query rewriting, no
filter — at the `k` its retriever defaults to: **policies 20, cases 4**. That keeps legs comparable
*within* a corpus, which is the comparison the suite exists for. It does not make policy and case
numbers comparable to each other.

The `rerank=` flag is always passed explicitly rather than inherited from `RERANK_ENABLED`, so
flipping that env var cannot quietly turn a baseline into a second copy of the reranked leg.

The two corpora are shaped differently, and it shows:

- **Policies** are 800-token chunks with a breadcrumb prefix, and a golden's `expected_output` cites
  several sections across more than one document. Recall genuinely needs several slots.
- **Cases** are one case per chunk, every point already resolved. A golden narrates exactly one
  prior case, so a single correct hit satisfies it — the suite sits near ceiling and does not
  discriminate much. Treat a pass there as "nothing is broken."

## The production path, and why `policy_rerank_top_n` is 12

2026-09-04, 30 goldens, `gpt-5.4-mini`, two runs per row.

`policy-graph-rerank` is the only leg that scores the **graph** rather than a retriever. It runs
`analyze_query_core` for the real fan-out, then `retrieve_policies_core`:

```
complaint
  ├─ analyze_query        -> original + 2-3 policy-worded rewrites (max 4 queries)
  ├─ hybrid search, k=20 per query, unreranked      -> ~60-80 hits
  ├─ merge_hits                                     -> ~45 unique (dedup)
  ├─ one rerank of the union vs the original wording
  └─ 12 chunks, ~2,400 tokens
```


| `top_n` | Precision | Recall    | Recall ≥ 0.7 | Worst recall | Chunks | ~tokens |
| --------- | ----------- | ----------- | --------------- | -------------- | -------- | --------- |
| 10      | 0.856     | 0.878     | 83%           | 0.43         | 10     | 1,980   |
| **12**  | 0.849     | **0.905** | **88%**       | **0.57**     | **12** | 2,376   |

12 ships. 10 was the first candidate and missed a 0.90 recall bar over two runs. Precision looks
flat between them — see the metric caveat above; that is the expected shape, not evidence of a
tie. The recall *floor* moving 0.43 → 0.57 is the sturdier reason to prefer 12.

Note what the rerank replaces: `merge_hits` sorts by `max` of RRF scores drawn from *different*
searches, which is not a joint ranking. With reranking on, that order is discarded entirely and the
merge is doing dedup and nothing else — which still matters, since it is what keeps the pool under
the reranker's `MAX_DOCUMENTS = 100` and stops us paying to rerank the same chunk three times.

### Single-query legs, for scale

Averaged over the runs in `results/`, so noise is smoothed. `k` is the candidate pool, `n` the
kept count.


| Leg                    | `k` | `n` | Precision | Recall | Chunks |
| ------------------------ | ----- | ----- | ----------- | -------- | -------- |
| `policy-dense`         | 20  | —  | 0.709     | 0.945  | 20     |
| `policy-hybrid`        | 20  | —  | 0.664     | 0.918  | 20     |
| `policy-dense-rerank`  | 60  | 10  | 0.883     | 0.858  | 10     |
| `policy-hybrid-rerank` | 60  | 10  | 0.868     | 0.867  | 10     |
| `policy-dense-rerank`  | 20  | 15  | 0.812     | 0.913  | 15     |
| `policy-dense-rerank`  | 20  | 20  | 0.779     | 0.964  | 20     |

The graph leg reaches 0.905 on 12 chunks; a single query needs 15 for 0.913 and 20 for 0.964. Note
also that a wider *pool* is nearly free — `k=60 → 10` beats `k=20 → 10` on both metrics — but with
the union reranked as one call, `policy_top_k` is capped by `MAX_DOCUMENTS`: at most 4 queries ×
`policy_top_k` may reach the reranker.

The **case** legs have not been re-run since the golden set grew from 10 to 30. Numbers there are
stale; re-run before quoting them.

## Open questions

- **Per-query reranking (variant B).** An archived leg that reranked *each query* to 6 over a `k=60`
  pool, then merged without a cap, scored **0.943 recall at 12.7 chunks** — better than the shipped
  0.905 at the same size, but with no budget guarantee. Reranking per query also collapses the pool
  before the merge, which is what would lift the `MAX_DOCUMENTS` ceiling on `policy_top_k`. The
  untested config: `k=60` → rerank each query to 6 → merge → rerank to 12. Costs 5 rerank calls per
  complaint instead of 1.
- **Is reranking against the original wording self-defeating?** The rewrites exist to reach chunks
  the customer's own phrasing does not match; ranking the union by that phrasing may push exactly
  those back down. An attribution probe — which query found each surviving chunk — would settle it
  with retrieval only, no judge.
- **Widen the case corpus.** 20 seed cases is too few for `k=4` to be interesting.

## Running them

Qdrant must be up and **both** collections populated first, or every score is zero for reasons that
have nothing to do with retrieval quality:

```bash
uv run cms-retrieve "warranty claim for a unit that stopped charging" --corpus policies --json
uv run cms-retrieve "my X200 vacuum stopped charging" --corpus cases --json
```

`aggregate.py` is the usual entry point: it calls `evaluate()`, which prints the **Aggregate
Metrics** panel (average score and pass rate per metric) plus the cost line. One leg per
invocation, same goldens and judge as the test files.

```bash
uv run python evals/retriever/aggregate.py --leg policy-graph-rerank
uv run python evals/retriever/aggregate.py --leg policy-dense-rerank
uv run python evals/retriever/aggregate.py --leg case-dense

# sweep the cap without editing settings
POLICY_RERANK_TOP_N=15 uv run python evals/retriever/aggregate.py --leg policy-graph-rerank
```

Each run writes a timestamped `test_run_<YYYYMMDD_HHMMSS>.json` to `evals/results/<leg>/`
(gitignored, override with `--results-folder`) — unlike `.deepeval/.latest_test_run.json`, which
every run overwrites. That is what makes legs comparable after the fact and stops parallel legs
clobbering each other. Hyperparameters (`leg`, `top_k`, `top_n`, `rerank`, `multi_query`, judge,
golden set) are recorded in each file, so a run stays attributable.

The `test_*.py` files exist for `deepeval test run`, which prints per-golden output:

```bash
uv run deepeval test run evals/retriever/test_policy_hybrid.py --ignore-errors --identifier policy-hybrid
```

To run legs concurrently, give each its own stdout and lower `--max-concurrent`: the judge rate
limit is per account, so six processes at the default means far too many calls in flight.

```powershell
$legs = "policy-dense","policy-sparse","policy-hybrid","case-dense","case-sparse","case-hybrid"
New-Item -ItemType Directory -Force runs | Out-Null
foreach ($leg in $legs) {
  Start-Process -NoNewWindow uv `
    -ArgumentList "run python evals/retriever/aggregate.py --leg $leg --max-concurrent 5" `
    -RedirectStandardOutput "runs/$leg.txt"
}
```

## Worth knowing

- **`uv run pytest` will not run these.** `testpaths = ["tests"]` keeps `evals/` out of the ordinary
  suite, so nobody spends judge tokens on a normal test run. Explicit paths still collect.
- **`--collect-only` is free.** `uv run pytest evals/retriever/ --collect-only -q` reports 240 tests
  (8 suites × 30 goldens) and proves the imports resolve without calling the judge.
- **Judge variance is ±0.05 at n=30.** Same config, four runs, recall came out 0.887 / 0.920 / 0.912
  / 0.935. Treat differences of 0.05 or less as noise and run any real comparison twice.
- **Time is network-bound.** Identical inputs have taken 89s and 224s. Not a performance signal.
- **Read the reasons, not just the scores.** `include_reason=True` is on; the judge's written
  reasons are what tell you *why* a leg missed.
- **`policy-graph-rerank` is async and runs the whole dataset in one event loop.** It has to: the
  embedding client is `lru_cache`d and binds its connection pool to the loop that built it, so a
  second `asyncio.run` doing concurrent embeds dies with "Event loop is closed". `build_contexts`
  branches on `asyncio.iscoroutinefunction`; the sync legs keep their loop-per-golden.
- **The suites live flat in `retriever/`** with no `__init__.py`, so `from adapters import ...`
  resolves via pytest's rootdir insertion. Don't add one, and don't move the tests into subfolders
  without a `sys.path` shim.

## The judge

`gpt-5.4-mini`, pinned in `retriever/metrics.py`, reached **through OpenRouter** — `OpenAIModel`
takes the gateway's `api_key` and `base_url`, so the suite needs no OpenAI key.

The id stays unprefixed on purpose. deepeval looks it up in its model registry with a plain dict
lookup, so `openai/gpt-5.4-mini` would miss and lose the three things the registry buys:
`temperature=1` instead of the `0.0` the gpt-5 reasoning endpoint rejects, native structured outputs
for the verdicts rather than reparsing JSON, and registered prices so the cost line is real.
OpenRouter resolves the bare id to `openai/gpt-5.4-mini` itself.
