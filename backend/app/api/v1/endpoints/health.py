import datetime
from fastapi import APIRouter, Depends, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.v1.endpoints.social import verify_operator_auth
from app.core.config import settings
from app.db.session import check_db_connection, get_db
from app.models.article import NewsArticle
from app.models.ingestion import DiscoveryIngestionRun
from app.models.newsletter import EmailSubscriber
from app.models.social import SocialPost
from app.models.webz_ledger import WebzUsageLedger
from app.schemas.health import (
    HealthResponse,
    LivenessResponse,
    OperationalStatusResponse,
    ReadinessResponse,
    SystemMetricsResponse,
)

router = APIRouter()


@router.get(
    "/health",
    response_model=HealthResponse,
    summary="API Health Status",
    description="Returns current application operational status and database connection state.",
)
async def health_check() -> HealthResponse:
    db_ok = await check_db_connection()
    return HealthResponse(
        status="ok" if db_ok else "degraded",
        environment=settings.ENVIRONMENT,
        database_connected=db_ok,
        version="0.1.0",
    )


@router.get(
    "/health/live",
    response_model=LivenessResponse,
    summary="Process Liveness Probe",
    description="Returns 200 OK immediately if the FastAPI worker process is running.",
)
async def liveness_check() -> LivenessResponse:
    return LivenessResponse(
        status="alive",
        timestamp=datetime.datetime.now(datetime.timezone.utc).isoformat(),
    )


@router.get(
    "/health/ready",
    response_model=ReadinessResponse,
    summary="Container Readiness Probe",
    description="Verifies database connectivity before routing inbound traffic. Returns 503 if not ready.",
)
async def readiness_check(response: Response) -> ReadinessResponse:
    db_ok = await check_db_connection(timeout_seconds=2.0)
    if not db_ok:
        response.status_code = status.HTTP_503_SERVICE_UNAVAILABLE
        return ReadinessResponse(
            status="unready",
            database_ready=False,
            detail="Database connection probe failed",
        )
    return ReadinessResponse(
        status="ready",
        database_ready=True,
        detail="All core subsystems ready",
    )


@router.get(
    "/health/metrics",
    response_model=SystemMetricsResponse,
    summary="Operational Subsystem Metrics",
    description="Provides high-level operational counts without exposing credentials or internal topology.",
)
async def metrics_check(db: AsyncSession = Depends(get_db)) -> SystemMetricsResponse:
    try:
        art_count_stmt = select(func.count(NewsArticle.id)).where(NewsArticle.status == "published")
        art_count_res = await db.execute(art_count_stmt)
        total_articles = art_count_res.scalar() or 0

        sub_count_stmt = select(func.count(EmailSubscriber.id)).where(EmailSubscriber.status == "active")
        sub_count_res = await db.execute(sub_count_stmt)
        active_subscribers = sub_count_res.scalar() or 0
        db_ok = True
    except Exception:
        total_articles = 0
        active_subscribers = 0
        db_ok = False

    return SystemMetricsResponse(
        environment=settings.ENVIRONMENT,
        version="0.1.0",
        database_connected=db_ok,
        total_articles=total_articles,
        active_subscribers=active_subscribers,
        social_dry_run=settings.SOCIAL_DRY_RUN,
        email_dry_run=settings.EMAIL_DRY_RUN,
        worker_enabled=settings.WORKER_ENABLED,
    )


@router.get(
    "/health/ops",
    response_model=OperationalStatusResponse,
    summary="Complete Operational and Pipeline Status",
    description="Provides real-time operational status covering scheduler, ingestion runs, article counts, filter reasons, API credit usage, and social publishing states. Requires operator authorization.",
    dependencies=[Depends(verify_operator_auth)],
)
async def ops_status_check(
    db: AsyncSession = Depends(get_db),
    is_operator: bool = Depends(verify_operator_auth),
) -> OperationalStatusResponse:
    db_ok = await check_db_connection()

    scheduler_info = {
        "configured": True,
        "worker_enabled": settings.WORKER_ENABLED,
        "timezone": settings.WEBZ_IO_TIMEZONE,
        "collection_jobs": {
            "webz_morning_collection": "08:00 Asia/Dhaka (Daily General Collection)",
            "webz_evening_business": "20:00 Asia/Dhaka (Daily Business & Markets Collection)",
        },
        "social_publishing_job": f"Interval ({settings.SOCIAL_PUBLISHING_INTERVAL_MINUTES}m)",
        "newsletter_job": f"Daily at {settings.NEWSLETTER_SCHEDULE_HOUR:02d}:{settings.NEWSLETTER_SCHEDULE_MINUTE:02d} UTC",
    }

    ingestion_info: dict = {
        "last_run": None,
        "total_runs": 0,
    }
    recent_errors: list[str] = []

    articles_summary: dict = {
        "total": 0,
        "published": 0,
        "filtered": 0,
        "filter_reasons": {},
    }

    api_usage: dict = {
        "provider": "Webz.io",
        "monthly_budget_ceiling": "$4.00",
        "emergency_reserve": "$1.00",
        "billing_period": datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m"),
        "total_requests": 0,
        "billable_requests": 0,
        "estimated_cost_total": "0.0000",
        "actual_cost_total": "0.0000",
        "remaining_allowance": "4.0000",
        "requests_left": None,
    }

    fb_configured = bool(
        settings.FACEBOOK_PAGE_ID
        and settings.FACEBOOK_PAGE_ACCESS_TOKEN
        and not settings.FACEBOOK_PAGE_ID.startswith("your_")
    )
    x_configured = bool(
        settings.X_API_KEY
        and settings.X_ACCESS_TOKEN
        and not settings.X_API_KEY.startswith("your_")
    )

    social_info: dict = {
        "global_enabled": settings.SOCIAL_PUBLISHING_ENABLED,
        "dry_run": settings.SOCIAL_DRY_RUN,
        "facebook": {
            "enabled": settings.FACEBOOK_ENABLED,
            "configured": fb_configured,
            "page_id": (
                f"{settings.FACEBOOK_PAGE_ID[:4]}...{settings.FACEBOOK_PAGE_ID[-4:]}"
                if fb_configured and settings.FACEBOOK_PAGE_ID
                else "UNCONFIGURED"
            ),
            "published": 0,
            "pending": 0,
            "failed": 0,
        },
        "x": {
            "enabled": settings.X_ENABLED,
            "configured": x_configured,
            "api_key": (
                f"{settings.X_API_KEY[:4]}...{settings.X_API_KEY[-4:]}"
                if x_configured and settings.X_API_KEY
                else "UNCONFIGURED"
            ),
            "published": 0,
            "pending": 0,
            "failed": 0,
        },
    }

    if db_ok:
        try:
            # 1. Ingestion runs
            run_stmt = select(DiscoveryIngestionRun).order_by(DiscoveryIngestionRun.id.desc()).limit(1)
            last_run = (await db.execute(run_stmt)).scalar_one_or_none()
            total_runs_stmt = select(func.count(DiscoveryIngestionRun.id))
            total_runs = (await db.execute(total_runs_stmt)).scalar() or 0

            if last_run:
                ingestion_info["last_run"] = {
                    "id": last_run.id,
                    "started_at": last_run.started_at.isoformat() if last_run.started_at else None,
                    "completed_at": last_run.completed_at.isoformat() if last_run.completed_at else None,
                    "status": last_run.status,
                    "fetched": last_run.fetched_count,
                    "inserted": last_run.inserted_count,
                    "filtered": last_run.filtered_count,
                    "failed": last_run.failed_count,
                    "error": last_run.error_message,
                }
                if last_run.error_message:
                    recent_errors.append(f"Ingestion run #{last_run.id}: {last_run.error_message}")
            ingestion_info["total_runs"] = total_runs

            # 2. Article counts & filter breakdown
            art_tot_stmt = select(func.count(NewsArticle.id))
            articles_summary["total"] = (await db.execute(art_tot_stmt)).scalar() or 0

            art_pub_stmt = select(func.count(NewsArticle.id)).where(NewsArticle.status == "published")
            articles_summary["published"] = (await db.execute(art_pub_stmt)).scalar() or 0

            art_fil_stmt = select(func.count(NewsArticle.id)).where(NewsArticle.status == "filtered")
            articles_summary["filtered"] = (await db.execute(art_fil_stmt)).scalar() or 0

            reasons_stmt = (
                select(NewsArticle.filter_reason, func.count(NewsArticle.id))
                .where(NewsArticle.status == "filtered")
                .group_by(NewsArticle.filter_reason)
            )
            reasons_rows = (await db.execute(reasons_stmt)).all()
            for r, count in reasons_rows:
                articles_summary["filter_reasons"][r or "Unspecified"] = count

            # 3. API Usage from Ledger
            period = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m")
            ledger_stmt = (
                select(
                    func.count(WebzUsageLedger.id),
                    func.coalesce(func.sum(WebzUsageLedger.billable_count), 0),
                    func.coalesce(func.sum(WebzUsageLedger.estimated_cost), 0),
                    func.coalesce(func.sum(WebzUsageLedger.actual_cost), 0),
                )
                .where(WebzUsageLedger.billing_period == period)
            )
            l_row = (await db.execute(ledger_stmt)).first()
            if l_row:
                api_usage["total_requests"] = l_row[0]
                api_usage["billable_requests"] = l_row[1]
                api_usage["estimated_cost_total"] = str(l_row[2])
                api_usage["actual_cost_total"] = str(l_row[3])

            latest_l_stmt = select(WebzUsageLedger).order_by(WebzUsageLedger.id.desc()).limit(1)
            latest_l = (await db.execute(latest_l_stmt)).scalar_one_or_none()
            if latest_l:
                api_usage["remaining_allowance"] = str(latest_l.remaining_allowance)
                api_usage["requests_left"] = latest_l.requests_left
                if latest_l.error_message:
                    recent_errors.append(f"Webz API error: {latest_l.error_message}")

            # 4. Social counts
            for plat in ("facebook", "x"):
                pub_c = (await db.execute(select(func.count(SocialPost.id)).where(SocialPost.platform == plat, SocialPost.status == "PUBLISHED"))).scalar() or 0
                pen_c = (await db.execute(select(func.count(SocialPost.id)).where(SocialPost.platform == plat, SocialPost.status.in_(["PENDING", "PUBLISHING"])))).scalar() or 0
                fai_c = (await db.execute(select(func.count(SocialPost.id)).where(SocialPost.platform == plat, SocialPost.status.in_(["FAILED", "FAILED_AMBIGUOUS"])))).scalar() or 0
                social_info[plat]["published"] = pub_c
                social_info[plat]["pending"] = pen_c
                social_info[plat]["failed"] = fai_c

        except Exception as exc:
            recent_errors.append(f"Diagnostics error: {str(exc)}")

    return OperationalStatusResponse(
        environment=settings.ENVIRONMENT,
        version="0.1.0",
        database_connected=db_ok,
        scheduler=scheduler_info,
        ingestion=ingestion_info,
        articles_summary=articles_summary,
        api_usage=api_usage,
        social_publishing=social_info,
        recent_errors=recent_errors[:5],
    )
