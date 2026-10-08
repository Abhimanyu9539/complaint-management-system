"""Load a versioned prompt, `templates/<name>/<version>/{system,human}.txt`, as a `ChatPromptTemplate`."""

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
