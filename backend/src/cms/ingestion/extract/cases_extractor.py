"""Extract historical resolved complaints through LangChain loaders.

The source corpus is a JSON array, so JSONLoader emits one LangChain Document
per case. Structured fields are copied into Document.metadata; the seed runner
then projects that metadata back into the existing database record shape.
Reading a case row remains a table access in db.repositories.cases.
"""

import logging
from pathlib import Path

from langchain_community.document_loaders import JSONLoader

logger = logging.getLogger(__name__)

_CASE_FIELDS = (
    "id",
    "department",
    "category",
    "resolution_path",
    "complaint_text",
    "dept_guidance",
    "resolution_text",
)


def _case_metadata(record: dict, metadata: dict) -> dict:
    """Copy and validate one structured case record into document metadata."""
    if not isinstance(record, dict):
        raise TypeError(f"Expected a case object, got {type(record).__name__}")

    missing = [field for field in _CASE_FIELDS if field not in record]
    if missing:
        raise ValueError(
            f"Case record is missing required field(s): {', '.join(missing)}"
        )

    return {**metadata, **{field: record[field] for field in _CASE_FIELDS}}


def load_seed_cases(path: Path) -> list[dict]:
    """Load one LangChain Document per case and restore domain records."""
    documents = JSONLoader(
        file_path=str(path),
        jq_schema=".[]",
        text_content=False,
        metadata_func=_case_metadata,
    ).load()

    cases = [
        {field: document.metadata[field] for field in _CASE_FIELDS}
        for document in documents
    ]
    logger.debug("Loaded %d case(s) from %s", len(cases), path)
    return cases


def build_case_text(case: dict) -> str:
    """Flatten a case record into one labelled block of text.

    The section labels are kept in the embedded text on purpose - they give the
    retriever (and later the drafting prompt) the structure of the case, so a
    hit can be read as "this is the complaint, this is what we did about it".
    The optional department guidance is present only for escalated cases.
    """
    sections = [f"COMPLAINT:\n{case['complaint_text']}"]

    guidance = case.get("dept_guidance")
    if guidance:
        sections.append(f"DEPARTMENT GUIDANCE:\n{guidance}")

    sections.append(f"RESOLUTION:\n{case['resolution_text']}")
    return "\n\n".join(sections)
