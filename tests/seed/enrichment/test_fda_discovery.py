"""Tests for the FDA biologic discovery provider."""

from __future__ import annotations

import json
from datetime import date
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ember_data.seed.enrichment.fda_discovery import FDABiologicDiscovery
from ember_data.seed.enrichment_log import EnrichmentAction
from ember_data.seed.schema import BiologicEntry

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture()
def fda_fixture_rows() -> list[dict]:
    """Load the recorded FDA biologics fixture."""
    with (FIXTURES_DIR / "fda_biologics.json").open() as f:
        return json.load(f)


@pytest.fixture()
def mock_client(fda_fixture_rows: list[dict]) -> MagicMock:
    """Create a mock BigQueryClient that returns fixture data."""
    client = MagicMock()
    client.query_with_params.return_value = fda_fixture_rows
    return client


@pytest.fixture()
def existing_entries() -> list[BiologicEntry]:
    """Seed entries that should be filtered out during discovery."""
    return [
        BiologicEntry(
            drug_name="adalimumab",
            originator="AbbVie",
            target_antigen="TNF-alpha",
        ),
        BiologicEntry(
            drug_name="Trastuzumab",  # uppercase to test case-insensitive
            originator="Genentech",
            target_antigen="HER2",
        ),
    ]


class TestFDABiologicDiscovery:
    """Tests for FDABiologicDiscovery.discover()."""

    def test_discovers_new_biologics(
        self,
        mock_client: MagicMock,
        existing_entries: list[BiologicEntry],
    ) -> None:
        """New biologics not in existing seed are returned."""
        provider = FDABiologicDiscovery(client=mock_client)
        new_entries, log_entries = provider.discover(existing_entries)

        discovered_names = {e.drug_name for e in new_entries}
        # These should be discovered (not in existing seed)
        assert "nivolumab" in discovered_names
        assert "etanercept" in discovered_names
        assert "insulin glargine" in discovered_names
        assert "filgrastim" in discovered_names
        assert "interferon beta-1a" in discovered_names
        assert "trastuzumab emtansine" in discovered_names
        assert "agalsidase beta" in discovered_names

    def test_skips_existing_entries_case_insensitive(
        self,
        mock_client: MagicMock,
        existing_entries: list[BiologicEntry],
    ) -> None:
        """Entries already in seed are excluded (case-insensitive)."""
        provider = FDABiologicDiscovery(client=mock_client)
        new_entries, _ = provider.discover(existing_entries)

        discovered_names = {e.drug_name.lower() for e in new_entries}
        assert "adalimumab" not in discovered_names
        assert "trastuzumab" not in discovered_names

    def test_returns_empty_when_all_exist(
        self,
        mock_client: MagicMock,
        fda_fixture_rows: list[dict],
    ) -> None:
        """Returns empty lists when all FDA results are already in seed."""
        all_existing = [
            BiologicEntry(
                drug_name=row["openfda_generic_name"],
                originator=row.get("openfda_manufacturer_name", ""),
                target_antigen="",
            )
            for row in fda_fixture_rows
            if row.get("openfda_generic_name")
        ]
        provider = FDABiologicDiscovery(client=mock_client)
        new_entries, log_entries = provider.discover(all_existing)

        assert new_entries == []
        assert log_entries == []

    def test_handles_empty_query_results(self) -> None:
        """Handles empty BigQuery results gracefully."""
        client = MagicMock()
        client.query_with_params.return_value = []

        provider = FDABiologicDiscovery(client=client)
        new_entries, log_entries = provider.discover([])

        assert new_entries == []
        assert log_entries == []

    def test_entries_have_enriched_source_and_date(
        self,
        mock_client: MagicMock,
    ) -> None:
        """Returned entries have source='enriched_fda' and last_updated set."""
        provider = FDABiologicDiscovery(client=mock_client)
        new_entries, _ = provider.discover([])

        for entry in new_entries:
            assert entry.source == "enriched_fda"
            assert entry.last_updated == date.today()

    def test_log_entries_have_correct_action_and_confidence(
        self,
        mock_client: MagicMock,
    ) -> None:
        """Log entries use NEW_ENTRY action and medium confidence."""
        provider = FDABiologicDiscovery(client=mock_client)
        _, log_entries = provider.discover([])

        assert len(log_entries) > 0
        for log_entry in log_entries:
            assert log_entry.action == EnrichmentAction.NEW_ENTRY
            assert log_entry.confidence == "medium"
            assert log_entry.source == "bigquery_fda"

    def test_brand_names_split_correctly(self) -> None:
        """Multi-valued brand names are split on comma-space."""
        client = MagicMock()
        client.query_with_params.return_value = [
            {
                "openfda_generic_name": "somemab",
                "openfda_brand_name": "BRAND A, BRAND B, BRAND C",
                "openfda_manufacturer_name": "Test Corp",
                "openfda_product_type": "BLA",
            },
        ]
        provider = FDABiologicDiscovery(client=client)
        new_entries, _ = provider.discover([])

        assert len(new_entries) == 1
        assert new_entries[0].brand_names == ["BRAND A", "BRAND B", "BRAND C"]

    def test_target_antigen_empty(
        self,
        mock_client: MagicMock,
    ) -> None:
        """Target antigen is set to empty string (not available from FDA)."""
        provider = FDABiologicDiscovery(client=mock_client)
        new_entries, _ = provider.discover([])

        for entry in new_entries:
            assert entry.target_antigen == ""

    def test_category_inference(self) -> None:
        """Category is inferred from generic name patterns."""
        client = MagicMock()
        client.query_with_params.return_value = [
            {
                "openfda_generic_name": "nivolumab",
                "openfda_brand_name": "OPDIVO",
                "openfda_manufacturer_name": "BMS",
                "openfda_product_type": "BLA",
            },
            {
                "openfda_generic_name": "etanercept",
                "openfda_brand_name": "ENBREL",
                "openfda_manufacturer_name": "Amgen",
                "openfda_product_type": "BLA",
            },
            {
                "openfda_generic_name": "insulin glargine",
                "openfda_brand_name": "LANTUS",
                "openfda_manufacturer_name": "Sanofi",
                "openfda_product_type": "BLA",
            },
            {
                "openfda_generic_name": "filgrastim",
                "openfda_brand_name": "NEUPOGEN",
                "openfda_manufacturer_name": "Amgen",
                "openfda_product_type": "BLA",
            },
        ]
        provider = FDABiologicDiscovery(client=client)
        new_entries, _ = provider.discover([])

        by_name = {e.drug_name: e for e in new_entries}
        assert by_name["nivolumab"].category == "mAb"
        assert by_name["etanercept"].category == "fusion_protein"
        assert by_name["insulin glargine"].category == "insulin"
        assert by_name["filgrastim"].category == "gcsf"

    def test_managed_dataset_used_in_query(self) -> None:
        """When managed_dataset is set, the query targets the cache table."""
        client = MagicMock()
        client.query_with_params.return_value = []

        provider = FDABiologicDiscovery(
            client=client, managed_dataset="my_dataset"
        )
        provider.discover([])

        sql = client.query_with_params.call_args[0][0]
        assert "my_dataset" in sql
        assert "fda_drug_labels_cache" in sql

    def test_handles_query_error_gracefully(self) -> None:
        """BigQuery errors are caught and empty lists returned."""
        client = MagicMock()
        client.query_with_params.side_effect = RuntimeError("BQ timeout")

        provider = FDABiologicDiscovery(client=client)
        new_entries, log_entries = provider.discover([])

        assert new_entries == []
        assert log_entries == []

    def test_revenue_year_is_none(
        self,
        mock_client: MagicMock,
    ) -> None:
        """Returned entries have revenue_year=None."""
        provider = FDABiologicDiscovery(client=mock_client)
        new_entries, _ = provider.discover([])

        for entry in new_entries:
            assert entry.revenue_year is None
