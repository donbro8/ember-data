"""Patent domain model."""

from datetime import date

from pydantic import BaseModel, Field


class Patent(BaseModel):
    """A patent document."""

    publication_number: str
    title: str
    abstract: str
    claims: list[str]
    assignee: str
    filing_date: date
    grant_date: date | None = None
    cited_by_count: int = 0
    relevant_targets: list[str] = Field(default_factory=list)
