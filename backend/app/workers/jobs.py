import asyncio
import datetime
from typing import Any, Dict
from app.core.config import settings
from app.core.logging import logger
from app.db.session import async_session_factory
from app.services.webz_ingestion_service import WebzIngestionService

# Single execution lock to guarantee strictly sequential, non-overlapping collection runs
_webz_collection_lock = asyncio.Lock()


async def collect_webz_morning_job() -> Dict[str, Any]:
    """Scheduled morning news acquisition job (08:00 Asia/Dhaka).
    
    Executes the confirmed Webz.io query covering Business, Finance/Economy,
    Science, and Technology (with per-article editorial classification and English filtering).
    """
    if _webz_collection_lock.locked():
        logger.warning(
            "[WEBZ SCHEDULER] Morning collection skipped: another collection job is currently in progress."
        )
        return {"status": "skipped", "reason": "lock_busy"}

    async with _webz_collection_lock:
        start_time = datetime.datetime.now(datetime.timezone.utc)
        logger.info(f"[WEBZ SCHEDULER] Starting 08:00 Asia/Dhaka Morning collection cycle at {start_time.isoformat()}...")

        try:
            async with async_session_factory() as session:
                service = WebzIngestionService()
                results = await service.run_category_collection(
                    db=session,
                    category="confirmed",
                    job_name="webz_morning_collection",
                    freshness_hours=24,
                    target_articles=settings.WEBZ_IO_TARGET_ARTICLES_PER_JOB,
                )
                elapsed = (datetime.datetime.now(datetime.timezone.utc) - start_time).total_seconds()
                logger.info(
                    f"[WEBZ SCHEDULER] Morning collection completed in {elapsed:.2f}s: "
                    f"status={results.get('status')}, fetched={results.get('articles_fetched', results.get('fetched', 0))}, "
                    f"parsed={results.get('json_records_parsed', 0)}, passed={results.get('validation_passed', 0)}, "
                    f"rejected={results.get('validation_rejected', results.get('filtered', 0))}, "
                    f"skipped_dups={results.get('duplicate_records_skipped', results.get('duplicate', 0))}, "
                    f"rights_failures={results.get('rights_validation_failures', 0)}, "
                    f"published={results.get('total_published', results.get('inserted', 0))}, "
                    f"stop_reason={results.get('stop_reason')}"
                )
                return results
        except Exception as exc:
            logger.exception(f"[WEBZ SCHEDULER] Unexpected error during Morning collection: {exc}")
            return {"status": "error", "error": str(exc)}


# Backward-compatibility alias
collect_webz_sports_morning_job = collect_webz_morning_job


async def collect_webz_evening_job() -> Dict[str, Any]:
    """Scheduled evening news acquisition job: Business, Finance & Economy (20:00 Asia/Dhaka).
    
    Attempts to collect up to 10 eligible fresh articles using Webz.io News API.
    Protected by a single execution lock and durable PostgreSQL budget ledger.
    """
    if _webz_collection_lock.locked():
        logger.warning(
            "[WEBZ SCHEDULER] Evening Business collection skipped: another collection job is currently in progress."
        )
        return {"status": "skipped", "reason": "lock_busy"}

    async with _webz_collection_lock:
        start_time = datetime.datetime.now(datetime.timezone.utc)
        logger.info(f"[WEBZ SCHEDULER] Starting 20:00 Asia/Dhaka Business collection cycle at {start_time.isoformat()}...")

        try:
            async with async_session_factory() as session:
                service = WebzIngestionService()
                results = await service.run_category_collection(
                    db=session,
                    category="business",
                    job_name="webz_evening_business",
                    freshness_hours=24,
                    target_articles=settings.WEBZ_IO_TARGET_ARTICLES_PER_JOB,
                )
                elapsed = (datetime.datetime.now(datetime.timezone.utc) - start_time).total_seconds()
                logger.info(
                    f"[WEBZ SCHEDULER] Evening Business collection completed in {elapsed:.2f}s: "
                    f"status={results.get('status')}, fetched={results.get('articles_fetched', results.get('fetched', 0))}, "
                    f"parsed={results.get('json_records_parsed', 0)}, passed={results.get('validation_passed', 0)}, "
                    f"rejected={results.get('validation_rejected', results.get('filtered', 0))}, "
                    f"skipped_dups={results.get('duplicate_records_skipped', results.get('duplicate', 0))}, "
                    f"rights_failures={results.get('rights_validation_failures', 0)}, "
                    f"published={results.get('total_published', results.get('inserted', 0))}, "
                    f"stop_reason={results.get('stop_reason')}"
                )
                return results
        except Exception as exc:
            logger.exception(f"[WEBZ SCHEDULER] Unexpected error during Evening Business collection: {exc}")
            return {"status": "error", "error": str(exc)}


# Backward-compatibility alias
collect_webz_business_evening_job = collect_webz_evening_job
