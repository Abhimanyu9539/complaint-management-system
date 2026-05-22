import pytest
from langchain_core.runnables import RunnableLambda

from cms.config.settings import get_settings
from cms.guardrails import fact_check as fact_check_module
from cms.schemas.guardrails import FactCheckFindings, UnsupportedClaim


class _FakeModel:
    """Stands in for the chat model: `with_structured_output` returns a canned runnable.

    A `RunnableLambda`, so the real `fact_check_claims/v1` template still renders
    and pipes into it — the tests see the prompt the model would get.
    """

    def __init__(self, reply: FactCheckFindings | Exception) -> None:
        self.reply = reply
        self.prompts: list[str] = []

    def with_structured_output(self, schema):
        def run(prompt_value):
            self.prompts.append(prompt_value.to_string())
            if isinstance(self.reply, Exception):
                raise self.reply
            return self.reply

        return RunnableLambda(run)


def _claims(count: int) -> list[UnsupportedClaim]:
    return [UnsupportedClaim(claim=f"claim {i}", reason=f"reason {i}") for i in range(count)]


def _install(monkeypatch, reply: FactCheckFindings | Exception) -> _FakeModel:
    model = _FakeModel(reply)
    monkeypatch.setattr(fact_check_module, "get_chat_model", lambda name: model)
    return model


async def test_unsupported_claims_are_returned(monkeypatch) -> None:
    model = _install(monkeypatch, FactCheckFindings(unsupported_claims=_claims(2)))

    claims = await fact_check_module.find_unsupported_claims(
        "Covered within 60 days [1].", "[1] Warranty\nCovered for 12 months."
    )

    assert [claim.claim for claim in claims] == ["claim 0", "claim 1"]
    # Both variables interpolated into the real template.
    assert "Covered within 60 days [1]." in model.prompts[0]
    assert "Covered for 12 months." in model.prompts[0]
    assert "{draft}" not in model.prompts[0] and "{context}" not in model.prompts[0]


async def test_claims_are_capped(monkeypatch) -> None:
    _install(monkeypatch, FactCheckFindings(unsupported_claims=_claims(7)))
    monkeypatch.setattr(get_settings(), "fact_check_max_claims", 2)

    claims = await fact_check_module.find_unsupported_claims("draft", "context")

    assert len(claims) == 2


async def test_no_claims_is_an_empty_list(monkeypatch) -> None:
    _install(monkeypatch, FactCheckFindings())

    assert await fact_check_module.find_unsupported_claims("draft", "context") == []


async def test_a_model_error_raises(monkeypatch) -> None:
    _install(monkeypatch, RuntimeError("openrouter down"))

    with pytest.raises(RuntimeError):
        await fact_check_module.find_unsupported_claims("draft", "context")
