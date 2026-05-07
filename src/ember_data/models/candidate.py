"""Candidate and CandidateScores domain models."""

from datetime import datetime

from pydantic import BaseModel, Field, model_validator

from ember_data.models.article import Article
from ember_data.models.patent import Patent
from ember_data.models.provenance import SourceProvenance
from ember_data.models.target import Target
from ember_data.models.trial import Trial


class CandidateScores(BaseModel):
    """Scoring dimensions for a candidate with configurable weights."""

    clinical_stage: float = Field(ge=0, le=1)
    ip_freedom: float = Field(ge=0, le=1)
    evidence_strength: float = Field(ge=0, le=1)
    novelty: float = Field(ge=0, le=1)
    overall: float = Field(default=0.0, ge=0, le=1)

    # Configurable weights (defaults per spec)
    weight_clinical_stage: float = 0.3
    weight_ip_freedom: float = 0.25
    weight_evidence_strength: float = 0.25
    weight_novelty: float = 0.2

    # Dynamic retrieval scoring signals (optional; populated by semantic/structured search)
    semantic_score: float | None = Field(default=None, ge=0, le=1)
    structured_score: float | None = Field(default=None, ge=0, le=1)
    evidence_score: float | None = Field(default=None, ge=0, le=1)

    @model_validator(mode="after")
    def compute_overall(self) -> "CandidateScores":
        """Compute overall score as weighted sum of dimensions."""
        self.overall = (
            self.clinical_stage * self.weight_clinical_stage
            + self.ip_freedom * self.weight_ip_freedom
            + self.evidence_strength * self.weight_evidence_strength
            + self.novelty * self.weight_novelty
        )
        return self


class Candidate(BaseModel):
    """A scored, ranked result from the agent pipeline.

    Supports both PLAN-001 structured results (target required) and dynamic
    search results (target optional, drug_name/contributing_sources present).
    """

    id: str
    target: Target | None = None
    drug_name: str | None = None
    trials: list[Trial] = Field(default_factory=list)
    patents: list[Patent] = Field(default_factory=list)
    articles: list[Article] = Field(default_factory=list)
    scores: CandidateScores
    risk_flags: list[str] = Field(default_factory=list)
    confidence: float = Field(ge=0, le=1)

    # Dynamic search result fields
    matched_dimensions: list[str] = Field(default_factory=list)
    contributing_sources: list[SourceProvenance] = Field(default_factory=list)
    retrieved_at: datetime | None = None
    synthesis_summary: str | None = None
