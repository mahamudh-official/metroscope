"""Content licensing, media rights, and statutory copyright evaluation service.

Enforces strict compliance with publisher copyrights, media licensing, and Webz.io Terms of Service:
1. Webz.io standard API terms grant search/discovery and metadata analysis rights,
   NOT commercial republication rights for third-party publisher articles or media.
2. `ai_allow: true` in Webz.io indicates crawler accessibility under robots.txt/headers,
   NOT a license to republish copyrighted editorial copy or images.
3. External Creative Commons (CC BY) links in an article or footer do NOT imply
   that the publisher's editorial reporting is open-source or freely republishable.
4. Separate authorization decisions are enforced for:
   - Full article body text
   - Primary / hero image
   - Inline article images
   Authorization of one does NOT imply authorization of the others.
5. Statutory public domain under 17 U.S.C. § 105 applies specifically to official works of the
   U.S. Federal Government (e.g. NASA, NOAA, CDC, NIH, White House).
   The broad generic '*.gov' wildcard is explicitly prohibited.
6. Commercial publisher content remains summary-only unless a valid licensing or
   syndication agreement specifically permits full-text or image reproduction.
7. Image rights are evaluated independently: third-party wire photos (e.g. AP, Getty, Reuters)
   appearing on government portals are recognized as non-public-domain and rejected.
"""

from dataclasses import dataclass, field
import re
from typing import Any, Dict, List, Optional, Set
from urllib.parse import urlparse

from app.core.logging import logger

# Domains with verified statutory public domain status (works of U.S. Federal Government under 17 U.S.C. § 105)
VERIFIED_PUBLIC_DOMAIN_DOMAINS: Set[str] = {
    "whitehouse.gov",
    "nasa.gov",
    "cdc.gov",
    "nih.gov",
    "defense.gov",
    "state.gov",
    "justice.gov",
    "energy.gov",
    "noaa.gov",
    "epa.gov",
    "sec.gov",
    "fbi.gov",
    "loc.gov",
}

# Explicit contractual syndication partner domains for MetroScope
AUTHORIZED_SYNDICATION_DOMAINS: Set[str] = set()

# Known third-party wire services and stock photo agencies whose works are copyrighted
# even if hosted on an otherwise public-domain site
THIRD_PARTY_MEDIA_AGENCIES = [
    re.compile(r"\b(getty(?:\s*images)?|ap(?:\s*photo)?|associated\s*press|reuters|afp|agence\s*france-presse|shutterstock|istock|alamy|epa|bloomberg(?:\s*photo)?)\b", re.IGNORECASE),
]


@dataclass
class RightsDecision:
    """Auditable rights decision for an article component."""
    authorized: bool
    reason: str
    component: str  # "full_text", "hero_image", "inline_image"
    audit_notes: List[str] = field(default_factory=list)


@dataclass
class ArticleRightsPackage:
    """Comprehensive rights package encompassing text and media decisions."""
    full_text_authorized: bool
    full_text_reason: str
    hero_image_authorized: bool
    hero_image_reason: str
    inline_images_authorized: bool
    inline_images_reason: str
    audit_log: List[str] = field(default_factory=list)


class ContentRightsService:
    """Evaluates publication rights across article body text, hero image, and inline media."""

    def __init__(
        self,
        public_domain_whitelist: Optional[Set[str]] = None,
        authorized_syndication_whitelist: Optional[Set[str]] = None,
        authorized_domains: Optional[Any] = None,
    ):
        self.public_domain_domains = (
            set(public_domain_whitelist)
            if public_domain_whitelist is not None
            else set(VERIFIED_PUBLIC_DOMAIN_DOMAINS)
        )
        if authorized_domains is not None:
            self.authorized_syndication_domains = set(authorized_domains)
        elif authorized_syndication_whitelist is not None:
            self.authorized_syndication_domains = set(authorized_syndication_whitelist)
        else:
            self.authorized_syndication_domains = set(AUTHORIZED_SYNDICATION_DOMAINS)

    @staticmethod
    def _clean_domain(domain: Optional[str]) -> str:
        if not domain:
            return ""
        clean = domain.lower().strip()
        if "://" in clean or "/" in clean:
            parsed = urlparse(clean if "://" in clean else f"http://{clean}")
            clean = (parsed.hostname or clean).lower().strip()
        if clean.startswith("www."):
            clean = clean[4:]
        return clean

    def is_verified_public_domain(self, domain: str) -> bool:
        """Checks if a domain is a verified U.S. Federal Government public domain source.
        
        Strictly rejects generic '*.gov' wildcards (state, county, municipal, or foreign gov).
        Only matches explicit federal whitelist domains or their subdomains (e.g., mars.nasa.gov).
        """
        clean = self._clean_domain(domain)
        if not clean:
            return False
        # Exact domain match
        if clean in self.public_domain_domains:
            return True
        # Explicit subdomain of whitelisted domain (e.g. 'images.nasa.gov' -> 'nasa.gov')
        for pd in self.public_domain_domains:
            if clean.endswith(f".{pd}"):
                return True
        return False

    def is_authorized_syndication_domain(self, domain: str) -> bool:
        """Checks if a publisher domain has an active contractual syndication agreement."""
        clean = self._clean_domain(domain)
        if not clean:
            return False
        if clean in self.authorized_syndication_domains:
            return True
        for sd in self.authorized_syndication_domains:
            if clean.endswith(f".{sd}"):
                return True
        return False

    # -------------------------------------------------------------------------
    # 1. Full Article Text Evaluation
    # -------------------------------------------------------------------------

    def evaluate_full_text_rights(
        self,
        domain: Optional[str] = None,
        raw_post: Optional[Any] = None,
        explicit_override: Optional[bool] = None,
    ) -> RightsDecision:
        """Determines whether full article body text can be publicly rendered."""
        if explicit_override is not None:
            return RightsDecision(
                authorized=explicit_override,
                reason="Administrative override",
                component="full_text",
                audit_notes=["Explicit administrator override applied"],
            )

        clean = self._clean_domain(domain)
        audit_notes: List[str] = []

        # Audit negative indicators
        if raw_post and getattr(raw_post, "ai_allow", None) is True:
            audit_notes.append("ai_allow: true detected but rejected (crawler signal, not license)")

        if raw_post and hasattr(raw_post, "external_links"):
            ext = getattr(raw_post, "external_links", []) or []
            if any("creativecommons.org" in str(link).lower() for link in ext):
                audit_notes.append("External CC link detected but rejected (does not license third-party publisher copy)")

        # 1. Statutory Public Domain check (US Federal Government)
        if self.is_verified_public_domain(clean):
            reason = f"Statutory Public Domain: US Federal Government under 17 U.S.C. § 105 ({clean})"
            logger.info(f"[CONTENT RIGHTS] Full text authorized: {reason}")
            return RightsDecision(
                authorized=True,
                reason=reason,
                component="full_text",
                audit_notes=audit_notes,
            )

        # 2. Contractual syndication partner check
        if self.is_authorized_syndication_domain(clean):
            reason = f"Contractual syndication license agreement ({clean})"
            logger.info(f"[CONTENT RIGHTS] Full text authorized: {reason}")
            return RightsDecision(
                authorized=True,
                reason=reason,
                component="full_text",
                audit_notes=audit_notes,
            )

        # 3. Default: Commercial publisher content is summary-only
        reason = f"Commercial publisher '{clean}': full-text republication rights not established (summary-only)"
        logger.debug(f"[CONTENT RIGHTS] Full text restricted: {reason}")
        return RightsDecision(
            authorized=False,
            reason=reason,
            component="full_text",
            audit_notes=audit_notes,
        )

    # -------------------------------------------------------------------------
    # 2. Primary / Hero Image Evaluation
    # -------------------------------------------------------------------------

    def evaluate_hero_image_rights(
        self,
        domain: Optional[str] = None,
        image_url: Optional[str] = None,
        raw_post: Optional[Any] = None,
        explicit_override: Optional[bool] = None,
    ) -> RightsDecision:
        """Determines whether a hero/featured image is authorized for public rendering."""
        if explicit_override is not None:
            return RightsDecision(
                authorized=explicit_override,
                reason="Administrative override",
                component="hero_image",
            )

        if not image_url or not isinstance(image_url, str) or not image_url.strip():
            return RightsDecision(
                authorized=False,
                reason="No hero image URL provided",
                component="hero_image",
            )

        clean_dom = self._clean_domain(domain)
        audit: List[str] = []

        # Check for third-party agency wire credits in thread metadata or caption
        thread = getattr(raw_post, "thread", None) if raw_post else None
        agency = str(getattr(thread, "licensing_agency", "") or "") if thread else ""
        if agency:
            for pat in THIRD_PARTY_MEDIA_AGENCIES:
                if pat.search(agency):
                    reason = f"Third-party wire/agency photo credit detected ({agency})"
                    return RightsDecision(
                        authorized=False,
                        reason=reason,
                        component="hero_image",
                        audit_notes=[f"Agency: {agency}"],
                    )

        # 1. Statutory Public Domain check (US Federal Government)
        if self.is_verified_public_domain(clean_dom):
            # Verify the image URL is from a trusted public domain CDN / host or same domain
            img_host = self._clean_domain(image_url)
            # If the image is hosted by a wire service on a gov page, reject it
            for pat in THIRD_PARTY_MEDIA_AGENCIES:
                if pat.search(img_host):
                    return RightsDecision(
                        authorized=False,
                        reason=f"Third-party agency image host on public domain site ({img_host})",
                        component="hero_image",
                    )
            reason = f"US Federal Government public domain visual media ({clean_dom})"
            return RightsDecision(
                authorized=True,
                reason=reason,
                component="hero_image",
                audit_notes=audit,
            )

        # 2. Contractual syndication partner check
        if self.is_authorized_syndication_domain(clean_dom):
            reason = f"Contractual visual media syndication rights ({clean_dom})"
            return RightsDecision(
                authorized=True,
                reason=reason,
                component="hero_image",
                audit_notes=audit,
            )

        # 3. Commercial publishers: Do NOT display external copyrighted images publicly
        reason = f"Commercial publisher visual media: copyright reserved by {clean_dom} (image-free layout)"
        return RightsDecision(
            authorized=False,
            reason=reason,
            component="hero_image",
            audit_notes=audit,
        )

    # -------------------------------------------------------------------------
    # 3. Inline Article Images Evaluation
    # -------------------------------------------------------------------------

    def evaluate_inline_image_rights(
        self,
        domain: Optional[str] = None,
        image_url: Optional[str] = None,
        caption: Optional[str] = None,
        credit: Optional[str] = None,
        raw_post: Optional[Any] = None,
    ) -> RightsDecision:
        """Determines whether an inline article image is authorized for public rendering."""
        if not image_url or not isinstance(image_url, str) or not image_url.strip():
            return RightsDecision(
                authorized=False,
                reason="No inline image URL provided",
                component="inline_image",
            )

        clean_dom = self._clean_domain(domain)

        # Check caption or credit for third-party copyright markers
        meta_str = f"{caption or ''} {credit or ''}"
        for pat in THIRD_PARTY_MEDIA_AGENCIES:
            if pat.search(meta_str):
                return RightsDecision(
                    authorized=False,
                    reason=f"Third-party copyright in inline image credit: {meta_str.strip()[:60]}",
                    component="inline_image",
                )

        if self.is_verified_public_domain(clean_dom):
            return RightsDecision(
                authorized=True,
                reason=f"US Federal Government public domain inline media ({clean_dom})",
                component="inline_image",
            )

        if self.is_authorized_syndication_domain(clean_dom):
            return RightsDecision(
                authorized=True,
                reason=f"Contractual syndication inline media ({clean_dom})",
                component="inline_image",
            )

        return RightsDecision(
            authorized=False,
            reason=f"Commercial publisher inline media: copyright reserved by {clean_dom}",
            component="inline_image",
        )

    # -------------------------------------------------------------------------
    # 4. Comprehensive Evaluation & Backwards Compatibility
    # -------------------------------------------------------------------------

    def evaluate_publication_rights(
        self,
        domain: Optional[str] = None,
        raw_post: Optional[Any] = None,
        explicit_override: Optional[bool] = None,
    ) -> bool:
        """Backwards-compatible interface returning boolean for full-text authorization."""
        dec = self.evaluate_full_text_rights(
            domain=domain,
            raw_post=raw_post,
            explicit_override=explicit_override,
        )
        return dec.authorized

    def evaluate_article_rights(
        self,
        domain: Optional[str] = None,
        raw_post: Optional[Any] = None,
        hero_image_url: Optional[str] = None,
        inline_images: Optional[List[Dict[str, Any]]] = None,
        explicit_override: Optional[bool] = None,
    ) -> ArticleRightsPackage:
        """Evaluates complete rights package for an article across text and media."""
        text_dec = self.evaluate_full_text_rights(
            domain=domain,
            raw_post=raw_post,
            explicit_override=explicit_override,
        )
        hero_dec = self.evaluate_hero_image_rights(
            domain=domain,
            image_url=hero_image_url,
            raw_post=raw_post,
            explicit_override=explicit_override,
        )
        inline_auth = False
        inline_reason = "No inline images provided"
        if inline_images:
            # Inline images authorized only if publisher rights permit
            any_auth = False
            for img in inline_images:
                url = img.get("url") if isinstance(img, dict) else str(img)
                cap = img.get("caption") if isinstance(img, dict) else None
                cred = img.get("credit") if isinstance(img, dict) else None
                i_dec = self.evaluate_inline_image_rights(
                    domain=domain,
                    image_url=url,
                    caption=cap,
                    credit=cred,
                    raw_post=raw_post,
                )
                if i_dec.authorized:
                    any_auth = True
            inline_auth = any_auth
            inline_reason = "Evaluated inline media rights" if any_auth else "Inline media unauthorized"

        return ArticleRightsPackage(
            full_text_authorized=text_dec.authorized,
            full_text_reason=text_dec.reason,
            hero_image_authorized=hero_dec.authorized,
            hero_image_reason=hero_dec.reason,
            inline_images_authorized=inline_auth,
            inline_images_reason=inline_reason,
            audit_log=text_dec.audit_notes + hero_dec.audit_notes,
        )
