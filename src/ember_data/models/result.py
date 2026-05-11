"""PatentJurisdiction model, ResultType enum, CandidateResult model, and related utilities."""

import hashlib
import re
import unicodedata
from datetime import date
from enum import Enum
from typing import Any, Literal

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
    expiry_derivation_method: (
        Literal["filing_20yr", "spc_adjusted", "pta_adjusted", "verified", "manual"] | None
    ) = None
    expiry_derivation_provenance: str | None = None
    status: Literal["active", "expired", "pending"]
    title: str | None = None
    url: str


class TrialSummary(BaseModel):
    """Lightweight summary of a clinical trial for embedding in CandidateResult."""

    nct_id: str
    phase: str
    status: str
    indication: str | None = None
    sponsor: str | None = None
    url: str | None = None


class ArticleSummary(BaseModel):
    """Lightweight summary of a scientific article; pmid is nullable for preprints."""

    pmid: str | None = None
    title: str
    journal: str | None = None
    year: int | None = None
    doi: str | None = None
    url: str | None = None


class ResultType(str, Enum):
    """Classification of a CandidateResult as a drug or target entity."""

    DRUG = "DRUG"
    TARGET = "TARGET"


def _normalize(text: str) -> str:
    """Apply Unicode NFC normalization, then lowercase and strip all whitespace."""
    nfc = unicodedata.normalize("NFC", text)
    return re.sub(r"\s+", "", nfc.lower())


def build_canonical_id(result: "CandidateResult") -> str:
    """Return a stable canonical identifier for a CandidateResult.

    Three-tier fallback:
    1. fda_generic_name present → ``fda:{name}`` normalized
    2. drug_name + target present → ``drug:{name}|target:{name}`` sorted
    3. Otherwise → SHA-256 hash of sorted source IDs
    """
    if result.fda_generic_name:
        return f"fda:{_normalize(result.fda_generic_name)}"

    if result.drug_name and result.target:
        drug_part = f"drug:{_normalize(result.drug_name)}"
        target_part = f"target:{_normalize(result.target)}"
        parts = sorted([drug_part, target_part])
        return "|".join(parts)

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
    earliest_patent_expiry_derivation_method: (
        Literal["filing_20yr", "spc_adjusted", "pta_adjusted", "verified", "manual"] | None
    ) = None
    earliest_patent_expiry_verified_date: date | None = None
    data_exclusivity_expiry: date | None = None
    data_exclusivity_regime: str | None = None
    framework_regulatory_context: dict[str, Any] = Field(default_factory=dict)

    # Scoring
    overall_score: float | None = Field(default=None, ge=0, le=1)

    # Provenance
    sources_contributed: list[str] = Field(default_factory=list)
    source_urls: list[str] = Field(default_factory=list)

    # Optional enrichment fields
    indication: list[str] = Field(default_factory=list)
    mechanism_of_action: str | None = None
    clinical_stage: str | None = None
    risk_flags: list[str] = Field(default_factory=list)
    synthesis_summary: str | None = None

    # Score breakdown
    structured_score: float | None = None
    semantic_score: float | None = None
    evidence_score: float | None = None

    # Score and match explanation (additive; backward compatible)
    matched_dimensions: list[str] = Field(default_factory=list)
    missed_dimensions: list[str] = Field(default_factory=list)
    concrete_labels: dict[str, str] = Field(default_factory=dict)
    component_scores: dict[str, float] = Field(default_factory=dict)
    threshold_metadata: dict[str, Any] = Field(default_factory=dict)
    suppression_metadata: dict[str, Any] = Field(default_factory=dict)
    evidence_summary: dict[str, Any] = Field(default_factory=dict)

    # Identity enrichment
    brand_names: list[str] = Field(default_factory=list)
    originator: str | None = None
    target_aliases: list[str] = Field(default_factory=list)
    modality: str | None = None
    category: str | None = None

    # Evidence
    trials: list[TrialSummary] = Field(default_factory=list)
    trial_count: int = 0
    latest_trial_phase: str | None = None
    articles: list[ArticleSummary] = Field(default_factory=list)
    article_count: int = 0

    # Commercial
    annual_revenue_usd_millions: float | None = None
    revenue_year: int | None = None
    biosimilar_competitors: list[str] = Field(default_factory=list)
    biosimilar_competitor_count: int = 0
    has_approved_biosimilar: bool = False

    # FDA
    fda_brand_name: str | None = None
    fda_manufacturer: str | None = None
    fda_therapeutic_area: str | None = None

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
