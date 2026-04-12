"""Materialise the seed corpus as the flat document set deepeval can load.

`generate_goldens_from_docs` reads files off disk through LangChain loaders, and
`doc_chunker.get_loader` accepts only `.pdf`, `.txt`, `.docx`, `.md`, `.markdown`
and `.mdx`. Two consequences follow, and together they are the whole reason this
module exists:

- **`cases.json` is not a loadable format.** Each case is written out as its own
  `C-1001.md` using `build_case_text` — the exact text `ingest_case` embedded
  into Qdrant, so a golden written against it is grounded in text the retriever
  can actually return.
- **Policy frontmatter would be chunked as content.** Left in, the generator
  writes goldens about `version:` and `effective_date:`. `read_policy_file`
  already splits metadata from body; only the body is written out.

Putting both corpora in one directory is what lets the whole dataset come out of
a *single* `generate_goldens_from_docs` call instead of one call per corpus
stitched together afterwards.

The returned index is keyed by the materialised filename because that is what
comes back on `golden.source_file`. Recovering ground truth is then a dict
lookup — no identity smuggled into the context text, no regex to parse it back
out, and no such thing as a golden whose source cannot be resolved.
"""

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cms.ingestion.extract.cases_extractor import build_case_text, load_seed_cases
from cms.ingestion.extract.policy_extractor import find_seed_policies, read_policy_file
from cms.ingestion.seed import case_title, resolve_seed_dir

logger = logging.getLogger(__name__)


@dataclass(frozen=True)
class SourceDoc:
    """One materialised document, plus the ground truth a metric will need later.

    `title` is deliberately the same string the ingest path writes to the Qdrant
    payload — the policy's frontmatter title, or `case_title`'s
    ``"C-1001 — warranty / faulty_product"``. That is what makes `verify` able to
    recognise a retrieved chunk as this document without a Postgres round trip:
    `source_ref` is a database column and never reaches the vector store.
    """

    source_ref: str  # "warranty-policy.md" | "C-1001"
    corpus: Literal["policy", "case"]
    department: str | None  # None = company-wide policy
    title: str
    path: Path  # the materialised .md


def _write(doc_dir: Path, name: str, body: str) -> Path:
    path = doc_dir / name
    path.write_text(body, encoding="utf-8")
    return path


def materialize_policies(doc_dir: Path) -> list[SourceDoc]:
    """Every seed policy, frontmatter stripped, one `.md` per document.

    A single unreadable file is logged and skipped rather than failing the run —
    the same call `list_seed_entries` makes, and for the same reason: one
    malformed document must not cost the other 33.
    """
    docs: list[SourceDoc] = []
    for path in find_seed_policies(resolve_seed_dir() / "policies"):
        try:
            meta, body = read_policy_file(path)
        except Exception:
            logger.exception("Could not read policy %s — skipping it", path.name)
            continue

        if not body.strip():
            logger.warning("Policy %s has an empty body — skipping it", path.name)
            continue

        docs.append(
            SourceDoc(
                source_ref=path.name,
                corpus="policy",
                department=meta.get("department") or None,
                title=meta.get("title", path.stem),
                path=_write(doc_dir, path.name, body),
            )
        )

    logger.info("Materialised %d policy document(s)", len(docs))
    return docs


def materialize_cases(doc_dir: Path) -> list[SourceDoc]:
    """Every seed case as its own `.md`, holding exactly the embedded text.

    A malformed `cases.json` raises — that failure has no partial answer,
    matching `run_seed`'s contract.
    """
    cases = load_seed_cases(resolve_seed_dir() / "cases.json")
    docs = [
        SourceDoc(
            source_ref=case["id"],
            corpus="case",
            department=case["department"],
            title=case_title(case),
            path=_write(doc_dir, f"{case['id']}.md", build_case_text(case)),
        )
        for case in cases
    ]
    logger.info("Materialised %d case document(s)", len(docs))
    return docs


def materialize_corpus(doc_dir: Path) -> dict[str, SourceDoc]:
    """The whole seed corpus on disk as `.md`, keyed by materialised filename.

    Raises on a filename collision rather than letting one document silently
    overwrite another: the key is the only link back to ground truth, so two
    documents sharing one would mislabel every golden written from either.
    """
    doc_dir.mkdir(parents=True, exist_ok=True)

    index: dict[str, SourceDoc] = {}
    for doc in [*materialize_policies(doc_dir), *materialize_cases(doc_dir)]:
        existing = index.get(doc.path.name)
        if existing is not None:
            raise ValueError(
                f"{doc.path.name} is claimed by both {existing.source_ref!r} and "
                f"{doc.source_ref!r} — rename one seed document"
            )
        index[doc.path.name] = doc

    if not index:
        raise ValueError(f"No seed documents found under {resolve_seed_dir()}")

    logger.info("Materialised %d document(s) into %s", len(index), doc_dir)
    return index
