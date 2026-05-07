"""Biosimilar candidate domain model."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field

from ember_data.models.patent import Patent


class CompetitiveLandscape(BaseModel):
    """Summary of approved biosimilar competition for a reference biologic."""

    approved_biosimilars: list[str] = Field(default_factory=list)
    count: int = 0


class BiosimilarCandidate(BaseModel):
    """A reference biologic evaluated for biosimilar development opportunity."""

    drug_name: str
    brand_names: list[str] = Field(default_factory=list)
    originator: str
    target_antigen: str
    modality: str = "mAb"
    cell_line: str = ""
    cell_line_class: str = "mammalian"
    indications: list[str] = Field(default_factory=list)
    annual_revenue_usd_millions: float = 0.0
    revenue_year: int | None = None
    earliest_expiry: date
    patent_expiry_us: date | None = None
    patent_expiry_eu: date | None = None
    key_patent_numbers: list[str] = Field(default_factory=list)
    competitive_landscape: CompetitiveLandscape = Field(
        default_factory=CompetitiveLandscape
    )
    has_approved_biosimilar: bool = False
    notes: str = ""
    rank: int = 0
    patents: list[Patent] = Field(default_factory=list)
