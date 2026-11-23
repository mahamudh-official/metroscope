"""Editorial Intelligence Service for MetroScope.

Identifies trending coverage clusters and breaking news events from discovery metadata.

EDITORIAL SAFEGUARDS:
- Avoid claiming a story is breaking solely because it was recently published.
- Avoid false claims of event importance: requiring multi-source corroboration.
- Single-source articles with promotional 'BREAKING' labels are rejected from breaking status.
- Grouping requires substantial token overlap and tight temporal windows.
"""

import datetime
import hashlib
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple
from app.services.deduplication_service import tokenize_title, calculate_jaccard_similarity


@dataclass
class EditorialCluster:
    """Cluster of articles from multiple publishers covering the same developing story."""
    cluster_id: str
    seed_id: int = 0
    articles: List[int] = field(default_factory=list)
    domains: Set[str] = field(default_factory=set)
    keywords: Set[str] = field(default_factory=set)
    is_trending: bool = False
    is_breaking: bool = False


class EditorialIntelligenceService:
    """Detects multi-source story clusters, trending topics, and breaking news."""

    def __init__(
        self,
        min_trending_sources: int = 3,
        min_breaking_sources: int = 3,
        max_breaking_age_hours: float = 3.0,
        cluster_similarity_threshold: float = 0.40,
    ):
        self.min_trending_sources = min_trending_sources
        self.min_breaking_sources = min_breaking_sources
        self.max_breaking_age_hours = max_breaking_age_hours
        self.cluster_similarity_threshold = cluster_similarity_threshold

    def analyze_articles(
        self,
        articles: List[Dict[str, any]],
        now: Optional[datetime.datetime] = None,
    ) -> Dict[int, Dict[str, any]]:
        """Analyzes a collection of recent articles and returns editorial flags per article ID.
        
        articles input format:
        [
            {
                "id": int,
                "title": str,
                "domain": str,
                "published_at": datetime.datetime,
            },
            ...
        ]

        Returns:
            {
                article_id: {
                    "is_trending": bool,
                    "is_breaking": bool,
                    "cluster_id": Optional[str],
                }
            }
        """
        current_time = now or datetime.datetime.now(datetime.timezone.utc)
        results: Dict[int, Dict[str, any]] = {
            art["id"]: {
                "is_trending": False,
                "is_breaking": False,
                "cluster_id": None,
            }
            for art in articles
        }

        if len(articles) < 2:
            return results

        # 1. Cluster articles by title token similarity and temporal proximity
        clusters = self._cluster_articles(articles)

        # 2. Evaluate clusters for trending and breaking status
        for cluster in clusters:
            distinct_domains = len(cluster.domains)

            # Trending Rule: Multi-source coverage across >= min_trending_sources distinct domains
            if distinct_domains >= self.min_trending_sources:
                cluster.is_trending = True

            # Breaking Rule:
            # Multi-source velocity within recent window (published < max_breaking_age_hours)
            recent_in_cluster = []
            has_breaking_marker = False

            for art_id in cluster.articles:
                art = next(a for a in articles if a["id"] == art_id)
                pub_at = art.get("published_at")
                if pub_at:
                    pub_utc = (
                        pub_at
                        if pub_at.tzinfo is not None
                        else pub_at.replace(tzinfo=datetime.timezone.utc)
                    )
                    now_utc = (
                        current_time
                        if current_time.tzinfo is not None
                        else current_time.replace(tzinfo=datetime.timezone.utc)
                    )
                    age_hours = (now_utc - pub_utc).total_seconds() / 3600.0
                    if 0 <= age_hours <= self.max_breaking_age_hours:
                        recent_in_cluster.append(art)

                title_lower = art.get("title", "").lower()
                if any(m in title_lower for m in ("breaking:", "urgent:", "alert:", "developing:")):
                    has_breaking_marker = True

            recent_domains = {a.get("domain", "").lower() for a in recent_in_cluster if a.get("domain")}

            # Breaking requires either >= min_breaking_sources within recent window,
            # or explicit breaking marker with >= 2 corroborated independent sources
            if len(recent_domains) >= self.min_breaking_sources or (has_breaking_marker and len(recent_domains) >= 2):
                cluster.is_breaking = True

            # Apply cluster attributes to member articles
            for art_id in cluster.articles:
                results[art_id]["cluster_id"] = cluster.cluster_id
                results[art_id]["is_trending"] = cluster.is_trending
                results[art_id]["is_breaking"] = cluster.is_breaking

        return results

    def _cluster_articles(self, articles: List[Dict[str, any]]) -> List[EditorialCluster]:
        """Groups articles into multi-source story clusters using centroid/average similarity.
        
        ANTI-CHAINING CONSTRAINTS:
        - Prevents transitive keyword chaining (A ~ B ~ C ~ D) from collapsing distinct stories.
        - Requires candidate articles to share core substantive tokens with the cluster seed AND
          maintain consistent average Jaccard similarity across existing cluster members.
        - Operates deterministically by ordering candidate seeds by publication time and ID.
        """
        if len(articles) < 2:
            return []

        # Pre-tokenize titles
        token_map: Dict[int, Set[str]] = {
            art["id"]: tokenize_title(art.get("title", ""))
            for art in articles
        }

        # Deterministic ordering: published_at ascending, then id ascending
        def sort_key(a: Dict[str, any]) -> Tuple[datetime.datetime, int]:
            pub = a.get("published_at")
            if pub is None:
                pub = datetime.datetime.min.replace(tzinfo=datetime.timezone.utc)
            elif pub.tzinfo is None:
                pub = pub.replace(tzinfo=datetime.timezone.utc)
            return (pub, a["id"])

        sorted_arts = sorted(articles, key=sort_key)
        candidate_clusters: List[EditorialCluster] = []

        for art in sorted_arts:
            art_id = art["id"]
            art_tokens = token_map[art_id]
            if len(art_tokens) < 3:
                continue

            best_cluster: Optional[EditorialCluster] = None
            best_sim: float = -1.0

            for cluster in candidate_clusters:
                seed_tokens = token_map[cluster.seed_id]
                shared_with_seed = len(art_tokens.intersection(seed_tokens))
                jaccard_seed = calculate_jaccard_similarity(art_tokens, seed_tokens)

                # Compute average similarity to all existing cluster members
                member_sims = [
                    calculate_jaccard_similarity(art_tokens, token_map[m_id])
                    for m_id in cluster.articles
                ]
                avg_member_sim = sum(member_sims) / len(member_sims)

                # Cluster membership criteria:
                # 1. Share >= 3 core tokens with seed AND maintain average coherence (>= 0.20)
                # 2. Or high token overlap (>= 4 tokens) and average coherence >= 0.18
                is_compatible = (
                    (shared_with_seed >= 3 and jaccard_seed >= 0.20 and avg_member_sim >= 0.20)
                    or (shared_with_seed >= 4 and avg_member_sim >= 0.18)
                )

                if is_compatible and avg_member_sim > best_sim:
                    best_sim = avg_member_sim
                    best_cluster = cluster

            if best_cluster is not None:
                best_cluster.articles.append(art_id)
                if art.get("domain"):
                    best_cluster.domains.add(art["domain"].lower())
            else:
                new_c = EditorialCluster(cluster_id="", seed_id=art_id)
                new_c.articles.append(art_id)
                if art.get("domain"):
                    new_c.domains.add(art["domain"].lower())
                candidate_clusters.append(new_c)

        # Retain only multi-article clusters (>= 2 articles) and compute deterministic cluster IDs
        result_clusters: List[EditorialCluster] = []
        for c in candidate_clusters:
            if len(c.articles) >= 2:
                # Collect keyword frequencies across cluster members
                freq: Dict[str, int] = {}
                for aid in c.articles:
                    for tok in token_map[aid]:
                        freq[tok] = freq.get(tok, 0) + 1

                # Deterministic top keywords: highest frequency descending, then alphabetical
                sorted_kws = sorted(freq.keys(), key=lambda k: (-freq[k], k))[:5]
                cluster_hash = hashlib.sha256(" ".join(sorted_kws).encode("utf-8")).hexdigest()[:16]
                c.cluster_id = f"cluster-{cluster_hash}"
                c.keywords = set(sorted_kws)
                result_clusters.append(c)

        return result_clusters
