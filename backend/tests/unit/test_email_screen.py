from cms.config.settings import get_settings
from cms.schemas.emails import EmailScreen
from cms.schemas.guardrails import GuardResult
from cms.services import email_screen

NOTICE = EmailScreen(kind="notification", reason="An account security alert.")


def _install(monkeypatch, verdict=NOTICE, judge_error=None, guard_passed=True) -> list:
    """Stub the input guard and the model. Returns the bodies the model was shown."""
    judged = []

    async def run_input_guard(text):
        return GuardResult(passed=guard_passed, text=f"masked: {text}" if guard_passed else "")

    async def judge(subject, body):
        judged.append(body)
        if judge_error:
            raise judge_error
        return verdict

    monkeypatch.setattr(email_screen, "run_input_guard", run_input_guard)
    monkeypatch.setattr(email_screen, "_judge", judge)
    monkeypatch.setattr(get_settings(), "email_screen_enabled", True)
    monkeypatch.setattr(get_settings(), "guardrails_enabled", True)
    monkeypatch.setattr(get_settings(), "email_screen_max_chars", 10)
    return judged


async def test_the_model_sees_the_masked_and_shortened_body(monkeypatch) -> None:
    judged = _install(monkeypatch)

    verdict = await email_screen.screen_email("Alert", "  You gave access to an app.")

    assert verdict == NOTICE
    assert judged == ["masked: You gave a"]


async def test_a_model_error_returns_none(monkeypatch) -> None:
    _install(monkeypatch, judge_error=RuntimeError("model down"))

    assert await email_screen.screen_email("Alert", "Body") is None


async def test_a_refused_body_is_not_sent_to_the_model(monkeypatch) -> None:
    judged = _install(monkeypatch, guard_passed=False)

    assert await email_screen.screen_email("Alert", "Body") is None
    assert judged == []


async def test_the_screen_can_be_turned_off(monkeypatch) -> None:
    judged = _install(monkeypatch)
    monkeypatch.setattr(get_settings(), "email_screen_enabled", False)

    assert await email_screen.screen_email("Alert", "Body") is None
    assert judged == []
