"""Tests for ember-data domain models."""

from datetime import date, datetime, timezone

import pytest

from ember_data.models import (
    Article,
    Candidate,
    CandidateScores,
    Patent,
    SourceProvenance,
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


class TestSourceProvenance:
    def test_creation_all_fields(self):
        now = datetime(2025, 1, 15, 12, 0, 0, tzinfo=timezone.utc)
        prov = SourceProvenance(
            source_name="PubMed",
            source_id="pmid:12345678",
            source_url="https://pubmed.ncbi.nlm.nih.gov/12345678/",
            retrieved_at=now,
            matched_fields=["title", "abstract"],
        )
        assert prov.source_name == "PubMed"
        assert prov.source_id == "pmid:12345678"
        assert prov.source_url == "https://pubmed.ncbi.nlm.nih.gov/12345678/"
        assert prov.retrieved_at == now
        assert prov.matched_fields == ["title", "abstract"]

    def test_source_id_and_url_optional(self):
        now = datetime(2025, 3, 1, 9, 0, 0, tzinfo=timezone.utc)
        prov = SourceProvenance(
            source_name="ClinicalTrials",
            retrieved_at=now,
        )
        assert prov.source_id is None
        assert prov.source_url is None
        assert prov.matched_fields == []

    def test_matched_fields_default_empty(self):
        prov = SourceProvenance(
            source_name="DrugBank",
            retrieved_at=datetime(2025, 6, 1, tzinfo=timezone.utc),
        )
        assert prov.matched_fields == []

    def test_source_name_required(self):
        with pytest.raises(Exception):
            SourceProvenance(retrieved_at=datetime(2025, 1, 1, tzinfo=timezone.utc))


class TestCandidateScoresDynamicFields:
    def test_optional_scores_default_none(self):
        scores = CandidateScores(
            clinical_stage=0.5,
            ip_freedom=0.5,
            evidence_strength=0.5,
            novelty=0.5,
        )
        assert scores.semantic_score is None
        assert scores.structured_score is None
        assert scores.evidence_score is None

    def test_optional_scores_populated(self):
        scores = CandidateScores(
            clinical_stage=0.6,
            ip_freedom=0.7,
            evidence_strength=0.8,
            novelty=0.5,
            semantic_score=0.92,
            structured_score=0.75,
            evidence_score=0.88,
        )
        assert scores.semantic_score == pytest.approx(0.92)
        assert scores.structured_score == pytest.approx(0.75)
        assert scores.evidence_score == pytest.approx(0.88)

    def test_optional_scores_bounds(self):
        with pytest.raises(Exception):
            CandidateScores(
                clinical_stage=0.5,
                ip_freedom=0.5,
                evidence_strength=0.5,
                novelty=0.5,
                semantic_score=1.5,
            )

    def test_overall_unaffected_by_optional_scores(self):
        base = CandidateScores(
            clinical_stage=0.8,
            ip_freedom=0.6,
            evidence_strength=0.7,
            novelty=0.9,
        )
        with_extras = CandidateScores(
            clinical_stage=0.8,
            ip_freedom=0.6,
            evidence_strength=0.7,
            novelty=0.9,
            semantic_score=0.5,
            structured_score=0.5,
            evidence_score=0.5,
        )
        assert base.overall == pytest.approx(with_extras.overall)


class TestCandidateDynamicFields:
    def _make_scores(self) -> CandidateScores:
        return CandidateScores(
            clinical_stage=0.7,
            ip_freedom=0.6,
            evidence_strength=0.8,
            novelty=0.5,
        )

    def test_target_optional(self):
        candidate = Candidate(
            id="CAND-DYN-001",
            scores=self._make_scores(),
            confidence=0.75,
        )
        assert candidate.target is None

    def test_drug_name_field(self):
        candidate = Candidate(
            id="CAND-DYN-002",
            drug_name="Sotorasib",
            scores=self._make_scores(),
            confidence=0.80,
        )
        assert candidate.drug_name == "Sotorasib"

    def test_matched_dimensions_default_empty(self):
        candidate = Candidate(
            id="CAND-DYN-003",
            scores=self._make_scores(),
            confidence=0.70,
        )
        assert candidate.matched_dimensions == []

    def test_matched_dimensions_populated(self):
        candidate = Candidate(
            id="CAND-DYN-004",
            scores=self._make_scores(),
            confidence=0.70,
            matched_dimensions=["mechanism_of_action", "clinical_stage"],
        )
        assert candidate.matched_dimensions == ["mechanism_of_action", "clinical_stage"]

    def test_contributing_sources_default_empty(self):
        candidate = Candidate(
            id="CAND-DYN-005",
            scores=self._make_scores(),
            confidence=0.65,
        )
        assert candidate.contributing_sources == []

    def test_contributing_sources_with_provenance(self):
        now = datetime(2025, 4, 10, 8, 30, 0, tzinfo=timezone.utc)
        prov1 = SourceProvenance(
            source_name="PubMed",
            source_id="pmid:99887766",
            retrieved_at=now,
            matched_fields=["abstract"],
        )
        prov2 = SourceProvenance(
            source_name="ClinicalTrials",
            source_url="https://clinicaltrials.gov/study/NCT12345678",
            retrieved_at=now,
            matched_fields=["title", "status"],
        )
        candidate = Candidate(
            id="CAND-DYN-006",
            scores=self._make_scores(),
            confidence=0.90,
            contributing_sources=[prov1, prov2],
        )
        assert len(candidate.contributing_sources) == 2
        assert candidate.contributing_sources[0].source_name == "PubMed"
        assert candidate.contributing_sources[1].source_name == "ClinicalTrials"

    def test_retrieved_at_optional(self):
        candidate = Candidate(
            id="CAND-DYN-007",
            scores=self._make_scores(),
            confidence=0.60,
        )
        assert candidate.retrieved_at is None

    def test_retrieved_at_populated(self):
        ts = datetime(2025, 5, 1, 14, 0, 0, tzinfo=timezone.utc)
        candidate = Candidate(
            id="CAND-DYN-008",
            scores=self._make_scores(),
            confidence=0.78,
            retrieved_at=ts,
        )
        assert candidate.retrieved_at == ts

    def test_synthesis_summary_optional(self):
        candidate = Candidate(
            id="CAND-DYN-009",
            scores=self._make_scores(),
            confidence=0.55,
        )
        assert candidate.synthesis_summary is None

    def test_synthesis_summary_populated(self):
        summary = "Sotorasib shows strong Phase III evidence against KRAS G12C."
        candidate = Candidate(
            id="CAND-DYN-010",
            scores=self._make_scores(),
            confidence=0.88,
            synthesis_summary=summary,
        )
        assert candidate.synthesis_summary == summary

    def test_full_dynamic_candidate(self):
        now = datetime(2025, 5, 7, 10, 0, 0, tzinfo=timezone.utc)
        prov = SourceProvenance(
            source_name="USPTO",
            source_id="US-11234567-B2",
            retrieved_at=now,
            matched_fields=["claims", "assignee"],
        )
        scores = CandidateScores(
            clinical_stage=0.9,
            ip_freedom=0.4,
            evidence_strength=0.85,
            novelty=0.7,
            semantic_score=0.93,
            structured_score=0.80,
            evidence_score=0.87,
        )
        candidate = Candidate(
            id="CAND-DYN-FULL",
            drug_name="Adagrasib",
            scores=scores,
            confidence=0.91,
            matched_dimensions=["mechanism_of_action", "ip_landscape"],
            contributing_sources=[prov],
            retrieved_at=now,
            synthesis_summary="Adagrasib is a KRAS G12C inhibitor with strong IP position.",
        )
        assert candidate.id == "CAND-DYN-FULL"
        assert candidate.drug_name == "Adagrasib"
        assert candidate.target is None
        assert candidate.matched_dimensions == ["mechanism_of_action", "ip_landscape"]
        assert len(candidate.contributing_sources) == 1
        assert candidate.retrieved_at == now
        assert "Adagrasib" in candidate.synthesis_summary
        assert candidate.scores.semantic_score == pytest.approx(0.93)
