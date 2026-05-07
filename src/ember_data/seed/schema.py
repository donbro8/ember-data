"""Schema for the mAb reference seed dataset."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel, Field


class MabEntry(BaseModel):
    """A single monoclonal antibody entry from the curated seed dataset.

    Used as input to the biosimilar screening pipeline (stage 1 hard filter).
    """

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
    patent_expiry_us: date | None = None
    patent_expiry_eu: date | None = None
    key_patent_numbers: list[str] = Field(default_factory=list)
    biosimilar_competitors: list[str] = Field(default_factory=list)
    has_approved_biosimilar: bool = False
    notes: str = ""
