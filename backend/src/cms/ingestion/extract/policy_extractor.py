"""Extract company policy documents.

Two jobs: find the policy files on disk, and split the frontmatter off a policy
markdown file so the metadata and the body can go their separate ways. Reading a
policy *row* is a table access and lives in `db.repositories.policies`, not here.
"""

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def find_seed_policies(directory: Path) -> list[Path]:
    """The policy markdown files in the seed corpus, in a stable order."""
    paths = sorted(directory.glob("*.md"))
    logger.debug("Found %d policy file(s) in %s", len(paths), directory)
    return paths


def read_policy_file(path: Path) -> tuple[dict[str, str], str]:
    """Read one policy file, returning its frontmatter and its body."""
    return parse_frontmatter(path.read_text(encoding="utf-8"))


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
