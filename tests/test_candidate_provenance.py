"""Tests for SourceProvenance, Candidate, and CandidateScores."""

from __future__ import annotations

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ember_data.models.candidate import Candidate, CandidateScores
from ember_data.models.provenance import SourceProvenance
from ember_data.models.target import Target, TargetType


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _now() -> datetime:
    return datetime(2026, 5, 7, 12, 0, 0, tzinfo=timezone.utc)


def _scores(**overrides) -> CandidateScores:
    defaults = dict(
        clinical_stage=0.8,
        ip_freedom=0.6,
        evidence_strength=0.7,
        novelty=0.5,
    )
    defaults.update(overrides)
    return CandidateScores(**defaults)


def _provenance(**overrides) -> SourceProvenance:
    defaults = dict(
        source_name="ClinicalTrials.gov",
        retrieved_at=_now(),
    )
    defaults.update(overrides)
    return SourceProvenance(**defaults)


# ---------------------------------------------------------------------------
# SourceProvenance
# ---------------------------------------------------------------------------


class TestSourceProvenanceConstruction:
    def test_required_fields(self) -> None:
        prov = SourceProvenance(source_name="PubMed", retrieved_at=_now())
        assert prov.source_name == "PubMed"
        assert prov.retrieved_at == _now()

    def test_optional_fields_default_none(self) -> None:
        prov = SourceProvenance(source_name="PubMed", retrieved_at=_now())
        assert prov.source_id is None
        assert prov.source_url is None

    def test_matched_fields_default_empty(self) -> None:
        prov = SourceProvenance(source_name="PubMed", retrieved_at=_now())
        assert prov.matched_fields == []

    def test_full_construction(self) -> None:
        prov = SourceProvenance(
            source_name="PubMed",
            source_id="PMC12345",
            source_url="https://pubmed.ncbi.nlm.nih.gov/12345",
            retrieved_at=_now(),
            matched_fields=["drug_name", "indication"],
        )
        assert prov.source_id == "PMC12345"
        assert prov.source_url == "https://pubmed.ncbi.nlm.nih.gov/12345"
        assert "drug_name" in prov.matched_fields


class TestSourceProvenanceSerialization:
    def test_model_dump_contains_all_fields(self) -> None:
        prov = SourceProvenance(
            source_name="PubMed",
            source_id="PMC12345",
            source_url="https://example.com",
            retrieved_at=_now(),
            matched_fields=["drug_name"],
        )
        data = prov.model_dump()
        assert data["source_name"] == "PubMed"
        assert data["source_id"] == "PMC12345"
        assert data["source_url"] == "https://example.com"
        assert data["matched_fields"] == ["drug_name"]
        assert "retrieved_at" in data

    def test_model_dump_json_is_string(self) -> None:
        prov = _provenance()
        json_str = prov.model_dump_json()
        assert isinstance(json_str, str)
        assert "ClinicalTrials.gov" in json_str

    def test_roundtrip_from_dict(self) -> None:
        prov = SourceProvenance(
            source_name="USPTO",
            source_id="US10000001",
            retrieved_at=_now(),
            matched_fields=["patent_number"],
        )
        data = prov.model_dump()
        restored = SourceProvenance.model_validate(data)
        assert restored.source_name == prov.source_name
        assert restored.source_id == prov.source_id
        assert restored.matched_fields == prov.matched_fields


# ---------------------------------------------------------------------------
# CandidateScores
# ---------------------------------------------------------------------------


class TestCandidateScoresComputation:
    def test_overall_computed_on_construction(self) -> None:
        scores = CandidateScores(
            clinical_stage=1.0,
            ip_freedom=1.0,
            evidence_strength=1.0,
            novelty=1.0,
        )
        # 1.0*0.3 + 1.0*0.25 + 1.0*0.25 + 1.0*0.2 = 1.0
        assert scores.overall == pytest.approx(1.0)

    def test_overall_all_zero(self) -> None:
        scores = CandidateScores(
            clinical_stage=0.0,
            ip_freedom=0.0,
            evidence_strength=0.0,
            novelty=0.0,
        )
        assert scores.overall == pytest.approx(0.0)

    def test_overall_weighted_sum_formula(self) -> None:
        scores = CandidateScores(
            clinical_stage=0.8,
            ip_freedom=0.6,
            evidence_strength=0.7,
            novelty=0.5,
        )
        expected = 0.8 * 0.3 + 0.6 * 0.25 + 0.7 * 0.25 + 0.5 * 0.2
        assert scores.overall == pytest.approx(expected)

    def test_overall_partial_weights(self) -> None:
        scores = CandidateScores(
            clinical_stage=1.0,
            ip_freedom=0.0,
            evidence_strength=0.0,
            novelty=0.0,
        )
        # Only clinical_stage contributes: 1.0 * 0.3
        assert scores.overall == pytest.approx(0.3)

    def test_score_dimension_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            CandidateScores(
                clinical_stage=1.1,
                ip_freedom=0.5,
                evidence_strength=0.5,
                novelty=0.5,
            )

    def test_score_dimension_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            CandidateScores(
                clinical_stage=-0.1,
                ip_freedom=0.5,
                evidence_strength=0.5,
                novelty=0.5,
            )


class TestCandidateScoresOptionalRetrievalSignals:
    def test_retrieval_signals_default_none(self) -> None:
        scores = _scores()
        assert scores.semantic_score is None
        assert scores.structured_score is None
        assert scores.evidence_score is None

    def test_semantic_score_populated(self) -> None:
        scores = _scores(semantic_score=0.85)
        assert scores.semantic_score == pytest.approx(0.85)

    def test_structured_score_populated(self) -> None:
        scores = _scores(structured_score=0.72)
        assert scores.structured_score == pytest.approx(0.72)

    def test_evidence_score_populated(self) -> None:
        scores = _scores(evidence_score=0.61)
        assert scores.evidence_score == pytest.approx(0.61)

    def test_all_retrieval_signals_populated(self) -> None:
        scores = _scores(semantic_score=0.9, structured_score=0.8, evidence_score=0.7)
        assert scores.semantic_score == pytest.approx(0.9)
        assert scores.structured_score == pytest.approx(0.8)
        assert scores.evidence_score == pytest.approx(0.7)

    def test_retrieval_signal_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            _scores(semantic_score=1.1)


# ---------------------------------------------------------------------------
# Candidate
# ---------------------------------------------------------------------------


def _target() -> Target:
    return Target(
        id="tgt-001",
        name="PD-1",
        type=TargetType.PROTEIN,
        organism="Homo sapiens",
    )


class TestCandidateConstruction:
    def test_minimal_with_drug_name_no_target(self) -> None:
        candidate = Candidate(
            id="cand-001",
            drug_name="pembrolizumab",
            scores=_scores(),
            confidence=0.9,
        )
        assert candidate.id == "cand-001"
        assert candidate.target is None
        assert candidate.drug_name == "pembrolizumab"
        assert candidate.confidence == pytest.approx(0.9)

    def test_target_none_is_valid_when_drug_name_present(self) -> None:
        candidate = Candidate(
            id="cand-002",
            target=None,
            drug_name="nivolumab",
            scores=_scores(),
            confidence=0.75,
        )
        assert candidate.target is None

    def test_with_target(self) -> None:
        candidate = Candidate(
            id="cand-003",
            target=_target(),
            scores=_scores(),
            confidence=0.85,
        )
        assert candidate.target is not None
        assert candidate.target.name == "PD-1"

    def test_lists_default_empty(self) -> None:
        candidate = Candidate(
            id="cand-004",
            scores=_scores(),
            confidence=0.5,
        )
        assert candidate.trials == []
        assert candidate.patents == []
        assert candidate.articles == []
        assert candidate.risk_flags == []

    def test_confidence_at_zero(self) -> None:
        candidate = Candidate(id="cand-005", scores=_scores(), confidence=0.0)
        assert candidate.confidence == 0.0

    def test_confidence_at_one(self) -> None:
        candidate = Candidate(id="cand-006", scores=_scores(), confidence=1.0)
        assert candidate.confidence == 1.0

    def test_confidence_out_of_range_raises(self) -> None:
        with pytest.raises(ValidationError):
            Candidate(id="cand-007", scores=_scores(), confidence=1.1)


class TestCandidateDynamicFields:
    def test_matched_dimensions_populated(self) -> None:
        candidate = Candidate(
            id="cand-010",
            scores=_scores(),
            confidence=0.8,
            matched_dimensions=["target", "modality", "indication"],
        )
        assert "target" in candidate.matched_dimensions
        assert len(candidate.matched_dimensions) == 3

    def test_matched_dimensions_default_empty(self) -> None:
        candidate = Candidate(id="cand-011", scores=_scores(), confidence=0.5)
        assert candidate.matched_dimensions == []

    def test_contributing_sources_populated(self) -> None:
        sources = [
            _provenance(source_name="ClinicalTrials.gov"),
            _provenance(source_name="PubMed"),
        ]
        candidate = Candidate(
            id="cand-012",
            scores=_scores(),
            confidence=0.8,
            contributing_sources=sources,
        )
        assert len(candidate.contributing_sources) == 2
        assert candidate.contributing_sources[0].source_name == "ClinicalTrials.gov"

    def test_contributing_sources_default_empty(self) -> None:
        candidate = Candidate(id="cand-013", scores=_scores(), confidence=0.5)
        assert candidate.contributing_sources == []

    def test_retrieved_at_populated(self) -> None:
        ts = _now()
        candidate = Candidate(
            id="cand-014",
            scores=_scores(),
            confidence=0.7,
            retrieved_at=ts,
        )
        assert candidate.retrieved_at == ts

    def test_retrieved_at_default_none(self) -> None:
        candidate = Candidate(id="cand-015", scores=_scores(), confidence=0.5)
        assert candidate.retrieved_at is None

    def test_synthesis_summary_populated(self) -> None:
        candidate = Candidate(
            id="cand-016",
            scores=_scores(),
            confidence=0.7,
            synthesis_summary="Strong PD-1 inhibitor with Phase III data.",
        )
        assert "Phase III" in candidate.synthesis_summary

    def test_synthesis_summary_default_none(self) -> None:
        candidate = Candidate(id="cand-017", scores=_scores(), confidence=0.5)
        assert candidate.synthesis_summary is None


# ---------------------------------------------------------------------------
# Candidate serialization
# ---------------------------------------------------------------------------


class TestCandidateSerialization:
    def test_model_dump_includes_contributing_sources(self) -> None:
        sources = [
            SourceProvenance(
                source_name="USPTO",
                source_id="US10000001",
                retrieved_at=_now(),
                matched_fields=["patent_number"],
            )
        ]
        candidate = Candidate(
            id="cand-020",
            scores=_scores(),
            confidence=0.85,
            contributing_sources=sources,
        )
        data = candidate.model_dump()
        assert "contributing_sources" in data
        assert len(data["contributing_sources"]) == 1
        assert data["contributing_sources"][0]["source_name"] == "USPTO"

    def test_model_dump_json_is_string(self) -> None:
        candidate = Candidate(
            id="cand-021",
            drug_name="trastuzumab",
            scores=_scores(),
            confidence=0.9,
            retrieved_at=_now(),
            synthesis_summary="HER2-targeted mAb.",
        )
        json_str = candidate.model_dump_json()
        assert isinstance(json_str, str)
        assert "trastuzumab" in json_str
        assert "HER2-targeted mAb." in json_str

    def test_model_dump_includes_dynamic_fields(self) -> None:
        candidate = Candidate(
            id="cand-022",
            scores=_scores(),
            confidence=0.75,
            matched_dimensions=["modality", "target"],
            retrieved_at=_now(),
            synthesis_summary="Summary text.",
        )
        data = candidate.model_dump()
        assert data["matched_dimensions"] == ["modality", "target"]
        assert data["synthesis_summary"] == "Summary text."
        assert data["retrieved_at"] is not None

    def test_roundtrip_from_dict(self) -> None:
        source = _provenance(source_name="EMA", source_id="EMA-001")
        candidate = Candidate(
            id="cand-023",
            drug_name="rituximab",
            scores=_scores(),
            confidence=0.88,
            contributing_sources=[source],
            matched_dimensions=["indication"],
        )
        data = candidate.model_dump()
        restored = Candidate.model_validate(data)
        assert restored.id == candidate.id
        assert restored.drug_name == candidate.drug_name
        assert len(restored.contributing_sources) == 1
        assert restored.contributing_sources[0].source_name == "EMA"
        assert restored.matched_dimensions == ["indication"]
