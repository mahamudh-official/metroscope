import datetime
from decimal import Decimal
from typing import Optional
from sqlalchemy import (
    Boolean,
    DateTime,
    Integer,
    Numeric,
    String,
    Text,
    func,
    Index,
)
from sqlalchemy.orm import Mapped, mapped_column
from app.db.base import Base
from app.models.base import TimestampMixin


class WebzUsageLedger(Base, TimestampMixin):
    """PostgreSQL-backed usage and financial accounting ledger for Webz.io News API.
    
    Tracks exact request counts, billable units, estimated and actual costs,
    reserved allowances, and budget stop reasons. Enforces the $4.00 collection
    ceiling and $1.00 protected reserve under the $5.00 monthly allocation.
    """

    __tablename__ = "webz_usage_ledger"

    id: Mapped[int] = mapped_column(primary_key=True, autoincrement=True)
    billing_period: Mapped[str] = mapped_column(String(20), index=True, nullable=False)
    job_name: Mapped[str] = mapped_column(String(100), index=True, nullable=False)
    endpoint: Mapped[str] = mapped_column(String(255), nullable=False)
    query_params: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    status_code: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    success: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    returned_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    billable_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    estimated_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("0.0050"),
        nullable=False,
    )
    actual_cost: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
    )
    reserved_cost: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("0.0050"),
        nullable=False,
    )
    requests_left: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    credits_used: Mapped[Optional[Decimal]] = mapped_column(
        Numeric(10, 4),
        nullable=True,
    )
    remaining_allowance: Mapped[Decimal] = mapped_column(
        Numeric(10, 4),
        default=Decimal("4.0000"),
        nullable=False,
    )
    stop_reason: Mapped[Optional[str]] = mapped_column(String(100), nullable=True)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)

    __table_args__ = (
        Index("ix_webz_ledger_period_created", "billing_period", "created_at"),
    )

    def __repr__(self) -> str:
        return f"<WebzUsageLedger id={self.id} period={self.billing_period} job={self.job_name} success={self.success}>"
