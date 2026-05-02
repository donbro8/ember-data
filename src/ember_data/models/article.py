"""Article domain model."""

from datetime import date

from pydantic import BaseModel, Field


class Article(BaseModel):
    """A research article from PubMed or user-uploaded literature."""

    pmid: str | None = None
    title: str
    authors: list[str]
    journal: str
    pub_date: date
    abstract: str
    mesh_terms: list[str] = Field(default_factory=list)
    cited_by_count: int = 0
    doi: str | None = None
