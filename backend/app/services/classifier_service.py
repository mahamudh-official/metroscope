import re
from dataclasses import dataclass, field
from typing import Dict, List, Optional, Set, Tuple

# Semantic keyword taxonomy for news classification across the approved 10 categories
CATEGORY_KEYWORD_MAP: Dict[str, Set[str]] = {
    "technology": {
        "ai", "artificial intelligence", "tech", "technology", "software", "chip", "chips",
        "semiconductor", "semiconductors", "nvidia", "intel", "amd", "apple", "google",
        "microsoft", "meta", "cyber", "cybersecurity", "cloud", "robot", "robotics",
        "algorithm", "quantum", "crypto", "bitcoin", "blockchain", "gadget", "smartphone",
        "app", "apps", "openai", "chatgpt", "llm", "deep learning", "machine learning",
        "generative ai", "data center", "autonomous vehicle", "self-driving", "silicon valley",
    },
    "business": {
        "business", "economy", "economic", "market", "markets", "stock", "stocks",
        "wall street", "nasdaq", "dow jones", "s&p", "fed", "federal reserve",
        "inflation", "treasury", "yield", "yields", "bank", "banks", "banking",
        "interest rate", "interest rates", "trade", "tariff", "tariffs", "gdp",
        "earnings", "revenue", "profit", "merger", "acquisition", "investor", "investors",
        "corporate", "ceo", "cfo", "retail", "consumer spending", "labor market",
        "unemployment", "mortgage rate", "housing market", "central bank", "commercial real estate",
    },
    "politics": {
        "politics", "political", "congress", "senate", "senator", "senators",
        "house of representatives", "white house", "president", "presidential",
        "democrat", "democrats", "democratic", "republican", "republicans",
        "gop", "bipartisan", "legislation", "bill", "lawmaker", "lawmakers",
        "election", "elections", "ballot", "campaign", "governor", "supreme court",
        "judge", "attorney general", "doj", "pentagon", "policy", "capitol hill",
        "filibuster", "veto", "judiciary", "primary election", "caucus", "inauguration",
    },
    "science": {
        "science", "scientific", "nasa", "space", "astronomy", "telescope", "physics",
        "physicist", "quantum", "mars", "moon", "lunar", "galaxy", "universe", "fossil",
        "paleontology", "genome", "genetics", "biology", "chemist", "chemistry",
        "laboratory", "experiment", "researchers", "study finds", "discovery", "james webb",
        "astrophysics", "black hole", "particle physics", "cern", "spacex", "cosmic",
        "asteroid", "comet", "solar flare", "supernova", "planet", "exoplanet", "geology",
        "neuroscience", "archaeology", "paleontologist", "dinosaurs", "dna", "crispr",
        "stem cell", "evolution", "scientists", "scientific study", "scientific discovery",
    },
    "health": {
        "health", "healthcare", "medical", "medicine", "hospital", "hospitals",
        "doctor", "doctors", "patient", "patients", "disease", "cancer", "vaccine",
        "vaccines", "fda", "cdc", "who", "virus", "infection", "clinical trial",
        "treatment", "therapy", "pharma", "pharmaceutical", "mental health", "wellness",
        "surgeon", "surgery", "outbreak", "public health", "drug approval", "fda approves",
        "alzheimer", "dementia", "cardiology", "diabetes", "pediatric", "pandemic",
    },
    "environment": {
        "environment", "climate", "climate change", "global warming", "carbon",
        "emissions", "renewable", "solar", "wind energy", "clean energy",
        "wildfire", "wildfires", "hurricane", "flood", "flooding", "drought",
        "conservation", "epa", "pollution", "ecology", "biodiversity",
        "green energy", "fossil fuels", "sea level", "deforestation", "endangered species",
        "wildlife", "ocean", "arctic", "glacier", "greenhouse gas", "net zero",
        "ecosystem", "heatwave", "storm",
    },
    "sports": {
        "sport", "sports", "nfl", "nba", "mlb", "nhl", "fifa", "soccer", "football",
        "basketball", "baseball", "hockey", "olympic", "olympics", "championship",
        "super bowl", "playoffs", "coach", "tournament", "athlete", "quarterback",
        "touchdown", "world cup", "tennis", "golf", "pga", "formula 1", "grand slam",
        "nascar", "ufc", "boxing", "premier league", "champions league", "stanley cup",
        "world series", "wnba", "mls", "marathon",
    },
    "entertainment": {
        "entertainment", "movie", "movies", "film", "films", "cinema", "actor",
        "actress", "hollywood", "box office", "music", "song", "album", "concert",
        "grammy", "oscar", "oscars", "emmy", "streaming", "netflix", "disney",
        "celebrity", "broadway", "billboard", "premiere", "tv show", "screenplay",
        "trailer", "film festival", "music festival", "cannes", "sundance", "spotify", "hbo", "paramount",
        "warner", "rock", "pop star", "singer", "director", "filmmaker", "comedian",
    },
    "world": {
        "world", "global", "international", "united nations", "un", "nato",
        "ukraine", "russia", "china", "taiwan", "middle east", "israel", "gaza",
        "iran", "europe", "european union", "eu", "britain", "uk", "france",
        "germany", "japan", "diplomacy", "ambassador", "treaty", "foreign policy",
        "prime minister", "summit", "ceasefire", "peace talks", "sanctions", "geopolitics",
        "foreign minister", "kremlin", "kyiv", "beijing", "tokyo", "seoul", "london",
        "paris", "berlin", "canada", "mexico", "syria", "yemen", "red sea", "sudan",
    },
    "us": {
        "america", "american", "united states", "usa", "nationwide", "homeland",
        "statewide", "federal", "interstate", "national",
    },
}


@dataclass
class ClassificationResult:
    """Detailed outcome of category classification."""
    category_slug: str
    confidence_score: int
    matched_keywords: List[str] = field(default_factory=list)


def classify_article_detailed(
    title: str,
    domain: Optional[str] = None,
    snippet: Optional[str] = None,
    default_category: str = "us",
) -> ClassificationResult:
    """Performs semantic text classification, returning category, confidence, and keyword evidence.
    
    Weights:
    - Keywords in title receive 3x multiplier for multi-word phrases, 2x for single words.
    - Keywords in snippet or domain receive standard weighting (2x multi-word, 1x single-word).
    
    Tie-breaking:
    Deterministic alphabetical ordering by category slug when top scores are tied.
    
    Fallback:
    If highest score < 2, falls back to `default_category` ('us' by default).
    """
    title_text = (title or "").lower()
    context_text = f"{domain or ''} {snippet or ''}".lower()

    scores: Dict[str, int] = {cat: 0 for cat in CATEGORY_KEYWORD_MAP}
    matches: Dict[str, List[str]] = {cat: [] for cat in CATEGORY_KEYWORD_MAP}

    for category, keywords in CATEGORY_KEYWORD_MAP.items():
        for kw in keywords:
            is_multi_word = " " in kw

            # Title matching (higher weight)
            if is_multi_word:
                if kw in title_text:
                    scores[category] += 4
                    matches[category].append(kw)
            else:
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, title_text):
                    scores[category] += 3
                    matches[category].append(kw)

            # Context/domain/snippet matching
            if is_multi_word:
                if kw in context_text:
                    scores[category] += 2
                    if kw not in matches[category]:
                        matches[category].append(kw)
            else:
                pattern = rf"\b{re.escape(kw)}\b"
                if re.search(pattern, context_text):
                    scores[category] += 1
                    if kw not in matches[category]:
                        matches[category].append(kw)

    # Sort candidates: highest score first; alphabetical tie-break
    sorted_candidates = sorted(scores.items(), key=lambda item: (-item[1], item[0]))
    best_category, max_score = sorted_candidates[0]

    if max_score >= 2:
        return ClassificationResult(
            category_slug=best_category,
            confidence_score=max_score,
            matched_keywords=matches[best_category],
        )

    return ClassificationResult(
        category_slug=default_category,
        confidence_score=max_score,
        matched_keywords=[],
    )


def classify_article(
    title: str,
    domain: Optional[str] = None,
    snippet: Optional[str] = None,
    default_category: str = "us",
) -> str:
    """Classifies an article into an editorial category slug (backward compatible wrapper)."""
    result = classify_article_detailed(
        title=title,
        domain=domain,
        snippet=snippet,
        default_category=default_category,
    )
    return result.category_slug
