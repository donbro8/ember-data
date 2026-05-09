"""PatentJurisdiction model, ResultType enum, CandidateResult model, and related utilities."""

import hashlib
import re
from datetime import date
from enum import Enum
from typing import Literal

from pydantic import BaseModel, Field, model_validator

JURISDICTION_NAMES: dict[str, str] = {
    "US": "United States",
    "EP": "European Patent Office",
    "EU": "European Union",
    "JP": "Japan",
    "CN": "China",
    "KR": "South Korea",
    "CA": "Canada",
    "AU": "Australia",
    "GB": "United Kingdom",
    "IN": "India",
    "BR": "Brazil",
    "WIPO": "World Intellectual Property Organization",
}


def build_patent_url(publication_number: str) -> str:
    """Return a Google Patents URL for the given publication number."""
    return f"https://patents.google.com/patent/{publication_number}"


class PatentJurisdiction(BaseModel):
    """Per-country patent representation with expiry approximation flag."""

    country_code: str
    country_name: str
    publication_number: str
    filing_date: date | None = None
    grant_date: date | None = None
    expiry_date: date | None = None
    expiry_date_approximate: bool = False
    status: Literal["active", "expired", "pending"]
    title: str | None = None
    url: str


class ResultType(str, Enum):
    """Classification of a CandidateResult as a drug or target entity."""

    DRUG = "DRUG"
    TARGET = "TARGET"


def _normalize(text: str) -> str:
    """Lowercase and strip all whitespace from a string."""
    return re.sub(r"\s+", "", text.lower())


def build_canonical_id(result: "CandidateResult") -> str:
    """Return a stable canonical identifier for a CandidateResult.

    Three-tier fallback:
    1. fda_generic_name present → normalize to lowercase, strip spaces
    2. drug_name + target present → ``{drug_name}_{target}`` normalized
    3. Otherwise → SHA-256 hash of sorted source IDs
    """
    if result.fda_generic_name:
        return _normalize(result.fda_generic_name)

    if result.drug_name and result.target:
        return _normalize(f"{result.drug_name}_{result.target}")

    # Tier 3: hash of sorted source IDs
    sorted_ids = sorted(result.sources_contributed)
    payload = "|".join(sorted_ids).encode()
    return hashlib.sha256(payload).hexdigest()


class CandidateResult(BaseModel):
    """Unified output schema for all agent query results."""

    # Core identity
    drug_name: str | None = None
    fda_generic_name: str | None = None
    target: str | None = None

    # Computed fields (populated by model_validator after init)
    result_type: ResultType = Field(default=ResultType.TARGET)
    canonical_id: str = Field(default="")
    display_label: str = Field(default="")

    # Patent data
    patents: list[PatentJurisdiction] = Field(default_factory=list)
    earliest_patent_expiry: date | None = None
    earliest_expiry_jurisdiction: str | None = None

    # Scoring
    overall_score: float | None = Field(default=None, ge=0, le=1)

    # Provenance
    sources_contributed: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)

    # Optional enrichment fields
    indication: str | None = None
    mechanism_of_action: str | None = None
    clinical_stage: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    synthesis_summary: str | None = None

    @model_validator(mode="after")
    def compute_derived_fields(self) -> "CandidateResult":
        """Deterministically assign result_type, canonical_id, and display_label."""
        # result_type
        if self.drug_name or self.fda_generic_name:
            self.result_type = ResultType.DRUG
        else:
            self.result_type = ResultType.TARGET

        # canonical_id
        self.canonical_id = build_canonical_id(self)

        # display_label
        if self.result_type == ResultType.DRUG:
            self.display_label = self.fda_generic_name or self.drug_name or ""
        else:
            self.display_label = self.target or ""

        return self
