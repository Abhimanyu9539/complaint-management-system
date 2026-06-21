import pytest

from cms.config.settings import get_settings
from cms.services import email_sender


class _FakeSMTP:
    """Stands in for `smtplib.SMTP`: records the host and every message sent."""

    sent: list = []

    def __init__(self, host, port, timeout=None) -> None:
        self.host = host

    def __enter__(self):
        return self

    def __exit__(self, *exc) -> None:
        return None

    def send_message(self, message) -> None:
        _FakeSMTP.sent.append(message)


@pytest.fixture
def fake_smtp(monkeypatch):
    _FakeSMTP.sent = []
    monkeypatch.setattr(email_sender.smtplib, "SMTP", _FakeSMTP)
    monkeypatch.setattr(get_settings(), "smtp_host", "localhost")
    return _FakeSMTP.sent


async def test_message_carries_the_headers_and_body(fake_smtp) -> None:
    message_id = await email_sender.send_email("jo@example.com", "Re: Kettle [T-1042]", "Dear customer,")

    [message] = fake_smtp
    settings = get_settings()
    assert message["To"] == "jo@example.com"
    assert message["From"] == settings.support_email_from
    assert message["Reply-To"] == settings.support_reply_to
    assert message["Subject"] == "Re: Kettle [T-1042]"
    assert message["Message-ID"] == message_id
    assert message.get_content().strip() == "Dear customer,"


async def test_non_local_host_is_refused_while_real_delivery_is_off(fake_smtp, monkeypatch) -> None:
    monkeypatch.setattr(get_settings(), "smtp_host", "smtp.gmail.com")
    monkeypatch.setattr(get_settings(), "email_real_delivery_enabled", False)

    with pytest.raises(email_sender.EmailSendError):
        await email_sender.send_email("jo@example.com", "s", "b")
    assert fake_smtp == []


async def test_smtp_failure_becomes_email_send_error(monkeypatch) -> None:
    def refuse(*args, **kwargs):
        raise ConnectionRefusedError("mailpit is down")

    monkeypatch.setattr(email_sender.smtplib, "SMTP", refuse)
    monkeypatch.setattr(get_settings(), "smtp_host", "localhost")

    with pytest.raises(email_sender.EmailSendError, match="ConnectionRefusedError"):
        await email_sender.send_email("jo@example.com", "s", "b")
