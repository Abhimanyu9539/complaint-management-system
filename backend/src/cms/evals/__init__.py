"""Evaluation-dataset tooling: build the golden set, and check it is usable.

Three modules, one per stage of `cms-evalset`:

- `corpus`  — the seed corpus materialised as the flat `.md` set deepeval's
  document loader can read. `cases.json` is not a loadable format and policy
  frontmatter would be chunked as content, so both are written out afresh.
- `build`   — one `Synthesizer.generate_goldens_from_docs` call over that set,
  then a grounding gate and a question-quality gate, then `goldens.json`.
- `verify`  — is each golden's own source retrievable for its own question?
  Free, needs Qdrant, and predicts the retriever evals' recall failures.

Nothing here runs at eval time. The dataset is a build artifact that is
generated, reviewed, and committed; `tests/evals/retriever/` consumes it.
"""
