"""Tests for SeedWriter — JSON and BigQuery persistence."""

from __future__ import annotations

import json
from datetime import date, datetime
from pathlib import Path
from unittest.mock import MagicMock


from ember_data.bigquery.managed_tables import (
    BIOLOGIC_SEED_SCHEMA,
    BIOLOGIC_SEED_TABLE,
    ENRICHMENT_LOG_SCHEMA,
    ENRICHMENT_LOG_TABLE,
)
from ember_data.seed.enrichment.writer import SeedWriter
from ember_data.seed.enrichment_log import (
    EnrichmentAction,
    EnrichmentLogEntry,
    EnrichmentReport,
)
from ember_data.seed.schema import BiologicEntry, VersionedSeedFile


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_entry(**overrides) -> BiologicEntry:
    defaults = {
        "drug_name": "adalimumab",
        "brand_names": ["Humira"],
        "originator": "AbbVie",
        "target_antigen": "TNF-alpha",
        "modality": "mAb",
        "category": "mAb",
        "indications": ["RA", "Crohn's"],
        "annual_revenue_usd_millions": 20000.0,
        "revenue_year": 2023,
        "patent_expiries": {"US": date(2023, 1, 31), "EU": date(2018, 10, 16)},
        "biosimilar_competitors": ["Amjevita"],
        "has_approved_biosimilar": True,
        "last_updated": date(2024, 1, 1),
        "source": "manual",
        "key_patent_numbers": ["US6090382"],
    }
    defaults.update(overrides)
    return BiologicEntry(**defaults)


def _make_seed(entries: list[BiologicEntry] | None = None) -> VersionedSeedFile:
    entries = entries or [_make_entry()]
    return VersionedSeedFile(
        data_version=3,
        last_enrichment_run=datetime(2024, 6, 1, 12, 0, 0),
        entry_count=len(entries),
        entries=entries,
    )


def _make_report(with_log: bool = True) -> EnrichmentReport:
    log = []
    if with_log:
        log.append(
            EnrichmentLogEntry(
                timestamp=datetime(2024, 6, 1, 12, 0, 0),
                action=EnrichmentAction.UPDATED_COMPETITORS,
                drug_name="adalimumab",
                field_changed="biosimilar_competitors",
                old_value="[]",
                new_value='["Amjevita"]',
                source="bigquery_fda",
                confidence="high",
            )
        )
    return EnrichmentReport(
        run_id="run-abc-123",
        started_at=datetime(2024, 6, 1, 11, 59, 0),
        completed_at=datetime(2024, 6, 1, 12, 0, 0),
        entries_scanned=10,
        entries_updated=1,
        new_entries_added=0,
        stale_revenue_flagged=0,
        log=log,
    )


# ---------------------------------------------------------------------------
# JSON write tests
# ---------------------------------------------------------------------------


class TestJsonWrite:
    def test_write_produces_valid_json(self, tmp_path: Path) -> None:
        """JSON write produces a file loadable by load_versioned_seed logic."""
        json_path = tmp_path / "seed.json"
        writer = SeedWriter(json_path=json_path)
        seed = _make_seed()
        report = _make_report(with_log=False)

        writer.write(seed, report)

        assert json_path.exists()
        raw = json.loads(json_path.read_text(encoding="utf-8"))
        roundtrip = VersionedSeedFile.model_validate(raw)
        assert roundtrip.data_version == seed.data_version
        assert len(roundtrip.entries) == len(seed.entries)
        assert roundtrip.entries[0].drug_name == "adalimumab"

    def test_write_is_atomic(self, tmp_path: Path) -> None:
        """Atomic write creates a temp file then renames to target."""
        json_path = tmp_path / "seed.json"
        writer = SeedWriter(json_path=json_path)
        seed = _make_seed()
        report = _make_report(with_log=False)

        writer.write(seed, report)

        # After write, target exists and temp does not.
        assert json_path.exists()
        tmp_file = json_path.with_suffix(".tmp")
        assert not tmp_file.exists()

    def test_json_roundtrip_preserves_data(self, tmp_path: Path) -> None:
        """Data written to JSON can be deserialized back to an identical model."""
        json_path = tmp_path / "seed.json"
        writer = SeedWriter(json_path=json_path)
        seed = _make_seed()
        report = _make_report(with_log=False)

        writer.write(seed, report)

        raw = json.loads(json_path.read_text(encoding="utf-8"))
        roundtrip = VersionedSeedFile.model_validate(raw)

        assert roundtrip.data_version == seed.data_version
        assert roundtrip.entry_count == seed.entry_count
        for orig, loaded in zip(seed.entries, roundtrip.entries, strict=True):
            assert orig.drug_name == loaded.drug_name
            assert orig.originator == loaded.originator
            assert orig.has_approved_biosimilar == loaded.has_approved_biosimilar
            assert orig.patent_expiries == loaded.patent_expiries


# ---------------------------------------------------------------------------
# BigQuery write tests
# ---------------------------------------------------------------------------


class TestBigQueryWrite:
    def test_write_calls_insert_rows(self) -> None:
        """BigQuery write calls insert_rows with correct table and data."""
        mock_client = MagicMock()
        writer = SeedWriter(bq_client=mock_client, bq_dataset="ember_dev")
        seed = _make_seed()
        report = _make_report(with_log=False)

        writer.write(seed, report)

        mock_client.insert_rows.assert_called_once()
        call_args = mock_client.insert_rows.call_args
        table = call_args[0][0]
        rows = call_args[0][1]
        assert table == f"ember_dev.{BIOLOGIC_SEED_TABLE}"
        assert len(rows) == 1
        row = rows[0]
        assert row["drug_name"] == "adalimumab"
        assert row["data_version"] == 3
        assert row["has_approved_biosimilar"] is True
        # patent_expiries_json should be a JSON string
        parsed = json.loads(row["patent_expiries_json"])
        assert "US" in parsed

    def test_write_log_calls_insert_rows_with_run_id(self) -> None:
        """write_log writes log entries with run_id included."""
        mock_client = MagicMock()
        writer = SeedWriter(bq_client=mock_client, bq_dataset="ember_dev")
        report = _make_report(with_log=True)

        writer.write_log(report)

        mock_client.insert_rows.assert_called_once()
        call_args = mock_client.insert_rows.call_args
        table = call_args[0][0]
        rows = call_args[0][1]
        assert table == f"ember_dev.{ENRICHMENT_LOG_TABLE}"
        assert len(rows) == 1
        row = rows[0]
        assert row["run_id"] == "run-abc-123"
        assert row["drug_name"] == "adalimumab"
        assert row["action"] == "updated_competitors"
        assert row["confidence"] == "high"


# ---------------------------------------------------------------------------
# Mixed / no-op configuration tests
# ---------------------------------------------------------------------------


class TestConfigVariations:
    def test_json_only_no_error(self, tmp_path: Path) -> None:
        """JSON-only writer (no BigQuery) works without error."""
        json_path = tmp_path / "seed.json"
        writer = SeedWriter(json_path=json_path)
        seed = _make_seed()
        report = _make_report()

        writer.write(seed, report)
        writer.write_log(report)  # should be no-op

        assert json_path.exists()

    def test_bq_only_no_error(self) -> None:
        """BigQuery-only writer (no JSON path) works without error."""
        mock_client = MagicMock()
        writer = SeedWriter(bq_client=mock_client, bq_dataset="ember_dev")
        seed = _make_seed()
        report = _make_report()

        writer.write(seed, report)
        writer.write_log(report)

        # insert_rows called twice: once for seed, once for log
        assert mock_client.insert_rows.call_count == 2

    def test_neither_configured_noop(self) -> None:
        """Neither JSON nor BigQuery configured — both methods are no-ops."""
        writer = SeedWriter()
        seed = _make_seed()
        report = _make_report()

        # Should not raise
        writer.write(seed, report)
        writer.write_log(report)

    def test_bq_client_without_dataset_is_noop(self) -> None:
        """BigQuery client without dataset is treated as not configured."""
        mock_client = MagicMock()
        writer = SeedWriter(bq_client=mock_client, bq_dataset=None)
        seed = _make_seed()
        report = _make_report()

        writer.write(seed, report)
        writer.write_log(report)

        mock_client.insert_rows.assert_not_called()


# ---------------------------------------------------------------------------
# Schema validation tests
# ---------------------------------------------------------------------------


class TestSchemas:
    def test_biologic_seed_schema_fields(self) -> None:
        """BIOLOGIC_SEED_SCHEMA has expected field names and types."""
        field_map = {f.name: f.field_type for f in BIOLOGIC_SEED_SCHEMA}
        assert field_map["drug_name"] == "STRING"
        assert field_map["brand_names"] == "STRING"
        assert field_map["annual_revenue_usd_millions"] == "FLOAT64"
        assert field_map["revenue_year"] == "INT64"
        assert field_map["patent_expiries_json"] == "STRING"
        assert field_map["has_approved_biosimilar"] == "BOOL"
        assert field_map["last_updated"] == "DATE"
        assert field_map["data_version"] == "INT64"
        assert field_map["key_patent_numbers"] == "STRING"

    def test_biologic_seed_schema_repeated_fields(self) -> None:
        """Repeated fields in BIOLOGIC_SEED_SCHEMA are marked REPEATED."""
        field_map = {f.name: f.mode for f in BIOLOGIC_SEED_SCHEMA}
        assert field_map["brand_names"] == "REPEATED"
        assert field_map["indications"] == "REPEATED"
        assert field_map["biosimilar_competitors"] == "REPEATED"
        assert field_map["key_patent_numbers"] == "REPEATED"

    def test_enrichment_log_schema_fields(self) -> None:
        """ENRICHMENT_LOG_SCHEMA has expected field names and types."""
        field_map = {f.name: f.field_type for f in ENRICHMENT_LOG_SCHEMA}
        assert field_map["run_id"] == "STRING"
        assert field_map["timestamp"] == "TIMESTAMP"
        assert field_map["action"] == "STRING"
        assert field_map["drug_name"] == "STRING"
        assert field_map["field_changed"] == "STRING"
        assert field_map["old_value"] == "STRING"
        assert field_map["new_value"] == "STRING"
        assert field_map["source"] == "STRING"
        assert field_map["confidence"] == "STRING"

    def test_enrichment_log_old_value_nullable(self) -> None:
        """old_value in ENRICHMENT_LOG_SCHEMA is NULLABLE."""
        field_map = {f.name: f.mode for f in ENRICHMENT_LOG_SCHEMA}
        assert field_map["old_value"] == "NULLABLE"

    def test_table_name_constants(self) -> None:
        assert BIOLOGIC_SEED_TABLE == "biologic_seed"
        assert ENRICHMENT_LOG_TABLE == "enrichment_log"
