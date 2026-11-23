"""Domain business logic services."""

from app.services.url_service import normalize_url, compute_url_hash, extract_domain
from app.services.normalizer_service import clean_title, generate_slug, clean_description
from app.services.classifier_service import (
    classify_article,
    classify_article_detailed,
    ClassificationResult,
)
from app.services.deduplication_service import (
    check_duplicate_hashes,
    is_duplicate_hash,
    find_near_duplicate,
    tokenize_title,
    calculate_jaccard_similarity,
)
from app.services.quality_service import (
    QualityScoringService,
    QualityAssessment,
    QualityWeights,
)
from app.services.relevance_service import (
    RelevanceService,
    FilterDecision,
)
from app.services.editorial_intelligence_service import (
    EditorialIntelligenceService,
    EditorialCluster,
)

__all__ = [
    "normalize_url",
    "compute_url_hash",
    "extract_domain",
    "clean_title",
    "generate_slug",
    "clean_description",
    "classify_article",
    "classify_article_detailed",
    "ClassificationResult",
    "check_duplicate_hashes",
    "is_duplicate_hash",
    "find_near_duplicate",
    "tokenize_title",
    "calculate_jaccard_similarity",
    "QualityScoringService",
    "QualityAssessment",
    "QualityWeights",
    "RelevanceService",
    "FilterDecision",
    "EditorialIntelligenceService",
    "EditorialCluster",
]
