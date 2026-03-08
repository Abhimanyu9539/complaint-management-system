"""The two chunking strategies from build.md §0.4.

`case`   — no split. A resolved complaint is semantically atomic: separating a
           resolution from the complaint it resolves destroys the retrieval
           unit, because neither half answers "how was this handled?" alone.
`policy` — header-aware split, then a size split. Policies are long-form and
           cited by clause ("per warranty §2.3"), so each chunk carries its
           heading breadcrumb and stays small enough to be precise.
"""

import logging

import tiktoken
from langchain_text_splitters import (
    MarkdownHeaderTextSplitter,
    RecursiveCharacterTextSplitter,
)

logger = logging.getLogger(__name__)

# ~800 tokens with 100 overlap (build.md §0.4). Overlap exists so a clause that
# straddles a chunk boundary is still fully present in at least one chunk.
POLICY_CHUNK_TOKENS = 800
POLICY_CHUNK_OVERLAP = 100

# Headers the policy corpus actually uses: `# Title`, `## N. Section`,
# `### N.M Clause`. Anything deeper is left inside the chunk body.
POLICY_HEADERS = [("#", "h1"), ("##", "h2"), ("###", "h3")]

# tiktoken has no encoding registered for embedding models by name in every
# version; cl100k_base is the encoding text-embedding-3-* uses.
_TOKEN_ENCODING = "cl100k_base"


def count_tokens(text: str) -> int:
    """Token count for `case_chunks.token_count` / `policy_chunks.token_count`.

    Never raises: the count is diagnostic metadata, so a tokenizer problem must
    not fail an otherwise good ingest.
    """
    try:
        return len(tiktoken.get_encoding(_TOKEN_ENCODING).encode(text))
    except Exception:
        logger.exception("Token counting failed; recording 0")
        return 0


def parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    """Split a leading `---` block of `key: value` lines from the body.

    Hand-rolled rather than pulling in pyyaml: the policy frontmatter is three
    flat string fields, and pyyaml is only a transitive dependency here — not
    something pyproject.toml declares, so importing it would be borrowing.
    """
    if not markdown.startswith("---"):
        return {}, markdown

    parts = markdown.split("---", 2)
    if len(parts) < 3:
        logger.warning("Unterminated frontmatter block; treating file as body-only")
        return {}, markdown

    meta: dict[str, str] = {}
    for line in parts[1].strip().splitlines():
        key, sep, value = line.partition(":")
        if sep:
            meta[key.strip()] = value.strip()

    return meta, parts[2].lstrip("\n")


def build_case_text(case: dict) -> str:
    """Flatten a case record into one labelled block of text.

    The section labels are kept in the embedded text on purpose — they give the
    retriever (and later the drafting prompt) the structure of the case, so a
    hit can be read as "this is the complaint, this is what we did about it".
    `dept_guidance` is present only for Path B (escalated) cases.
    """
    sections = [f"COMPLAINT:\n{case['complaint_text']}"]

    guidance = case.get("dept_guidance")
    if guidance:
        sections.append(f"DEPARTMENT GUIDANCE:\n{guidance}")

    sections.append(f"RESOLUTION:\n{case['resolution_text']}")
    return "\n\n".join(sections)


def chunk_case(text: str) -> list[str]:
    """One case = one chunk = one Qdrant point."""
    return [text]


def chunk_policy(text: str) -> list[str]:
    """Header-aware split, then size split, with the breadcrumb prepended.

    The breadcrumb matters at citation time: a bare paragraph about "structural
    failures" is useless to cite, while "Product Warranty Policy > 2.
    Manufacturing Defects > 2.3 …" tells the agent which clause they are
    quoting.
    """
    # strip_headers=True: the heading lines are re-added as the breadcrumb
    # below, so leaving them in place would just duplicate them in the chunk.
    header_splitter = MarkdownHeaderTextSplitter(
        headers_to_split_on=POLICY_HEADERS,
        strip_headers=True,
    )
    size_splitter = RecursiveCharacterTextSplitter.from_tiktoken_encoder(
        encoding_name=_TOKEN_ENCODING,
        chunk_size=POLICY_CHUNK_TOKENS,
        chunk_overlap=POLICY_CHUNK_OVERLAP,
    )

    chunks: list[str] = []
    for section in header_splitter.split_text(text):
        # Iterate POLICY_HEADERS, not the metadata dict, so the breadcrumb is
        # always in document order (h1 > h2 > h3).
        breadcrumb = " > ".join(
            section.metadata[name]
            for _, name in POLICY_HEADERS
            if section.metadata.get(name)
        )
        for piece in size_splitter.split_text(section.page_content):
            chunks.append(f"{breadcrumb}\n\n{piece}" if breadcrumb else piece)

    if not chunks:
        raise ValueError("Chunking produced no chunks for this policy")

    logger.debug("Chunked policy into %d chunk(s)", len(chunks))
    return chunks
