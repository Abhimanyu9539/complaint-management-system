"""Extract company policies through LangChain text loaders.

TextLoader owns filesystem decoding and returns a LangChain Document. The
existing lightweight frontmatter parser remains the normalization boundary:
metadata goes to the policy row and the body alone goes to chunking/embedding.
"""

import logging
from pathlib import Path

from langchain_community.document_loaders import TextLoader

logger = logging.getLogger(__name__)


def find_seed_policies(directory: Path) -> list[Path]:
    """The policy markdown files in the seed corpus, in a stable order."""
    paths = sorted(directory.glob("*.md"))
    logger.debug("Found %d policy file(s) in %s", len(paths), directory)
    return paths


def read_policy_file(path: Path) -> tuple[dict[str, str], str]:
    """Load one policy as a LangChain Document, returning metadata and body."""
    documents = TextLoader(str(path), encoding="utf-8").load()
    if len(documents) != 1:
        raise ValueError(f"Expected one document from policy file {path}")

    return parse_frontmatter(documents[0].page_content)


def parse_frontmatter(markdown: str) -> tuple[dict[str, str], str]:
    """Split a leading frontmatter delimiter block into key/value lines.

    The seed frontmatter is three flat string fields, so pulling in a YAML
    parser would add capability that this input does not need.
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
