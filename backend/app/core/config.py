from decimal import Decimal
from typing import List, Union
from pydantic import AnyHttpUrl, PostgresDsn, computed_field, field_validator
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=(".env", "../.env"),
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application
    PROJECT_NAME: str = "MetroScope"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    LOG_LEVEL: str = "INFO"
    API_V1_STR: str = "/api/v1"

    # Server
    BACKEND_HOST: str = "0.0.0.0"
    BACKEND_PORT: int = 8000

    # CORS Origins
    BACKEND_CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "https://themetroscope.com",
        "https://www.themetroscope.com",
        "https://api.themetroscope.com",
    ]

    @field_validator("BACKEND_CORS_ORIGINS", mode="before")
    @classmethod
    def assemble_cors_origins(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v  # type: ignore
        raise ValueError(v)

    # Security & Cryptography
    SECRET_KEY: str = "metroscope_secret_key_default_salt"
    OPERATOR_API_KEY: str | None = None

    # Trusted Hosts for Production Hardening
    ALLOWED_HOSTS: List[str] = [
        "localhost",
        "127.0.0.1",
        "themetroscope.com",
        "www.themetroscope.com",
        "api.themetroscope.com",
        "metroscope.news",
        "www.metroscope.news",
        "backend",
        "testserver",
        "test",
    ]

    @field_validator("ALLOWED_HOSTS", mode="before")
    @classmethod
    def assemble_allowed_hosts(cls, v: Union[str, List[str]]) -> List[str]:
        if isinstance(v, str) and not v.startswith("["):
            return [i.strip() for i in v.split(",") if i.strip()]
        elif isinstance(v, (list, str)):
            return v  # type: ignore
        raise ValueError(v)

    # Database Settings
    POSTGRES_SERVER: str = "127.0.0.1"
    POSTGRES_PORT: int = 5432
    POSTGRES_USER: str = "metroscope_user"
    POSTGRES_PASSWORD: str = "metroscope_secure_password"
    POSTGRES_DB: str = "metroscope"

    DATABASE_URL: str | None = None
    DATABASE_SYNC_URL: str | None = None

    @computed_field  # type: ignore[prop-decorator]
    @property
    def async_database_url(self) -> str:
        if self.DATABASE_URL:
            return self.DATABASE_URL
        return (
            f"postgresql+asyncpg://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    @computed_field  # type: ignore[prop-decorator]
    @property
    def sync_database_url(self) -> str:
        if self.DATABASE_SYNC_URL:
            return self.DATABASE_SYNC_URL
        return (
            f"postgresql://{self.POSTGRES_USER}:{self.POSTGRES_PASSWORD}@"
            f"{self.POSTGRES_SERVER}:{self.POSTGRES_PORT}/{self.POSTGRES_DB}"
        )

    # News Worker & Scheduling
    WORKER_ENABLED: bool = True

    # Webz.io News API Integration & Budget Protection
    WEBZ_IO_API_KEY: str | None = None
    WEBZ_IO_BASE_URL: str = "https://api.webz.io"
    WEBZ_IO_ENDPOINT: str = "/api/news"
    WEBZ_IO_QUERY: str = (
        '(category:"politics" OR category:"economy, business and finance" OR category:"science and technology" '
        'OR category:"health" OR category:"environment" OR category:"sport" OR category:"sports" '
        'OR category:"arts, culture and entertainment" OR category:"war, conflict and unrest") '
        'AND (country:US OR "international" OR "global" OR "world") AND language:english'
    )
    WEBZ_IO_COLLECTION_ENABLED: bool = True
    WEBZ_IO_MONTHLY_CREDIT: Decimal = Decimal("5.00")
    WEBZ_IO_COLLECTION_CEILING: Decimal = Decimal("4.00")
    WEBZ_IO_PROTECTED_RESERVE: Decimal = Decimal("1.00")
    WEBZ_IO_ESTIMATED_COST_PER_REQUEST: Decimal = Decimal("0.0050")
    WEBZ_IO_REQUEST_TIMEOUT_SECONDS: float = 15.0
    WEBZ_IO_MAX_RETRIES: int = 1
    WEBZ_IO_TIMEZONE: str = "Asia/Dhaka"
    WEBZ_IO_MORNING_SCHEDULE_HOUR: int = 8
    WEBZ_IO_MORNING_SCHEDULE_MINUTE: int = 0
    WEBZ_IO_EVENING_SCHEDULE_HOUR: int = 20
    WEBZ_IO_EVENING_SCHEDULE_MINUTE: int = 0
    # Backward-compatible schedule aliases
    WEBZ_IO_SPORTS_SCHEDULE_HOUR: int = 8
    WEBZ_IO_SPORTS_SCHEDULE_MINUTE: int = 0
    WEBZ_IO_BUSINESS_SCHEDULE_HOUR: int = 20
    WEBZ_IO_BUSINESS_SCHEDULE_MINUTE: int = 0
    WEBZ_IO_TARGET_ARTICLES_PER_JOB: int = 10
    INGESTION_MIN_QUALITY_SCORE: float = 30.0

    # Phase 5: Automated Social Publishing
    SITE_URL: str = "https://themetroscope.com"
    SOCIAL_PUBLISHING_ENABLED: bool = False
    SOCIAL_DRY_RUN: bool = True  # Dry-run mode enabled by default
    SOCIAL_PUBLISHING_INTERVAL_MINUTES: int = 30
    SOCIAL_MAX_POSTS_PER_RUN: int = 2
    SOCIAL_MIN_QUALITY_SCORE: float = 70.0
    STALE_PUBLISHING_TIMEOUT_MINUTES: int = 60

    # Facebook Page (Meta Graph API)
    FACEBOOK_ENABLED: bool = False
    FACEBOOK_PAGE_ID: str | None = None
    FACEBOOK_PAGE_ACCESS_TOKEN: str | None = None
    FACEBOOK_GRAPH_API_VERSION: str = "v27.0"
    FACEBOOK_API_VERSION: str | None = None  # Deprecated alias; preserved for backward compatibility
    FACEBOOK_DEFAULT_POST_TYPE: str = "photo"  # "photo" or "text"
    FACEBOOK_POST_CAPTION_ENABLED: bool = True
    FACEBOOK_FOLLOWUP_COMMENT_ENABLED: bool = True
    FACEBOOK_AUTO_PUBLISH: bool = False
    FACEBOOK_MAX_POSTS_PER_DAY: int = 48

    # X (Twitter API v2)
    X_ENABLED: bool = False
    X_API_KEY: str | None = None
    X_API_SECRET: str | None = None
    X_ACCESS_TOKEN: str | None = None
    X_ACCESS_TOKEN_SECRET: str | None = None
    X_BEARER_TOKEN: str | None = None
    X_MAX_POSTS_PER_DAY: int = 15  # Conservative default respecting X Free tier (17/24h)

    # Phase 6: Email Subscription & Newsletter Delivery
    EMAIL_DRY_RUN: bool = True  # Safe dry-run mode enabled by default
    SMTP_HOST: str = "localhost"
    SMTP_PORT: int = 587
    SMTP_USERNAME: str | None = None
    SMTP_PASSWORD: str | None = None
    SMTP_FROM_EMAIL: str = "newsletter@themetroscope.com"
    SMTP_FROM_NAME: str = "MetroScope News"
    SMTP_USE_TLS: bool = True
    SMTP_TIMEOUT_SECONDS: float = 15.0
    NEWSLETTER_SCHEDULE_HOUR: int = 6
    NEWSLETTER_SCHEDULE_MINUTE: int = 0
    NEWSLETTER_MIN_QUALITY_SCORE: float = 70.0
    NEWSLETTER_MAX_ARTICLES: int = 5
    SUBSCRIPTION_RATE_LIMIT_PER_HOUR: int = 5
    VERIFICATION_TOKEN_EXPIRE_HOURS: int = 24

    # Phase 7: Photo Card & ScreenshotOne Dual-Key Image Rendering
    SCREENSHOTONE_ACCESS_KEY_1: str | None = None
    SCREENSHOTONE_ACCESS_KEY_2: str | None = None
    SCREENSHOTONE_ACCESS_KEY: str | None = None  # Single-key backward-compatible fallback
    SCREENSHOTONE_SECRET_KEY: str | None = None
    SCREENSHOTONE_BASE_URL: str = "https://api.screenshotone.com"
    SCREENSHOTONE_TIMEOUT_SECONDS: float = 30.0
    SCREENSHOTONE_IMAGE_FORMAT: str = "jpeg"
    SCREENSHOTONE_IMAGE_QUALITY: int = 90

    def validate_production_configuration(self) -> List[str]:
        """Audits active settings against production security and reliability standards."""
        warnings: List[str] = []
        is_prod = self.ENVIRONMENT.lower() == "production"

        if is_prod:
            if self.DEBUG:
                warnings.append("CRITICAL: DEBUG mode is enabled in production environment.")
            if self.POSTGRES_PASSWORD == "metroscope_secure_password":
                warnings.append("WARNING: Default/sample POSTGRES_PASSWORD in use in production.")
            if self.SECRET_KEY == "metroscope_secret_key_default_salt":
                warnings.append("CRITICAL: Insecure default SECRET_KEY in use in production environment.")
            if not self.SOCIAL_DRY_RUN and self.SOCIAL_PUBLISHING_ENABLED:
                if not (self.FACEBOOK_PAGE_ACCESS_TOKEN or self.X_ACCESS_TOKEN):
                    warnings.append("WARNING: Live social publishing enabled without configured platform credentials.")
            if not self.EMAIL_DRY_RUN and self.SMTP_HOST == "localhost":
                warnings.append("WARNING: Live email sending enabled with localhost SMTP server.")
            if self.WORKER_ENABLED and self.WEBZ_IO_COLLECTION_ENABLED and not self.WEBZ_IO_API_KEY:
                warnings.append("WARNING: News worker enabled without configured WEBZ_IO_API_KEY.")
        return warnings


settings = Settings()
