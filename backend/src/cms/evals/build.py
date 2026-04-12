"""Generate the golden dataset from the seed corpus in one deepeval call.

This is deepeval's documented document path, unmodified:

    synthesizer = Synthesizer()
    goldens = synthesizer.generate_goldens_from_docs(document_paths=[...])

deepeval parses each document into chunks, quality-filters them with its critic
model, groups them into contexts, and writes `input` / `expected_output` /
`context` / `source_file` per golden. Everything in this module is either that
call or the two things it cannot do for itself: point it at a corpus it can read
(`cms.evals.corpus`), and join deepeval's `source_file` back to the department
and title the retriever evals need.

**No styling prompts.** The previous build passed `--input-format "... order
numbers ... and Rupee amounts where relevant"` and got exactly that: "order
12345" and "Rs. 15,000", invented facts that appear nowhere in the corpus and
that no retrieval could ever support. Ungrounded goldens were caused by the
instruction to embellish, so the fix is to not give one. Left unstyled, the
generator has nothing to work from but the chunk in front of it.

**Why the one config object.** `ContextConstructionConfig` is the documented
customization point for this method, and two of its defaults are wrong here:
`max_context_length=3` builds a context from three chunks, so a golden can only
be recalled if the retriever returns all three — that is what failed 26 of the
previous 40 goldens — and `chunk_size=1024` corresponds to no chunk this project
indexes (`chunk_policy` cuts at 800/100).
"""

import json
import logging
import tempfile
from pathlib import Path

from cms.evals.corpus import SourceDoc, materialize_corpus

logger = logging.getLogger(__name__)

# Not `settings.openai_model_main`: authoring a dataset is not serving traffic.
# `gpt-4.1-mini` over deepeval's default `gpt-4.1` is a rate-limit choice — this
# account caps `gpt-4.1` at 30k TPM, where the full corpus dies on 429s.
GENERATOR_MODEL = "gpt-4.1-mini"
EMBEDDING_MODEL = "text-embedding-3-small"

# deepeval defaults to 100. Nothing is written to disk until the run finishes,
# so a 429 storm at document 50 costs you the 49 before it.
MAX_CONCURRENT = 3

# Matches `chunk_policy`'s budget, so a generated context is the size of a chunk
# the retriever actually indexes. deepeval's splitter is token-based and not
# header-aware, but the retriever metrics judge semantic support rather than
# string identity, so the region matters and the exact cut does not.
CHUNK_SIZE = 800
CHUNK_OVERLAP = 100


def _record(golden, index: dict[str, SourceDoc]) -> dict | None:
    """One golden as a dataset row, with ground truth joined in by filename.

    `expected_department` and `source_ref` are what make retrieval measurable
    without an LLM: routing accuracy is "did the classifier pick
    `expected_department`", retrieval hit rate is "was `source_ref` among the
    chunks we retrieved". deepeval fills in `source_file` on this path, so the
    join is a dict lookup — no identity smuggled into the context text, and no
    such thing as a golden whose source cannot be resolved.
    """
    name = Path(golden.source_file).name if golden.source_file else None
    doc = index.get(name) if name else None
    if doc is None:
        logger.warning(
            "Golden %r came back with source_file=%r, which is not in the corpus index",
            (golden.input or "")[:80],
            golden.source_file,
        )
        return None

    metadata = golden.additional_metadata or {}
    return {
        "input": golden.input,
        "expected_output": golden.expected_output,
        "context": list(golden.context or []),
        "source_file": doc.source_ref,
        "additional_metadata": {
            "corpus": doc.corpus,
            "source_ref": doc.source_ref,
            "expected_department": doc.department,
            "title": doc.title,
            # deepeval's own critic scores, carried through rather than recomputed.
            "context_quality": metadata.get("context_quality"),
            "synthetic_input_quality": metadata.get("synthetic_input_quality"),
            "evolutions": metadata.get("evolutions"),
        },
    }


def generate(index: dict[str, SourceDoc]) -> tuple[list, float | None]:
    """The synthesis call. Returns the raw goldens and the run's cost."""
    from deepeval.models import OpenAIModel
    from deepeval.synthesizer import Synthesizer
    from deepeval.synthesizer.config import ContextConstructionConfig

    synthesizer = Synthesizer(
        model=OpenAIModel(model=GENERATOR_MODEL),
        max_concurrent=MAX_CONCURRENT,
        cost_tracking=True,
    )

    goldens = synthesizer.generate_goldens_from_docs(
        document_paths=[str(doc.path) for doc in index.values()],
        include_expected_output=True,
        max_goldens_per_context=1,
        context_construction_config=ContextConstructionConfig(
            # Not optional on Windows. deepeval hands this to `TextLoader`, and
            # `None` there means the platform codepage — cp1252 on this machine.
            # The corpus is UTF-8 and full of ₹ and §, so the default silently
            # yields `â‚¹8,000` and `Â§2.3` in every context it builds.
            encoding="utf-8",
            chunk_size=CHUNK_SIZE,
            chunk_overlap=CHUNK_OVERLAP,
            # One chunk per context, one context per document: every golden is
            # answerable from a single chunk the retriever can return, and the
            # corpus is covered exactly once.
            max_context_length=1,
            min_context_length=1,
            max_contexts_per_document=1,
            min_contexts_per_document=1,
            embedder=EMBEDDING_MODEL,
        ),
    )
    return goldens, synthesizer.synthesis_cost


def build_goldens(out_path: Path) -> list[dict]:
    """Materialise the corpus, generate, and write the dataset."""
    # The materialised corpus is a build input, not an artifact worth keeping:
    # it is derived from `data/seed/` and regenerated on every run.
    with tempfile.TemporaryDirectory(prefix="cms-evals-") as tmp:
        index = materialize_corpus(Path(tmp))
        goldens, cost = generate(index)
        records = [record for golden in goldens if (record := _record(golden, index))]

    if not records:
        raise ValueError("Generation produced no usable goldens")

    out_path.parent.mkdir(parents=True, exist_ok=True)
    # ensure_ascii=False: the corpus is full of ₹ and em dashes, and an escaped
    # ₹ is one more thing for a reader to get wrong.
    out_path.write_text(
        json.dumps(records, indent=2, ensure_ascii=False), encoding="utf-8"
    )
    logger.info(
        "Wrote %d golden(s) to %s%s",
        len(records),
        out_path,
        f" (cost ${cost:.4f})" if cost else "",
    )
    return records
