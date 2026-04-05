"""Build the contexts deepeval generates from, and annotate what it gives back.

`deepeval generate` owns the synthesis (see `tests/evals/README.md`). This
module owns the two ends it cannot reach on its own.

**Why `--method contexts` for both corpora, when the skill prefers `--method
docs`.** deepeval's document path re-chunks with its own `TokenTextSplitter`
at 1024 tokens / 0 overlap, which does not correspond to *any* chunk this
project indexed — `chunk_policy` splits header-aware at 800/100. A golden
written against text that exists in no Qdrant point is a poor ruler for
retrieval, which is the whole reason the dataset exists. Going through
contexts built by the project's own chunker means every golden is grounded in
text the retriever can actually return. It also avoids pulling chromadb +
onnxruntime in purely to re-embed a corpus that is already embedded.

**Why the header line.** `--method contexts` has no `source_files` parameter,
so a generated golden comes back with `source_file: null` and no way home. The
fix is to carry the identity *inside* the first chunk of each context, in a
line both the generator and `annotate_goldens` can read:

    POLICY warranty-policy.md (warranty) — Product Warranty Policy
    CASE C-1001 (warranty) — faulty_product

It earns its place twice: `annotate_goldens` parses it back into ground-truth
metadata, and the generator sees which department and document it is writing
about, which is what keeps a §-citation in the expected output honest.
"""

import json
import logging
import re
from collections import OrderedDict, defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Literal

from cms.ingestion.extract.cases_extractor import build_case_text, load_seed_cases
from cms.ingestion.extract.policy_extractor import find_seed_policies, read_policy_file
from cms.ingestion.seed import resolve_seed_dir
from cms.ingestion.transform.chunker import chunk_policy

logger = logging.getLogger(__name__)

# A policy runs to a dozen chunks; handing all of them to the generator as one
# context buries the clause that matters in scope boilerplate. Three is enough
# for a question that needs more than one clause to answer.
MAX_CHUNKS_PER_CONTEXT = 3

# Frontmatter omits `department` entirely for the 16 company-wide policies, and
# NULL there means "applies to every department" — not "missing". The header
# line needs a word for it that survives the round trip.
COMPANY_WIDE = "company-wide"

_HEADER = re.compile(
    r"^(?P<corpus>POLICY|CASE)\s+(?P<source_ref>\S+)\s+\((?P<department>[^)]*)\)\s+—\s+(?P<title>.*)$"
)


@dataclass(frozen=True)
class EvalContext:
    """One deepeval context, plus the ground truth a metric will need later."""

    source_ref: str  # "warranty-policy.md" | "C-1001"
    corpus: Literal["policy", "case"]
    department: str | None  # None = company-wide policy
    title: str
    chunks: list[str]

    def header(self) -> str:
        label = "POLICY" if self.corpus == "policy" else "CASE"
        return (
            f"{label} {self.source_ref} ({self.department or COMPANY_WIDE}) — {self.title}"
        )

    def to_context(self) -> list[str]:
        """The `list[str]` deepeval wants, with the header on the first chunk.

        First chunk only: repeating it on every chunk would have the generator
        treat the restated identity as content worth asking about.
        """
        if not self.chunks:
            raise ValueError(f"{self.source_ref} produced no chunks")
        return [f"{self.header()}\n\n{self.chunks[0]}", *self.chunks[1:]]


def _sample_evenly(items: list[str], limit: int) -> list[str]:
    """Up to `limit` items spread across `items`, not the first `limit`.

    Every policy opens with scope and definitions, so taking the head of each
    document would yield a corpus of near-identical "what does this policy
    cover?" goldens.
    """
    if limit <= 0:
        raise ValueError("limit must be positive")
    if len(items) <= limit:
        return list(items)
    step = len(items) / limit
    return [items[int(index * step)] for index in range(limit)]


def select_stratified(contexts: list[EvalContext], limit: int | None) -> list[EvalContext]:
    """Up to `limit` contexts, round-robin across departments.

    Taking the first N of a filename-sorted list would spend the whole budget
    in the alphabetically early departments. Round-robin gives every department
    a golden before any department gets a second one. Deterministic: the same
    corpus always yields the same selection, so regenerating the dataset shows
    up as a content diff rather than a reshuffle.
    """
    if limit is None or limit >= len(contexts):
        return list(contexts)

    strata: dict[str, list[EvalContext]] = defaultdict(list)
    for context in sorted(contexts, key=lambda c: c.source_ref):
        strata[context.department or COMPANY_WIDE].append(context)

    # OrderedDict over a sorted key list keeps the rotation stable run to run.
    ordered = OrderedDict((key, strata[key]) for key in sorted(strata))
    selected: list[EvalContext] = []
    depth = 0
    while len(selected) < limit:
        added = False
        for bucket in ordered.values():
            if depth < len(bucket):
                selected.append(bucket[depth])
                added = True
                if len(selected) == limit:
                    break
        if not added:  # every bucket exhausted before reaching `limit`
            break
        depth += 1

    logger.info(
        "Selected %d of %d context(s) across %d department stratum/strata",
        len(selected),
        len(contexts),
        len(ordered),
    )
    return selected


def build_policy_contexts() -> list[EvalContext]:
    """One context per seed policy, up to `MAX_CHUNKS_PER_CONTEXT` chunks each.

    A single unreadable file is logged and skipped rather than failing the run —
    the same call the admin picker's `list_seed_entries` makes, and for the same
    reason: one malformed document must not cost the other 33.
    """
    contexts: list[EvalContext] = []
    for path in find_seed_policies(resolve_seed_dir() / "policies"):
        try:
            meta, body = read_policy_file(path)
            chunks = _sample_evenly(chunk_policy(body), MAX_CHUNKS_PER_CONTEXT)
        except Exception:
            logger.exception("Could not build a context from policy %s — skipping it", path.name)
            continue

        contexts.append(
            EvalContext(
                source_ref=path.name,
                corpus="policy",
                department=meta.get("department") or None,
                title=meta.get("title", path.stem),
                chunks=chunks,
            )
        )

    logger.info("Built %d policy context(s)", len(contexts))
    return contexts


def build_case_contexts() -> list[EvalContext]:
    """One context per seed case, one chunk each.

    `chunk_case` is identity by design (a resolved complaint is semantically
    atomic), so the context is exactly the text `ingest_case` embedded.
    A malformed `cases.json` raises — that failure has no partial answer,
    matching `run_seed`'s contract.
    """
    cases = load_seed_cases(resolve_seed_dir() / "cases.json")
    contexts = [
        EvalContext(
            source_ref=case["id"],
            corpus="case",
            department=case["department"],
            title=case["category"],
            chunks=[build_case_text(case)],
        )
        for case in cases
    ]
    logger.info("Built %d case context(s)", len(contexts))
    return contexts


def build_contexts(
    *, policy_limit: int | None = None, case_limit: int | None = None
) -> list[EvalContext]:
    """The full selection, policies first, each corpus stratified separately.

    Stratified per corpus rather than over the union: the corpora answer
    different questions ("what is the rule?" vs. "what did we do last time?")
    and a shared budget would let 34 policies crowd out the 20 cases.
    """
    return [
        *select_stratified(build_policy_contexts(), policy_limit),
        *select_stratified(build_case_contexts(), case_limit),
    ]


def write_contexts_file(contexts: list[EvalContext], path: Path) -> int:
    """Write the `[["chunk", ...], ...]` file `--contexts-file` expects."""
    if not contexts:
        raise ValueError("Refusing to write an empty contexts file")

    payload = [context.to_context() for context in contexts]
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        # ensure_ascii=False: the corpus is full of ₹ and em dashes, and an
        # escaped ₹ in the prompt is one more thing for the generator to
        # get wrong when it restates an amount.
        path.write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        logger.exception("Could not write the contexts file to %s", path)
        raise

    logger.info("Wrote %d context(s) to %s", len(payload), path)
    return len(payload)


def parse_header(chunk: str) -> dict[str, str | None] | None:
    """Recover the ground truth from a context's first line, or None."""
    match = _HEADER.match(chunk.splitlines()[0].strip() if chunk else "")
    if match is None:
        return None

    department = match.group("department").strip()
    return {
        "corpus": match.group("corpus").lower(),
        "source_ref": match.group("source_ref"),
        "expected_department": None if department == COMPANY_WIDE else department,
        "title": match.group("title").strip(),
    }


def annotate_goldens(goldens_path: Path, out_path: Path) -> int:
    """Attach ground-truth metadata to a generated goldens file.

    `synthesizer.save_as` writes only `input`/`actual_output`/`expected_output`/
    `context`/`source_file`, and drops `additional_metadata` entirely — so the
    identity we planted in the context has to be read back out here and
    promoted to a field a metric can filter on.

    Fields are read with `.get()` so a deepeval release that adds or renames a
    key does not break this; a golden whose header will not parse is *kept*
    with a null `source_ref` and logged at WARNING. Dropping it silently would
    quietly shrink the dataset, which is exactly the failure a committed
    baseline is supposed to make visible.
    """
    try:
        raw = json.loads(goldens_path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        logger.exception("Could not read generated goldens from %s", goldens_path)
        raise

    # `save_as` writes a bare array; tolerate a {"goldens": [...]} wrapper too.
    goldens = raw.get("goldens", []) if isinstance(raw, dict) else raw
    if not isinstance(goldens, list) or not goldens:
        raise ValueError(f"No goldens found in {goldens_path}")

    annotated: list[dict] = []
    unresolved = 0
    for golden in goldens:
        context = golden.get("context") or []
        metadata = parse_header(context[0]) if context else None
        if metadata is None:
            unresolved += 1
            logger.warning(
                "Golden %r has no parseable source header — keeping it with source_ref=null",
                (golden.get("input") or "")[:80],
            )
            metadata = {
                "corpus": None,
                "source_ref": None,
                "expected_department": None,
                "title": None,
            }

        annotated.append(
            {
                "input": golden.get("input"),
                "expected_output": golden.get("expected_output"),
                "context": context,
                "source_file": metadata["source_ref"],
                "additional_metadata": metadata,
            }
        )

    try:
        out_path.parent.mkdir(parents=True, exist_ok=True)
        out_path.write_text(
            json.dumps(annotated, indent=2, ensure_ascii=False), encoding="utf-8"
        )
    except OSError:
        logger.exception("Could not write the dataset to %s", out_path)
        raise

    logger.info(
        "Wrote %d golden(s) to %s (%d without a resolvable source)",
        len(annotated),
        out_path,
        unresolved,
    )
    return len(annotated)
