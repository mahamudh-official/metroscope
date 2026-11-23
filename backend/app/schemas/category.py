from typing import Optional
from pydantic import BaseModel, ConfigDict, Field


class CategoryBase(BaseModel):
    name: str = Field(max_length=100)
    slug: str = Field(max_length=100)
    description: Optional[str] = Field(default=None, max_length=500)


class CategoryResponse(CategoryBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    article_count: Optional[int] = Field(default=None, description="Number of published articles in category")
