"""Extract historical resolved complaints.

Two jobs: read the case corpus off disk, and flatten a case record into the
single block of text that gets embedded. Reading a case *row* is a table access
and lives in `db.repositories.cases`, not here.
"""

import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def load_seed_cases(path: Path) -> list[dict]:
    """Read the seed case corpus from its JSON file."""
    cases = json.loads(path.read_text(encoding="utf-8"))
    logger.debug("Loaded %d case(s) from %s", len(cases), path)
    return cases


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
