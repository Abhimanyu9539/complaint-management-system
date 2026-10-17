"""Before minting: is a past case already the same complaint, resolved the same way?"""

import logging

from langchain_core.documents import Document
from langsmith import traceable

from cms.config.settings import get_settings
from cms.llm.chat.openrouter_chat import get_chat_model
from cms.llm.prompts.registry import load_prompt
from cms.observability.usage import UsageCollector
from cms.retrieval.retrievers.case_retriever import retrieve_cases_reranked
from cms.schemas.flywheel import CaseComparison

logger = logging.getLogger(__name__)

PROMPT_NAME = "case_duplicate"


@traceable(name="case_duplicate")
async def _compare(new_case: str, past_case: str) -> CaseComparison:
    settings = get_settings()
    prompt = load_prompt(PROMPT_NAME, settings.case_duplicate_prompt_version)
    model = get_chat_model(settings.openrouter_model_cheap).with_structured_output(CaseComparison)
    chain = prompt | model
    return await chain.ainvoke(
        {"new_case": new_case, "past_case": past_case},
        # Counted in the metrics only; there is no run row to save it on.
        config={"callbacks": [UsageCollector(default_node=PROMPT_NAME)]},
    )


async def _similar_cases(complaint: str) -> list[tuple[Document, float]]:
    """Past cases whose rerank score against the complaint clears the threshold, best first."""
    settings = get_settings()
    if not settings.rerank_enabled:
        # Without the rerank the scores are RRF values, on another scale.
        logger.info("Duplicate check skipped: reranking is off")
        return []

    hits = await retrieve_cases_reranked(complaint, settings.case_pool_k, settings.flywheel_dedupe_top_n)
    threshold = settings.flywheel_similar_case_threshold
    for document, score in hits:
        logger.info(
            "Duplicate check: %s scored %.3f (threshold %.2f)",
            document.metadata.get("title"),
            score,
            threshold,
        )
    return [hit for hit in hits if hit[1] >= threshold]


async def find_duplicate(new_case: str, complaint: str) -> dict | None:
    """The past case that already covers `new_case`, or None if it should be minted.

    A failed search or judge call is logged and treated as no duplicate: minting one
    case too many is safer than losing one.
    """
    try:
        similar = await _similar_cases(complaint)
    except Exception:
        logger.exception("Duplicate check: case search failed; minting anyway")
        return None

    for document, score in similar:
        title = document.metadata.get("title")
        try:
            verdict = await _compare(new_case, document.page_content)
        except Exception:
            logger.exception("Duplicate check: the judge failed on %s; minting anyway", title)
            return None

        logger.info(
            "Duplicate check: %s same_complaint=%s same_resolution=%s (%s)",
            title,
            verdict.same_complaint,
            verdict.same_resolution,
            verdict.reason,
        )
        if verdict.same_complaint and verdict.same_resolution:
            return {
                "case_id": document.metadata.get("doc_id"),
                "title": title,
                "score": round(score, 3),
                "reason": verdict.reason,
            }
    return None
