"""Tests for seed enrichment log data models."""

from __future__ import annotations

import dataclasses
from datetime import datetime, timezone

from ember_data.seed.enrichment_log import (
    EnrichmentAction,
    EnrichmentLogEntry,
    EnrichmentReport,
)


def _make_log_entry(**overrides: object) -> EnrichmentLogEntry:
    """Helper to build an EnrichmentLogEntry with sensible defaults."""
    defaults = {
        "timestamp": datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc),
        "action": EnrichmentAction.UPDATED_COMPETITORS,
        "drug_name": "Humira",
        "field_changed": "biosimilar_competitors",
        "old_value": "Hadlima",
        "new_value": "Hadlima, Yusimry",
        "source": "bigquery_fda",
        "confidence": "high",
    }
    defaults.update(overrides)
    return EnrichmentLogEntry(**defaults)  # type: ignore[arg-type]


class TestEnrichmentAction:
    """EnrichmentAction enum tests."""

    def test_values_are_strings(self) -> None:
        for member in EnrichmentAction:
            assert isinstance(member.value, str)
            assert isinstance(member, str)

    def test_json_serializable_via_value(self) -> None:
        assert EnrichmentAction.NEW_ENTRY.value == "new_entry"
        assert EnrichmentAction.UPDATED_COMPETITORS.value == "updated_competitors"
        assert (
            EnrichmentAction.UPDATED_PATENT_JURISDICTION.value
            == "updated_patent_jurisdiction"
        )
        assert (
            EnrichmentAction.FLAGGED_STALE_REVENUE.value == "flagged_stale_revenue"
        )
        assert (
            EnrichmentAction.UPDATED_BIOSIMILAR_STATUS.value
            == "updated_biosimilar_status"
        )

    def test_member_count(self) -> None:
        assert len(EnrichmentAction) == 5


class TestEnrichmentLogEntry:
    """EnrichmentLogEntry dataclass tests."""

    def test_construct_and_attribute_access(self) -> None:
        ts = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
        entry = EnrichmentLogEntry(
            timestamp=ts,
            action=EnrichmentAction.UPDATED_COMPETITORS,
            drug_name="Humira",
            field_changed="biosimilar_competitors",
            old_value="Hadlima",
            new_value="Hadlima, Yusimry",
            source="bigquery_fda",
            confidence="high",
        )
        assert entry.timestamp == ts
        assert entry.action == EnrichmentAction.UPDATED_COMPETITORS
        assert entry.drug_name == "Humira"
        assert entry.field_changed == "biosimilar_competitors"
        assert entry.old_value == "Hadlima"
        assert entry.new_value == "Hadlima, Yusimry"
        assert entry.source == "bigquery_fda"
        assert entry.confidence == "high"

    def test_old_value_none_for_new_entry(self) -> None:
        entry = _make_log_entry(
            action=EnrichmentAction.NEW_ENTRY,
            old_value=None,
        )
        assert entry.old_value is None


class TestEnrichmentReport:
    """EnrichmentReport dataclass tests."""

    def test_construct_with_empty_log(self) -> None:
        now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
        report = EnrichmentReport(
            run_id="run-001",
            started_at=now,
            completed_at=now,
            entries_scanned=100,
            entries_updated=5,
            new_entries_added=2,
            stale_revenue_flagged=3,
        )
        assert report.log == []
        assert report.entries_scanned == 100
        assert report.entries_updated == 5
        assert report.new_entries_added == 2
        assert report.stale_revenue_flagged == 3

    def test_default_log_is_empty_list(self) -> None:
        now = datetime.now(tz=timezone.utc)
        r1 = EnrichmentReport(
            run_id="a", started_at=now, completed_at=now,
            entries_scanned=0, entries_updated=0,
            new_entries_added=0, stale_revenue_flagged=0,
        )
        r2 = EnrichmentReport(
            run_id="b", started_at=now, completed_at=now,
            entries_scanned=0, entries_updated=0,
            new_entries_added=0, stale_revenue_flagged=0,
        )
        # Verify independent default lists (not shared mutable default)
        assert r1.log is not r2.log

    def test_construct_with_populated_log(self) -> None:
        now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
        entry = _make_log_entry()
        report = EnrichmentReport(
            run_id="run-002",
            started_at=now,
            completed_at=now,
            entries_scanned=50,
            entries_updated=1,
            new_entries_added=0,
            stale_revenue_flagged=0,
            log=[entry],
        )
        assert len(report.log) == 1
        assert report.log[0].drug_name == "Humira"


class TestRoundTrip:
    """Round-trip serialization tests."""

    def test_log_entry_round_trip(self) -> None:
        original = _make_log_entry()
        as_dict = dataclasses.asdict(original)

        # Reconstruct — action comes back as a string, so wrap it
        as_dict["action"] = EnrichmentAction(as_dict["action"])
        reconstructed = EnrichmentLogEntry(**as_dict)

        assert reconstructed.timestamp == original.timestamp
        assert reconstructed.action == original.action
        assert reconstructed.drug_name == original.drug_name
        assert reconstructed.field_changed == original.field_changed
        assert reconstructed.old_value == original.old_value
        assert reconstructed.new_value == original.new_value
        assert reconstructed.source == original.source
        assert reconstructed.confidence == original.confidence

    def test_report_round_trip(self) -> None:
        now = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
        entry = _make_log_entry()
        original = EnrichmentReport(
            run_id="run-rt",
            started_at=now,
            completed_at=now,
            entries_scanned=10,
            entries_updated=1,
            new_entries_added=0,
            stale_revenue_flagged=0,
            log=[entry],
        )
        as_dict = dataclasses.asdict(original)

        # Reconstruct nested log entries
        log_dicts = as_dict.pop("log")
        reconstructed_log = []
        for ld in log_dicts:
            ld["action"] = EnrichmentAction(ld["action"])
            reconstructed_log.append(EnrichmentLogEntry(**ld))

        reconstructed = EnrichmentReport(**as_dict, log=reconstructed_log)

        assert reconstructed.run_id == original.run_id
        assert reconstructed.started_at == original.started_at
        assert reconstructed.completed_at == original.completed_at
        assert reconstructed.entries_scanned == original.entries_scanned
        assert reconstructed.entries_updated == original.entries_updated
        assert reconstructed.new_entries_added == original.new_entries_added
        assert reconstructed.stale_revenue_flagged == original.stale_revenue_flagged
        assert len(reconstructed.log) == 1
        assert reconstructed.log[0].drug_name == original.log[0].drug_name
