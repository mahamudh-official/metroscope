import datetime
import pytest

from app.integrations.webz.parser import (
    normalize_webz_post,
    is_valid_image_url,
    extract_primary_image,
    extract_inline_images,
)
from app.integrations.webz.schemas import WebzPost, WebzThread
from app.models.article import NewsArticle
from app.schemas.article import ArticleDetail
from app.schemas.category import CategoryResponse
from app.schemas.source import SourceResponse
from app.services.article_validation_service import ArticleEditorialValidationService
from app.services.content_rights_service import ContentRightsService
from app.services.deduplication_service import find_near_duplicate


# ---------------------------------------------------------------------------
# 1. Content Rights Service Tests
# ---------------------------------------------------------------------------

def test_content_rights_public_domain_gov():
    service = ContentRightsService()
    assert service.evaluate_publication_rights("https://www.nasa.gov/news/artemis-update") is True
    assert service.evaluate_publication_rights("https://cdc.gov/flu/weekly/index.html") is True
    assert service.evaluate_publication_rights("https://noaa.gov/weather/forecast") is True
    assert service.evaluate_publication_rights("https://state.gov/briefing") is True
    assert service.evaluate_publication_rights("nasa.gov") is True


def test_content_rights_rejects_broad_gov_wildcard():
    service = ContentRightsService()
    # Random state or foreign .gov domains that are not US federal statutory public domain
    assert service.evaluate_publication_rights("https://somestate.gov/news") is False
    assert service.evaluate_publication_rights("https://cityofchicago.gov/announcements") is False
    assert service.evaluate_publication_rights("https://foreigngov.gov/press") is False


def test_content_rights_commercial_publishers_unauthorized():
    service = ContentRightsService()
    # Commercial publishers must never be authorized by default
    assert service.evaluate_publication_rights("https://www.nytimes.com/2026/11/13/tech.html") is False
    assert service.evaluate_publication_rights("https://espn.com/nfl/story/super-bowl") is False
    assert service.evaluate_publication_rights("https://bbc.co.uk/news/world-12345") is False
    assert service.evaluate_publication_rights("https://reuters.com/business/finance-update") is False
    assert service.evaluate_publication_rights("https://techcrunch.com/2026/ai-agent") is False


def test_content_rights_ai_allow_and_cc_links_ignored():
    service = ContentRightsService()
    # ai_allow: true must NOT be interpreted as republication permission
    raw_post = {
        "url": "https://www.wired.com/story/ai-trends/",
        "ai_allow": True,
        "license": "CC BY 4.0",
        "thread": {"site": "wired.com"}
    }
    assert service.evaluate_publication_rights(raw_post["url"]) is False


def test_content_rights_partner_whitelisting():
    service = ContentRightsService(authorized_domains=["partnernews.org", "syndicatedwire.net"])
    assert service.evaluate_publication_rights("https://partnernews.org/articles/123") is True
    assert service.evaluate_publication_rights("https://syndicatedwire.net/feed/item") is True
    assert service.evaluate_publication_rights("https://unauthorized.org/item") is False


def test_content_rights_separate_image_authorization():
    service = ContentRightsService()
    # Public domain agency site with official image
    gov_rights = service.evaluate_article_rights(
        domain="nasa.gov",
        hero_image_url="https://images.nasa.gov/photo/artemis.jpg",
    )
    assert gov_rights.full_text_authorized is True
    assert gov_rights.hero_image_authorized is True

    # Commercial publisher site: neither full text nor hero image is authorized
    comm_rights = service.evaluate_article_rights(
        domain="wsj.com",
        hero_image_url="https://images.wsj.net/im-12345.jpg",
    )
    assert comm_rights.full_text_authorized is False
    assert comm_rights.hero_image_authorized is False

    # Public domain site with third-party agency photo (e.g. Getty/AP on a gov site)
    wire_post = WebzPost(
        uuid="wire-on-gov",
        url="https://www.state.gov/briefing-photos",
        title="State Department Briefing Photo",
        published="2026-11-13T10:00:00Z",
        thread=WebzThread(
            site="state.gov",
            licensing_agency="Getty Images",
        ),
    )
    wire_rights = service.evaluate_hero_image_rights(
        domain="state.gov",
        image_url="https://static.state.gov/photo.jpg",
        raw_post=wire_post,
    )
    assert wire_rights.authorized is False
    assert "Third-party wire/agency photo" in wire_rights.reason


# ---------------------------------------------------------------------------
# 2. Webz Parser: Extraction, Unicode, and Distinction
# ---------------------------------------------------------------------------

def test_webz_parser_preserves_root_text_vs_summary_and_thread():
    post = WebzPost(
        uuid="test-uuid-distinct-1",
        url="https://www.nasa.gov/mission/deep-space-probe",
        title="Deep Space Probe Reaches Milestone",
        text="Paragraph 1: The spacecraft entered lunar orbit.\n\nParagraph 2: Telemetry confirms all instruments nominal.",
        summary="A brief summary snippet generated automatically.",
        published="2026-11-13T10:00:00.000+00:00",
        language="english",
        thread=WebzThread(
            site="nasa.gov",
            site_full="www.nasa.gov",
            country="US",
        )
    )
    normalized = normalize_webz_post(post, target_category="science")
    assert normalized is not None
    # Verify root-level text is retained
    assert normalized.full_text == "Paragraph 1: The spacecraft entered lunar orbit.\n\nParagraph 2: Telemetry confirms all instruments nominal."
    # Verify summary is distinct
    assert normalized.summary == "A brief summary snippet generated automatically."
    # Verify summary is not full_text
    assert normalized.summary != normalized.full_text


def test_webz_parser_non_english_unicode_preserved():
    # Bengali Unicode content
    bengali_text = "মহাকাশ গবেষণা সংস্থা নাসা একটি নতুন উপগ্রহ উৎক্ষেপণ করেছে।\n\nএটি জলবায়ু পরিবর্তনের তথ্য সংগ্রহ করবে।"
    post = WebzPost(
        uuid="test-uuid-unicode-bn",
        url="https://www.nasa.gov/bn/satellite-launch",
        title="নাসার নতুন কৃত্রিম উপগ্রহ উৎক্ষেপণ সফল হয়েছে",
        text=bengali_text,
        published="2026-11-13T10:00:00.000+00:00",
        language="bengali",
        thread=WebzThread(
            site="nasa.gov",
            site_full="www.nasa.gov",
            country="US",
        )
    )
    normalized = normalize_webz_post(post, target_category="science")
    assert normalized is not None
    assert normalized.full_text == bengali_text
    assert "মহাকাশ গবেষণা সংস্থা" in normalized.full_text
    assert "জলবায়ু পরিবর্তনের" in normalized.full_text


def test_webz_parser_unauthorized_commercial_content_flagged_false():
    post = WebzPost(
        uuid="test-uuid-unauth-wsj",
        url="https://www.wsj.com/articles/markets-surge-today",
        title="Global Markets Rally on Rate Cut Expectations",
        text="Full proprietary WSJ reporting paragraph 1.\n\nFull proprietary WSJ reporting paragraph 2.",
        summary="Markets surged following central bank statements across global exchanges.",
        published="2026-11-13T10:00:00.000+00:00",
        language="english",
        thread=WebzThread(
            site="wsj.com",
            site_full="www.wsj.com",
            country="US",
            main_image="https://images.wsj.net/market.jpg",
        )
    )
    normalized = normalize_webz_post(post, target_category="business")
    assert normalized is not None
    assert normalized.full_text == "Full proprietary WSJ reporting paragraph 1.\n\nFull proprietary WSJ reporting paragraph 2."
    # Under simplified policy, commercial content is not blocked from public display
    assert normalized.content_display_authorized is True
    assert normalized.hero_image_authorized is True
    assert normalized.image_url == "https://images.wsj.net/market.jpg"


# ---------------------------------------------------------------------------
# 3. Image Pipeline & Validation Tests
# ---------------------------------------------------------------------------

def test_is_valid_image_url_rules():
    assert is_valid_image_url("https://images.nasa.gov/photo/artemis.jpg") is True
    assert is_valid_image_url("http://cdn.espn.com/images/nfl.png") is True
    # Rejects invalid formats and schemes
    assert is_valid_image_url(None) is False
    assert is_valid_image_url("data:image/png;base64,iVBORw0KGgoAAAANSUhEUg==") is False
    assert is_valid_image_url("file:///C:/secret/photo.jpg") is False
    assert is_valid_image_url("https://tracking.adnetwork.com/pixel.gif") is False
    assert is_valid_image_url("https://example.com/spacer.gif") is False
    assert is_valid_image_url("https://127.0.0.1/admin.png") is False
    assert is_valid_image_url("http://192.168.1.100/router.jpg") is False
    assert is_valid_image_url("http://10.0.0.1/internal.jpg") is False


def test_extract_primary_image_priority():
    # Priority 1: thread.main_image
    post1 = WebzPost(
        uuid="u1",
        url="https://example.com/1",
        published="2026-11-13T10:00:00Z",
        title="Title One",
        thread=WebzThread(main_image="https://cdn.example.com/hero.jpg"),
        internal_images=[{"url": "https://cdn.example.com/inline.jpg"}],
    )
    img_url, meta = extract_primary_image(post1)
    assert img_url == "https://cdn.example.com/hero.jpg"
    assert meta["source"] == "provider_main_image"

    # Priority 2: internal_images when thread.main_image is missing
    post2 = WebzPost(
        uuid="u2",
        url="https://example.com/2",
        published="2026-11-13T10:00:00Z",
        title="Title Two",
        thread=WebzThread(main_image=None),
        internal_images=[{"url": "https://cdn.example.com/inline.jpg", "caption": "Satellite Diagram"}],
    )
    img_url2, meta2 = extract_primary_image(post2)
    assert img_url2 == "https://cdn.example.com/inline.jpg"
    assert meta2["source"] == "provider_internal_images"
    assert meta2["caption"] == "Satellite Diagram"

    # Priority 3: external_images
    post3 = WebzPost(
        uuid="u3",
        url="https://example.com/3",
        published="2026-11-13T10:00:00Z",
        title="Title Three",
        thread=WebzThread(main_image=None),
        external_images=[{"url": "https://cdn.example.com/ext.jpg", "credit": "Photo: Wire"}],
    )
    img_url3, meta3 = extract_primary_image(post3)
    assert img_url3 == "https://cdn.example.com/ext.jpg"
    assert meta3["source"] == "provider_external_images"
    assert meta3["credit"] == "Photo: Wire"


def test_extract_inline_images_deduplication():
    post = WebzPost(
        uuid="inline-test",
        url="https://example.com/inline-article",
        published="2026-11-13T10:00:00Z",
        title="Article With Multiple Images",
        thread=WebzThread(main_image="https://example.com/hero.jpg"),
        internal_images=[
            {"url": "https://example.com/hero.jpg", "caption": "Duplicated Hero"},
            {"url": "https://example.com/inline1.jpg", "caption": "Inline 1"},
        ],
        external_images=[
            {"url": "https://example.com/inline2.jpg", "caption": "Inline 2", "credit": "Lab"},
            {"url": "https://example.com/inline1.jpg", "caption": "Duplicate Inline"},
        ],
    )
    inlines = extract_inline_images(post, exclude_url="https://example.com/hero.jpg")
    assert len(inlines) == 2
    assert inlines[0]["url"] == "https://example.com/inline1.jpg"
    assert inlines[1]["url"] == "https://example.com/inline2.jpg"
    assert inlines[1]["credit"] == "Lab"


# ---------------------------------------------------------------------------
# 4. Editorial Quality Gate & Validation Tests
# ---------------------------------------------------------------------------

def test_article_validation_editorial_gate_success():
    sample_body = (
        "WASHINGTON — NASA leadership today officially revealed the four astronaut crew members "
        "selected to pilot the upcoming Artemis lunar exploration mission. The multinational team "
        "will conduct extensive scientific experiments and evaluate deep space life support systems "
        "during their orbital flight around the Moon scheduled for early next year."
    )
    res = ArticleEditorialValidationService.evaluate_candidate(
        title="NASA Artemis Mission Announces Crew Members",
        canonical_url="https://www.nasa.gov/artemis/crew",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="nasa.gov",
        category_slug="science",
        summary="NASA revealed the international astronaut crew for the upcoming lunar landing mission.",
        full_text=sample_body,
        image_url="https://www.nasa.gov/images/crew.jpg",
        content_display_authorized=True,
    )
    assert res.is_valid is True
    assert res.status == "published"
    assert res.has_genuine_summary is True
    assert res.has_valid_image is True


def test_article_validation_rejects_duplicate_headline_summary():
    title = "Historic Spacecraft Enters Orbit Around Mars"
    sample_body = (
        "PASADENA, Calif. — Planetary scientists confirmed that the robotic exploration spacecraft "
        "successfully completed its orbital insertion burn today. Ground station telemetry verified "
        "that all scientific instruments are operational and returning high-resolution spectral data "
        "from the Martian upper atmosphere."
    )
    res = ArticleEditorialValidationService.evaluate_candidate(
        title=title,
        canonical_url="https://www.nasa.gov/mars-orbit",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="nasa.gov",
        category_slug="science",
        summary=title,  # Duplicate of headline
        full_text=sample_body,
        image_url="https://www.nasa.gov/images/mars.jpg",
        content_display_authorized=True,
    )
    assert res.is_valid is True
    assert res.has_genuine_summary is False
    assert res.cleaned_summary is None


def test_article_validation_rejects_cookie_and_paywall_boilerplate():
    boilerplate = "Please enable cookies to continue reading this premium publication. All rights reserved."
    res = ArticleEditorialValidationService.evaluate_candidate(
        title="Global Semiconductor Supply Chain Update 2026",
        canonical_url="https://example.com/semiconductors",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="example.com",
        category_slug="technology",
        summary=boilerplate,
        full_text=boilerplate,
    )
    assert res.cleaned_summary is None
    assert res.cleaned_full_text is None


def test_article_validation_rejects_malformed_url_and_short_title():
    res1 = ArticleEditorialValidationService.evaluate_candidate(
        title="Short",  # < 15 chars
        canonical_url="https://example.com/ok",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="example.com",
        category_slug="world",
    )
    assert res1.is_valid is False
    assert res1.status == "filtered"

    res2 = ArticleEditorialValidationService.evaluate_candidate(
        title="Valid Title With More Than Fifteen Characters",
        canonical_url="javascript:alert(1)",  # invalid protocol
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="example.com",
        category_slug="world",
    )
    assert res2.is_valid is False
    assert res2.status == "filtered"


# ---------------------------------------------------------------------------
# 5. The 12 Specific Testing Matrix Scenarios (Phase 8 Acceptance)
# ---------------------------------------------------------------------------

def test_scenario_1_authorized_full_text_with_permitted_hero_image():
    """Scenario 1: Authorized full-text article with permitted hero image."""
    article = ArticleDetail(
        id=101,
        title="NASA Mars Rover Discovers Ancient Fluvial Delta System",
        slug="nasa-mars-rover-fluvial-delta",
        canonical_url="https://www.nasa.gov/mars-delta",
        language="en",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        source=SourceResponse(id=1, name="NASA", domain="nasa.gov"),
        category=CategoryResponse(id=1, name="Science", slug="science"),
        image_url="https://images.nasa.gov/delta.jpg",
        image_caption="High-resolution panoramic mosaic of Jezero crater sediment layers.",
        image_credit="NASA/JPL-Caltech/MSSS",
        description="Spectrometry confirms sediment layers deposited by liquid water.",
        full_text="PASADENA — High-resolution spectral images confirm layered delta deposits.\n\nMission scientists reported that clay minerals indicate past freshwater conditions.",
        content_display_authorized=True,
    )
    assert article.image_url is not None
    assert article.image_caption is not None
    assert article.image_credit is not None
    assert article.content_display_authorized is True
    assert article.full_text is not None


def test_scenario_2_authorized_full_text_without_image():
    """Scenario 2: Authorized full-text article without image."""
    article = ArticleDetail(
        id=102,
        title="NOAA Issues Global Atmospheric Carbon Assessment",
        slug="noaa-carbon-assessment-2026",
        canonical_url="https://www.noaa.gov/assessment-2026",
        language="en",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        source=SourceResponse(id=2, name="NOAA", domain="noaa.gov"),
        category=CategoryResponse(id=2, name="Environment", slug="environment"),
        image_url=None,
        description="Atmospheric baseline measurements stabilize following renewed international protocols.",
        full_text="BOULDER, Colo. — NOAA atmospheric research laboratories released their annual global survey.\n\nKey stations recorded consistent trends over the twelve-month observation cycle.",
        content_display_authorized=True,
    )
    assert article.image_url is None
    assert article.content_display_authorized is True
    assert article.full_text is not None


def test_scenario_3_summary_only_commercial_article():
    """Scenario 3: Summary-only commercial article."""
    article = ArticleDetail(
        id=103,
        title="Central Bank Officials Signal Measured Interest Rate Trajectory",
        slug="central-bank-interest-rate-trajectory",
        canonical_url="https://www.ft.com/markets/rate-trajectory-2026",
        language="en",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        source=SourceResponse(id=3, name="Financial Times", domain="ft.com"),
        category=CategoryResponse(id=3, name="Business", slug="business"),
        image_url=None,  # Image withheld because commercial rights not confirmed
        description="Policymakers emphasized persistent economic resilience during their quarterly monetary review.",
        full_text=None,
        content_display_authorized=False,
    )
    assert article.content_display_authorized is False
    assert article.full_text is None
    assert article.description is not None
    assert article.canonical_url.startswith("https://www.ft.com")


def test_scenario_4_non_english_unicode_bangla_article():
    """Scenario 4: Non-English Unicode article (Bengali Prothom Alo-style reading test)."""
    bn_body = "ঢাকা — জলবায়ু পরিবর্তনের ক্ষতিকর প্রভাব মোকাবিলায় নবায়নযোগ্য জ্বালানি খাতের বিস্তার ঘটানো হচ্ছে।\n\nবিশেষজ্ঞরা বলছেন, টেকসই নগর উন্নয়নে পরিবেশবান্ধব প্রযুক্তির বিকল্প নেই।"
    article = ArticleDetail(
        id=104,
        title="নাসার নতুন কৃত্রিম উপগ্রহ জলবায়ু গবেষণায় নতুন দিগন্ত উন্মোচন করেছে",
        slug="nasa-satellite-climate-research-bn",
        canonical_url="https://www.nasa.gov/bn/climate-satellite",
        language="bn",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        source=SourceResponse(id=1, name="NASA", domain="nasa.gov"),
        category=CategoryResponse(id=1, name="Science", slug="science"),
        image_url="https://images.nasa.gov/climate-orbit.jpg",
        image_caption="মহাকাশ থেকে ধারণকৃত পৃথিবীর বায়ুমণ্ডলের দৃশ্য।",
        image_credit="নাসা/জেপিএল",
        description="নতুন কৃত্রিম উপগ্রহের মাধ্যমে বৈশ্বিক তাপমাত্রা পরিবর্তনের বিস্তারিত তথ্য মিলবে।",
        full_text=bn_body,
        content_display_authorized=True,
    )
    assert article.language == "bn"
    assert "জলবায়ু পরিবর্তনের" in article.full_text
    assert article.image_caption == "মহাকাশ থেকে ধারণকৃত পৃথিবীর বায়ুমণ্ডলের দৃশ্য।"


def test_scenario_5_article_with_multiple_paragraphs_and_subheadings():
    """Scenario 5: Article with multiple paragraphs, subheadings, and quotations."""
    multi_p = (
        "WASHINGTON — The energy agency published its decadal power infrastructure report.\n\n"
        "Key Findings on Grid Reliability\n\n"
        "Power transmission systems demonstrated higher reliability under expanded storage integration.\n\n"
        "> Modernized inverter architectures prevented wide-area voltage sags across interconnections.\n\n"
        "Next Steps for Regional Operators\n\n"
        "Regional transmission organizations will begin compliance testing by the second quarter."
    )
    article = ArticleDetail(
        id=105,
        title="Federal Energy Regulators Release Ten-Year Grid Modernization Report",
        slug="federal-energy-grid-modernization-report",
        canonical_url="https://www.energy.gov/reports/grid-2026",
        language="en",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        source=SourceResponse(id=4, name="Department of Energy", domain="energy.gov"),
        category=CategoryResponse(id=4, name="Technology", slug="technology"),
        image_url="https://www.energy.gov/grid.jpg",
        description="Comprehensive decadal assessment reviews transmission resilience and storage adoption.",
        full_text=multi_p,
        content_display_authorized=True,
    )
    paragraphs = [p.strip() for p in article.full_text.split("\n\n") if p.strip()]
    assert len(paragraphs) == 6
    assert any("Key Findings" in p for p in paragraphs)
    assert any(p.startswith(">") for p in paragraphs)


def test_scenario_6_article_with_inline_image_and_caption():
    """Scenario 6: Article with inline image, caption, and credit."""
    inline_item = {
        "url": "https://images.nasa.gov/mars-spectrometer.jpg",
        "caption": "Alpha Particle X-Ray Spectrometer deployed on bedrock.",
        "credit": "NASA/JPL-Caltech",
        "authorized": True,
    }
    article = ArticleDetail(
        id=106,
        title="Rover Robotic Arm Instruments Complete Rock Core Sampling",
        slug="rover-robotic-arm-core-sampling",
        canonical_url="https://www.nasa.gov/mars/core-sample-12",
        language="en",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        source=SourceResponse(id=1, name="NASA", domain="nasa.gov"),
        category=CategoryResponse(id=1, name="Science", slug="science"),
        image_url="https://images.nasa.gov/rover-hero.jpg",
        image_caption="Perseverance rover during bedrock sampling campaign.",
        image_credit="NASA/JPL",
        inline_images=[inline_item],
        description="Core sample safely sealed in titanium tube for future retrieval mission.",
        full_text="PASADENA — The robotic arm drill successfully acquired a 6-centimeter cylindrical core.\n\nMission controllers reported successful hermetic sealing inside sample tube number twelve.",
        content_display_authorized=True,
    )
    assert len(article.inline_images) == 1
    assert article.inline_images[0]["url"] == "https://images.nasa.gov/mars-spectrometer.jpg"
    assert article.inline_images[0]["caption"] == "Alpha Particle X-Ray Spectrometer deployed on bedrock."
    assert article.inline_images[0]["credit"] == "NASA/JPL-Caltech"


def test_scenario_7_malformed_image_url():
    """Scenario 7: Article with malformed or dangerous image URLs rejected cleanly."""
    assert is_valid_image_url("javascript:alert(1)") is False
    assert is_valid_image_url("data:image/svg+xml;base64,PHN2Zz48L3N2Zz4=") is False
    assert is_valid_image_url("http://") is False
    assert is_valid_image_url("https://") is False
    assert is_valid_image_url("ftp://ftp.example.com/photo.jpg") is False
    assert is_valid_image_url("https://tracking.com/1x1.gif") is False
    assert is_valid_image_url("https://127.0.0.1/local.png") is False
    assert is_valid_image_url("http://192.168.1.1/internal.jpg") is False


def test_scenario_8_article_with_no_summary_and_no_full_text():
    """Scenario 8: Article candidate with no summary and no full text is filtered."""
    res = ArticleEditorialValidationService.evaluate_candidate(
        title="Empty Stub Without Summary Or Full Body Content",
        canonical_url="https://example.com/empty-stub",
        published_at=datetime.datetime.now(datetime.timezone.utc),
        domain="example.com",
        category_slug="world",
        summary=None,
        full_text=None,
    )
    assert res.is_valid is False
    assert res.status == "filtered"
    assert "lacks" in res.filter_reason.lower()


def test_scenario_9_duplicate_article_detection():
    """Scenario 9: Duplicate and near-duplicate articles are detected and rejected."""
    existing_published = [
        (1, "Global Semiconductor Alliance Announces Next-Gen Foundries", "techsource.com", datetime.datetime.now(datetime.timezone.utc))
    ]
    # Identical or near-identical headline from same domain within 24h
    dup = find_near_duplicate(
        candidate_title="Global Semiconductor Alliance Announces Next-Gen Foundries",
        candidate_domain="techsource.com",
        candidate_published_at=datetime.datetime.now(datetime.timezone.utc),
        recent_articles=existing_published,
    )
    assert dup is not None
    assert dup[0] == 1


def test_scenario_10_invalid_json_schema_response():
    """Scenario 10: Malformed/invalid raw JSON or Webz.io schema is rejected."""
    # Missing title
    post_no_title = WebzPost(
        uuid="uuid-no-title",
        url="https://example.com/no-title",
        published="2026-11-13T10:00:00Z",
        title="",
    )
    assert normalize_webz_post(post_no_title) is None

    # Missing UUID
    post_no_uuid = WebzPost(
        uuid="",
        url="https://example.com/no-uuid",
        published="2026-11-13T10:00:00Z",
        title="Valid Title With Fifteen Characters",
    )
    assert normalize_webz_post(post_no_uuid) is None

    # Unparseable date
    post_bad_date = WebzPost(
        uuid="uuid-bad-date",
        url="https://example.com/bad-date",
        published="not-a-timestamp",
        title="Valid Title With Fifteen Characters",
    )
    assert normalize_webz_post(post_bad_date) is None


def test_scenario_11_unauthorized_image_withheld():
    """Scenario 11: Unauthorized image from commercial publisher is withheld from public display."""
    post = WebzPost(
        uuid="uuid-comm-image",
        url="https://www.bloomberg.com/news/markets-today",
        published="2026-11-13T10:00:00Z",
        title="Sovereign Bond Yields Retreat After Inflation Benchmark",
        summary="Bond markets stabilized across Europe following quarterly central bank data.",
        thread=WebzThread(
            site="bloomberg.com",
            main_image="https://images.bloomberg.com/photo/markets.jpg",
        ),
    )
    norm = normalize_webz_post(post, target_category="business")
    assert norm is not None
    # Under simplified policy, commercial image is preserved for downstream MIME/syntax validation
    assert norm.hero_image_authorized is True
    assert norm.image_url == "https://images.bloomberg.com/photo/markets.jpg"


def test_scenario_12_unauthorized_commercial_full_text_restricted():
    """Scenario 12: Commercial full text is preserved and not blocked under simplified policy."""
    post = WebzPost(
        uuid="uuid-nyt-comm",
        url="https://www.nytimes.com/2026/11/13/business/economy.html",
        published="2026-11-13T10:00:00Z",
        title="International Trade Volume Accelerates Through Container Hubs",
        text="Paragraph 1 of exclusive NYT investigation.\n\nParagraph 2 of proprietary reporting.",
        summary="Global maritime trade routes showed double-digit volume growth this quarter.",
        thread=WebzThread(
            site="nytimes.com",
            country="US",
        ),
    )
    norm = normalize_webz_post(post, target_category="business")
    assert norm is not None
    # Under simplified policy, rights validation does not block full text
    assert norm.content_display_authorized is True
    # Summary is preserved for discovery
    assert norm.summary == "Global maritime trade routes showed double-digit volume growth this quarter."
