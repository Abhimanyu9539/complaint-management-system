# Retriever Evals

This document tracks evaluation runs for the retriever component (policy chunk retrieval). The run below is the **accepted retriever run** — the current baseline configuration used for retriever evaluation.

# Accepted run: policy-graph-rerank

```Shell
cd backend
uv run python evals/retriever/aggregate.py --leg policy-graph-rerank
```


| Setting                                   | Value                                                           |
| ------------------------------------------- | ----------------------------------------------------------------- |
| Leg                                       | `policy-graph-rerank`                                           |
| Retrieval mode                            | **hybrid** (dense + BM25 sparse, fused by Qdrant RRF) per query |
| Queries per complaint                     | original + 2-3 rewrites from`analyze_query` (max 4)             |
| Candidate pool per query (`policy_top_k`) | 20, unreranked                                                  |
| Merge                                     | dedup by chunk_id, union of all queries (~45 unique chunks)     |
| Final rerank                              | one call, union vs. the original complaint wording              |
| Kept after rerank (`policy_rerank_top_n`) | **12**                                                          |
| Judge                                     | `gpt-5.4-mini`                                                  |
| Goldens                                   | 30 (`evals/datasets/policies.json`)                             |

## Scores

Most recent single run:


| Metric    | Score |
| ----------- | ------- |
| Precision | 0.845 |
| Recall    | 0.935 |

---

# Accepted run: policy-graph-generate

The generation baseline. Same goldens and judge as the retriever leg; scores the draft the
`generate` node writes, not the chunks it was given.

```Shell
cd backend
uv run python evals/generator/aggregate.py --leg policy-graph-generate
```


| Setting          | Value                                               |
| ------------------ | ----------------------------------------------------- |
| Leg              | `policy-graph-generate`                             |
| Retrieval        | `policy-graph-rerank` above, unchanged — 12 chunks |
| Generation model | `openai/gpt-5.4-mini` (`openrouter_model_main`)     |
| Prompt           | `generate/v1`                                       |
| Judge            | `gpt-5.4-mini`                                      |
| Goldens          | 30 (`evals/datasets/policies.json`)                 |
| Cost             | ~$0.52 and ~85s per run                             |

## Scores

Two runs, 2026-09-07. Both are reported because one of the three metrics is not stable enough
to quote from a single run.


| Metric              | Threshold | Run 1             | Run 2             | Run 3        |
| --------------------- | ----------- | ------------------- | ------------------- | -------------- |
| Faithfulness        | 0.80      | **0.995** (30/30) | **0.986** (30/30) | 0.99 (30/30) |
| Answer Relevancy    | 0.70      | 0.932 (30/30)     | 0.844 (24/30)     | 0.93 (28/30) |
| Correctness [GEval] | 0.70      | 0.723 (26/30)     | 0.737 (27/30)     | 0.72 (22/30) |

Citation health (deterministic, no judge): **0 of 30** drafts cited nothing, **0 of 30** cited a
marker that was never offered. Both runs.

## Reading these

- **Faithfulness is the one to trust, and it is high.** The draft says almost nothing the retrieved
  chunks do not support, stable across runs. This is the number that would have justified building
  `check_groundedness`; at 0.99 an inline judge on every request is cost for a failure that barely
  occurs.
- **Answer Relevancy is the noisiest and the least well-matched.** A 0.09 swing and six extra
  failures between identical configurations is outside the ±0.05 band the retriever README
  measured. The likely cause is shape, not quality: the metric penalises output that does not
  directly answer the input, and an agent-facing draft deliberately carries procedural material —
  checks to confirm, what is missing from the complaint — that reads as off-question. Treat it as
  a weak signal until it is either replaced or its criteria narrowed.
- **Correctness is the real headline, and it is the one with room.** ~0.73 with 4 failures, stable
  across runs. The failures share one pattern — see below.

## What the correctness failures show

Four goldens fail, and they fail the same way: **the draft offers a remedy in a situation where
policy says to stop and hand off.**


| Golden         | Score | What went wrong                                                                                                                               |
| ---------------- | ------- | ----------------------------------------------------------------------------------------------------------------------------------------------- |
| `test_case_7`  | 0.20  | Burn injury. Draft authorised immediate refund*and* replacement; policy says support stops offering remedies entirely and only Legal decides. |
| `test_case_6`  | 0.60  | Foreign material in food. Draft promised an immediate full refund on request.                                                                 |
| `test_case_27` | 0.60  | Introduced a 30-day return rule; the expected answer is no customer-facing response at all.                                                   |
| `test_case_28` | 0.50  | Invented operational specifics (chase twice, 3 business days, close after 10 days).                                                           |

Note that faithfulness is ~1.0 on these same cases. **This is not hallucination — it is
precedence.** The retrieved context legitimately contains both the remedy clauses and the safety
or legal override, and the draft blends them instead of letting the override win. `generate/v1`
says only "where two extracts conflict or one overrides another, say which applies and why," which
is too weak to stop it.

The fix is a `generate/v2` with an explicit precedence rule: when an extract routes the case
elsewhere (safety, injury, legal, fraud), that overrides every remedy the other extracts describe,
and no remedy is offered at all. Not yet done — `v1` is the recorded baseline to move against.
