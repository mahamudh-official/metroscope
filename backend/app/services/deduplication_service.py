"""Deduplication and Near-Duplicate Detection Service for MetroScope.

Primary: Exact Canonical URL SHA-256 Hash Matching (zero false positives).
Secondary: Conservative Near-Duplicate Detection for syndicated wire copy
and publisher headline revisions within a 24-hour publication window.

CONSERVATIVE RULES:
- Different reports from independent journalists covering the same developing event
  must NOT be merged.
- Thresholds:
  * Same Domain + Jaccard Token Similarity >= 0.70 -> Near-Duplicate (headline revision/re-post).
  * Cross Domain + Jaccard Token Similarity >= 0.85 -> Syndicated Wire Copy.
  * Cross Domain + Jaccard Token Similarity < 0.85 -> Independent reporting (preserved!).
"""

import datetime
import re
from typing import List, Optional, Set, Tuple
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from app.models.article import NewsArticle

STOPWORDS: Set[str] = {
    "a", "an", "the", "in", "on", "at", "to", "for", "of", "and", "or",
    "is", "are", "was", "were", "be", "been", "being", "with", "by", "from",
    "as", "into", "through", "after", "over", "between", "out", "against",
    "during", "without", "before", "under", "around", "among", "this", "that",
    "these", "those", "it", "its", "they", "them", "their", "we", "us", "our",
    "he", "him", "his", "she", "her", "you", "your", "who", "which", "what",
    "says", "said", "new", "report", "update", "video", "photos",
}


def tokenize_title(title: str) -> Set[str]:
    """Extracts normalized significant alphanumeric tokens from an article title."""
    if not title:
        return set()
    # Normalize decimal numbers like 7.2 -> 7_2 to keep magnitude/version tokens
    cleaned = re.sub(r"(\d+)\.(\d+)", r"\1_\2", title.lower())
    raw_tokens = re.findall(r"\b[a-z0-9_]{2,}\b", cleaned)
    tokens = set()
    for t in raw_tokens:
        if t in STOPWORDS:
            continue
        # Light stemming: normalize common trailing 's' (e.g. cuts->cut, rates->rate, strikes->strike, holds->hold)
        # Preserve words ending in 'ss' or 'sses' (e.g. pass, passes, glass)
        if len(t) > 3 and t.endswith("s") and not t.endswith("ss") and not t.endswith("sses"):
            t = t[:-1]
        tokens.add(t)
    return tokens


def calculate_jaccard_similarity(tokens_a: Set[str], tokens_b: Set[str]) -> float:
    """Calculates standard Jaccard token similarity: |A ∩ B| / |A ∪ B|."""
    if not tokens_a or not tokens_b:
        return 0.0
    intersection = len(tokens_a.intersection(tokens_b))
    union = len(tokens_a.union(tokens_b))
    if union == 0:
        return 0.0
    return round(intersection / union, 4)


def find_near_duplicate(
    candidate_title: str,
    candidate_domain: str,
    candidate_published_at: Optional[datetime.datetime],
    recent_articles: List[Tuple[int, str, str, Optional[datetime.datetime]]],
    same_domain_threshold: float = 0.70,
    cross_domain_threshold: float = 0.85,
    max_time_delta_hours: int = 24,
) -> Optional[Tuple[int, float, str]]:
    """Evaluates candidate article against recent published articles for near-duplicate match.
    
    recent_articles: list of (article_id, title, domain, published_at)
    
    Returns:
        (matched_article_id, similarity_score, decision_reason) if near-duplicate found,
        or None if the candidate is considered independent reporting.
    """
    candidate_tokens = tokenize_title(candidate_title)
    if len(candidate_tokens) < 3:
        return None

    cand_domain = (candidate_domain or "").lower()

    for art_id, prev_title, prev_domain, prev_published_at in recent_articles:
        # Time window check (if timestamps available, timezone-safe)
        if candidate_published_at and prev_published_at:
            cand_pub = (
                candidate_published_at
                if candidate_published_at.tzinfo is not None
                else candidate_published_at.replace(tzinfo=datetime.timezone.utc)
            )
            prev_pub = (
                prev_published_at
                if prev_published_at.tzinfo is not None
                else prev_published_at.replace(tzinfo=datetime.timezone.utc)
            )
            delta_seconds = abs((cand_pub - prev_pub).total_seconds())
            if delta_seconds > (max_time_delta_hours * 3600):
                continue

        prev_tokens = tokenize_title(prev_title)
        similarity = calculate_jaccard_similarity(candidate_tokens, prev_tokens)

        # Case 1: Same publisher domain (re-published or updated headline)
        if cand_domain and prev_domain and cand_domain == prev_domain.lower():
            if similarity >= same_domain_threshold:
                return (
                    art_id,
                    similarity,
                    f"Same-domain headline revision (similarity={similarity:.2f} >= {same_domain_threshold})",
                )

        # Case 2: Cross-domain identical syndicated wire copy
        if similarity >= cross_domain_threshold:
            return (
                art_id,
                similarity,
                f"Syndicated cross-domain wire copy (similarity={similarity:.2f} >= {cross_domain_threshold})",
            )

    return None


async def check_duplicate_hashes(
    db: AsyncSession, hashes: Set[str]
) -> Set[str]:
    """Returns the subset of canonical URL hashes that already exist in the database."""
    if not hashes:
        return set()

    stmt = select(NewsArticle.canonical_url_hash).where(
        NewsArticle.canonical_url_hash.in_(hashes)
    )
    result = await db.execute(stmt)
    existing_hashes = {row[0] for row in result.all()}
    return existing_hashes


async def is_duplicate_hash(db: AsyncSession, url_hash: str) -> bool:
    """Checks whether a single canonical URL hash already exists."""
    stmt = select(NewsArticle.id).where(NewsArticle.canonical_url_hash == url_hash).limit(1)
    result = await db.execute(stmt)
    return result.scalar_one_or_none() is not None
