"""MetroScope email subscription and newsletter delivery subsystem."""

from app.newsletter.provider import EmailProvider, SMTPEmailProvider, MockEmailProvider, EmailDeliveryResult
from app.newsletter.service import NewsletterSubscriptionService, normalize_email, hash_token, generate_unsubscribe_token
from app.newsletter.campaign_service import NewsletterCampaignService
from app.newsletter.templates import render_verification_email, render_newsletter_email, render_unsubscribe_confirmation_email

__all__ = [
    "EmailProvider",
    "SMTPEmailProvider",
    "MockEmailProvider",
    "EmailDeliveryResult",
    "NewsletterSubscriptionService",
    "NewsletterCampaignService",
    "normalize_email",
    "hash_token",
    "generate_unsubscribe_token",
    "render_verification_email",
    "render_newsletter_email",
    "render_unsubscribe_confirmation_email",
]
