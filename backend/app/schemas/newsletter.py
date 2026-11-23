"""Pydantic v2 schemas for newsletter subscription and delivery APIs."""

from typing import Optional
from pydantic import BaseModel, EmailStr, Field


class NewsletterSubscribeRequest(BaseModel):
    """Payload for newsletter subscription."""
    email: EmailStr = Field(..., description="Reader email address for newsletter subscription")


class NewsletterSubscribeResponse(BaseModel):
    """Response payload for subscription requests."""
    success: bool
    status: str
    message: str


class NewsletterVerifyResponse(BaseModel):
    """Response payload for email double opt-in verification."""
    success: bool
    status: str
    message: str


class NewsletterUnsubscribeResponse(BaseModel):
    """Response payload for reader unsubscription requests."""
    success: bool
    status: str
    message: str


class NewsletterStatusResponse(BaseModel):
    """Basic subscription subsystem metrics and health."""
    total_active_subscribers: int
    dry_run_enabled: bool
    service_status: str
