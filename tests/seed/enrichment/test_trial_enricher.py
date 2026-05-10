"""Tests for BiosimilarTrialEnricher."""

from __future__ import annotations

import json
from datetime import UTC, date, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ember_data.clients.clinicaltrials import ClinicalTrialsClient
from ember_data.models.provenance import SourceProvenance
from ember_data.models.trial import Trial, TrialPhase
from ember_data.seed.enrichment.trial_enricher import BiosimilarTrialEnricher
from ember_data.seed.enrichment_log import EnrichmentAction
from ember_data.seed.schema import BiologicEntry

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture() -> list[dict]:
    with open(FIXTURES / "biosimilar_trials.json") as f:
        return json.load(f)["studies"]


def _make_entry(
    drug_name: str = "adalimumab",
    revenue: float = 1000.0,
    competitors: list[str] | None = None,
    has_approved_biosimilar: bool = False,
) -> BiologicEntry:
    return BiologicEntry(
        drug_name=drug_name,
        originator="AbbVie",
        target_antigen="TNF-alpha",
        annual_revenue_usd_millions=revenue,
        biosimilar_competitors=competitors or [],
        has_approved_biosimilar=has_approved_biosimilar,
    )


def _trial_from_study(study: dict) -> Trial:
    """Build a Trial from fixture study data (simplified)."""
    proto = study["protocolSection"]
    id_mod = proto["identificationModule"]
    design = proto["designModule"]
    status_mod = proto["statusModule"]
    conditions_mod = proto.get("conditionsModule", {})
    arms_mod = proto.get("armsInterventionsModule", {})
    sponsor_mod = proto.get("sponsorCollaboratorsModule", {})
    outcomes_mod = proto.get("outcomesModule", {})

    phase_map = {"PHASE1": "I", "PHASE2": "II", "PHASE3": "III", "PHASE4": "IV"}
    raw_phase = design["phases"][0]

    return Trial(
        nct_id=id_mod["nctId"],
        title=id_mod.get("officialTitle", id_mod.get("briefTitle", "")),
        phase=TrialPhase(phase_map[raw_phase]),
        status=status_mod["overallStatus"],
        conditions=conditions_mod.get("conditions", []),
        interventions=[
            iv["name"] for iv in arms_mod.get("interventions", []) if iv.get("name")
        ],
        sponsor=sponsor_mod.get("leadSponsor", {}).get("name", ""),
        start_date=date.fromisoformat(
            status_mod["startDateStruct"]["date"]
        ),
        primary_endpoints=[
            o["measure"]
            for o in outcomes_mod.get("primaryOutcomes", [])
            if o.get("measure")
        ],
    )


def _mock_search_results(studies: list[dict]) -> list[tuple[Trial, SourceProvenance]]:
    """Convert fixture studies into (Trial, SourceProvenance) tuples."""
    results = []
    for study in studies:
        trial = _trial_from_study(study)
        prov = SourceProvenance(
            source_name="ClinicalTrials.gov",
            source_id=trial.nct_id,
            source_url=f"https://clinicaltrials.gov/study/{trial.nct_id}",
            retrieved_at=datetime.now(UTC),
            matched_fields=["condition"],
        )
        results.append((trial, prov))
    return results


@pytest.fixture()
def fixture_studies() -> list[dict]:
    return _load_fixture()


@pytest.fixture()
def mock_client(fixture_studies: list[dict]) -> ClinicalTrialsClient:
    client = MagicMock(spec=ClinicalTrialsClient)
    client.search.return_value = _mock_search_results(fixture_studies)
    return client


class TestBiosimilarTrialEnricher:
    """Tests for BiosimilarTrialEnricher.enrich()."""

    def test_new_competitor_added(self, mock_client: ClinicalTrialsClient) -> None:
        entry = _make_entry()
        enricher = BiosimilarTrialEnricher(client=mock_client)
        logs = enricher.enrich([entry])

        assert "Amgen Inc." in entry.biosimilar_competitors
        assert "Samsung Bioepis Co., Ltd." in entry.biosimilar_competitors
        assert "Celltrion Inc." in entry.biosimilar_competitors

        competitor_logs = [
            lg
            for lg in logs
            if lg.action == EnrichmentAction.UPDATED_COMPETITORS
        ]
        assert len(competitor_logs) == 3

    def test_existing_competitor_not_duplicated(
        self, mock_client: ClinicalTrialsClient
    ) -> None:
        entry = _make_entry(competitors=["Amgen Inc."])
        enricher = BiosimilarTrialEnricher(client=mock_client)
        logs = enricher.enrich([entry])

        assert entry.biosimilar_competitors.count("Amgen Inc.") == 1
        competitor_logs = [
            lg
            for lg in logs
            if lg.action == EnrichmentAction.UPDATED_COMPETITORS
        ]
        # Only 2 new competitors (Samsung, Celltrion), not Amgen
        assert len(competitor_logs) == 2

    def test_biosimilar_status_updated_for_phase_iii(
        self, mock_client: ClinicalTrialsClient
    ) -> None:
        entry = _make_entry(has_approved_biosimilar=False)
        enricher = BiosimilarTrialEnricher(client=mock_client)
        logs = enricher.enrich([entry])

        assert entry.has_approved_biosimilar is True
        status_logs = [
            lg
            for lg in logs
            if lg.action == EnrichmentAction.UPDATED_BIOSIMILAR_STATUS
        ]
        assert len(status_logs) == 1
        assert status_logs[0].field_changed == "has_approved_biosimilar"

    def test_biosimilar_status_not_changed_if_already_true(
        self, mock_client: ClinicalTrialsClient
    ) -> None:
        entry = _make_entry(has_approved_biosimilar=True)
        enricher = BiosimilarTrialEnricher(client=mock_client)
        logs = enricher.enrich([entry])

        assert entry.has_approved_biosimilar is True
        status_logs = [
            lg
            for lg in logs
            if lg.action == EnrichmentAction.UPDATED_BIOSIMILAR_STATUS
        ]
        assert len(status_logs) == 0

    def test_last_updated_set_on_modified_entries(
        self, mock_client: ClinicalTrialsClient
    ) -> None:
        entry = _make_entry()
        assert entry.last_updated is None
        enricher = BiosimilarTrialEnricher(client=mock_client)
        enricher.enrich([entry])

        assert entry.last_updated == date.today()

    def test_max_entries_cap(self, mock_client: ClinicalTrialsClient) -> None:
        entries = [_make_entry(drug_name=f"drug_{i}", revenue=float(i)) for i in range(5)]
        enricher = BiosimilarTrialEnricher(client=mock_client)
        enricher.enrich(entries, max_entries=2)

        # Only 2 calls should be made (highest revenue first: drug_4, drug_3)
        assert mock_client.search.call_count == 2

    def test_highest_revenue_processed_first(
        self, mock_client: ClinicalTrialsClient
    ) -> None:
        entries = [
            _make_entry(drug_name="low_rev", revenue=100.0),
            _make_entry(drug_name="high_rev", revenue=5000.0),
            _make_entry(drug_name="mid_rev", revenue=500.0),
        ]
        enricher = BiosimilarTrialEnricher(client=mock_client)
        enricher.enrich(entries, max_entries=2)

        call_args = [call.kwargs.get("condition", call.args[0] if call.args else "")
                     for call in mock_client.search.call_args_list]
        # First call should be for high_rev, second for mid_rev
        assert "high_rev" in call_args[0]
        assert "mid_rev" in call_args[1]

    def test_per_entry_error_continues(self) -> None:
        client = MagicMock(spec=ClinicalTrialsClient)
        client.search.side_effect = [
            RuntimeError("API error"),
            _mock_search_results(_load_fixture()),
        ]

        entries = [
            _make_entry(drug_name="failing_drug", revenue=2000.0),
            _make_entry(drug_name="ok_drug", revenue=1000.0),
        ]
        enricher = BiosimilarTrialEnricher(client=client)
        logs = enricher.enrich(entries)

        # First entry failed, second should still be enriched
        assert client.search.call_count == 2
        assert len(logs) > 0
        assert all(lg.drug_name == "ok_drug" for lg in logs)

    def test_log_entry_source_and_confidence(
        self, mock_client: ClinicalTrialsClient
    ) -> None:
        entry = _make_entry()
        enricher = BiosimilarTrialEnricher(client=mock_client)
        logs = enricher.enrich([entry])

        for lg in logs:
            assert lg.source == "clinicaltrials"
            assert lg.confidence == "high"
