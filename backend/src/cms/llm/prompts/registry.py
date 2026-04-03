"""The versioned prompt loader `llm/prompts/`'s docstring promised.

One directory per `(name, version)` under `templates/`, holding a
`system.txt` and a `human.txt` — loaded into a `ChatPromptTemplate` rather
than kept as inline strings in node code, so a prompt tweak is a file edit,
not a code change, and the version is part of the path rather than implicit.

Plain text files, not YAML: `ingestion/load/storage_loader.py` and
`ingestion/extract/policy_extractor.py` both decline to add `pyyaml` as a
real dependency (today it's only pulled in transitively) for inputs just as
simple as this — a couple of flat text blocks don't need a parser, and a bare
`.txt` file needs no escaping for multi-line prompt text the way a YAML block
scalar would. This module extends that same call rather than reopening it.

`analyze_query` is this loader's first consumer. The two pre-existing
placeholder directories (`templates/tier_classification/`,
`templates/resolution/`) predate build.md's RAG-agent design — they were
sturcture.md's node names for a different, superseded architecture — and are
left empty; nothing here assumes they will ever be filled.
"""

import logging
from functools import lru_cache
from pathlib import Path

from langchain_core.prompts import ChatPromptTemplate

logger = logging.getLogger(__name__)

TEMPLATES_DIR = Path(__file__).parent / "templates"


@lru_cache
def load_prompt(name: str, version: str = "v1") -> ChatPromptTemplate:
    """Load `templates/<name>/<version>/{system,human}.txt` as a two-message
    `ChatPromptTemplate`.

    Cached: the files never change at runtime, so one read per `(name,
    version)` per process. A missing file fails loudly here rather than
    silently sending an empty prompt to a paying API.
    """
    directory = TEMPLATES_DIR / name / version
    try:
        system = (directory / "system.txt").read_text(encoding="utf-8")
        human = (directory / "human.txt").read_text(encoding="utf-8")
    except Exception:
        logger.exception("Failed to load prompt '%s/%s' from %s", name, version, directory)
        raise
    return ChatPromptTemplate.from_messages([("system", system), ("human", human)])
