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
