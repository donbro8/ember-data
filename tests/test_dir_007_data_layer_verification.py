"""DIR-007 data-layer verification coverage for TASK-150."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import patch

from ember_data.classification.enums import CellLineClass, Jurisdiction, ModalityClassification
from ember_data.classification.spec import DateWindow, SearchSpec
from ember_data.clients.clinicaltrials import ClinicalTrialsClient
from ember_data.models.result import CandidateResult, PatentJurisdiction
from ember_data.seed.enrichment.patent_enricher import PatentJurisdictionEnricher
from ember_data.seed.schema import BiologicEntry


def test_dir_007_search_spec_opportunity_shape() -> None:
    spec = SearchSpec(
        query_type="opportunity",
        modality=ModalityClassification.MONOCLONAL_ANTIBODY,
        cell_line_class=CellLineClass.MAMMALIAN,
        min_revenue_millions=500.0,
        jurisdictions=[Jurisdiction.US, Jurisdiction.EU, Jurisdiction.JP],
        patent_expiry_window=DateWindow.between(date(2025, 1, 1), date(2028, 12, 31)),
    )

    assert spec.query_type == "opportunity"
    assert spec.modality == ModalityClassification.MONOCLONAL_ANTIBODY
    assert spec.cell_line_class == CellLineClass.MAMMALIAN
    assert spec.min_revenue_millions == 500.0
    assert spec.jurisdictions == [Jurisdiction.US, Jurisdiction.EU, Jurisdiction.JP]
    assert spec.patent_expiry_window is not None
    assert spec.patent_expiry_window.start == date(2025, 1, 1)
    assert spec.patent_expiry_window.end == date(2028, 12, 31)


def test_clinical_trials_optional_condition_intervention_term_request() -> None:
    client = ClinicalTrialsClient()
    captured_urls: list[str] = []

    def capture_url(url: str, max_attempts: int = 3) -> tuple[str, dict[str, str]]:
        captured_urls.append(url)
        return json.dumps({"studies": []}), {}

    with patch.object(client, "_retry_get", side_effect=capture_url):
        client.search(condition="cancer", intervention="adalimumab", term="TNF")

    assert captured_urls
    url = captured_urls[0]
    assert "query.cond=cancer" in url
    assert "query.intr=adalimumab" in url
    assert "query.term=TNF" in url


def test_seed_jurisdiction_coverage_reporting() -> None:
    entries = [
        BiologicEntry(
            drug_name="Drug A",
            originator="Org A",
            target_antigen="Target A",
            patent_expiries={"US": date(2028, 1, 1), "EU": date(2029, 1, 1)},
        ),
        BiologicEntry(
            drug_name="Drug B",
            originator="Org B",
            target_antigen="Target B",
            patent_expiries={"JP": date(2030, 1, 1), "CN": date(2031, 1, 1)},
        ),
    ]

    enricher = PatentJurisdictionEnricher(client=object())  # type: ignore[arg-type]
    report = enricher.build_coverage_report(entries, source="task-150", enriched_on=date(2026, 5, 11))

    assert report["source"] == "task-150"
    assert report["enriched_on"] == "2026-05-11"
    assert report["entry_count"] == 2

    coverage = report["coverage"]
    assert isinstance(coverage, dict)
    assert coverage["US"]["covered_entries"] == 1
    assert coverage["EU"]["covered_entries"] == 1
    assert coverage["JP"]["covered_entries"] == 1
    assert coverage["CN"]["covered_entries"] == 1
    assert coverage["KR"]["status"] == "unknown_or_unavailable"


def test_expiry_derivation_and_regulatory_context_models() -> None:
    patent = PatentJurisdiction(
        country_code="US",
        country_name="United States",
        publication_number="US-1234567-A1",
        status="active",
        url="https://patents.google.com/patent/US1234567A1",
        expiry_derivation_method="verified",
        expiry_derivation_provenance="orange_book",
        expiry_date=date(2032, 6, 1),
    )

    result = CandidateResult(
        drug_name="adalimumab",
        patents=[patent],
        earliest_patent_expiry=date(2032, 6, 1),
        earliest_expiry_jurisdiction="US",
        earliest_patent_expiry_derivation_method="verified",
        earliest_patent_expiry_verified_date=date(2032, 6, 1),
        data_exclusivity_expiry=date(2030, 1, 1),
        data_exclusivity_regime="US-BLA-12yr",
        framework_regulatory_context={"region": "US", "framework": "BLA"},
    )

    assert result.patents[0].expiry_derivation_method == "verified"
    assert result.earliest_patent_expiry_derivation_method == "verified"
    assert result.earliest_patent_expiry_verified_date == date(2032, 6, 1)
    assert result.data_exclusivity_expiry == date(2030, 1, 1)
    assert result.framework_regulatory_context == {"region": "US", "framework": "BLA"}


def test_contract_surface_mentions_dir_007_data_fields() -> None:
    contract_path = Path(".contracts/package/ember-agents-to-ember-data.yaml")
    text = contract_path.read_text(encoding="utf-8")

    for required_field in [
        "query_type",
        "modality",
        "cell_line_class",
        "min_revenue_millions",
        "jurisdictions",
        "patent_expiry_window",
    ]:
        assert required_field in text
