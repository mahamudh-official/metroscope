"""Comprehensive tests for Facebook complete Page publishing integration.

Covers:
- FacebookPageClient text post (feed), photo post (multipart photos), and follow-up comments
- Dual-key ScreenshotOne integration with Facebook photo post generation
- FacebookPublishingService multi-step workflow, partial publishing, retries, and duplicate prevention
- FastAPI REST endpoints: status, preview, publish, status-check, and retry with operator authentication.
"""

import datetime
from unittest.mock import AsyncMock, patch
import httpx
import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.models.article import NewsArticle
from app.models.category import NewsCategory
from app.models.social import SocialPost
from app.social.facebook_client import FacebookPageClient
from app.social.facebook_service import FacebookPublishingService


# ---------------------------------------------------------------------------
# Client Unit Tests
# ---------------------------------------------------------------------------

@pytest.mark.asyncio
async def test_facebook_client_publish_photo_post_live_mocked():
    client = FacebookPageClient(
        page_id="643848822147472",
        access_token="fake_page_token_123",
        dry_run=False,
    )

    fake_image_bytes = b"\xff\xd8\xff\xe0\x00\x10JFIF" + b"\x00" * 100
    mock_resp = httpx.Response(
        status_code=200,
        json={"id": "photo_987654321", "post_id": "643848822147472_post_123456"},
        request=httpx.Request("POST", "https://graph.facebook.com"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish_photo_post(
            image_bytes=fake_image_bytes,
            caption="Test Photo Headline\n\nDetails in comments",
            article_id=42,
        )

    assert result.success is True
    assert result.external_post_id == "643848822147472_post_123456"
    assert result.response_data["id"] == "photo_987654321"

    # Verify multipart payload
    assert mock_post.called
    call_kwargs = mock_post.call_args.kwargs
    assert "source" in call_kwargs["files"]
    assert call_kwargs["data"]["caption"] == "Test Photo Headline\n\nDetails in comments"
    assert call_kwargs["data"]["access_token"] == "fake_page_token_123"


@pytest.mark.asyncio
async def test_facebook_client_publish_photo_post_dry_run():
    client = FacebookPageClient(page_id="643848822147472", access_token="tok", dry_run=True)
    result = await client.publish_photo_post(
        image_bytes=b"FAKE_BYTES",
        caption="Dry Run Caption",
        article_id=99,
    )
    assert result.success is True
    assert result.dry_run is True
    assert "dryrun-fb-photo-" in str(result.response_data.get("id"))
    assert "dryrun-fb-photo-" in result.external_post_id


@pytest.mark.asyncio
async def test_facebook_client_publish_comment_live_mocked():
    client = FacebookPageClient(
        page_id="643848822147472",
        access_token="fake_page_token_123",
        dry_run=False,
    )

    mock_resp = httpx.Response(
        status_code=200,
        json={"id": "comment_999888777"},
        request=httpx.Request("POST", "https://graph.facebook.com"),
    )

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp
        result = await client.publish_comment(
            post_id="643848822147472_post_123456",
            message="Read the full article at https://metroscope.news/article/sample",
            article_id=42,
        )

    assert result.success is True
    assert result.external_post_id == "comment_999888777"
    assert mock_post.called
    call_kwargs = mock_post.call_args.kwargs
    assert call_kwargs["data"]["message"] == "Read the full article at https://metroscope.news/article/sample"


@pytest.mark.asyncio
async def test_facebook_client_publish_comment_dry_run():
    client = FacebookPageClient(dry_run=True)
    result = await client.publish_comment(
        post_id="post_123",
        message="Dry run comment",
        article_id=88,
    )
    assert result.success is True
    assert result.dry_run is True
    assert "dryrun-fb-comment-" in result.external_post_id


# ---------------------------------------------------------------------------
# Service Integration Tests
# ---------------------------------------------------------------------------

@pytest.fixture
async def sample_published_article(db_session: AsyncSession) -> NewsArticle:
    cat = NewsCategory(name="Technology", slug="technology")
    db_session.add(cat)
    await db_session.commit()

    art = NewsArticle(
        title="Breakthrough in Quantum Computing Architecture",
        slug="breakthrough-quantum-computing",
        description="Researchers unveil scalable solid-state quantum processor.",
        canonical_url="https://example.com/quantum",
        original_url="https://example.com/quantum",
        canonical_url_hash="q" * 64,
        category_id=cat.id,
        image_url="https://images.example.com/quantum.jpg",
        published_at=datetime.datetime(2026, 11, 17, 12, 0, 0, tzinfo=datetime.timezone.utc),
        author="MetroScope News Desk",
        status="published",
        quality_score=85.0,
    )
    db_session.add(art)
    await db_session.commit()
    await db_session.refresh(art)
    return art


@pytest.mark.asyncio
async def test_service_photo_post_full_workflow_success(
    db_session: AsyncSession, sample_published_article: NewsArticle
):
    mock_fb_client = FacebookPageClient(page_id="123", access_token="tok", dry_run=False)
    service = FacebookPublishingService(facebook_client=mock_fb_client, dry_run=False)

    fake_card_bytes = b"PHOTO_CARD_JPEG"

    # Mock photo card render
    with patch.object(service.photo_card_service, "render_image", new_callable=AsyncMock) as mock_render:
        mock_render.return_value = fake_card_bytes

        # Mock Facebook photo post & follow-up comment
        with patch.object(mock_fb_client, "publish_photo_post", new_callable=AsyncMock) as mock_photo_post:
            from app.social.base import SocialPostResult
            mock_photo_post.return_value = SocialPostResult(
                success=True,
                platform="facebook",
                external_post_id="post_777888",
                response_data={"id": "photo_111222", "post_id": "post_777888"},
            )

            with patch.object(mock_fb_client, "publish_comment", new_callable=AsyncMock) as mock_comment:
                mock_comment.return_value = SocialPostResult(
                    success=True,
                    platform="facebook",
                    external_post_id="comment_333444",
                )

                result = await service.publish_article(
                    db=db_session,
                    article_id=sample_published_article.id,
                    post_type="photo",
                    include_comment=True,
                )

    assert result.success is True
    assert result.status == "PUBLISHED"
    assert result.post_id == "post_777888"
    assert result.photo_id == "photo_111222"
    assert result.comment_id == "comment_333444"

    # Verify database persistence
    saved_post = await db_session.get(SocialPost, result.social_post_id)
    assert saved_post is not None
    assert saved_post.status == "PUBLISHED"
    assert saved_post.external_post_id == "post_777888"
    assert saved_post.external_photo_id == "photo_111222"
    assert saved_post.external_comment_id == "comment_333444"
    assert saved_post.post_type == "photo"


@pytest.mark.asyncio
async def test_service_partially_published_when_comment_fails_and_retry_succeeds(
    db_session: AsyncSession, sample_published_article: NewsArticle
):
    mock_fb_client = FacebookPageClient(page_id="123", access_token="tok", dry_run=False)
    service = FacebookPublishingService(facebook_client=mock_fb_client, dry_run=False)

    from app.social.base import SocialPostResult

    with patch.object(service.photo_card_service, "render_image", new_callable=AsyncMock) as mock_render:
        mock_render.return_value = b"BYTES"
        with patch.object(mock_fb_client, "publish_photo_post", new_callable=AsyncMock) as mock_photo_post:
            mock_photo_post.return_value = SocialPostResult(
                success=True,
                platform="facebook",
                external_post_id="post_partial_123",
                response_data={"id": "photo_partial_123", "post_id": "post_partial_123"},
            )
            with patch.object(mock_fb_client, "publish_comment", new_callable=AsyncMock) as mock_comment:
                # Comment initially fails
                mock_comment.return_value = SocialPostResult(
                    success=False,
                    platform="facebook",
                    error_message="Rate limit on comments endpoint",
                )

                result = await service.publish_article(
                    db=db_session,
                    article_id=sample_published_article.id,
                    post_type="photo",
                    include_comment=True,
                )

    assert result.success is True
    assert result.status == "PARTIALLY_PUBLISHED"
    assert result.post_id == "post_partial_123"
    assert result.comment_id is None
    assert "follow-up comment failed" in (result.error_message or "")

    # Now retry the partially published post
    with patch.object(mock_fb_client, "publish_comment", new_callable=AsyncMock) as mock_retry_comment:
        mock_retry_comment.return_value = SocialPostResult(
            success=True,
            platform="facebook",
            external_post_id="comment_retry_ok_999",
        )
        retry_result = await service.retry_post(db=db_session, social_post_id=result.social_post_id)

    assert retry_result.success is True
    assert retry_result.status == "PUBLISHED"
    assert retry_result.comment_id == "comment_retry_ok_999"

    # Confirm database record updated to PUBLISHED
    updated = await db_session.get(SocialPost, result.social_post_id)
    assert updated.status == "PUBLISHED"
    assert updated.external_comment_id == "comment_retry_ok_999"


@pytest.mark.asyncio
async def test_service_idempotency_prevents_duplicate_publishing(
    db_session: AsyncSession, sample_published_article: NewsArticle
):
    service = FacebookPublishingService(dry_run=True)

    # First publication
    res1 = await service.publish_article(db=db_session, article_id=sample_published_article.id)
    assert res1.success is True
    assert res1.status == "PUBLISHED"

    # Second publication without force flag should return ALREADY_PUBLISHED
    res2 = await service.publish_article(db=db_session, article_id=sample_published_article.id, force=False)
    assert res2.success is True
    assert res2.status == "ALREADY_PUBLISHED"
    assert res2.post_id == res1.post_id


def test_facebook_service_generate_caption_exact_structure(sample_published_article: NewsArticle):
    service = FacebookPublishingService(dry_run=True)
    caption = service.generate_caption(sample_published_article)
    expected = f"{sample_published_article.title}\n\nRead more in the comments."
    assert caption == expected
    # Verify title is the only article-specific content in caption
    assert sample_published_article.title in caption
    assert "Read more in the comments." in caption
    # Verify no URL in caption
    assert "https://" not in caption
    assert sample_published_article.slug not in caption
    assert "#MetroScope" not in caption


def test_facebook_service_generate_followup_comment_exact_structure(sample_published_article: NewsArticle):
    service = FacebookPublishingService(dry_run=True)
    comment = service.generate_followup_comment(sample_published_article, base_url="https://metroscope.news")
    expected_url = f"https://metroscope.news/article/{sample_published_article.slug}"
    expected = f"{sample_published_article.title}\n{expected_url}"
    assert comment == expected
    lines = comment.split("\n")
    assert len(lines) == 2
    assert lines[0] == sample_published_article.title
    assert lines[1] == expected_url
    # English only, no Bengali text, no promotional copy
    assert "বাংলা" not in comment
    assert "Read the full article" not in comment
    assert "Briefing" not in comment
    assert "Source:" not in comment


# ---------------------------------------------------------------------------
# FastAPI Endpoint Integration Tests
# ---------------------------------------------------------------------------

AUTH_HEADER = {"Authorization": "Bearer test-operator-token"}
API_KEY_HEADER = {"X-API-Key": "test-operator-token"}


@pytest.mark.asyncio
async def test_api_facebook_status_endpoint(client: httpx.AsyncClient):
    # Unauthenticated request must be rejected
    unauth_resp = await client.get("/api/v1/social/facebook/status")
    assert unauth_resp.status_code == 401

    resp = await client.get("/api/v1/social/facebook/status", headers=AUTH_HEADER)
    assert resp.status_code == 200
    data = resp.json()
    assert "facebook_enabled" in data
    assert "facebook_configured" in data
    assert "screenshotone" in data
    assert "slots" in data["screenshotone"]
    # Secret tokens must NEVER appear raw in response
    assert "token" not in str(data).lower() or "masked" in str(data).lower()


@pytest.mark.asyncio
async def test_api_facebook_endpoint_security_unauthorized_rejected(
    client: httpx.AsyncClient, sample_published_article: NewsArticle
):
    # 1. Preview without auth -> 401
    resp_prev = await client.post(f"/api/v1/social/facebook/preview/{sample_published_article.id}")
    assert resp_prev.status_code == 401
    prev_err = resp_prev.json().get("message") or resp_prev.json().get("detail") or ""
    assert "operator authorization" in prev_err.lower()

    # 2. Publish without auth -> 401
    resp_pub = await client.post(f"/api/v1/social/facebook/publish/{sample_published_article.id}")
    assert resp_pub.status_code == 401
    pub_err = resp_pub.json().get("message") or resp_pub.json().get("detail") or ""
    assert "operator authorization" in pub_err.lower()

    # 3. Posts check without auth -> 401
    resp_posts = await client.get(f"/api/v1/social/facebook/posts/{sample_published_article.id}")
    assert resp_posts.status_code == 401

    # 4. Retry without auth -> 401
    resp_retry = await client.post("/api/v1/social/facebook/retry/999")
    assert resp_retry.status_code == 401

    # 5. Invalid token -> 401
    resp_bad = await client.post(
        f"/api/v1/social/facebook/publish/{sample_published_article.id}",
        headers={"Authorization": "Bearer completely-invalid-token-123"},
    )
    assert resp_bad.status_code == 401


@pytest.mark.asyncio
async def test_api_facebook_preview_endpoint(
    client: httpx.AsyncClient, sample_published_article: NewsArticle
):
    resp = await client.post(
        f"/api/v1/social/facebook/preview/{sample_published_article.id}",
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["article_id"] == sample_published_article.id
    assert data["photo_caption"] == f"{sample_published_article.title}\n\nRead more in the comments."
    assert data["followup_comment"] == f"{sample_published_article.title}\n{data['canonical_url']}"


@pytest.mark.asyncio
async def test_api_facebook_publish_and_status_endpoints(
    client: httpx.AsyncClient, sample_published_article: NewsArticle
):
    # Operator authentication via X-API-Key header
    publish_resp = await client.post(
        f"/api/v1/social/facebook/publish/{sample_published_article.id}",
        params={"post_type": "text", "include_comment": "true"},
        headers=API_KEY_HEADER,
    )
    assert publish_resp.status_code == 200
    pub_data = publish_resp.json()
    assert pub_data["success"] is True
    assert pub_data["status"] == "PUBLISHED"

    # Status check endpoint with Bearer auth
    status_resp = await client.get(
        f"/api/v1/social/facebook/posts/{sample_published_article.id}",
        headers=AUTH_HEADER,
    )
    assert status_resp.status_code == 200
    post_info = status_resp.json()
    assert post_info["article_id"] == sample_published_article.id
    assert post_info["platform"] == "facebook"
    assert post_info["status"] == "PUBLISHED"


@pytest.mark.asyncio
async def test_api_facebook_force_publish_cannot_bypass_unpublished_status(
    client: httpx.AsyncClient, db_session: AsyncSession
):
    cat = NewsCategory(name="Politics", slug="politics")
    db_session.add(cat)
    await db_session.commit()

    draft_art = NewsArticle(
        title="Unpublished Draft Story",
        slug="unpublished-draft-story",
        description="This article is draft/quarantined.",
        canonical_url="https://example.com/draft",
        original_url="https://example.com/draft",
        canonical_url_hash="d" * 64,
        category_id=cat.id,
        status="filtered",  # NOT published
        published_at=datetime.datetime(2026, 11, 17, 12, 0, 0, tzinfo=datetime.timezone.utc),
    )
    db_session.add(draft_art)
    await db_session.commit()
    await db_session.refresh(draft_art)

    # Attempt publish with force=True on unpublished article
    resp = await client.post(
        f"/api/v1/social/facebook/publish/{draft_art.id}",
        params={"force": "true"},
        headers=AUTH_HEADER,
    )
    assert resp.status_code == 400
    err_text = (resp.json().get("message") or resp.json().get("detail") or "").lower()
    assert "only 'published' articles" in err_text
