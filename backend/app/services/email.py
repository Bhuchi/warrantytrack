"""Outbound email (CLOUDAPPG5-98).

Two backends, chosen by `EMAIL_BACKEND`:

* `ses` — Amazon SES.
* `log` — writes the message to the application log and returns success, so
  the expiry scan can be developed and demoed without an AWS account and
  without mailing anybody by accident. Not allowed in production, because an
  email that silently is not sent is worse than one that fails loudly (see
  app/core/config.py).

Sending never raises at the caller. A warranty notification that cannot be
emailed must still appear in the bell menu — the in-app row is the record, the
email is the nudge — so failures are logged and reported in the return value
instead of aborting the scan half way through a workspace.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

import boto3
from botocore.exceptions import BotoCoreError, ClientError

from app.core.config import settings

logger = logging.getLogger(__name__)

_ses_client = None


def _client():
    global _ses_client
    if _ses_client is None:
        _ses_client = boto3.client("ses", region_name=settings.aws_region)
    return _ses_client


@dataclass(frozen=True)
class SendResult:
    """Whether one message went out, and why not if it did not."""

    sent: bool
    error: str | None = None


def send(to: str, subject: str, body: str) -> SendResult:
    """Send one plain-text email. Never raises."""
    if not to:
        return SendResult(sent=False, error="No recipient address.")

    if settings.email_backend == "log":
        # Indented so a multi-line body is obvious as one message in the log.
        logger.info(
            "EMAIL (log backend)\n  to: %s\n  subject: %s\n  %s",
            to,
            subject,
            body.replace("\n", "\n  "),
        )
        return SendResult(sent=True)

    if not settings.ses_sender_email:
        return SendResult(sent=False, error="SES_SENDER_EMAIL is not set.")

    try:
        _client().send_email(
            Source=settings.ses_sender_email,
            Destination={"ToAddresses": [to]},
            Message={
                "Subject": {"Data": subject, "Charset": "UTF-8"},
                "Body": {"Text": {"Data": body, "Charset": "UTF-8"}},
            },
        )
    except (BotoCoreError, ClientError) as exc:  # pragma: no cover - needs AWS
        logger.warning("SES send to %s failed: %s", to, exc)
        return SendResult(sent=False, error=str(exc))

    return SendResult(sent=True)
