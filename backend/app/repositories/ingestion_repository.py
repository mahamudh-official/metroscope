import datetime
from typing import Optional
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.ingestion import DiscoveryIngestionRun


async def create_ingestion_run(
    db: AsyncSession, provider: str = "webz"
) -> DiscoveryIngestionRun:
    """Creates a new tracking record for a discovery ingestion cycle."""
    run = DiscoveryIngestionRun(
        provider=provider,
        started_at=datetime.datetime.now(datetime.timezone.utc),
        status="running",
        fetched_count=0,
        inserted_count=0,
        duplicate_count=0,
        failed_count=0,
    )
    db.add(run)
    await db.commit()
    await db.refresh(run)
    return run


async def update_ingestion_run(
    db: AsyncSession,
    run_id: int,
    status: str,
    fetched: int = 0,
    inserted: int = 0,
    duplicate: int = 0,
    failed: int = 0,
    filtered: int = 0,
    error_message: Optional[str] = None,
) -> Optional[DiscoveryIngestionRun]:
    """Updates an ingestion run upon completion or failure."""
    stmt = select(DiscoveryIngestionRun).where(DiscoveryIngestionRun.id == run_id)
    result = await db.execute(stmt)
    run = result.scalar_one_or_none()
    if not run:
        return None

    run.status = status
    run.completed_at = datetime.datetime.now(datetime.timezone.utc)
    run.fetched_count = fetched
    run.inserted_count = inserted
    run.duplicate_count = duplicate
    run.filtered_count = filtered
    run.failed_count = failed
    run.error_message = error_message

    await db.commit()
    await db.refresh(run)
    return run
