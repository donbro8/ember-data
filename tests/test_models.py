"""Tests for ember-data domain models."""

from datetime import date

import pytest

from ember_data.models import (
    Article,
    Candidate,
    CandidateScores,
    Patent,
    Target,
    TargetType,
    Trial,
    TrialPhase,
)


class TestTargetType:
    def test_enum_values(self):
        assert TargetType.GENE == "gene"
        assert TargetType.PROTEIN == "protein"
        assert TargetType.PATHWAY == "pathway"


class TestTarget:
    def test_creation_all_fields(self):
        target = Target(
            id="TGT-001",
            name="KRAS G12C",
            type=TargetType.GENE,
            organism="Homo sapiens",
            aliases=["KRAS", "K-Ras4B"],
            gene_id="3845",
            uniprot_id="P01116",
        )
        assert target.id == "TGT-001"
        assert target.name == "KRAS G12C"
        assert target.type == TargetType.GENE
        assert target.organism == "Homo sapiens"
        assert target.aliases == ["KRAS", "K-Ras4B"]
        assert target.gene_id == "3845"
        assert target.uniprot_id == "P01116"

    def test_optional_fields_default_none(self):
        target = Target(
            id="TGT-002",
            name="BRCA1",
            type=TargetType.PROTEIN,
            organism="Homo sapiens",
        )
        assert target.gene_id is None
        assert target.uniprot_id is None
        assert target.aliases == []


class TestTrialPhase:
    def test_enum_values(self):
        assert TrialPhase.I == "I"
        assert TrialPhase.II == "II"
        assert TrialPhase.III == "III"
        assert TrialPhase.IV == "IV"


class TestTrial:
    def test_creation(self):
        trial = Trial(
            nct_id="NCT04303780",
            title="Study of Drug X in NSCLC",
            phase=TrialPhase.II,
            status="recruiting",
            conditions=["Non-Small Cell Lung Cancer"],
            interventions=["Drug X"],
            sponsor="Acme Pharma",
            start_date=date(2024, 1, 15),
            primary_endpoints=["Overall Survival"],
        )
        assert trial.nct_id == "NCT04303780"
        assert trial.phase == TrialPhase.II
        assert trial.status == "recruiting"
        assert trial.conditions == ["Non-Small Cell Lung Cancer"]
        assert trial.start_date == date(2024, 1, 15)

    def test_optional_results_summary(self):
        trial = Trial(
            nct_id="NCT00000001",
            title="Test",
            phase=TrialPhase.I,
            status="completed",
            conditions=[],
            interventions=[],
            sponsor="Test Sponsor",
            start_date=date(2023, 1, 1),
            primary_endpoints=[],
        )
        assert trial.results_summary is None


class TestPatent:
    def test_creation(self):
        patent = Patent(
            publication_number="US-11234567-B2",
            title="Composition for treating cancer",
            abstract="A pharmaceutical composition...",
            claims=["A method of treating cancer..."],
            assignee="Acme Pharma Inc.",
            filing_date=date(2020, 6, 15),
            grant_date=date(2023, 3, 1),
            cited_by_count=42,
            relevant_targets=["KRAS", "EGFR"],
        )
        assert patent.publication_number == "US-11234567-B2"
        assert patent.grant_date == date(2023, 3, 1)
        assert patent.cited_by_count == 42
        assert patent.relevant_targets == ["KRAS", "EGFR"]

    def test_optional_grant_date(self):
        patent = Patent(
            publication_number="US-20230001-A1",
            title="Pending patent",
            abstract="Abstract",
            claims=["Claim 1"],
            assignee="Test Corp",
            filing_date=date(2023, 1, 1),
        )
        assert patent.grant_date is None

    def test_cited_by_count_default(self):
        patent = Patent(
            publication_number="US-20230002-A1",
            title="New patent",
            abstract="Abstract",
            claims=["Claim 1"],
            assignee="Test Corp",
            filing_date=date(2023, 1, 1),
        )
        assert patent.cited_by_count == 0


class TestArticle:
    def test_creation(self):
        article = Article(
            pmid="12345678",
            title="KRAS mutations in lung cancer",
            authors=["Smith J", "Doe A"],
            journal="Nature",
            pub_date=date(2024, 6, 1),
            abstract="We investigated...",
            mesh_terms=["Lung Neoplasms", "KRAS"],
            cited_by_count=100,
            doi="10.1038/s41586-024-00001-0",
        )
        assert article.pmid == "12345678"
        assert article.doi == "10.1038/s41586-024-00001-0"
        assert article.mesh_terms == ["Lung Neoplasms", "KRAS"]

    def test_optional_pmid_doi(self):
        article = Article(
            title="Internal Report",
            authors=["Lab Team"],
            journal="Internal",
            pub_date=date(2024, 1, 1),
            abstract="Summary",
        )
        assert article.pmid is None
        assert article.doi is None

    def test_mesh_terms_default_empty(self):
        article = Article(
            title="Test",
            authors=[],
            journal="Test",
            pub_date=date(2024, 1, 1),
            abstract="Test",
        )
        assert article.mesh_terms == []


class TestCandidateScores:
    def test_overall_computed_from_defaults(self):
        scores = CandidateScores(
            clinical_stage=0.8,
            ip_freedom=0.6,
            evidence_strength=0.7,
            novelty=0.9,
        )
        # Default weights: clinical_stage=0.3, ip_freedom=0.25,
        # evidence_strength=0.25, novelty=0.2
        expected = 0.8 * 0.3 + 0.6 * 0.25 + 0.7 * 0.25 + 0.9 * 0.2
        assert scores.overall == pytest.approx(expected)

    def test_custom_weights(self):
        scores = CandidateScores(
            clinical_stage=1.0,
            ip_freedom=0.0,
            evidence_strength=0.0,
            novelty=0.0,
            weight_clinical_stage=1.0,
            weight_ip_freedom=0.0,
            weight_evidence_strength=0.0,
            weight_novelty=0.0,
        )
        assert scores.overall == pytest.approx(1.0)

    def test_all_zeros(self):
        scores = CandidateScores(
            clinical_stage=0.0,
            ip_freedom=0.0,
            evidence_strength=0.0,
            novelty=0.0,
        )
        assert scores.overall == pytest.approx(0.0)


class TestCandidate:
    def test_creation_with_nested_target(self):
        target = Target(
            id="TGT-001",
            name="KRAS G12C",
            type=TargetType.GENE,
            organism="Homo sapiens",
        )
        scores = CandidateScores(
            clinical_stage=0.8,
            ip_freedom=0.6,
            evidence_strength=0.7,
            novelty=0.9,
        )
        candidate = Candidate(
            id="CAND-001",
            target=target,
            scores=scores,
            risk_flags=["Patent cliff in 2025"],
            confidence=0.85,
        )
        assert candidate.id == "CAND-001"
        assert candidate.target.name == "KRAS G12C"
        assert candidate.scores.overall > 0
        assert candidate.risk_flags == ["Patent cliff in 2025"]
        assert candidate.confidence == 0.85
        assert candidate.trials == []
        assert candidate.patents == []
        assert candidate.articles == []
