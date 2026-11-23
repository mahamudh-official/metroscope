"""Base abstractions and data structures for social media publishing adapters."""

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
import json
from typing import Any, Dict, Optional, Tuple


@dataclass
class SocialPostResult:
    """Standardized outcome from a social media publishing attempt."""
    success: bool
    platform: str
    external_post_id: Optional[str] = None
    error_message: Optional[str] = None
    dry_run: bool = False
    ambiguous: bool = False
    response_data: Dict[str, Any] = field(default_factory=dict)


def mask_secret(secret: Optional[str], visible_chars: int = 4) -> str:
    """Masks sensitive credentials for safe logging."""
    if not secret:
        return "[NOT SET]"
    if len(secret) <= visible_chars * 2:
        return "***"
    return f"{secret[:visible_chars]}...{secret[-visible_chars:]}"


def safe_parse_json_response(
    response_text: str,
    status_code: int,
    provider: str,
) -> Tuple[Optional[Dict[str, Any]], Optional[str]]:
    """Safely decodes and validates a JSON dictionary from an HTTP response.

    Returns:
        (data_dict, None) if the payload is valid JSON and a dictionary.
        (None, error_diagnostic) if empty, malformed, or a non-dict structure.

    Guarantees:
        - Never raises JSONDecodeError or ValueError.
        - Preserves HTTP status and safe diagnostic info without secrets.
    """
    if not response_text or not response_text.strip():
        return None, f"{provider} returned an empty response body (HTTP {status_code})"

    try:
        data = json.loads(response_text)
    except Exception as exc:
        clean_preview = response_text[:120].replace("\n", " ").replace("\r", " ").strip()
        return None, (
            f"{provider} returned malformed JSON (HTTP {status_code}): '{clean_preview}' "
            f"(error: {type(exc).__name__})"
        )

    if not isinstance(data, dict):
        return None, (
            f"{provider} returned a non-object JSON structure "
            f"(expected object, got {type(data).__name__}, HTTP {status_code})"
        )

    return data, None


class SocialPlatformClient(ABC):
    """Abstract base class for social media publishing clients."""

    @property
    @abstractmethod
    def platform_name(self) -> str:
        """Name of the platform (e.g. 'facebook', 'x')."""
        pass

    @abstractmethod
    def is_configured(self) -> bool:
        """Returns True if the required credentials and configuration are present."""
        pass

    @abstractmethod
    async def publish(
        self,
        text: str,
        link: Optional[str] = None,
        article_id: Optional[int] = None,
    ) -> SocialPostResult:
        """Publishes a news post to the social platform.
        
        Must respect dry-run settings and return SocialPostResult.
        """
        pass
