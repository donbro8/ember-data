"""Source provenance model for dynamic search results."""

from datetime import datetime

from pydantic import BaseModel, Field


class SourceProvenance(BaseModel):
    """Records the origin and retrieval context of a search result contribution."""

    source_name: str
    source_id: str | None = None
    source_url: str | None = None
    retrieved_at: datetime
    matched_fields: list[str] = Field(default_factory=list)
