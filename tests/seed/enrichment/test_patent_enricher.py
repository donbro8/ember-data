"""Tests for PatentJurisdictionEnricher."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from ember_data.bigquery.client import BigQueryClient
from ember_data.seed.enrichment.patent_enricher import PatentJurisdictionEnricher
from ember_data.seed.enrichment_log import EnrichmentAction
from ember_data.seed.schema import BiologicEntry

FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture() -> list[dict]:
    with open(FIXTURES / "patent_jurisdictions.json") as f:
        return json.load(f)


def _make_entry(
    drug_name: str = "adalimumab",
    patent_expiries: dict[str, date] | None = None,
) -> BiologicEntry:
    return BiologicEntry(
        drug_name=drug_name,
        originator="AbbVie",
        target_antigen="TNF-alpha",
        patent_expiries=patent_expiries or {},
    )


@pytest.fixture()
def fixture_rows() -> list[dict]:
    return _load_fixture()


@pytest.fixture()
def mock_client(fixture_rows: list[dict]) -> BigQueryClient:
    client = MagicMock(spec=BigQueryClient)
    client.search_patents.return_value = fixture_rows
    return client


class TestPatentJurisdictionEnricher:
    """Tests for PatentJurisdictionEnricher.enrich()."""

    def test_new_jurisdiction_added(self, mock_client: BigQueryClient) -> None:
        entry = _make_entry()
        enricher = PatentJurisdictionEnricher(client=mock_client)
        logs = enricher.enrich([entry])

        # US, EU, JP should be added (XX is invalid)
        assert "US" in entry.patent_expiries
        assert "EU" in entry.patent_expiries
        assert "JP" in entry.patent_expiries
        assert entry.patent_expiries["US"] == date(2035, 3, 15)
        assert entry.patent_expiries["EU"] == date(2036, 7, 22)
        assert entry.patent_expiries["JP"] == date(2037, 9, 5)

        jurisdiction_logs = [
            lg
            for lg in logs
            if lg.action == EnrichmentAction.UPDATED_PATENT_JURISDICTION
        ]
        assert len(jurisdiction_logs) == 3

    def test_existing_jurisdiction_not_overwritten(
        self, mock_client: BigQueryClient
    ) -> None:
        entry = _make_entry(
            patent_expiries={"US": date(2030, 1, 1)},
        )
        enricher = PatentJurisdictionEnricher(client=mock_client)
        logs = enricher.enrich([entry])

        # US should keep original date
        assert entry.patent_expiries["US"] == date(2030, 1, 1)
        # EU and JP should be added
        assert "EU" in entry.patent_expiries
        assert "JP" in entry.patent_expiries

        jurisdiction_logs = [
            lg
            for lg in logs
            if lg.action == EnrichmentAction.UPDATED_PATENT_JURISDICTION
        ]
        # Only EU and JP, not US
        assert len(jurisdiction_logs) == 2

    def test_invalid_jurisdiction_ignored(
        self, mock_client: BigQueryClient
    ) -> None:
        entry = _make_entry()
        enricher = PatentJurisdictionEnricher(client=mock_client)
        enricher.enrich([entry])

        # XX is not in _VALID_JURISDICTIONS
        assert "XX" not in entry.patent_expiries

    def test_last_updated_set_on_modified_entries(
        self, mock_client: BigQueryClient
    ) -> None:
        entry = _make_entry()
        assert entry.last_updated is None
        enricher = PatentJurisdictionEnricher(client=mock_client)
        enricher.enrich([entry])

        assert entry.last_updated == date.today()

    def test_fewest_jurisdictions_processed_first(
        self, mock_client: BigQueryClient
    ) -> None:
        entries = [
            _make_entry(
                drug_name="many_patents",
                patent_expiries={"US": date(2030, 1, 1), "EU": date(2031, 1, 1), "JP": date(2032, 1, 1)},
            ),
            _make_entry(drug_name="no_patents", patent_expiries={}),
            _make_entry(
                drug_name="one_patent",
                patent_expiries={"US": date(2030, 1, 1)},
            ),
        ]
        enricher = PatentJurisdictionEnricher(client=mock_client)
        enricher.enrich(entries, max_entries=2)

        # Only 2 calls should be made: no_patents (0), one_patent (1)
        assert mock_client.search_patents.call_count == 2
        call_args = [
            call.kwargs.get("query", call.args[0] if call.args else "")
            for call in mock_client.search_patents.call_args_list
        ]
        assert call_args[0] == "no_patents"
        assert call_args[1] == "one_patent"

    def test_per_entry_error_continues(self) -> None:
        client = MagicMock(spec=BigQueryClient)
        client.search_patents.side_effect = [
            RuntimeError("BigQuery error"),
            _load_fixture(),
        ]

        entries = [
            _make_entry(drug_name="failing_drug"),
            _make_entry(drug_name="ok_drug"),
        ]
        enricher = PatentJurisdictionEnricher(client=client)
        logs = enricher.enrich(entries)

        assert client.search_patents.call_count == 2
        assert len(logs) > 0
        assert all(lg.drug_name == "ok_drug" for lg in logs)

    def test_log_field_changed_format(self, mock_client: BigQueryClient) -> None:
        entry = _make_entry()
        enricher = PatentJurisdictionEnricher(client=mock_client)
        logs = enricher.enrich([entry])

        jurisdiction_logs = [
            lg
            for lg in logs
            if lg.action == EnrichmentAction.UPDATED_PATENT_JURISDICTION
        ]
        field_names = {lg.field_changed for lg in jurisdiction_logs}
        assert "patent_expiries.US" in field_names
        assert "patent_expiries.EU" in field_names
        assert "patent_expiries.JP" in field_names

    def test_log_entry_source_and_confidence(
        self, mock_client: BigQueryClient
    ) -> None:
        entry = _make_entry()
        enricher = PatentJurisdictionEnricher(client=mock_client)
        logs = enricher.enrich([entry])

        for lg in logs:
            assert lg.source == "bigquery_patents"
            assert lg.confidence == "medium"

    def test_us_eu_flat_fields_synced(self, mock_client: BigQueryClient) -> None:
        entry = _make_entry()
        enricher = PatentJurisdictionEnricher(client=mock_client)
        enricher.enrich([entry])

        # After adding US and EU via patent_expiries, flat fields should sync
        assert entry.patent_expiry_us == date(2035, 3, 15)
        assert entry.patent_expiry_eu == date(2036, 7, 22)
