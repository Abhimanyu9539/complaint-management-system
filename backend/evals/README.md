# Evals

Retrieval quality for the **policy** and **case** retrievers, scored with
[deepeval](https://deepeval.com).

```
evals/
├── conftest.py              # truststore + OPENAI_API_KEY, applies to every suite here
├── datasets/
│   ├── policies.json        # 10 goldens
│   └── cases.json           # 10 goldens
└── retriever/
    ├── adapters.py          # each leg -> retrieved chunk texts, in rank order
    ├── metrics.py           # the shared judge and thresholds
    ├── test_policy_dense.py
    ├── test_policy_sparse.py
    ├── test_policy_hybrid.py
    ├── test_case_dense.py
    ├── test_case_sparse.py
    └── test_case_hybrid.py
```

There is no `generate` node in the graph yet, so retrieval is the only stage that can be
evaluated end to end today — and neither metric needs an `actual_output`.

## The metrics

| Metric                        | What it asks                                                      | Threshold |
| ----------------------------- | ----------------------------------------------------------------- | --------- |
| `ContextualPrecisionMetric` | Are the relevant chunks ranked*above* the irrelevant ones?      | 0.7       |
| `ContextualRecallMetric`    | Does the retrieved set cover everything`expected_output` needs? | 0.7       |

`ContextualRelevancyMetric` is present in `metrics.py` but **commented out**. It penalises every
irrelevant *sentence* inside an otherwise-correct chunk, which at `k=10` over 800-token policy
chunks marks correct retrievals down for the surrounding boilerplate they inevitably carry. Its
threshold constant is left in place so re-enabling it is a one-line change.

## Six files, two corpora, three legs each

One file per leg, because the comparison *is* the result:

- `test_*_dense.py` — the semantic leg alone (OpenAI embeddings, cosine)
- `test_*_sparse.py` — the lexical leg alone (local BM25, exact terms)
- `test_*_hybrid.py` — what production uses: both legs, fused by Qdrant (RRF)

All six are driven by the raw `golden.input` — no query rewriting, no filter — and each takes the
`k` its own retriever defaults to: **policies at `DEFAULT_K = 10`, cases at `DEFAULT_K = 4`**.
That keeps the three legs comparable *within* a corpus, which is the comparison the suite exists
for. It does not make policy and case numbers comparable to each other; they are different tasks
at different k. If hybrid is not beating `max(dense, sparse)` on recall, RRF is not earning its keep.

The two corpora are shaped differently, and it shows in the scores:

- **Policies** are split by `chunk_policy` into 800-token chunks with a breadcrumb prefix, and a
  golden's `expected_output` cites several sections across more than one document. Recall genuinely
  needs several slots.
- **Cases** are one case per chunk (`chunk_case` returns `[text]`) with no `lifecycle` filter —
  every point in the collection is already a resolved case. A golden's `expected_output` narrates
  exactly one prior case, so a single correct hit satisfies it.

## Running them

Qdrant must be up and **both** collections populated first, or every score is zero for reasons
that have nothing to do with retrieval quality:

```bash
uv run cms-retrieve "warranty claim for a unit that stopped charging" --corpus policies --json
uv run cms-retrieve "my X200 vacuum stopped charging" --corpus cases --json
```

Then, from `backend/`:



```bash
uv run deepeval test run evals/retriever/test_policy_dense.py  --ignore-errors --identifier policy-dense-k10
uv run deepeval test run evals/retriever/test_policy_sparse.py --ignore-errors --identifier policy-sparse-k10
uv run deepeval test run evals/retriever/test_policy_hybrid.py --ignore-errors --identifier policy-hybrid-k10

uv run deepeval test run evals/retriever/test_case_dense.py  --ignore-errors --identifier case-dense-k4
uv run deepeval test run evals/retriever/test_case_sparse.py --ignore-errors --identifier case-sparse-k4
uv run deepeval test run evals/retriever/test_case_hybrid.py --ignore-errors --identifier case-hybrid-k4
```



### Aggregate scores only

`deepeval test run` builds its table in the CLI process *after* pytest returns, so running the
test files under plain `pytest` prints per-golden results and no summary. `retriever/aggregate.py`
takes the other path — `evaluate()`, which wraps up its own run and prints the **Aggregate
Metrics** panel (average score and pass rate per metric) plus the cost line:

```bash
uv run python evals/retriever/aggregate.py --leg policy-hybrid
uv run python evals/retriever/aggregate.py --leg case-dense
```

Same goldens, same adapters, same judge as the six test files — one leg per invocation. It logs
the leg, `top_k`, judge and golden set as hyperparameters, so runs stay attributable.

Each run also writes a timestamped `test_run_<YYYYMMDD_HHMMSS>.json` to
`evals/results/<leg>/` (gitignored, override with `--results-folder`) — unlike
`.deepeval/.latest_test_run.json`, which every run overwrites. That is what makes legs
comparable after the fact, and what stops parallel legs from clobbering each other.

To run legs concurrently, give each its own stdout and lower `--max-concurrent`: the OpenAI rate
limit is per account, so six processes at the default 20 means 120 judge calls in flight.

```powershell
$legs = "policy-dense","policy-sparse","policy-hybrid","case-dense","case-sparse","case-hybrid"
New-Item -ItemType Directory -Force runs | Out-Null
foreach ($leg in $legs) {
  Start-Process -NoNewWindow uv `
    -ArgumentList "run python evals/retriever/aggregate.py --leg $leg --max-concurrent 5" `
    -RedirectStandardOutput "runs/$leg.txt"
}
```

Worth knowing:

- **`uv run pytest` will not run these.** `testpaths = ["tests"]` keeps `evals/` out of the
  ordinary suite, so nobody spends judge tokens on a normal test run. Explicit paths still collect.
- **`--collect-only` is free.** `uv run pytest evals/retriever/ --collect-only -q` should report
  60 tests (6 suites × 10 goldens) and proves the imports resolve without calling the judge.
- **Budget scales with the dataset.** Two LLM-judged metrics per golden. The cost is printed at
  the end of every run.
- **Read the reasons, not just the scores.** `include_reason=True` is on — the judge's written
  reasons are what tell you *why* a leg missed.
- **Only the most recent run survives on disk.** `.deepeval/.latest_test_run.json` is overwritten
  each time; copy it aside if you want to compare legs numerically.
- **Add `--num-processes 4`** once the dataset is big enough to be worth it.
- All six suites live flat in `retriever/` with no `__init__.py`, so `from adapters import ...`
  resolves via pytest's rootdir insertion. Don't add one, and don't move the tests into subfolders
  without adding a `sys.path` shim.

## The judge

`gpt-5.4-mini`, pinned in `retriever/metrics.py`. deepeval has that id in its model registry,
which buys three things a newer or dated id would not: it forces `temperature=1` instead of the
`0.0` the gpt-5 reasoning endpoint rejects, it uses native structured outputs for the verdicts
rather than reparsing JSON, and its prices are registered so the cost line is real.

## The baseline run

2026-08-28, `gpt-5.4-mini`, 10 goldens per leg, precision + recall only.

### Policies, `k=10`

| Leg    | Precision      | Recall         | Passed | Cost   | Time |
| ------ | -------------- | -------------- | ------ | ------ | ---- |
| dense  | **0.81** | **0.90** | 7/10   | $0.102 | 140s |
| sparse | 0.75           | 0.75           | 3/10   | $0.108 | 84s  |
| hybrid | 0.80           | 0.88           | 6/10   | $0.102 | 238s |

Dense edges hybrid on both means, but the pass counts tell a different story than the means do:
**hybrid is the only leg where all 10 goldens clear the 0.7 recall bar** (dense drops one below
it). Hybrid loses on the mean and wins on the floor — which is the trade RRF is supposed to make,
and the more useful property for a retriever feeding a generate step. Sparse alone is weak, as
expected: the goldens are paraphrased customer complaints, so there is little exact-term overlap
for BM25 to work with.

### Cases, `k=4`

| Leg    | Precision      | Recall         | Passed | Cost   | Time |
| ------ | -------------- | -------------- | ------ | ------ | ---- |
| dense  | **1.00** | **1.00** | 10/10  | $0.061 | 224s |
| sparse | **1.00** | **1.00** | 10/10  | $0.062 | 73s  |
| hybrid | **1.00** | 0.97           | 9/10   | $0.062 | 107s |

**This suite is at ceiling and is not currently discriminating.** With 20 seed cases, one case per
chunk, `k=4`, and a golden whose `expected_output` narrates exactly one of them, all three legs
find the target — including BM25, because the goldens reuse the cases' product names and order
context verbatim. Treat 10/10 as "nothing is broken", not as evidence that the ranking is good.

The single miss is worth noting anyway: hybrid scored 0.67 recall on the lost-package golden where
**both dense and sparse scored 1.00**. RRF fused two correct rankings into a worse one and pushed
the target case out of the top 4. On this corpus hybrid is strictly the worst of the three.

Caveats before acting on any of this:

- **Judge variance is real at n=10.** The case-dense leg was re-run during this session and gave
  10/10 both times, but the earlier 2-golden policy baseline flipped between 2/2 and 1/2 with no
  code change. Treat single-point differences of 0.05 or less as noise.
- **Time is network-bound, not work-bound.** Dense took 89s on one run and 224s on the next with
  identical inputs. Don't read the timing column as a performance signal.

Next steps, in order: widen the case corpus (20 cases is too few for `k=4` to be interesting) and
widen the policy goldens (34 policy docs sit in `data/seed/policies/`, and
`deepeval generate --method docs` is the documented path); then sweep `k` on policies, where recall
is actually the binding constraint; then decide whether hybrid's better recall floor is worth its
worse mean.
