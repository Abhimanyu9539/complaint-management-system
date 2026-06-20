"""Send one plain-text email over SMTP. In development that is Mailpit, which delivers nothing."""

import asyncio
import logging
import smtplib
from email.message import EmailMessage
from email.utils import make_msgid, parseaddr

from cms.config.settings import get_settings

logger = logging.getLogger(__name__)


class EmailSendError(Exception):
    """The email did not leave. Nothing was sent, so the caller may retry."""


def build_message(to: str, subject: str, body: str) -> EmailMessage:
    """The message with From, To, Reply-To, Subject and a fresh Message-ID."""
    settings = get_settings()
    domain = parseaddr(settings.support_email_from)[1].rpartition("@")[2] or None

    message = EmailMessage()
    message["From"] = settings.support_email_from
    message["To"] = to
    message["Reply-To"] = settings.support_reply_to
    message["Subject"] = subject
    message["Message-ID"] = make_msgid(domain=domain)
    message.set_content(body)
    return message


def _send(message: EmailMessage) -> None:
    """The blocking SMTP conversation; run in a thread."""
    settings = get_settings()
    with smtplib.SMTP(
        settings.smtp_host, settings.smtp_port, timeout=settings.smtp_timeout_seconds
    ) as smtp:
        if settings.smtp_starttls:
            smtp.starttls()
        if settings.smtp_username:
            smtp.login(settings.smtp_username, settings.smtp_password or "")
        smtp.send_message(message)


async def send_email(to: str, subject: str, body: str) -> str:
    """Send `body` to `to` and return the Message-ID. Raises `EmailSendError` on any failure.

    Until the API has a login, only a local SMTP server is allowed: an open send
    endpoint pointed at a real mail server would mail anyone on request.
    """
    settings = get_settings()
    if not settings.email_real_delivery_enabled and settings.smtp_host not in settings.local_smtp_hosts:
        raise EmailSendError(
            f"SMTP host {settings.smtp_host!r} is not local and real delivery is disabled."
        )

    message = build_message(to, subject, body)
    try:
        await asyncio.to_thread(_send, message)
    except Exception as exc:
        logger.exception("Email to %s failed via %s:%s", to, settings.smtp_host, settings.smtp_port)
        raise EmailSendError(f"{type(exc).__name__}: {exc}") from exc

    logger.info("Email sent to %s: %r (%s)", to, subject, message["Message-ID"])
    return message["Message-ID"]
