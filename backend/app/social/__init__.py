"""Social publishing package for automated news distribution."""

from app.social.base import (
    SocialPlatformClient,
    SocialPostResult,
    mask_secret,
    safe_parse_json_response,
)
from app.social.content_formatter import (
    calculate_x_post_weighted_length,
    format_category_hashtag,
    format_facebook_caption,
    format_facebook_first_comment,
    format_facebook_post,
    format_x_post,
    get_article_url,
    validate_x_post_length,
)
from app.social.facebook_client import FacebookPageClient
from app.social.publishing_scheduler import (
    publish_social_news_job,
    recover_stale_publishing_job,
)
from app.social.publishing_service import SocialPublishingService
from app.social.x_client import XClient

__all__ = [
    "SocialPlatformClient",
    "SocialPostResult",
    "mask_secret",
    "safe_parse_json_response",
    "format_facebook_caption",
    "format_facebook_first_comment",
    "format_facebook_post",
    "format_x_post",
    "format_category_hashtag",
    "get_article_url",
    "validate_x_post_length",
    "calculate_x_post_weighted_length",
    "FacebookPageClient",
    "XClient",
    "SocialPublishingService",
    "publish_social_news_job",
    "recover_stale_publishing_job",
]
