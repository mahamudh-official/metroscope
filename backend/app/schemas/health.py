from pydantic import BaseModel, Field


class HealthResponse(BaseModel):
    status: str = Field(default="ok", description="Overall application status")
    environment: str = Field(description="Runtime environment name")
    database_connected: bool = Field(description="PostgreSQL connectivity state")
    version: str = Field(default="0.1.0", description="API version")
