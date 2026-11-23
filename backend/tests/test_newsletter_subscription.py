"""Unit and integration tests for email subscription, double opt-in verification, and unsubscription."""

import datetime
import pytest
from httpx import AsyncClient
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.newsletter import EmailSubscriber
from app.newsletter.provider import MockEmailProvider
from app.newsletter.service import (
    NewsletterSubscriptionService,
    ensure_utc,
    generate_unsubscribe_token,
    hash_token,
    normalize_email,
)
from app.repositories import newsletter_repository


def test_email_normalization_and_validation():
    service = NewsletterSubscriptionService()

    assert normalize_email("  Reader@Example.COM  ") == "reader@example.com"
    assert normalize_email("USER+newsletter@Domain.Org ") == "user+newsletter@domain.org"

    assert service.validate_email_format("reader@example.com") is True
    assert service.validate_email_format("invalid-email") is False
    assert service.validate_email_format("@missing-local.com") is False
    assert service.validate_email_format("") is False


def test_token_hashing_and_unsubscribe_hmac():
    raw_token = "my-secret-verification-token-12345"
    digest = hash_token(raw_token)
    assert len(digest) == 64
    assert digest == hash_token(raw_token)  # Deterministic

    # Unsubscribe HMAC token
    unsub_token_1 = generate_unsubscribe_token("user1@example.com")
    unsub_token_2 = generate_unsubscribe_token("user2@example.com")
    assert len(unsub_token_1) == 64
    assert unsub_token_1 != unsub_token_2
    assert unsub_token_1 == generate_unsubscribe_token("user1@example.com")


@pytest.mark.asyncio
async def test_new_subscription_double_opt_in(db_session: AsyncSession):
    mock_provider = MockEmailProvider()
    service = NewsletterSubscriptionService(email_provider=mock_provider)

    res = await service.subscribe(db_session, "Reader@Example.com")
    assert res["success"] is True
    assert res["status"] == "verification_sent"
    assert len(mock_provider.sent_emails) == 1
    assert mock_provider.sent_emails[0]["to_email"] == "Reader@Example.com"
    assert "Confirm Your MetroScope Newsletter Subscription" in mock_provider.sent_emails[0]["subject"]

    # Verify database state
    subscriber = await newsletter_repository.get_subscriber_by_email_normalized(
        db_session, "reader@example.com"
    )
    assert subscriber is not None
    assert subscriber.status == "pending"
    assert subscriber.email == "Reader@Example.com"
    assert subscriber.email_normalized == "reader@example.com"
    assert subscriber.verification_token_hash is not None
    assert len(subscriber.verification_token_hash) == 64
    assert ensure_utc(subscriber.verification_expires_at) > datetime.datetime.now(datetime.timezone.utc)
    assert subscriber.verified_at is None


@pytest.mark.asyncio
async def test_duplicate_and_existing_subscription(db_session: AsyncSession):
    mock_provider = MockEmailProvider()
    service = NewsletterSubscriptionService(email_provider=mock_provider)

    # 1. Initial subscription -> pending
    await service.subscribe(db_session, "reader@example.com")
    assert len(mock_provider.sent_emails) == 1

    # 2. Resubscribe while pending -> re-sends verification
    res_pending = await service.subscribe(db_session, "reader@example.com")
    assert res_pending["status"] == "verification_sent"
    assert len(mock_provider.sent_emails) == 2

    # 3. Manually activate subscriber
    sub = await newsletter_repository.get_subscriber_by_email_normalized(db_session, "reader@example.com")
    sub.status = "active"
    sub.verified_at = datetime.datetime.now(datetime.timezone.utc)
    await db_session.commit()

    # 4. Subscribe while active -> already subscribed
    res_active = await service.subscribe(db_session, "reader@example.com")
    assert res_active["status"] == "already_subscribed"
    # Should not send an extra email
    assert len(mock_provider.sent_emails) == 2


@pytest.mark.asyncio
async def test_verification_success_and_invalidation(db_session: AsyncSession):
    mock_provider = MockEmailProvider()
    service = NewsletterSubscriptionService(email_provider=mock_provider)

    await service.subscribe(db_session, "subscriber@domain.com")

    # Extract raw token from verification URL
    sent_html = mock_provider.sent_emails[0]["html_body"]
    import re
    match = re.search(r"token=([A-Za-z0-9_-]+)", sent_html)
    assert match is not None
    raw_token = match.group(1)

    # Verify with valid token
    res = await service.verify(db_session, raw_token)
    assert res["success"] is True
    assert res["status"] == "active"

    # Verify DB state
    sub = await newsletter_repository.get_subscriber_by_email_normalized(db_session, "subscriber@domain.com")
    assert sub.status == "active"
    assert sub.verified_at is not None
    assert sub.verification_token_hash is None  # Invalidated for one-time use

    # Second attempt with same token -> invalid
    res_second = await service.verify(db_session, raw_token)
    assert res_second["success"] is False
    assert res_second["status"] == "invalid_token"


@pytest.mark.asyncio
async def test_verification_token_expired(db_session: AsyncSession):
    mock_provider = MockEmailProvider()
    service = NewsletterSubscriptionService(email_provider=mock_provider)

    await service.subscribe(db_session, "expired@domain.com")
    sent_html = mock_provider.sent_emails[0]["html_body"]
    import re
    match = re.search(r"token=([A-Za-z0-9_-]+)", sent_html)
    raw_token = match.group(1)

    # Force expiration in database
    sub = await newsletter_repository.get_subscriber_by_email_normalized(db_session, "expired@domain.com")
    sub.verification_expires_at = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=2)
    await db_session.commit()

    res = await service.verify(db_session, raw_token)
    assert res["success"] is False
    assert res["status"] == "expired"


@pytest.mark.asyncio
async def test_unsubscribe_flow(db_session: AsyncSession):
    mock_provider = MockEmailProvider()
    service = NewsletterSubscriptionService(email_provider=mock_provider)

    await service.subscribe(db_session, "reader@unsubscribe-test.com")
    raw_unsub_token = generate_unsubscribe_token("reader@unsubscribe-test.com")

    # Unsubscribe with valid token
    res = await service.unsubscribe(db_session, raw_unsub_token)
    assert res["success"] is True
    assert res["status"] == "unsubscribed"

    sub = await newsletter_repository.get_subscriber_by_email_normalized(db_session, "reader@unsubscribe-test.com")
    assert sub.status == "unsubscribed"
    assert sub.unsubscribed_at is not None

    # Unsubscribe again -> already unsubscribed
    res_again = await service.unsubscribe(db_session, raw_unsub_token)
    assert res_again["status"] == "already_unsubscribed"

    # Unsubscribe with invalid token
    res_invalid = await service.unsubscribe(db_session, "completely-invalid-token")
    assert res_invalid["status"] == "invalid_token"


@pytest.mark.asyncio
async def test_api_newsletter_endpoints(client: AsyncClient, db_session: AsyncSession):
    # 1. Status endpoint
    status_resp = await client.get("/api/v1/newsletter/status")
    assert status_resp.status_code == 200
    data = status_resp.json()
    assert "total_active_subscribers" in data
    assert data["service_status"] == "operational"

    # 2. Subscribe endpoint
    sub_resp = await client.post(
        "/api/v1/newsletter/subscribe",
        json={"email": "api_reader@example.com"},
    )
    assert sub_resp.status_code == 200
    sub_data = sub_resp.json()
    assert sub_data["success"] is True
    assert sub_data["status"] == "verification_sent"

    # 3. Invalid email payload
    bad_resp = await client.post(
        "/api/v1/newsletter/subscribe",
        json={"email": "not-a-valid-email"},
    )
    assert bad_resp.status_code == 422

    # 4. Unsubscribe endpoint with invalid token
    unsub_resp = await client.get("/api/v1/newsletter/unsubscribe?token=fake-token-999")
    assert unsub_resp.status_code == 200
    unsub_data = unsub_resp.json()
    assert unsub_data["success"] is False
    assert unsub_data["status"] == "invalid_token"
