"""Tests for SeedEnrichmentOrchestrator."""

from __future__ import annotations

from datetime import UTC, date, datetime, timedelta
from unittest.mock import MagicMock


from ember_data.seed.enrichment.orchestrator import SeedEnrichmentOrchestrator
from ember_data.seed.enrichment_log import EnrichmentAction, EnrichmentLogEntry
from ember_data.seed.schema import BiologicEntry, VersionedSeedFile


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_entry(
    drug_name: str = "testdrug",
    revenue_year: int | None = None,
    last_updated: date | None = None,
) -> BiologicEntry:
    return BiologicEntry(
        drug_name=drug_name,
        originator="Acme",
        target_antigen="CD20",
        revenue_year=revenue_year,
        last_updated=last_updated,
    )


def _make_seed(entries: list[BiologicEntry] | None = None) -> VersionedSeedFile:
    entries = entries or [_make_entry()]
    return VersionedSeedFile(
        data_version=1,
        entry_count=len(entries),
        entries=entries,
    )


def _make_log_entry(
    drug_name: str = "newdrug",
    action: EnrichmentAction = EnrichmentAction.NEW_ENTRY,
) -> EnrichmentLogEntry:
    return EnrichmentLogEntry(
        timestamp=datetime.now(UTC),
        action=action,
        drug_name=drug_name,
        field_changed="drug_name",
        old_value=None,
        new_value=drug_name,
        source="test",
        confidence="high",
    )


def _mock_fda_discovery(
    new_entries: list[BiologicEntry] | None = None,
    log_entries: list[EnrichmentLogEntry] | None = None,
) -> MagicMock:
    mock = MagicMock()
    mock.discover.return_value = (
        new_entries or [],
        log_entries or [],
    )
    return mock


def _mock_trial_enricher(
    log_entries: list[EnrichmentLogEntry] | None = None,
) -> MagicMock:
    mock = MagicMock()
    mock.enrich.return_value = log_entries or []
    return mock


def _mock_patent_enricher(
    log_entries: list[EnrichmentLogEntry] | None = None,
) -> MagicMock:
    mock = MagicMock()
    mock.enrich.return_value = log_entries or []
    return mock


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestAllProvidersSucceed:
    """All three providers configured and succeed."""

    def test_report_aggregates_all_logs(self) -> None:
        new_entry = _make_entry("newdrug", last_updated=date.today())
        fda_log = _make_log_entry("newdrug", EnrichmentAction.NEW_ENTRY)
        trial_log = _make_log_entry("testdrug", EnrichmentAction.UPDATED_COMPETITORS)
        patent_log = _make_log_entry("testdrug", EnrichmentAction.UPDATED_PATENT_JURISDICTION)

        fda = _mock_fda_discovery([new_entry], [fda_log])
        trial = _mock_trial_enricher([trial_log])
        patent = _mock_patent_enricher([patent_log])

        seed = _make_seed()
        orch = SeedEnrichmentOrchestrator(
            fda_discovery=fda,
            trial_enricher=trial,
            patent_enricher=patent,
        )
        report = orch.run(seed)

        # All three provider logs present
        actions = [entry.action for entry in report.log]
        assert EnrichmentAction.NEW_ENTRY in actions
        assert EnrichmentAction.UPDATED_COMPETITORS in actions
        assert EnrichmentAction.UPDATED_PATENT_JURISDICTION in actions

        assert report.new_entries_added == 1
        assert report.entries_scanned == 2  # original + new

    def test_version_incremented(self) -> None:
        seed = _make_seed()
        orch = SeedEnrichmentOrchestrator(
            fda_discovery=_mock_fda_discovery(),
            trial_enricher=_mock_trial_enricher(),
            patent_enricher=_mock_patent_enricher(),
        )
        orch.run(seed)
        assert seed.data_version == 2

    def test_last_enrichment_run_set(self) -> None:
        seed = _make_seed()
        before = datetime.now(UTC)
        orch = SeedEnrichmentOrchestrator(
            fda_discovery=_mock_fda_discovery(),
            trial_enricher=_mock_trial_enricher(),
            patent_enricher=_mock_patent_enricher(),
        )
        orch.run(seed)
        after = datetime.now(UTC)

        assert seed.last_enrichment_run is not None
        assert before <= seed.last_enrichment_run <= after

    def test_entry_count_updated_after_discovery(self) -> None:
        new_entry = _make_entry("newdrug")
        fda = _mock_fda_discovery([new_entry], [_make_log_entry()])
        seed = _make_seed()  # 1 entry initially
        orch = SeedEnrichmentOrchestrator(fda_discovery=fda)
        orch.run(seed)

        assert seed.entry_count == 2


class TestIndividualProviderFailure:
    """One provider fails; others still run."""

    def test_fda_failure_does_not_block_others(self) -> None:
        fda = MagicMock()
        fda.discover.side_effect = RuntimeError("BQ down")
        trial_log = _make_log_entry("testdrug", EnrichmentAction.UPDATED_COMPETITORS)
        trial = _mock_trial_enricher([trial_log])
        patent = _mock_patent_enricher()

        seed = _make_seed()
        orch = SeedEnrichmentOrchestrator(
            fda_discovery=fda,
            trial_enricher=trial,
            patent_enricher=patent,
        )
        report = orch.run(seed)

        assert report.new_entries_added == 0
        assert EnrichmentAction.UPDATED_COMPETITORS in [e.action for e in report.log]
        # Version still incremented
        assert seed.data_version == 2

    def test_trial_failure_does_not_block_patent(self) -> None:
        trial = MagicMock()
        trial.enrich.side_effect = RuntimeError("API down")
        patent_log = _make_log_entry("testdrug", EnrichmentAction.UPDATED_PATENT_JURISDICTION)
        patent = _mock_patent_enricher([patent_log])

        seed = _make_seed()
        orch = SeedEnrichmentOrchestrator(
            trial_enricher=trial,
            patent_enricher=patent,
        )
        report = orch.run(seed)

        assert EnrichmentAction.UPDATED_PATENT_JURISDICTION in [e.action for e in report.log]

    def test_patent_failure_does_not_block_run(self) -> None:
        patent = MagicMock()
        patent.enrich.side_effect = RuntimeError("timeout")

        seed = _make_seed()
        orch = SeedEnrichmentOrchestrator(patent_enricher=patent)
        report = orch.run(seed)

        # Run completes, version still incremented
        assert seed.data_version == 2
        assert report.entries_scanned == 1


class TestNoProvidersConfigured:
    """All providers are None."""

    def test_stale_revenue_still_flagged(self) -> None:
        stale_entry = _make_entry("olddrug", revenue_year=2020)
        seed = _make_seed([stale_entry])
        orch = SeedEnrichmentOrchestrator()
        report = orch.run(seed)

        assert report.stale_revenue_flagged == 1
        stale_actions = [
            e for e in report.log
            if e.action == EnrichmentAction.FLAGGED_STALE_REVENUE
        ]
        assert len(stale_actions) == 1
        assert stale_actions[0].drug_name == "olddrug"

    def test_version_incremented_with_no_providers(self) -> None:
        seed = _make_seed()
        orch = SeedEnrichmentOrchestrator()
        orch.run(seed)
        assert seed.data_version == 2

    def test_last_enrichment_run_set_with_no_providers(self) -> None:
        seed = _make_seed()
        orch = SeedEnrichmentOrchestrator()
        before = datetime.now(UTC)
        orch.run(seed)
        assert seed.last_enrichment_run is not None
        assert seed.last_enrichment_run >= before


class TestStaleRevenueDetection:
    """Stale revenue flagging logic."""

    def test_old_revenue_year_flagged(self) -> None:
        current_year = date.today().year
        stale = _make_entry("stale1", revenue_year=current_year - 2)
        seed = _make_seed([stale])
        report = SeedEnrichmentOrchestrator().run(seed)

        assert report.stale_revenue_flagged == 1
        log = report.log[0]
        assert log.action == EnrichmentAction.FLAGGED_STALE_REVENUE
        assert log.field_changed == "revenue_year"
        assert log.old_value == str(current_year - 2)
        assert log.new_value == "stale"
        assert log.source == "system"
        assert log.confidence == "high"

    def test_current_revenue_year_not_flagged(self) -> None:
        current_year = date.today().year
        fresh = _make_entry("fresh1", revenue_year=current_year)
        seed = _make_seed([fresh])
        report = SeedEnrichmentOrchestrator().run(seed)
        assert report.stale_revenue_flagged == 0

    def test_previous_year_not_flagged(self) -> None:
        """revenue_year == current_year - 1 should NOT be flagged (only < current - 1)."""
        current_year = date.today().year
        borderline = _make_entry("borderline", revenue_year=current_year - 1)
        seed = _make_seed([borderline])
        report = SeedEnrichmentOrchestrator().run(seed)
        assert report.stale_revenue_flagged == 0

    def test_none_revenue_year_not_flagged(self) -> None:
        entry = _make_entry("nodrug", revenue_year=None)
        seed = _make_seed([entry])
        report = SeedEnrichmentOrchestrator().run(seed)
        assert report.stale_revenue_flagged == 0

    def test_multiple_stale_entries(self) -> None:
        current_year = date.today().year
        entries = [
            _make_entry("stale1", revenue_year=current_year - 3),
            _make_entry("stale2", revenue_year=current_year - 5),
            _make_entry("fresh", revenue_year=current_year),
        ]
        seed = _make_seed(entries)
        report = SeedEnrichmentOrchestrator().run(seed)
        assert report.stale_revenue_flagged == 2


class TestReportFields:
    """Verify EnrichmentReport population."""

    def test_run_id_is_uuid(self) -> None:
        seed = _make_seed()
        report = SeedEnrichmentOrchestrator().run(seed)
        # UUID format: 8-4-4-4-12 hex chars
        import uuid

        uuid.UUID(report.run_id)  # raises if invalid

    def test_started_before_completed(self) -> None:
        seed = _make_seed()
        report = SeedEnrichmentOrchestrator().run(seed)
        assert report.started_at <= report.completed_at

    def test_entries_updated_counts_today(self) -> None:
        entries = [
            _make_entry("a", last_updated=date.today()),
            _make_entry("b", last_updated=date.today() - timedelta(days=30)),
            _make_entry("c", last_updated=None),
        ]
        seed = _make_seed(entries)
        report = SeedEnrichmentOrchestrator().run(seed)
        assert report.entries_updated == 1
