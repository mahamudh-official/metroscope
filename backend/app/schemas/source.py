from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class SourceBase(BaseModel):
    name: str = Field(max_length=255)
    domain: str = Field(max_length=255)
    website_url: Optional[str] = Field(default=None, max_length=1024)
    country: Optional[str] = Field(default=None, max_length=10)
    language: str = Field(default="en", max_length=10)


class SourceResponse(SourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
