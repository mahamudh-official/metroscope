"""API endpoints for public newsletter subscription, double opt-in verification, and unsubscription."""

from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.db.session import get_db
from app.newsletter.service import NewsletterSubscriptionService
from app.repositories import newsletter_repository
from app.schemas.newsletter import (
    NewsletterSubscribeRequest,
    NewsletterSubscribeResponse,
    NewsletterVerifyResponse,
    NewsletterUnsubscribeResponse,
    NewsletterStatusResponse,
)

router = APIRouter()
subscription_service = NewsletterSubscriptionService()


@router.post(
    "/subscribe",
    response_model=NewsletterSubscribeResponse,
    status_code=status.HTTP_200_OK,
    summary="Subscribe to MetroScope Daily Briefing",
    description="Registers an email for double opt-in verification. Dispatches a verification email.",
)
async def subscribe_to_newsletter(
    payload: NewsletterSubscribeRequest,
    db: AsyncSession = Depends(get_db),
) -> NewsletterSubscribeResponse:
    result = await subscription_service.subscribe(db=db, email=payload.email)
    return NewsletterSubscribeResponse(
        success=result["success"],
        status=result["status"],
        message=result["message"],
    )


@router.get(
    "/verify",
    response_model=NewsletterVerifyResponse,
    status_code=status.HTTP_200_OK,
    summary="Verify subscription email address",
    description="Validates the double opt-in token and activates the newsletter subscription.",
)
async def verify_subscription(
    token: str = Query(..., description="Secret verification token sent via email"),
    db: AsyncSession = Depends(get_db),
) -> NewsletterVerifyResponse:
    result = await subscription_service.verify(db=db, raw_token=token)
    return NewsletterVerifyResponse(
        success=result["success"],
        status=result["status"],
        message=result["message"],
    )


@router.get(
    "/unsubscribe",
    response_model=NewsletterUnsubscribeResponse,
    status_code=status.HTTP_200_OK,
    summary="Unsubscribe from newsletter",
    description="Validates the unsubscribe token and unsubscribes the recipient.",
)
async def unsubscribe_from_newsletter(
    token: str = Query(..., description="One-click unsubscribe token from newsletter footer"),
    db: AsyncSession = Depends(get_db),
) -> NewsletterUnsubscribeResponse:
    result = await subscription_service.unsubscribe(db=db, raw_token=token)
    return NewsletterUnsubscribeResponse(
        success=result["success"],
        status=result["status"],
        message=result["message"],
    )


@router.get(
    "/status",
    response_model=NewsletterStatusResponse,
    status_code=status.HTTP_200_OK,
    summary="Newsletter subsystem status",
    description="Returns aggregate subscriber count and operational mode.",
)
async def get_newsletter_status(
    db: AsyncSession = Depends(get_db),
) -> NewsletterStatusResponse:
    active_count = await newsletter_repository.count_active_subscribers(db)
    return NewsletterStatusResponse(
        total_active_subscribers=active_count,
        dry_run_enabled=settings.EMAIL_DRY_RUN,
        service_status="operational",
    )
