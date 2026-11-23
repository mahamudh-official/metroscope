import datetime
from typing import List, Optional
from sqlalchemy import DateTime, ForeignKey, Index, Integer, JSON, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.base import Base
from app.models.base import TimestampMixin


class EmailSubscriber(Base, TimestampMixin):
    """Stores verified and pending email subscribers for daily newsletter delivery."""

    __tablename__ = "email_subscribers"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    email_normalized: Mapped[str] = mapped_column(
        String(255), unique=True, index=True, nullable=False
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", index=True, nullable=False
    )  # "pending", "active", "unsubscribed"

    verification_token_hash: Mapped[Optional[str]] = mapped_column(
        String(64), index=True, nullable=True
    )
    verification_sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verification_expires_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    verified_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    unsubscribe_token_hash: Mapped[str] = mapped_column(
        String(64), unique=True, index=True, nullable=False
    )
    unsubscribed_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    deliveries: Mapped[List["NewsletterDelivery"]] = relationship(
        back_populates="subscriber", cascade="all, delete-orphan"
    )


class NewsletterCampaign(Base, TimestampMixin):
    """Tracks daily newsletter briefing campaigns and selected curated articles."""

    __tablename__ = "newsletter_campaigns"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    subject: Mapped[str] = mapped_column(String(255), nullable=False)
    scheduled_for: Mapped[datetime.datetime] = mapped_column(
        DateTime(timezone=True), index=True, nullable=False
    )
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )
    status: Mapped[str] = mapped_column(
        String(32), default="draft", index=True, nullable=False
    )  # "draft", "sending", "sent", "failed"

    article_ids: Mapped[list] = mapped_column(JSON, default=list, nullable=False)
    recipient_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    delivered_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    failed_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    deliveries: Mapped[List["NewsletterDelivery"]] = relationship(
        back_populates="campaign", cascade="all, delete-orphan"
    )


class NewsletterDelivery(Base, TimestampMixin):
    """Individual email recipient delivery records for a campaign."""

    __tablename__ = "newsletter_deliveries"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    campaign_id: Mapped[int] = mapped_column(
        ForeignKey("newsletter_campaigns.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    subscriber_id: Mapped[int] = mapped_column(
        ForeignKey("email_subscribers.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status: Mapped[str] = mapped_column(
        String(32), default="pending", index=True, nullable=False
    )  # "pending", "sent", "failed", "bounced"
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    sent_at: Mapped[Optional[datetime.datetime]] = mapped_column(
        DateTime(timezone=True), nullable=True
    )

    campaign: Mapped["NewsletterCampaign"] = relationship(back_populates="deliveries")
    subscriber: Mapped["EmailSubscriber"] = relationship(back_populates="deliveries")

    __table_args__ = (
        UniqueConstraint("campaign_id", "subscriber_id", name="uq_campaign_subscriber"),
    )
