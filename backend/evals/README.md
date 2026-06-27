# Evals

Two suites, scored with [deepeval](https://deepeval.com): **retrieval** quality for the policy and
case retrievers, and **generation** quality for the draft the `generate` node writes.

```
evals/
├── conftest.py              # truststore, stdout/stderr encoding, telemetry opt-out
├── datasets/
│   ├── policies.json        # 30 goldens — used by BOTH suites
│   ├── cases.json           # 30 goldens
│   └── tickets.json         # policies.json + the departments each golden may route to
├── analyzer/
│   ├── test_intent_routing.py   # chat: complaint vs knowledge lookup
│   └── test_ticket_routing.py   # tickets: which department owns the complaint
├── retriever/
│   ├── adapters.py          # each leg -> retrieved chunk texts, in rank order
│   ├── aggregate.py         # one leg -> the aggregate table (all 9 legs live here)
│   ├── metrics.py           # the shared judge and thresholds
│   ├── test_policy_dense.py         test_policy_dense_rerank.py
│   ├── test_policy_sparse.py        test_policy_hybrid_rerank.py
│   ├── test_policy_hybrid.py
│   ├── test_case_dense.py
│   ├── test_case_sparse.py
│   └── test_case_hybrid.py
└── generator/
    ├── adapters.py          # one golden -> (what the model saw, what it wrote)
    ├── aggregate.py         # the --leg entry point
    └── metrics.py           # judge + the three generation thresholds
```

The retriever metrics need no `actual_output` — nothing generates an answer on those legs. The
generator suite is the one that does, and it reuses the same `policies.json` goldens: their
`expected_output` was written as agent-facing policy guidance, which is exactly what `generate`
produces.

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

## The generation suite

One leg, `policy-graph-generate`: the real complaint branch end to end — `analyze_query_core` →
`retrieve_policies_core` → `generate_core`. The scores describe what ships.

| Metric                | What it asks                                              | Threshold |
| --------------------- | --------------------------------------------------------- | --------- |
| `FaithfulnessMetric`  | Is every claim supported by the chunks the model was given? | 0.8       |
| `AnswerRelevancyMetric` | Does the draft address the complaint?                     | 0.7       |
| `GEval` "Correctness" | Does it reach the reference's policy conclusions?           | 0.7       |

Faithfulness sits higher than the rest because an invented entitlement is the failure that
actually costs something, and the one a support agent is least able to catch.

Correctness is a `GEval` rather than a predefined metric because "correct" here is domain-specific:
the same coverage decision, the same remedy, the same checks — and explicitly *not* penalised for
different wording, ordering or length. The goldens are written in one particular voice and a draft
must not lose points for choosing another.

```bash
uv run python evals/generator/aggregate.py --leg policy-graph-generate
```

### Three things worth knowing before reading a score

- **`retrieval_context` is what the model actually saw**, not the raw hits. `build_context` stops
  at `generation_context_tokens`, so a hit past the cut never reached the model and must not count
  against faithfulness. `adapters.py` slices `hits[:len(offered)]` for this.
- **There is no `test_*.py` here, on purpose.** Like `policy-graph-rerank`, this leg is async and
  must run the whole dataset in one event loop — the cached embedding client binds its pool to the
  loop that made it, so a pytest file doing one `asyncio.run` per golden dies partway through with
  "Event loop is closed". `aggregate.py` is the entry point, and it prints per-case results as well
  as the aggregate.
- **A run costs ~$0.52 and ~85s**, materially more than a retriever leg — every golden pays for a
  generation call on top of the retrieval fan-out.

### Citation health — free, no judge

`aggregate.py` prints one line before the metrics: how many drafts cited nothing, and how many
cited a marker that was never offered. Both are computed from the draft text against
`retrieval_context`, so they cost nothing once generation has run, and they catch the two failures
a judge is overkill for. `used_citations` in `cms/rag/context.py` warns about each individually;
this is the per-run total.

At `generate/v1` both are **0 of 30**.

## Ticket graph

Two checks on the graph that drafts the customer reply. Both use `tickets.json`: the 30
`policies.json` complaints with the same `expected_output`, plus
`additional_metadata.expected_departments`, the one or two departments a golden may route to.
18 labels come from the department of the golden's source policy, the other 12 (company-wide
policies) from the routing rules in `complaint-intake-policy.md` §4–§6.

```bash
uv run pytest evals/analyzer/test_ticket_routing.py -s                 # ~30 cheap-model calls
uv run python evals/generator/aggregate.py --leg ticket-graph          # ~$0.6–1
```

- **Routing** runs `classify_ticket_core` once per golden and prints a per-golden table, top-1
  and top-2 accuracy, mean confidence when right and when wrong, and how many fall below
  `routing_confidence_floor`. It fails below `ROUTING_ACCURACY_FLOOR` (0.80).
- **`ticket-graph`** runs the compiled ticket graph (it computes and writes nothing) and scores the
  draft with the generation metrics above. Next to citation health it prints a gate line: drafts
  that passed the output guard first time, after a retry, still ungrounded, holding replies,
  inputs blocked, and tickets where a node failed.
- **Read Correctness as "reaches the same remedy".** The draft is a letter to the customer and the
  references are agent-facing policy notes, so wording and detail differ by design.

### Baseline (seed cases only, before any flywheel case is minted)

2026-10-03, `classify_ticket/v2` on `gpt-5.4-nano`, `customer_reply/v2`.

| Check | Result |
| --- | --- |
| Routing top-1 | **26/30 (0.87)** |
| Routing top-2 | 29/30 (0.97) |
| Mean confidence, right / wrong | 0.72 / 0.60 |
| Below the 0.60 floor | 9/30 |
| `ticket-graph` Faithfulness | **0.98**, 30/30 pass |
| `ticket-graph` Answer Relevancy | **0.82**, 21/30 pass |
| `ticket-graph` Correctness | **0.69**, 24/30 pass |
| Gate | 30/30 passed the guard first time; 0 retries, 0 holding replies |
| Citation health | 0 citing nothing, 0 citing a marker never offered |

The four routing misses are all company-wide-policy goldens: an account takeover and a carer's
access request went to `legal`, an order we cancelled to `returns`, and a complaint about an
AI-written reply to `sales`.

The `ticket-graph` run (judge `gpt-5.4-mini`, `--max-concurrent 5`) cost $0.45 in judge tokens.

- **Relevancy misses (9)**: the judge marks down process wording the customer did not ask for. The
  data-protection request (0.36) is handed to Legal as policy requires, which the judge reads as
  not answering; the missing parcel (0.33) gets a carrier claim, but explained in procedure.
- **Correctness misses (6)** are omitted entitlements or a wrong coverage call: app pairing (0.40)
  leaves out the goodwill gesture and the two-round troubleshooting limit, the helpline complaint
  (0.40) the statutory 48-hour and one-month timelines, and the manager request (0.30) promises a
  review instead of the reference's "a demand alone is not a reason to refer".
- At the default `--max-concurrent 10` the judge hit OpenRouter's 402 (`in_flight_budget_exhausted`)
  on a small balance; 5 finished cleanly.

These are the numbers a flywheel case has to improve on: re-run the leg once minted cases are in
the corpus and compare.

### `gpt-6-luna` for both the main and cheap models

2026-10-03, same prompts, corpus and judge (`gpt-5.4-mini`). `nemo_rails_enabled` is off, so no
guard judge ran. Two `ticket-graph` runs per side, `--max-concurrent 5`.

| Check | `gpt-5.4-mini` + `nano` | `gpt-6-luna` |
| --- | --- | --- |
| Routing top-1 / top-2 | 26/30 / 29/30 | 27/30 / 30/30 |
| Faithfulness | 0.98, 0.97 (30, 30 pass) | 0.95, 0.98 (29, 30 pass) |
| Answer Relevancy | 0.82, 0.86 (21, 25 pass) | 0.74, 0.82 (16, 22 pass) |
| Correctness | 0.69, 0.72 (24, 26 pass) | 0.76, 0.74 (26, 27 pass) |
| Gate / citation health | 30/30 first time; 0 / 0 | 30/30 first time; 0 / 0 |

- Even within judge noise: Luna is ~0.06 lower on relevancy and ~0.05 higher on correctness, at
  $0.10 / $0.50 per 1M tokens against mini's $0.75 / $4.50 and nano's $0.20 / $1.25.
- Per-golden relevancy swings both ways between runs (app pairing 1.00 → 0.38, overheating battery
  0.60 → 1.00), so read the averages, not single goldens.
- **Gift card (golden 26)**: both Luna runs asked the customer to reply with the gift card number;
  neither mini run did. The judge marked it against the privacy policy's "full card numbers" rule,
  which is written for payment cards, so whether it applies to gift cards is a policy call.

The policy graph against the September `gpt-5.4-mini` runs (rerank: the 7 runs at `top_n=12`;
generate: 3 runs). Luna ran generate on `GENERATE_PROMPT_VERSION=v1` to match them, so it saw the
same 12 policy chunks and no cases.

| Leg | Metric | `gpt-5.4-mini` (mean, range) | `gpt-6-luna` |
| --- | --- | --- | --- |
| `policy-graph-rerank` | Precision | 0.832 (0.805–0.855) | 0.847, 0.830 |
| | Recall | 0.912 (0.882–0.935) | 0.933, 0.955 |
| `policy-graph-generate` | Faithfulness | 0.989 (0.985–0.995), 30/30 | 0.974, 29/30 |
| | Answer Relevancy | 0.902 (0.844–0.932) | 0.860 |
| | Correctness | 0.726 (0.717–0.737) | 0.733 |

- Rerank recall sits at the top of mini's range with both Luna runs. The `analyze_query` prompt
  version of the September runs is not recorded, so part of that may be the prompt.
- Generate is one Luna run: the second stopped on OpenRouter's 402 (`in_flight_budget_exhausted`).
  The faithfulness miss is the bereavement golden, which skipped the one required retention offer.

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

### Case legs

2026-09-14, 30 goldens, `gpt-5.4-mini`. `k=4`, no rerank. The `retrieve_cases` graph node calls
`retrieve_cases_hybrid` with the original query, so `case-hybrid` *is* the graph path.

| Leg           | `k` | Runs | Precision | Recall | Recall (24 with a precedent) |
| ------------- | --- | ---- | --------- | ------ | ---------------------------- |
| `case-dense`  | 4   | 1    | 0.847     | 0.590  | 0.705                        |
| `case-hybrid` | 4   | 2    | 0.722     | 0.620  | 0.728                        |
| `case-sparse` | 4   | 0    | —         | —      | —                            |

- **6 of the 30 goldens are "no precedent" by design.** Their `expected_output` says the corpus holds
  no matching case. ContextualRecall cannot attribute that sentence to any retrieved chunk, so these
  goldens score ~0.15 whatever the retriever does. The last column leaves them out.
- This is well below the "near ceiling" described above, which predates the 30-golden set.
- `case-hybrid` precision moved 0.785 → 0.658 between its two runs. Treat a gap between dense and
  hybrid that small as noise until more runs are in.
- `case-sparse` has not been run on 30 goldens yet: the run stopped on an OpenRouter 402
  (`in_flight_budget_exhausted`).

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
