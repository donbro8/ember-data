"""Schema for the biologic reference seed dataset."""

from __future__ import annotations

from datetime import date
from typing import Any

from pydantic import BaseModel, Field, model_validator


_VALID_CATEGORIES = frozenset({
    "mAb",
    "fusion_protein",
    "insulin",
    "epo",
    "gcsf",
    "interferon",
    "adc",
    "bispecific",
    "enzyme",
    "other",
})

_VALID_JURISDICTIONS = frozenset({
    "US", "EU", "JP", "CN", "KR", "CA", "AU", "GB", "IN", "BR", "WIPO",
})


class BiologicEntry(BaseModel):
    """A single biologic entry from the curated seed dataset.

    Used as input to the biosimilar screening pipeline (stage 1 hard filter).
    """

    drug_name: str
    brand_names: list[str] = Field(default_factory=list)
    originator: str
    target_antigen: str
    modality: str = "mAb"
    category: str = "mAb"
    cell_line: str = ""
    cell_line_class: str = "mammalian"
    indications: list[str] = Field(default_factory=list)
    annual_revenue_usd_millions: float = 0.0
    revenue_year: int | None = None
    patent_expiry_us: date | None = None
    patent_expiry_eu: date | None = None
    patent_expiries: dict[str, date] = Field(default_factory=dict)
    key_patent_numbers: list[str] = Field(default_factory=list)
    biosimilar_competitors: list[str] = Field(default_factory=list)
    has_approved_biosimilar: bool = False
    notes: str = ""

    @model_validator(mode="before")
    @classmethod
    def _sync_patent_expiries(cls, data: Any) -> Any:  # noqa: ANN401
        """Keep patent_expiry_us/eu and patent_expiries dict in sync.

        If *patent_expiries* contains US/EU keys but the flat fields are not
        set, populate the flat fields from the dict.  Conversely, if the flat
        fields are set but patent_expiries is missing those keys, populate the
        dict from the flat fields.  This ensures backward compatibility with
        callers that pass only the flat fields as well as forward compatibility
        with callers that pass the dict.
        """
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


# Backward-compatible alias so existing imports still work.
MabEntry = BiologicEntry
