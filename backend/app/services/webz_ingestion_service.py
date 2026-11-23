import datetime
import json
from typing import Any, Dict, List, Optional
from sqlalchemy import select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.config import settings
from app.core.logging import logger
from app.integrations.webz.client import (
    WebzClient,
    WebzError,
    WebzAuthenticationError,
    WebzRateLimitError,
    WebzRequestError,
)
from app.integrations.webz.parser import normalize_webz_post
from app.integrations.webz.schemas import NormalizedWebzArticle, WebzResponse
from app.models.article import NewsArticle
from app.models.source import NewsSource
from app.models.ingestion import DiscoveryIngestionRun
from app.repositories.category_repository import get_all_categories_map
from app.repositories.ingestion_repository import create_ingestion_run, update_ingestion_run
from app.repositories.source_repository import get_or_create_source
from app.services.article_validation_service import ArticleEditorialValidationService
from app.services.budget_service import BudgetProtectionService
from app.services.deduplication_service import check_duplicate_hashes, find_near_duplicate
from app.services.editorial_intelligence_service import EditorialIntelligenceService
from app.services.normalizer_service import EDITORIAL_AUTHOR, generate_slug
from app.services.quality_service import QualityScoringService
from app.services.relevance_service import RelevanceService


class WebzIngestionService:
    """Orchestrates Webz.io news acquisition with durable budget protection,
    strict schema validation, metadata-only copyright compliance, and persistence.
    """

    def __init__(
        self,
        client: Optional[WebzClient] = None,
        budget_service: Optional[BudgetProtectionService] = None,
        quality_service: Optional[QualityScoringService] = None,
        relevance_service: Optional[RelevanceService] = None,
        editorial_service: Optional[EditorialIntelligenceService] = None,
    ):
        self.client = client or WebzClient()
        self.budget_service = budget_service or BudgetProtectionService()
        self.quality_service = quality_service or QualityScoringService()
        self.relevance_service = relevance_service or RelevanceService(
            min_quality_threshold=settings.INGESTION_MIN_QUALITY_SCORE
        )
        self.editorial_service = editorial_service or EditorialIntelligenceService()

    async def run_category_collection(
        self,
        db: AsyncSession,
        category: str = "sports",
        job_name: str = "webz_collection_job",
        freshness_hours: int = 24,
        target_articles: int = 10,
    ) -> Dict[str, Any]:
        """Executes a single protected news acquisition cycle for a target category.
        
        Enforces:
        - Budget preflight check ($4.00 collection ceiling, $1.00 emergency reserve)
        - Ledger cost reservation before dispatch
        - Exactly one API call for up to 10 articles (no automatic pagination)
        - UUID and canonical URL deduplication
        - Rejection of malformed or invalid records
        - Metadata-only summary storage (strict copyright protection)
        """
        stats: Dict[str, Any] = {
            "status": "pending",
            "category": category,
            "fetched": 0,
            "inserted": 0,
            "duplicate": 0,
            "filtered": 0,
            "failed": 0,
            # Phase 5 Unified Operational Counters
            "articles_fetched": 0,
            "json_records_parsed": 0,
            "validation_passed": 0,
            "validation_rejected": 0,
            "duplicate_records_skipped": 0,
            "rights_validation_failures": 0,
            "database_insertion_failures": 0,
            "total_published": 0,
            "stop_reason": None,
            "ledger_id": None,
            "run_id": None,
            "error": None,
        }

        # 1. Budget Preflight
        preflight = await self.budget_service.preflight_check(db=db)
        if not preflight.allowed:
            stats["status"] = "budget_blocked"
            stats["stop_reason"] = preflight.stop_reason
            logger.warning(
                f"[WEBZ COLLECTION] Aborted collection for category '{category}': {preflight.stop_reason}"
            )
            return stats

        # 2. Record Ingestion Run & Ledger Reservation
        run = await create_ingestion_run(db, provider="webz")
        stats["run_id"] = run.id

        query_str, ts_ms = self.client.build_query(category=category, freshness_hours=freshness_hours)
        ledger_entry = await self.budget_service.reserve_request(
            db=db,
            job_name=job_name,
            endpoint=self.client.endpoint,
            query_params=f"category={category}&q={query_str}&ts={ts_ms}&size={target_articles}",
            estimated_cost=preflight.estimated_cost,
        )
        stats["ledger_id"] = ledger_entry.id

        # 3. Webz.io API Dispatch
        response: Optional[WebzResponse] = None
        status_code: Optional[int] = None
        stop_reason: Optional[str] = None
        error_msg: Optional[str] = None

        try:
            response = await self.client.fetch_news_articles(
                query=query_str,
                checkpoint_ts_ms=ts_ms,
                freshness_hours=freshness_hours,
                size=target_articles,
            )
            status_code = 200
        except WebzRateLimitError as rle:
            status_code = 429
            stop_reason = "RATE_LIMIT_EXCEEDED"
            error_msg = str(rle)
        except WebzAuthenticationError as ae:
            status_code = 401
            stop_reason = "AUTHENTICATION_FAILED"
            error_msg = str(ae)
        except WebzRequestError as re:
            status_code = 400
            stop_reason = "CLIENT_REQUEST_ERROR"
            error_msg = str(re)
        except Exception as exc:
            status_code = 500
            stop_reason = "NETWORK_OR_SERVER_ERROR"
            error_msg = str(exc)

        # 4. Finalize Budget Ledger
        await self.budget_service.finalize_ledger_entry(
            db=db,
            entry=ledger_entry,
            status_code=status_code,
            response=response,
            stop_reason=stop_reason,
            error_message=error_msg,
        )

        if not response or status_code != 200:
            stats["status"] = "failed"
            stats["stop_reason"] = stop_reason
            stats["error"] = error_msg
            await update_ingestion_run(
                db,
                run_id=run.id,
                status="failed",
                error_message=error_msg,
            )
            return stats

        stats["fetched"] = len(response.posts)
        stats["articles_fetched"] = len(response.posts)
        stats["json_records_parsed"] = len(response.posts)

        # 5. Validation and Normalization
        valid_articles: List[NormalizedWebzArticle] = []
        for post in response.posts:
            norm_art = normalize_webz_post(post, target_category=category)
            if norm_art:
                valid_articles.append(norm_art)
            else:
                stats["filtered"] += 1
                stats["validation_rejected"] += 1

        if not valid_articles:
            stats["status"] = "success"
            await update_ingestion_run(
                db,
                run_id=run.id,
                status="success",
                fetched=stats["fetched"],
                inserted=0,
                duplicate=0,
                filtered=stats["filtered"],
                failed=stats["failed"],
            )
            return stats

        # 6. Deduplication (UUID & Canonical URL Hash)
        candidate_uuids = {art.uuid for art in valid_articles}
        candidate_hashes = {art.canonical_url_hash for art in valid_articles}

        # Check existing UUIDs in PostgreSQL
        existing_uuids_stmt = select(NewsArticle.uuid).where(NewsArticle.uuid.in_(candidate_uuids))
        existing_uuids = set((await db.execute(existing_uuids_stmt)).scalars().all())

        # Check existing Canonical URL Hashes
        existing_hashes = await check_duplicate_hashes(db, candidate_hashes)

        # Check recent articles for near-duplicate headline matching
        recent_cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
        recent_stmt = (
            select(NewsArticle.id, NewsArticle.title, NewsSource.domain, NewsArticle.published_at)
            .join(NewsSource, NewsArticle.source_id == NewsSource.id, isouter=True)
            .where(NewsArticle.published_at >= recent_cutoff, NewsArticle.status == "published")
        )
        recent_rows = (await db.execute(recent_stmt)).all()
        recent_articles_list = [(r[0], r[1], r[2] or "", r[3]) for r in recent_rows]

        # 7. Category and Source Mapping
        # Classify each article individually rather than using a single collection-level category
        category_map = await get_all_categories_map(db)
        cat_obj = category_map.get(category.lower())
        category_id = cat_obj.id if cat_obj else None

        seen_in_batch_uuids: set[str] = set()
        seen_in_batch_hashes: set[str] = set()
        for art in valid_articles:
            # Duplicate checks
            if art.uuid in existing_uuids or art.uuid in seen_in_batch_uuids:
                stats["duplicate"] += 1
                stats["duplicate_records_skipped"] += 1
                continue
            if art.canonical_url_hash in existing_hashes or art.canonical_url_hash in seen_in_batch_hashes:
                stats["duplicate"] += 1
                stats["duplicate_records_skipped"] += 1
                continue

            seen_in_batch_uuids.add(art.uuid)
            seen_in_batch_hashes.add(art.canonical_url_hash)

            # Near-duplicate check
            near_dup = find_near_duplicate(
                candidate_title=art.title,
                candidate_domain=art.domain,
                candidate_published_at=art.published_at,
                recent_articles=recent_articles_list,
            )
            if near_dup:
                logger.info(f"Skipping near-duplicate article '{art.title[:50]}...': {near_dup[2]}")
                stats["duplicate"] += 1
                stats["duplicate_records_skipped"] += 1
                continue

            # Rights tracking
            if not getattr(art, "content_display_authorized", False) or not getattr(art, "hero_image_authorized", False):
                stats["rights_validation_failures"] += 1

            # Quality Scoring & Relevance Gate
            quality = self.quality_service.score_article(
                title=art.title,
                canonical_url=art.canonical_url,
                domain=art.domain,
                snippet=art.summary,
                published_at=art.published_at,
                category_confidence=getattr(art, "classification_confidence", 0) or 6,
            )
            filter_decision = self.relevance_service.evaluate_article(
                title=art.title,
                country=art.country,
                language=art.language,
                domain=art.domain,
                snippet=art.summary,
                quality_score=quality.score,
            )
            article_status = "published" if filter_decision.is_admissible else "filtered"
            article_filter_reason = None if filter_decision.is_admissible else filter_decision.filter_reason

            # Editorial Quality Gate Validation
            val_result = ArticleEditorialValidationService.evaluate_candidate(
                title=art.title,
                canonical_url=art.canonical_url,
                published_at=art.published_at,
                domain=art.domain,
                category_slug=art.category_slug,
                summary=art.summary,
                full_text=getattr(art, "full_text", None),
                publisher_name=getattr(art, "publisher_name", None),
                author=art.author,
                image_url=art.image_url,
                language=art.language,
                content_display_authorized=getattr(art, "content_display_authorized", True),
            )

            # Strict Hero Image MIME Response & SSRF Network Safety Validation
            if filter_decision.is_admissible and val_result.is_valid and art.image_url:
                from app.services.image_validation_service import ImageValidationService
                img_mime_ok, img_mime_err = await ImageValidationService.validate_image_response_async(
                    art.image_url,
                )
                if not img_mime_ok:
                    val_result.is_valid = False
                    val_result.status = "filtered"
                    val_result.filter_reason = f"Featured hero image response failed validation: {img_mime_err}"

            # Strict Pre-Insertion Editorial Acceptance Gate
            if not filter_decision.is_admissible or not val_result.is_valid:
                article_status = "filtered"
                article_filter_reason = val_result.filter_reason or filter_decision.filter_reason or "Failed editorial validation"
                logger.warning(
                    f"REJECTED from publication: '{art.title[:50]}' "
                    f"(domain: {art.domain}, reason: {article_filter_reason})"
                )
            else:
                try:
                    from app.schemas.canonical_article import CanonicalMetroScopeArticle
                    CanonicalMetroScopeArticle(
                        uuid=art.uuid,
                        title=art.title,
                        canonical_url=art.canonical_url,
                        canonical_url_hash=art.canonical_url_hash,
                        domain=art.domain,
                        publisher_name=val_result.cleaned_publisher or art.domain,
                        published_at=art.published_at,
                        category_slug=art.category_slug,
                        language=art.language,
                        author=EDITORIAL_AUTHOR,
                        summary=val_result.cleaned_summary,
                        full_text=val_result.cleaned_full_text or "",
                        country=art.country,
                        content_display_authorized=True,
                        image_url=art.image_url or "",
                        hero_image_authorized=True,
                    )
                    article_status = "published"
                    article_filter_reason = None
                except Exception as exc:
                    article_status = "filtered"
                    article_filter_reason = f"Canonical schema validation error: {exc}"
                    logger.warning(
                        f"REJECTED from publication (canonical schema): '{art.title[:50]}' ({article_filter_reason})"
                    )

            final_summary = val_result.cleaned_summary if val_result.cleaned_summary else art.summary
            final_full_text = val_result.cleaned_full_text if val_result.cleaned_full_text else getattr(art, "full_text", None)
            final_publisher = val_result.cleaned_publisher or getattr(art, "publisher_name", None)
            final_author = EDITORIAL_AUTHOR

            # Resolve / Create Source using normalized publisher name
            publisher_display = final_publisher or art.domain
            source = await get_or_create_source(
                db=db,
                domain=art.domain,
                name=publisher_display,
                country=art.country,
                language=art.language,
            )

            # Per-article category classification (overrides collection-level default)
            art_cat_slug = art.category_slug
            art_cat_obj = category_map.get(art_cat_slug)
            art_category_id = art_cat_obj.id if art_cat_obj else category_id

            # Generate Unique Slug
            base_slug = generate_slug(art.title, max_length=80)
            unique_slug = f"{base_slug}-{art.canonical_url_hash[:8]}"

            # Construct NewsArticle adhering to content rights & persistence
            new_article = NewsArticle(
                title=art.title,
                slug=unique_slug,
                description=final_summary,
                full_text=final_full_text,
                content_display_authorized=getattr(art, "content_display_authorized", True),
                source_id=source.id,
                category_id=art_category_id,
                original_url=art.original_url,
                canonical_url=art.canonical_url,
                canonical_url_hash=art.canonical_url_hash,
                uuid=art.uuid,
                author=final_author,
                publisher_name=final_publisher,
                image_url=art.image_url,
                topics=json.dumps(art.topics) if art.topics else None,
                webz_categories=json.dumps(getattr(art, "webz_categories", [])) if getattr(art, "webz_categories", None) else None,
                trust_indicators=json.dumps(art.trust_indicators) if art.trust_indicators else None,
                image_metadata=json.dumps(art.image_metadata) if art.image_metadata else None,
                language=art.language,
                country=art.country,
                published_at=art.published_at,
                crawled_at=getattr(art, "crawled_at", None),
                discovered_at=datetime.datetime.now(datetime.timezone.utc),
                status=article_status,
                quality_score=quality.score,
                is_trending=False,
                is_breaking=getattr(art, "is_breaking", False),
                sentiment=getattr(art, "sentiment", None),
                cluster_id=None,
                filter_reason=article_filter_reason,
            )
            db.add(new_article)
            if article_status == "published":
                stats["inserted"] += 1
                stats["total_published"] += 1
                stats["validation_passed"] += 1
                recent_articles_list.append((0, art.title, art.domain, art.published_at))
            else:
                stats["filtered"] += 1
                stats["validation_rejected"] += 1

        # 8. Commit articles
        try:
            await db.commit()
        except Exception as commit_exc:
            await db.rollback()
            logger.error(f"[WEBZ COLLECTION] DB commit failed during collection: {commit_exc}")
            stats["database_insertion_failures"] += 1
            stats["failed"] += 1
            raise

        # 9. Update Editorial Intelligence (trending and breaking clusters)
        await self._update_editorial_intelligence(db)

        # 10. Update Ingestion Run Tracking
        stats["status"] = "success" if stats["failed"] == 0 else "partial"
        await update_ingestion_run(
            db,
            run_id=run.id,
            status=stats["status"],
            fetched=stats["fetched"],
            inserted=stats["inserted"],
            duplicate=stats["duplicate"],
            filtered=stats["filtered"],
            failed=stats["failed"],
        )

        logger.info(
            f"[WEBZ COLLECTION] Job '{job_name}' completed: category='{category}', "
            f"fetched={stats['fetched']}, inserted={stats['inserted']}, "
            f"duplicate={stats['duplicate']}, failed={stats['failed']}"
        )
        return stats

    async def _update_editorial_intelligence(self, db: AsyncSession) -> None:
        """Evaluates recent published articles for multi-source trending and breaking clusters."""
        try:
            recent_cutoff = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(hours=24)
            stmt = (
                select(NewsArticle.id, NewsArticle.title, NewsSource.domain, NewsArticle.published_at)
                .join(NewsSource, NewsArticle.source_id == NewsSource.id, isouter=True)
                .where(NewsArticle.published_at >= recent_cutoff, NewsArticle.status == "published")
                .order_by(NewsArticle.published_at.desc())
                .limit(100)
            )
            rows = (await db.execute(stmt)).all()
            if not rows:
                return

            article_dicts = [
                {
                    "id": r[0],
                    "title": r[1],
                    "domain": r[2] or "",
                    "published_at": r[3],
                }
                for r in rows
            ]

            cluster_results = self.editorial_service.analyze_articles(article_dicts)
            updated_count = 0

            for art_id, flags in cluster_results.items():
                if flags["is_trending"] or flags["is_breaking"] or flags["cluster_id"]:
                    up_stmt = (
                        update(NewsArticle)
                        .where(NewsArticle.id == art_id)
                        .values(
                            is_trending=flags["is_trending"],
                            is_breaking=flags["is_breaking"],
                            cluster_id=flags["cluster_id"],
                        )
                    )
                    await db.execute(up_stmt)
                    updated_count += 1

            if updated_count > 0:
                await db.commit()
                logger.info(f"Editorial Intelligence updated {updated_count} articles with clusters")

        except Exception as exc:
            logger.warning(f"Editorial Intelligence clustering encountered non-fatal issue: {exc}")
