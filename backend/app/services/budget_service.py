import asyncio
import datetime
from decimal import Decimal
from typing import NamedTuple, Optional
from pydantic import BaseModel
from sqlalchemy import case, func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.integrations.webz.client import WebzBudgetExceededError
from app.integrations.webz.schemas import WebzResponse
from app.models.webz_ledger import WebzUsageLedger

_budget_reservation_lock = asyncio.Lock()


class BudgetPeriodSummary(BaseModel):
    """Aggregate financial and request metrics for a billing period."""
    billing_period: str
    total_requests: int
    successful_requests: int
    total_returned_articles: int
    total_billable_articles: int
    total_spent: Decimal
    monthly_credit: Decimal
    collection_ceiling: Decimal
    protected_reserve: Decimal
    remaining_allowance: Decimal
    can_reserve_next_request: bool


class PreflightResult(NamedTuple):
    allowed: bool
    stop_reason: Optional[str]
    remaining_allowance: Decimal
    estimated_cost: Decimal


class BudgetProtectionService:
    """PostgreSQL-backed usage accounting and budget protection service.
    
    Guarantees:
    - Hard ceiling of $4.00 maximum monthly collection spend
    - Inviolable $1.00 protected reserve from the $5.00 total monthly credit
    - Upfront reservation before any network request is initiated
    - Rejection of requests when collection is disabled or credentials missing
    - Accurate tracking of provider-reported vs conservative estimated costs
    """

    def __init__(
        self,
        monthly_credit: Optional[Decimal] = None,
        collection_ceiling: Optional[Decimal] = None,
        protected_reserve: Optional[Decimal] = None,
        cost_per_request: Optional[Decimal] = None,
    ):
        self.monthly_credit = monthly_credit or settings.WEBZ_IO_MONTHLY_CREDIT
        self.collection_ceiling = collection_ceiling or settings.WEBZ_IO_COLLECTION_CEILING
        self.protected_reserve = protected_reserve or settings.WEBZ_IO_PROTECTED_RESERVE
        self.cost_per_request = cost_per_request or settings.WEBZ_IO_ESTIMATED_COST_PER_REQUEST

    @staticmethod
    def get_current_billing_period() -> str:
        """Returns the current billing cycle format (defaults to UTC YYYY-MM)."""
        now = datetime.datetime.now(datetime.timezone.utc)
        return now.strftime("%Y-%m")

    async def get_period_summary(
        self,
        db: AsyncSession,
        period: Optional[str] = None,
    ) -> BudgetPeriodSummary:
        """Calculates accurate aggregate spending and allowance for the billing period."""
        target_period = period or self.get_current_billing_period()

        stmt = select(
            func.count(WebzUsageLedger.id),
            func.coalesce(func.sum(case((WebzUsageLedger.success.is_(True), 1), else_=0)), 0),
            func.coalesce(func.sum(WebzUsageLedger.returned_count), 0),
            func.coalesce(func.sum(WebzUsageLedger.billable_count), 0),
            func.coalesce(
                func.sum(
                    func.coalesce(WebzUsageLedger.actual_cost, WebzUsageLedger.estimated_cost)
                ),
                Decimal("0.0000"),
            ),
        ).where(WebzUsageLedger.billing_period == target_period)

        row = (await db.execute(stmt)).one()
        total_reqs = int(row[0] or 0)
        success_reqs = int(row[1] or 0)
        returned_count = int(row[2] or 0)
        billable_count = int(row[3] or 0)
        total_spent = Decimal(str(row[4] or "0.0000"))

        remaining = max(Decimal("0.0000"), self.collection_ceiling - total_spent)
        can_reserve = remaining >= self.cost_per_request

        return BudgetPeriodSummary(
            billing_period=target_period,
            total_requests=total_reqs,
            successful_requests=success_reqs,
            total_returned_articles=returned_count,
            total_billable_articles=billable_count,
            total_spent=total_spent,
            monthly_credit=self.monthly_credit,
            collection_ceiling=self.collection_ceiling,
            protected_reserve=self.protected_reserve,
            remaining_allowance=remaining,
            can_reserve_next_request=can_reserve,
        )

    async def preflight_check(
        self,
        db: AsyncSession,
        estimated_cost: Optional[Decimal] = None,
        period: Optional[str] = None,
    ) -> PreflightResult:
        """Evaluates whether a new API request can safely be reserved and executed.
        
        Enforces:
        - Owner emergency disable switch
        - Credential verification
        - $4.00 collection ceiling
        - $1.00 emergency protected reserve
        """
        cost = estimated_cost or self.cost_per_request

        # 1. Owner immediate toggle check
        if not settings.WEBZ_IO_COLLECTION_ENABLED:
            logger.warning("[BUDGET PREFLIGHT] News collection is disabled by configuration (WEBZ_IO_COLLECTION_ENABLED=False).")
            return PreflightResult(
                allowed=False,
                stop_reason="COLLECTION_DISABLED_BY_OWNER",
                remaining_allowance=Decimal("0.0000"),
                estimated_cost=cost,
            )

        # 2. Token availability check
        if not settings.WEBZ_IO_API_KEY or not settings.WEBZ_IO_API_KEY.strip():
            logger.warning("[BUDGET PREFLIGHT] Webz.io API token is missing or empty.")
            return PreflightResult(
                allowed=False,
                stop_reason="CREDENTIALS_NOT_CONFIGURED",
                remaining_allowance=Decimal("0.0000"),
                estimated_cost=cost,
            )

        summary = await self.get_period_summary(db=db, period=period)

        # 3. Ceilings and reserve checks
        if summary.total_spent >= self.collection_ceiling:
            logger.warning(
                f"[BUDGET PREFLIGHT] Monthly collection ceiling of ${self.collection_ceiling} "
                f"reached (spent=${summary.total_spent}). Preserving ${self.protected_reserve} emergency reserve."
            )
            return PreflightResult(
                allowed=False,
                stop_reason="MONTHLY_COLLECTION_CEILING_REACHED",
                remaining_allowance=Decimal("0.0000"),
                estimated_cost=cost,
            )

        if summary.total_spent + cost > self.collection_ceiling:
            logger.warning(
                f"[BUDGET PREFLIGHT] Cannot safely reserve ${cost} for next request without "
                f"exceeding ${self.collection_ceiling} allowance ceiling (spent=${summary.total_spent})."
            )
            return PreflightResult(
                allowed=False,
                stop_reason="INSUFFICIENT_COLLECTION_ALLOWANCE",
                remaining_allowance=summary.remaining_allowance,
                estimated_cost=cost,
            )

        return PreflightResult(
            allowed=True,
            stop_reason=None,
            remaining_allowance=summary.remaining_allowance,
            estimated_cost=cost,
        )

    async def reserve_request(
        self,
        db: AsyncSession,
        job_name: str,
        endpoint: str,
        query_params: Optional[str] = None,
        estimated_cost: Optional[Decimal] = None,
        period: Optional[str] = None,
    ) -> WebzUsageLedger:
        """Creates a pending ledger record reserving estimated cost for the upcoming request.
        
        Uses an in-process lock and PostgreSQL transaction advisory lock (when running on
        PostgreSQL) to prevent duplicate concurrent budget reservations from exceeding
        the monthly collection ceiling.
        """
        cost = estimated_cost or self.cost_per_request
        target_period = period or self.get_current_billing_period()

        async with _budget_reservation_lock:
            bind = db.get_bind()
            if bind is not None and bind.dialect.name == "postgresql":
                await db.execute(text("SELECT pg_advisory_xact_lock(948271)"))

            summary = await self.get_period_summary(db=db, period=target_period)
            if summary.total_spent + cost > self.collection_ceiling:
                raise WebzBudgetExceededError(
                    f"Cannot reserve ${cost}: would exceed ${self.collection_ceiling} ceiling "
                    f"(currently spent=${summary.total_spent})."
                )
            new_remaining = max(Decimal("0.0000"), summary.remaining_allowance - cost)

            entry = WebzUsageLedger(
                billing_period=target_period,
                job_name=job_name,
                endpoint=endpoint,
                query_params=query_params,
                status_code=None,
                success=False,
                returned_count=0,
                billable_count=0,
                estimated_cost=cost,
                actual_cost=None,
                reserved_cost=cost,
                requests_left=None,
                credits_used=None,
                remaining_allowance=new_remaining,
                stop_reason=None,
                error_message=None,
            )
            db.add(entry)
            await db.commit()
            await db.refresh(entry)
            logger.info(
                f"[BUDGET RESERVATION] Reserved ${cost} for job='{job_name}', entry_id={entry.id}. "
                f"Remaining allowance: ${new_remaining}"
            )
            return entry

    async def finalize_ledger_entry(
        self,
        db: AsyncSession,
        entry: WebzUsageLedger,
        status_code: Optional[int],
        response: Optional[WebzResponse] = None,
        actual_cost: Optional[Decimal] = None,
        stop_reason: Optional[str] = None,
        error_message: Optional[str] = None,
    ) -> WebzUsageLedger:
        """Updates the reserved ledger record with verified API response metrics and final costs."""
        entry.status_code = status_code
        entry.success = bool(status_code and 200 <= status_code < 300)
        entry.stop_reason = stop_reason
        entry.error_message = error_message

        if response:
            entry.returned_count = len(response.posts)
            entry.billable_count = len(response.posts)
            entry.requests_left = response.requests_left
            if response.cost is not None:
                entry.actual_cost = response.cost
            elif actual_cost is not None:
                entry.actual_cost = actual_cost
            if response.credits_used is not None:
                entry.credits_used = response.credits_used

        # Recompute remaining allowance based on finalized entry
        summary = await self.get_period_summary(db=db, period=entry.billing_period)
        entry.remaining_allowance = summary.remaining_allowance

        await db.commit()
        await db.refresh(entry)
        logger.info(
            f"[BUDGET FINALIZED] Ledger entry #{entry.id} updated: success={entry.success}, "
            f"status={entry.status_code}, returned={entry.returned_count}, "
            f"actual_cost={entry.actual_cost}, remaining_allowance=${entry.remaining_allowance}"
        )
        return entry
