"""Email provider abstraction and SMTP client for MetroScope newsletter delivery."""

import abc
import asyncio
from dataclasses import dataclass
import datetime
import email.message
import json
from pathlib import Path
import smtplib
from typing import Optional
from app.core.config import settings
from app.core.logging import logger


@dataclass
class EmailDeliveryResult:
    """Outcome of an email delivery attempt."""
    success: bool
    recipient: str
    message_id: Optional[str] = None
    dry_run: bool = False
    error_message: Optional[str] = None


class EmailProvider(abc.ABC):
    """Abstract base class for email delivery providers."""

    @abc.abstractmethod
    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> EmailDeliveryResult:
        """Sends a single multipart email message."""
        pass


class SMTPEmailProvider(EmailProvider):
    """Standard SMTP email delivery provider using standard library smtplib in worker thread."""

    def __init__(
        self,
        host: Optional[str] = None,
        port: Optional[int] = None,
        username: Optional[str] = None,
        password: Optional[str] = None,
        from_email: Optional[str] = None,
        from_name: Optional[str] = None,
        use_tls: Optional[bool] = None,
        timeout: Optional[float] = None,
        dry_run: Optional[bool] = None,
    ):
        self.host = host or settings.SMTP_HOST
        self.port = port if port is not None else settings.SMTP_PORT
        self.username = username or settings.SMTP_USERNAME
        self.password = password or settings.SMTP_PASSWORD
        self.from_email = from_email or settings.SMTP_FROM_EMAIL
        self.from_name = from_name or settings.SMTP_FROM_NAME
        self.use_tls = use_tls if use_tls is not None else settings.SMTP_USE_TLS
        self.timeout = timeout or settings.SMTP_TIMEOUT_SECONDS
        self.dry_run = dry_run if dry_run is not None else settings.EMAIL_DRY_RUN

    def _send_sync(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> EmailDeliveryResult:
        """Synchronous SMTP delivery executed in thread pool."""
        if self.dry_run:
            logger.info(
                f"[EMAIL DRY-RUN] Would send email to '{to_email}' | Subject: '{subject}' | "
                f"HTML size: {len(html_body)} bytes | Text size: {len(text_body)} bytes"
            )
            # Local email capture for testing mode without external delivery
            try:
                log_dir = Path("logs")
                log_dir.mkdir(parents=True, exist_ok=True)
                capture_file = log_dir / "captured_emails.log"
                with open(capture_file, "a", encoding="utf-8") as f:
                    entry = {
                        "mode": "LOCAL_CAPTURE_NOT_DELIVERED",
                        "timestamp": datetime.datetime.now(datetime.timezone.utc).isoformat(),
                        "recipient": to_email,
                        "subject": subject,
                        "text_body": text_body,
                    }
                    f.write(json.dumps(entry) + "\n")
            except Exception as e:
                logger.warning(f"Could not persist to captured_emails.log: {e}")

            return EmailDeliveryResult(
                success=True,
                recipient=to_email,
                message_id=f"dryrun-msg-{hash(to_email + subject) & 0xffffffff:08x}",
                dry_run=True,
            )

        msg = email.message.EmailMessage()
        msg["Subject"] = subject
        msg["From"] = f"{self.from_name} <{self.from_email}>"
        msg["To"] = to_email
        msg.set_content(text_body)
        msg.add_alternative(html_body, subtype="html")

        try:
            with smtplib.SMTP(self.host, self.port, timeout=self.timeout) as server:
                server.ehlo()
                if self.use_tls:
                    server.starttls()
                    server.ehlo()
                if self.username and self.password:
                    server.login(self.username, self.password)
                server.send_message(msg)
                logger.info(f"Successfully delivered email to {to_email} via SMTP ({self.host}:{self.port})")
                return EmailDeliveryResult(
                    success=True,
                    recipient=to_email,
                    dry_run=False,
                )
        except Exception as exc:
            err_msg = f"SMTP delivery failed to {to_email}: {str(exc)}"
            logger.error(err_msg)
            return EmailDeliveryResult(
                success=False,
                recipient=to_email,
                error_message=err_msg,
                dry_run=False,
            )

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> EmailDeliveryResult:
        """Dispatches SMTP delivery to background thread to preserve async event loop."""
        return await asyncio.to_thread(
            self._send_sync, to_email, subject, html_body, text_body
        )


class MockEmailProvider(EmailProvider):
    """In-memory mock email provider for deterministic unit testing."""

    def __init__(self, should_fail: bool = False, error_message: str = "Mock delivery failure"):
        self.sent_emails: list[dict] = []
        self.should_fail = should_fail
        self.error_message = error_message

    async def send_email(
        self,
        to_email: str,
        subject: str,
        html_body: str,
        text_body: str,
    ) -> EmailDeliveryResult:
        if self.should_fail:
            return EmailDeliveryResult(
                success=False,
                recipient=to_email,
                error_message=self.error_message,
                dry_run=False,
            )

        self.sent_emails.append(
            {
                "to_email": to_email,
                "subject": subject,
                "html_body": html_body,
                "text_body": text_body,
            }
        )
        return EmailDeliveryResult(
            success=True,
            recipient=to_email,
            message_id=f"mock-msg-{len(self.sent_emails)}",
            dry_run=False,
        )
