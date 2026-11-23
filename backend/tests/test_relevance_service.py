import pytest
from app.services.relevance_service import RelevanceService


def test_relevance_accepts_us_domestic_story():
    service = RelevanceService(min_quality_threshold=30.0)
    decision = service.evaluate_article(
        title="Ohio Governor Announces New State Highway Renovation Grants",
        country="US",
        language="en",
        domain="cleveland.com",
        quality_score=65.0,
    )
    assert decision.is_admissible is True
    assert decision.relevance_type == "us_domestic"
    assert decision.filter_reason is None


def test_relevance_preserves_significant_international_story():
    service = RelevanceService(min_quality_threshold=30.0)
    # Story from non-US domain and non-US sourcecountry, but covering vital global geopolitics
    decision = service.evaluate_article(
        title="United Nations Security Council Passes Ukraine Ceasefire Resolution",
        country="FR",
        language="en",
        domain="france24.com",
        snippet="Global diplomats gathered in Geneva as the UN Security Council reached consensus on peacekeeping terms.",
        quality_score=75.0,
    )
    assert decision.is_admissible is True
    assert decision.relevance_type == "international_significance"
    assert decision.filter_reason is None


def test_relevance_rejects_commercial_product_spam():
    service = RelevanceService(min_quality_threshold=30.0)
    decision = service.evaluate_article(
        title="Thermomètre Moto Pour Guidon 22 - 25 Mm Étanche Précis Buy Now Best Price",
        country="US",
        language="fr",
        domain="spamseller.com",
        snippet="Save $10 on motorcycle handlebar thermometer with free shipping on sale today.",
        quality_score=60.0,
    )
    assert decision.is_admissible is False
    assert decision.relevance_type == "filtered"
    assert "Commercial advertisement or product listing" in decision.filter_reason


def test_relevance_rejects_low_quality_below_threshold():
    service = RelevanceService(min_quality_threshold=35.0)
    decision = service.evaluate_article(
        title="Valid Looking Title But Garbage Content",
        country="US",
        domain="junk.info",
        quality_score=22.0,  # Below 35.0 threshold
    )
    assert decision.is_admissible is False
    assert decision.relevance_type == "filtered"
    assert "below threshold" in decision.filter_reason


def test_relevance_rejects_malformed_short_titles():
    service = RelevanceService(min_quality_threshold=30.0)
    decision = service.evaluate_article(
        title="Too Short",
        country="US",
        quality_score=50.0,
    )
    assert decision.is_admissible is False
    assert "Title too short or malformed" in decision.filter_reason


def test_relevance_rejects_purely_local_foreign_trivia():
    service = RelevanceService(min_quality_threshold=30.0)
    # Non-US country, non-US topic, zero international or US significance
    decision = service.evaluate_article(
        title="Vecinos de barrio municipal denuncian acumulación de basura en calle secundaria",
        country="PE",
        language="es",
        domain="diariolocal.pe",
        quality_score=55.0,
    )
    assert decision.is_admissible is False
    assert "Foreign local report without US or international editorial relevance" in decision.filter_reason


# --- Task E (Phase 4.2) Commercial Regex False-Positive Regression Tests ---

def test_relevance_preserves_legitimate_financial_news_mentioning_handbag_sales():
    """Regression test: Luxury retail earnings report mentioning handbag sales must NOT be rejected."""
    service = RelevanceService(min_quality_threshold=30.0)
    decision = service.evaluate_article(
        title="Luxury Fashion House Reports Surging North American Revenue Driven by Handbag Sales",
        country="US",
        domain="wsj.com",
        snippet="Quarterly financial statements show resilient luxury demand despite broader retail headwinds.",
        quality_score=80.0,
    )
    assert decision.is_admissible is True
    assert decision.relevance_type == "us_domestic"
    assert decision.filter_reason is None


def test_relevance_preserves_retail_sector_economic_reporting():
    """Regression test: General retail and consumer economy reporting must NOT be rejected."""
    service = RelevanceService(min_quality_threshold=30.0)
    decision = service.evaluate_article(
        title="Commerce Department Reports Rebound in Consumer Spending on Apparel and Footwear",
        country="US",
        domain="reuters.com",
        snippet="Retail sector data indicates steady household expenditure across department stores nationwide.",
        quality_score=82.0,
    )
    assert decision.is_admissible is True
    assert decision.relevance_type == "us_domestic"
    assert decision.filter_reason is None


def test_relevance_rejects_commercial_product_listings():
    """Regression test: Explicit e-commerce product listings must be filtered."""
    service = RelevanceService(min_quality_threshold=30.0)
    decision = service.evaluate_article(
        title="Buy Designer Leather Handbags Under $50 with Free Shipping and Fast Delivery",
        country="US",
        domain="discountstore.com",
        snippet="Order today to get exclusive deals on luxury handbags in stock now.",
        quality_score=60.0,
    )
    assert decision.is_admissible is False
    assert decision.relevance_type == "filtered"
    assert "Commercial advertisement or product listing" in decision.filter_reason


def test_relevance_rejects_promotional_discount_advertisements():
    """Regression test: Promotional coupon / discount advertisements must be filtered."""
    service = RelevanceService(min_quality_threshold=30.0)
    decision = service.evaluate_article(
        title="Limited Time Offer: Use Promo Code SAVE25 for Extra Discount on Hoodies",
        country="US",
        domain="coupondealz.net",
        snippet="Shop the best deals online with coupon code at checkout.",
        quality_score=50.0,
    )
    assert decision.is_admissible is False
    assert decision.relevance_type == "filtered"
    assert "Commercial advertisement or product listing" in decision.filter_reason


def test_relevance_preserves_legitimate_business_reporting_mentioning_deals():
    """Regression test: M&A and corporate finance news mentioning 'deals' must NOT be rejected."""
    service = RelevanceService(min_quality_threshold=30.0)
    decision = service.evaluate_article(
        title="Wall Street Investment Banks Celebrate the Best Deals of the Year in Tech Sector",
        country="US",
        domain="bloomberg.com",
        snippet="Advisory fees surged as global merger and acquisition deals reached multi-year highs.",
        quality_score=85.0,
    )
    assert decision.is_admissible is True
    assert decision.relevance_type == "us_domestic"
    assert decision.filter_reason is None


def test_relevance_rejects_malformed_and_irrelevant_headlines():
    """Regression test: Malformed headlines and product catalogs must be filtered."""
    service = RelevanceService(min_quality_threshold=30.0)
    decision = service.evaluate_article(
        title="Capteur De Température Étanche Thermomètre Moto Pour Guidon 22mm",
        country="US",
        domain="techspecs.info",
        quality_score=45.0,
    )
    assert decision.is_admissible is False
    assert decision.relevance_type == "filtered"
    assert "Commercial advertisement or product listing" in decision.filter_reason
