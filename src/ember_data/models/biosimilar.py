"""Biosimilar candidate domain model."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, model_validator

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
    category: str = "mAb"
    modality: str = "mAb"
    cell_line: str = ""
    cell_line_class: str = "mammalian"
    indications: list[str] = Field(default_factory=list)
    annual_revenue_usd_millions: float = 0.0
    revenue_year: int | None = None
    earliest_expiry: date
    patent_expiry_us: date | None = None
    patent_expiry_eu: date | None = None
    patent_expiries: dict[str, date] = Field(default_factory=dict)
    earliest_expiry_jurisdiction: str = ""
    key_patent_numbers: list[str] = Field(default_factory=list)
    competitive_landscape: CompetitiveLandscape = Field(
        default_factory=CompetitiveLandscape
    )
    has_approved_biosimilar: bool = False
    notes: str = ""
    rank: int = 0
    patents: list[Patent] = Field(default_factory=list)

    @model_validator(mode="before")
    @classmethod
    def _sync_patent_expiries(cls, data: Any) -> Any:  # noqa: ANN401
        """Keep patent_expiry_us/eu and patent_expiries dict in sync."""
        if isinstance(data, dict):
            expiries: dict[str, date] = data.get("patent_expiries", {})

            # dict -> flat fields
            if "US" in expiries and not data.get("patent_expiry_us"):
                data["patent_expiry_us"] = expiries["US"]
            if "EU" in expiries and not data.get("patent_expiry_eu"):
                data["patent_expiry_eu"] = expiries["EU"]

            # flat fields -> dict
            if data.get("patent_expiry_us") and "US" not in expiries:
                expiries["US"] = data["patent_expiry_us"]
            if data.get("patent_expiry_eu") and "EU" not in expiries:
                expiries["EU"] = data["patent_expiry_eu"]

            if expiries:
                data["patent_expiries"] = expiries

        return data
