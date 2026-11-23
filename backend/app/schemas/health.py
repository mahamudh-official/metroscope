from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Overall application status")
    environment: str = Field(description="Runtime environment name")
    database_connected: bool = Field(description="PostgreSQL connectivity state")
    version: str = Field(default="0.1.0", description="API version")


class LivenessResponse(BaseModel):
    status: str = Field(default="alive", description="Process liveness state")
    timestamp: str = Field(description="ISO timestamp of the health check")


class ReadinessResponse(BaseModel):
    status: str = Field(description="Service readiness state ('ready' or 'unready')")
    database_ready: bool = Field(description="Database connectivity state")
    detail: Optional[str] = Field(default=None, description="Diagnostic detail")


class SystemMetricsResponse(BaseModel):
    environment: str
    version: str = "0.1.0"
    database_connected: bool
    total_articles: int
    active_subscribers: int
    social_dry_run: bool
    email_dry_run: bool
    worker_enabled: bool


class OperationalStatusResponse(BaseModel):
    environment: str
    version: str = "0.1.0"
    database_connected: bool
    scheduler: Dict[str, Any]
    ingestion: Dict[str, Any]
    articles_summary: Dict[str, Any]
    api_usage: Dict[str, Any]
    social_publishing: Dict[str, Any]
    recent_errors: List[str] = Field(default_factory=list)

