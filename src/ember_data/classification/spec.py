"""SearchSpec, DateWindow, ResolvedTerm, and DisambiguationRequest types."""

from __future__ import annotations

from datetime import date
from typing import Literal

from pydantic import BaseModel, Field

from ember_data.classification.enums import (
    ATCNode,
    CellLineClass,
    Jurisdiction,
    MeSHTerm,
    ModalityClassification,
    TargetClassification,
)


class DateWindow(BaseModel):
    """Inclusive date range with convenience constructors."""

    start: date | None = None
    end: date | None = None

    @classmethod
    def before(cls, cutoff: date) -> "DateWindow":
        """Match dates strictly before (and up to) *cutoff*."""
        return cls(end=cutoff)

    @classmethod
    def after(cls, cutoff: date) -> "DateWindow":
        """Match dates on or after *cutoff*."""
        return cls(start=cutoff)

    @classmethod
    def between(cls, start: date, end: date) -> "DateWindow":
        """Match dates within the inclusive [start, end] range."""
        return cls(start=start, end=end)

    @classmethod
    def not_yet_expired(cls, as_of: date | None = None) -> "DateWindow":
        """Match records whose end/expiry date is on or after *as_of* (defaults to today)."""
        cutoff = as_of if as_of is not None else date.today()
        return cls(start=cutoff)


class ResolvedTerm(BaseModel):
    """A taxonomy term resolved from a free-text input."""

    taxonomy: str
    identifier: str
    label: str
    confidence: float = Field(ge=0.0, le=1.0)
    synonyms: list[str] = Field(default_factory=list)
    parent_id: str | None = None


class DisambiguationRequest(BaseModel):
    """Emitted when a term cannot be resolved automatically and requires human selection."""

    raw_input: str
    options: list[ResolvedTerm]
    rationale: str


class SearchSpec(BaseModel):
    """Structured specification for a biotech data search query."""

    # Optional source query text retained for traceability.
    query: str = ""

    # Target dimension (UniProt/GO resolver)
    target: TargetClassification | ResolvedTerm | None = None

    # Drug/therapeutic dimension (ATC resolver)
    therapeutic_area: ATCNode | ResolvedTerm | None = None
    drug_names: list[str] = Field(default_factory=list)

    # Indication dimension (MeSH resolver)
    indications: list[MeSHTerm | ResolvedTerm] = Field(default_factory=list)

    # Modality dimension (Modality resolver)
    modality: ModalityClassification | None = None
    cell_line_class: CellLineClass | None = None

    # Temporal dimensions
    patent_expiry_window: DateWindow | None = None
    approval_date_range: DateWindow | None = None

    # Commercial / regulatory dimensions
    min_revenue_millions: float | None = Field(default=None, ge=0)
    jurisdictions: list[Jurisdiction] = Field(default_factory=list)

    # Meta
    include_existing_biosimilars: bool | None = None
    max_results: int = Field(default=500, ge=1, le=1000)

    # Resolved terms and pending user choices from the classification phase.
    resolved_terms: list[ResolvedTerm] = Field(default_factory=list)
    pending_disambiguations: list[DisambiguationRequest] = Field(default_factory=list)

    # Domain scope - which data sources to query.
    domains: list[Literal["trials", "patents", "articles", "candidates"]] = Field(
        default_factory=lambda: ["trials", "patents", "articles", "candidates"]
    )
