from langchain_core.documents import Document

from cms.config.settings import get_settings
from cms.schemas.flywheel import CaseComparison
from cms.services import case_dedupe

NEW_CASE = "COMPLAINT:\nKettle stopped heating.\n\nRESOLUTION:\nIssued a free replacement."


def _hit(doc_id: str, score: float) -> tuple[Document, float]:
    return Document(page_content=f"case {doc_id}", metadata={"doc_id": doc_id, "title": doc_id}), score


def _install(monkeypatch, hits, verdicts=None, judge_error=None) -> list:
    """Stub the search and the judge. Returns the past cases the judge was shown."""
    judged = []

    async def retrieve(query, pool_k, top_n):
        return hits

    async def compare(new_case, past_case):
        judged.append(past_case)
        if judge_error:
            raise judge_error
        return verdicts[past_case]

    monkeypatch.setattr(case_dedupe, "retrieve_cases_reranked", retrieve)
    monkeypatch.setattr(case_dedupe, "_compare", compare)
    monkeypatch.setattr(get_settings(), "rerank_enabled", True)
    monkeypatch.setattr(get_settings(), "flywheel_similar_case_threshold", 0.70)
    return judged


SAME = CaseComparison(same_complaint=True, same_resolution=True, reason="Same fault and remedy.")
OTHER_REMEDY = CaseComparison(same_complaint=True, same_resolution=False, reason="Refund, not replacement.")


async def test_the_same_complaint_and_resolution_is_a_duplicate(monkeypatch) -> None:
    _install(monkeypatch, [_hit("c1", 0.9)], {"case c1": SAME})

    duplicate = await case_dedupe.find_duplicate(NEW_CASE, "Kettle stopped heating.")

    assert duplicate == {"case_id": "c1", "title": "c1", "score": 0.9, "reason": SAME.reason}


async def test_a_different_resolution_is_not_a_duplicate(monkeypatch) -> None:
    verdicts = {"case c1": OTHER_REMEDY, "case c2": OTHER_REMEDY}
    judged = _install(monkeypatch, [_hit("c1", 0.9), _hit("c2", 0.8)], verdicts)

    assert await case_dedupe.find_duplicate(NEW_CASE, "Kettle stopped heating.") is None
    assert judged == ["case c1", "case c2"]


async def test_cases_below_the_threshold_are_not_judged(monkeypatch) -> None:
    judged = _install(monkeypatch, [_hit("c1", 0.69)], {"case c1": SAME})

    assert await case_dedupe.find_duplicate(NEW_CASE, "Kettle stopped heating.") is None
    assert judged == []


async def test_a_failed_judge_mints_anyway(monkeypatch) -> None:
    _install(monkeypatch, [_hit("c1", 0.9)], judge_error=RuntimeError("model down"))

    assert await case_dedupe.find_duplicate(NEW_CASE, "Kettle stopped heating.") is None


async def test_without_the_rerank_nothing_is_checked(monkeypatch) -> None:
    judged = _install(monkeypatch, [_hit("c1", 0.9)], {"case c1": SAME})
    monkeypatch.setattr(get_settings(), "rerank_enabled", False)

    assert await case_dedupe.find_duplicate(NEW_CASE, "Kettle stopped heating.") is None
    assert judged == []
