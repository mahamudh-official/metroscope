"""Service layer managing email subscriptions, double opt-in verification, and unsubscribe flows."""

import datetime
import hashlib
import re
import secrets
from typing import Any, Dict, Optional
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.newsletter.provider import EmailProvider, SMTPEmailProvider
from app.newsletter.templates import render_verification_email, render_unsubscribe_confirmation_email
from app.repositories import newsletter_repository


EMAIL_REGEX = re.compile(r"^[a-zA-Z0-9_.+-]+@[a-zA-Z0-9-]+\.[a-zA-Z0-9-.]+$")


def normalize_email(email: str) -> str:
    """Normalizes an email address by stripping whitespace and converting to lowercase."""
    return email.strip().lower()


def hash_token(raw_token: str) -> str:
    """Computes SHA-256 hexadecimal digest for secure token storage."""
    return hashlib.sha256(raw_token.strip().encode("utf-8")).hexdigest()


def ensure_utc(dt: Optional[datetime.datetime]) -> Optional[datetime.datetime]:
    """Ensures a datetime object is timezone-aware in UTC (normalizing SQLite naive returns)."""
    if dt is None:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=datetime.timezone.utc)
    return dt.astimezone(datetime.timezone.utc)


def generate_unsubscribe_token(email_normalized: str) -> str:
    """Generates a cryptographically secure token derived from secret and normalized email."""
    import hmac
    secret = (getattr(settings, "SECRET_KEY", None) or settings.POSTGRES_PASSWORD or "metroscope_secret_salt").encode("utf-8")
    message = f"metroscope-unsub:{email_normalized}".encode("utf-8")
    return hmac.new(secret, message, hashlib.sha256).hexdigest()


class NewsletterSubscriptionService:
    """Handles subscriber double opt-in registration, verification, and unsubscription."""

    def __init__(self, email_provider: Optional[EmailProvider] = None):
        self.email_provider = email_provider or SMTPEmailProvider()

    def validate_email_format(self, email: str) -> bool:
        """Validates that the email address conforms to standard syntax."""
        if not email or len(email) > 255:
            return False
        return bool(EMAIL_REGEX.match(email.strip()))

    async def subscribe(
        self,
        db: AsyncSession,
        email: str,
    ) -> Dict[str, Any]:
        """Initiates a subscription request with double opt-in verification."""
        clean_email = email.strip()
        if not self.validate_email_format(clean_email):
            return {
                "success": False,
                "status": "invalid_email",
                "message": "Please enter a valid email address.",
            }

        norm_email = normalize_email(clean_email)
        now = datetime.datetime.now(datetime.timezone.utc)

        # Check rate limit on subscription creations
        one_hour_ago = now - datetime.timedelta(hours=1)
        recent_count = await newsletter_repository.count_recent_subscriptions(db, since=one_hour_ago)
        # Apply safety threshold across platform
        if recent_count >= settings.SUBSCRIPTION_RATE_LIMIT_PER_HOUR * 50:
            logger.warning(f"Subscription rate limit threshold exceeded ({recent_count} requests in 1hr)")
            return {
                "success": False,
                "status": "rate_limited",
                "message": "Too many subscription attempts. Please try again later.",
            }

        existing = await newsletter_repository.get_subscriber_by_email_normalized(db, norm_email)

        if existing and existing.status == "active":
            return {
                "success": True,
                "status": "already_subscribed",
                "message": "This email address is already subscribed to the MetroScope newsletter.",
            }

        raw_verify_token = secrets.token_urlsafe(32)
        verify_token_hash = hash_token(raw_verify_token)
        expires_at = now + datetime.timedelta(hours=settings.VERIFICATION_TOKEN_EXPIRE_HOURS)

        if existing:
            # Resubscribe or re-send verification
            existing.status = "pending"
            existing.verification_token_hash = verify_token_hash
            existing.verification_sent_at = now
            existing.verification_expires_at = expires_at
            # Keep consistent unsubscribe token hash
            raw_unsub_token = generate_unsubscribe_token(norm_email)
            existing.unsubscribe_token_hash = hash_token(raw_unsub_token)
            subscriber = existing
        else:
            raw_unsub_token = generate_unsubscribe_token(norm_email)
            unsub_token_hash = hash_token(raw_unsub_token)
            subscriber = await newsletter_repository.create_subscriber(
                db=db,
                email=clean_email,
                email_normalized=norm_email,
                verification_token_hash=verify_token_hash,
                verification_expires_at=expires_at,
                unsubscribe_token_hash=unsub_token_hash,
            )

        await db.commit()
        await db.refresh(subscriber)

        # Build verification URL
        verify_url = f"{settings.SITE_URL.rstrip('/')}/verify-subscription?token={raw_verify_token}"
        html_body, text_body = render_verification_email(email=subscriber.email, verify_url=verify_url)

        delivery_result = await self.email_provider.send_email(
            to_email=subscriber.email,
            subject="Confirm Your MetroScope Newsletter Subscription",
            html_body=html_body,
            text_body=text_body,
        )

        if not delivery_result.success:
            logger.error(f"Failed to dispatch verification email to {subscriber.email}: {delivery_result.error_message}")

        return {
            "success": True,
            "status": "verification_sent",
            "message": "Verification link sent! Please check your inbox to activate your subscription.",
        }

    async def verify(
        self,
        db: AsyncSession,
        raw_token: str,
    ) -> Dict[str, Any]:
        """Validates a verification token and transitions subscriber to 'active'."""
        if not raw_token or not raw_token.strip():
            return {
                "success": False,
                "status": "invalid_token",
                "message": "A verification token is required.",
            }

        token_hash = hash_token(raw_token)
        subscriber = await newsletter_repository.get_subscriber_by_verification_token_hash(db, token_hash)

        if not subscriber:
            return {
                "success": False,
                "status": "invalid_token",
                "message": "The verification link is invalid or has already been used.",
            }

        now = datetime.datetime.now(datetime.timezone.utc)
        expires_at = ensure_utc(subscriber.verification_expires_at)
        if expires_at and now > expires_at:
            return {
                "success": False,
                "status": "expired",
                "message": "This verification link has expired. Please subscribe again to receive a fresh link.",
            }

        subscriber.status = "active"
        subscriber.verified_at = now
        subscriber.verification_token_hash = None
        subscriber.verification_expires_at = None

        await db.commit()
        await db.refresh(subscriber)

        logger.info(f"Subscriber verified successfully: {subscriber.email_normalized} (ID: {subscriber.id})")
        return {
            "success": True,
            "status": "active",
            "message": "Your subscription is now active! You will receive the MetroScope Daily Briefing.",
        }

    async def unsubscribe(
        self,
        db: AsyncSession,
        raw_token: str,
    ) -> Dict[str, Any]:
        """Unsubscribes a reader via one-click unsubscribe token."""
        if not raw_token or not raw_token.strip():
            return {
                "success": False,
                "status": "invalid_token",
                "message": "An unsubscribe token is required.",
            }

        token_hash = hash_token(raw_token)
        subscriber = await newsletter_repository.get_subscriber_by_unsubscribe_token_hash(db, token_hash)

        if not subscriber:
            return {
                "success": False,
                "status": "invalid_token",
                "message": "The unsubscribe link is invalid.",
            }

        if subscriber.status == "unsubscribed":
            return {
                "success": True,
                "status": "already_unsubscribed",
                "message": "You are already unsubscribed from the MetroScope newsletter.",
            }

        now = datetime.datetime.now(datetime.timezone.utc)
        subscriber.status = "unsubscribed"
        subscriber.unsubscribed_at = now

        await db.commit()
        await db.refresh(subscriber)

        logger.info(f"Subscriber unsubscribed: {subscriber.email_normalized} (ID: {subscriber.id})")
        return {
            "success": True,
            "status": "unsubscribed",
            "message": "You have been successfully unsubscribed from the MetroScope newsletter.",
        }
