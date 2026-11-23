import datetime
from typing import Optional
from pydantic import BaseModel, ConfigDict


class IngestionRunResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    provider: str
    started_at: datetime.datetime
    completed_at: Optional[datetime.datetime] = None
    status: str
    fetched_count: int
    inserted_count: int
    duplicate_count: int
    filtered_count: int = 0
    failed_count: int
    error_message: Optional[str] = None
    created_at: datetime.datetime
