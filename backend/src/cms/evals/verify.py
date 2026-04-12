"""Check that each golden's own source is retrievable for its own question.

The dataset exists to measure retrieval, so a golden whose source document the
retriever cannot find is a broken ruler: the retriever evals will score it as a
failure no matter how good retrieval is. This is the cheapest possible check —
no LLM judge, no tokens, just the production `retrieve()` — and it predicts the
`ContextualRecall` failures directly.

Separate from `build` on purpose. Generation costs real money and only needs
OpenAI; this needs Qdrant up and both collections populated. Coupling them would
mean a Qdrant outage wasting a paid synthesis run.

**How a retrieved chunk is recognised as the golden's source.** `source_ref` is
a Postgres column and never reaches the vector store, so the match is on
`title`, which the ingest path does write to the payload and which is identical
on both sides by construction: a policy's frontmatter title (`register_seed_policy`
and `SourceDoc` both read `meta["title"]`), or `case_title`'s
``"C-1001 — warranty / faulty_product"``.
"""

import json
import logging
from dataclasses import dataclass
from pathlib import Path

from cms.retrieval.retrievers.hybrid_retriever import retrieve

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class VerifyRow:
    """One golden's retrievability, as a rank into what `retrieve()` returned."""

    source_ref: str | None
    corpus: str | None
    title: str | None
    input: str
    rank: int | None  # 1-based position in the fused result; None = not found
    retrieved: int

    @property
    def found(self) -> bool:
        return self.rank is not None


@dataclass
class VerifyResult:
    rows: list[VerifyRow]

    @property
    def found(self) -> list[VerifyRow]:
        return [row for row in self.rows if row.found]

    @property
    def missing(self) -> list[VerifyRow]:
        return [row for row in self.rows if not row.found]

    def summary(self) -> str:
        total = len(self.rows)
        found = self.found
        rate = (len(found) / total * 100) if total else 0.0
        lines = [f"{len(found)}/{total} golden(s) found their own source ({rate:.0f}%)"]
        if found:
            ranks = sorted(row.rank for row in found)
            mean = sum(ranks) / len(ranks)
            lines.append(f"  rank of first hit: mean {mean:.1f}, worst {ranks[-1]}")
        for row in self.missing:
            lines.append(f"  NOT retrievable: {row.source_ref} — {row.input[:70]!r}")
        return "\n".join(lines)


def _rank_of_source(golden: dict) -> VerifyRow:
    metadata = golden.get("additional_metadata") or {}
    title = metadata.get("title")
    corpus = metadata.get("corpus")
    query = golden.get("input") or ""

    chunks = retrieve(query).chunks
    rank = next(
        (
            position
            for position, chunk in enumerate(chunks, start=1)
            if chunk.title == title and chunk.corpus == corpus
        ),
        None,
    )
    return VerifyRow(
        source_ref=metadata.get("source_ref"),
        corpus=corpus,
        title=title,
        input=query,
        rank=rank,
        retrieved=len(chunks),
    )


def verify_goldens(goldens_path: Path) -> VerifyResult:
    """Run every golden's input through `retrieve()` and locate its own source."""
    try:
        goldens = json.loads(goldens_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read goldens from %s", goldens_path)
        raise

    if not isinstance(goldens, list) or not goldens:
        raise ValueError(f"No goldens found in {goldens_path}")

    rows: list[VerifyRow] = []
    for golden in goldens:
        # One unreachable Qdrant call should not discard the rows already
        # checked — this is a report, and a partial report is still useful.
        try:
            rows.append(_rank_of_source(golden))
        except Exception:
            logger.exception(
                "Retrieval failed for %r", (golden.get("input") or "")[:80]
            )
            raise

    result = VerifyResult(rows=rows)
    logger.info(
        "Verified %d golden(s); %d found their own source",
        len(rows),
        len(result.found),
    )
    return result
