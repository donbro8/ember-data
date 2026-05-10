"""Tests for ChangeDetector: all 7 change types plus write/get operations."""

from __future__ import annotations

from datetime import datetime, timezone
from unittest.mock import MagicMock

from ember_data.bigquery.change_detector import ChangeDetector, ChangeEntry
from ember_data.bigquery.watch_schema import ChangeType

_NOW = datetime(2026, 5, 10, 12, 0, 0, tzinfo=timezone.utc)
_DATASET = "ember_test"
_WATCH_ID = "watch-abc-123"
_CURRENT_RUN = "run-current-001"
_PREV_RUN = "run-previous-001"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_detector(
    current_rows: list[dict],
    previous_rows: list[dict],
) -> tuple[ChangeDetector, MagicMock]:
    """Return (ChangeDetector, mock_client) with fetch results pre-configured."""
    client = MagicMock()
    # First call → current run, second call → previous run
    client.query_with_params.side_effect = [current_rows, previous_rows]
    detector = ChangeDetector(client, _DATASET)
    return detector, client


def _base_row(**overrides: object) -> dict:
    """Minimal run_results row with sensible defaults."""
    row: dict = {
        "canonical_id": "candidate-001",
        "display_label": "Drug A",
        "overall_score": 0.75,
        "trial_count": 3,
        "biosimilar_competitor_count": 2,
        "patent_country_codes": ["US", "EU"],
        "patent_expiry_dates": {"US": "2030-01-01", "EU": "2031-06-15"},
    }
    row.update(overrides)
    return row


# ---------------------------------------------------------------------------
# detect_changes: new_candidate
# ---------------------------------------------------------------------------


class TestNewCandidate:
    def test_detects_new_candidate(self) -> None:
        current = [_base_row(canonical_id="candidate-001", display_label="Drug A")]
        previous: list[dict] = []
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        assert len(changes) == 1
        assert changes[0].change_type == ChangeType.NEW_CANDIDATE.value
        assert changes[0].canonical_id == "candidate-001"
        assert changes[0].display_label == "Drug A"
        assert "Drug A" in changes[0].detail  # type: ignore[operator]

    def test_new_candidate_detail_format(self) -> None:
        current = [_base_row(display_label="Biosimilar X")]
        previous: list[dict] = []
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        assert changes[0].detail == "New candidate: Biosimilar X"

    def test_no_change_when_same_candidates(self) -> None:
        row = _base_row()
        detector, _ = _make_detector([row], [row])
        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)
        # No structural changes, only check for absence of new/removed
        change_types = {c.change_type for c in changes}
        assert ChangeType.NEW_CANDIDATE.value not in change_types
        assert ChangeType.REMOVED_CANDIDATE.value not in change_types


# ---------------------------------------------------------------------------
# detect_changes: removed_candidate
# ---------------------------------------------------------------------------


class TestRemovedCandidate:
    def test_detects_removed_candidate(self) -> None:
        current = [_base_row(canonical_id="candidate-003", display_label="Drug C")]
        previous = [
            _base_row(canonical_id="candidate-002", display_label="Drug B"),
            _base_row(canonical_id="candidate-003", display_label="Drug C"),
        ]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        removed = [c for c in changes if c.change_type == ChangeType.REMOVED_CANDIDATE.value]
        assert len(removed) == 1
        assert removed[0].canonical_id == "candidate-002"

    def test_removed_candidate_detail_format(self) -> None:
        current = [_base_row(canonical_id="candidate-other", display_label="Other")]
        previous = [
            _base_row(canonical_id="candidate-other", display_label="Other"),
            _base_row(display_label="Old Drug"),
        ]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        removed = [c for c in changes if c.change_type == ChangeType.REMOVED_CANDIDATE.value]
        assert removed[0].detail == "Removed: Old Drug"

    def test_empty_current_run_skips_detection(self) -> None:
        """An empty current run should return no changes to avoid false removal flood."""
        current: list[dict] = []
        previous = [_base_row(canonical_id="candidate-002", display_label="Drug B")]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        assert len(changes) == 0


# ---------------------------------------------------------------------------
# detect_changes: score_change
# ---------------------------------------------------------------------------


class TestScoreChange:
    def test_detects_score_change_above_threshold(self) -> None:
        current = [_base_row(overall_score=0.9)]
        previous = [_base_row(overall_score=0.7)]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        score_changes = [c for c in changes if c.change_type == ChangeType.SCORE_CHANGE.value]
        assert len(score_changes) == 1
        assert "0.7" in score_changes[0].detail  # type: ignore[operator]
        assert "0.9" in score_changes[0].detail  # type: ignore[operator]

    def test_no_score_change_just_below_threshold(self) -> None:
        # delta of 0.09 — just under the 0.1 threshold
        current = [_base_row(overall_score=0.79)]
        previous = [_base_row(overall_score=0.70)]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        score_changes = [c for c in changes if c.change_type == ChangeType.SCORE_CHANGE.value]
        assert len(score_changes) == 0

    def test_no_score_change_below_threshold(self) -> None:
        current = [_base_row(overall_score=0.75)]
        previous = [_base_row(overall_score=0.72)]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        score_changes = [c for c in changes if c.change_type == ChangeType.SCORE_CHANGE.value]
        assert len(score_changes) == 0

    def test_score_change_detail_format(self) -> None:
        current = [_base_row(overall_score=0.95)]
        previous = [_base_row(overall_score=0.50)]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        score_changes = [c for c in changes if c.change_type == ChangeType.SCORE_CHANGE.value]
        assert score_changes[0].detail == "Score changed from 0.5 to 0.95"


# ---------------------------------------------------------------------------
# detect_changes: new_trial
# ---------------------------------------------------------------------------


class TestNewTrial:
    def test_detects_new_trial(self) -> None:
        current = [_base_row(trial_count=5)]
        previous = [_base_row(trial_count=3)]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        trial_changes = [c for c in changes if c.change_type == ChangeType.NEW_TRIAL.value]
        assert len(trial_changes) == 1
        assert trial_changes[0].detail == "Trial count increased from 3 to 5"

    def test_no_new_trial_when_same(self) -> None:
        current = [_base_row(trial_count=3)]
        previous = [_base_row(trial_count=3)]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        trial_changes = [c for c in changes if c.change_type == ChangeType.NEW_TRIAL.value]
        assert len(trial_changes) == 0

    def test_no_new_trial_when_decreased(self) -> None:
        current = [_base_row(trial_count=2)]
        previous = [_base_row(trial_count=3)]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        trial_changes = [c for c in changes if c.change_type == ChangeType.NEW_TRIAL.value]
        assert len(trial_changes) == 0


# ---------------------------------------------------------------------------
# detect_changes: new_biosimilar_competitor
# ---------------------------------------------------------------------------


class TestNewBiosimilarCompetitor:
    def test_detects_new_biosimilar_competitor(self) -> None:
        current = [_base_row(biosimilar_competitor_count=4)]
        previous = [_base_row(biosimilar_competitor_count=2)]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        bio_changes = [
            c for c in changes if c.change_type == ChangeType.NEW_BIOSIMILAR_COMPETITOR.value
        ]
        assert len(bio_changes) == 1
        assert bio_changes[0].detail == "New biosimilar competitor (now 4 total)"

    def test_no_biosimilar_change_when_same(self) -> None:
        row = _base_row(biosimilar_competitor_count=2)
        detector, _ = _make_detector([row], [row])

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        bio_changes = [
            c for c in changes if c.change_type == ChangeType.NEW_BIOSIMILAR_COMPETITOR.value
        ]
        assert len(bio_changes) == 0


# ---------------------------------------------------------------------------
# detect_changes: patent_expiry_update
# ---------------------------------------------------------------------------


class TestPatentExpiryUpdate:
    def test_detects_expiry_date_change(self) -> None:
        current = [
            _base_row(patent_expiry_dates={"US": "2035-01-01", "EU": "2031-06-15"})
        ]
        previous = [
            _base_row(patent_expiry_dates={"US": "2030-01-01", "EU": "2031-06-15"})
        ]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        expiry_changes = [
            c for c in changes if c.change_type == ChangeType.PATENT_EXPIRY_UPDATE.value
        ]
        assert len(expiry_changes) == 1
        assert expiry_changes[0].detail == "Patent expiry updated in US"

    def test_multiple_expiry_changes(self) -> None:
        current = [
            _base_row(
                patent_expiry_dates={"US": "2035-01-01", "EU": "2034-06-15"}
            )
        ]
        previous = [
            _base_row(
                patent_expiry_dates={"US": "2030-01-01", "EU": "2031-06-15"}
            )
        ]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        expiry_changes = [
            c for c in changes if c.change_type == ChangeType.PATENT_EXPIRY_UPDATE.value
        ]
        assert len(expiry_changes) == 2

    def test_no_expiry_change_when_same(self) -> None:
        row = _base_row(patent_expiry_dates={"US": "2030-01-01"})
        detector, _ = _make_detector([row], [row])

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        expiry_changes = [
            c for c in changes if c.change_type == ChangeType.PATENT_EXPIRY_UPDATE.value
        ]
        assert len(expiry_changes) == 0

    def test_new_jurisdiction_not_flagged_as_expiry_update(self) -> None:
        """A jurisdiction that didn't exist in previous should NOT trigger expiry_update."""
        current = [
            _base_row(patent_expiry_dates={"US": "2030-01-01", "JP": "2032-03-01"})
        ]
        previous = [
            _base_row(patent_expiry_dates={"US": "2030-01-01"})
        ]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        expiry_changes = [
            c for c in changes if c.change_type == ChangeType.PATENT_EXPIRY_UPDATE.value
        ]
        assert len(expiry_changes) == 0


# ---------------------------------------------------------------------------
# detect_changes: new_jurisdiction
# ---------------------------------------------------------------------------


class TestNewJurisdiction:
    def test_detects_new_jurisdiction(self) -> None:
        current = [_base_row(patent_country_codes=["US", "EU", "JP"])]
        previous = [_base_row(patent_country_codes=["US", "EU"])]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        jurisdiction_changes = [
            c for c in changes if c.change_type == ChangeType.NEW_JURISDICTION.value
        ]
        assert len(jurisdiction_changes) == 1
        assert "JP" in jurisdiction_changes[0].detail  # type: ignore[operator]

    def test_new_jurisdiction_detail_includes_sorted_codes(self) -> None:
        current = [_base_row(patent_country_codes=["US", "EU", "CN", "JP"])]
        previous = [_base_row(patent_country_codes=["US", "EU"])]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        jurisdiction_changes = [
            c for c in changes if c.change_type == ChangeType.NEW_JURISDICTION.value
        ]
        assert len(jurisdiction_changes) == 1
        assert jurisdiction_changes[0].detail == "New patent jurisdiction: CN, JP"

    def test_no_jurisdiction_change_when_same(self) -> None:
        row = _base_row(patent_country_codes=["US", "EU"])
        detector, _ = _make_detector([row], [row])

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        jurisdiction_changes = [
            c for c in changes if c.change_type == ChangeType.NEW_JURISDICTION.value
        ]
        assert len(jurisdiction_changes) == 0

    def test_no_new_jurisdiction_when_codes_removed(self) -> None:
        """Removing a jurisdiction should NOT produce new_jurisdiction."""
        current = [_base_row(patent_country_codes=["US"])]
        previous = [_base_row(patent_country_codes=["US", "EU"])]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        jurisdiction_changes = [
            c for c in changes if c.change_type == ChangeType.NEW_JURISDICTION.value
        ]
        assert len(jurisdiction_changes) == 0


# ---------------------------------------------------------------------------
# detect_changes: multiple changes for one candidate
# ---------------------------------------------------------------------------


class TestMultipleChanges:
    def test_multiple_change_types_for_same_candidate(self) -> None:
        current = [
            _base_row(
                overall_score=0.95,
                trial_count=6,
                biosimilar_competitor_count=5,
                patent_country_codes=["US", "EU", "JP"],
                patent_expiry_dates={"US": "2035-01-01", "EU": "2031-06-15"},
            )
        ]
        previous = [
            _base_row(
                overall_score=0.50,
                trial_count=3,
                biosimilar_competitor_count=2,
                patent_country_codes=["US", "EU"],
                patent_expiry_dates={"US": "2030-01-01", "EU": "2031-06-15"},
            )
        ]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        types = {c.change_type for c in changes}
        assert ChangeType.SCORE_CHANGE.value in types
        assert ChangeType.NEW_TRIAL.value in types
        assert ChangeType.NEW_BIOSIMILAR_COMPETITOR.value in types
        assert ChangeType.NEW_JURISDICTION.value in types
        assert ChangeType.PATENT_EXPIRY_UPDATE.value in types

    def test_mixed_candidates(self) -> None:
        """New, removed, and modified candidates in one call."""
        current = [
            _base_row(canonical_id="drug-A", display_label="Drug A"),
            _base_row(canonical_id="drug-C", display_label="Drug C"),  # new
        ]
        previous = [
            _base_row(canonical_id="drug-A", display_label="Drug A"),
            _base_row(canonical_id="drug-B", display_label="Drug B"),  # removed
        ]
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        types = {c.change_type for c in changes}
        assert ChangeType.NEW_CANDIDATE.value in types
        assert ChangeType.REMOVED_CANDIDATE.value in types


# ---------------------------------------------------------------------------
# ChangeEntry metadata
# ---------------------------------------------------------------------------


class TestChangeEntryMetadata:
    def test_change_entry_has_unique_change_id(self) -> None:
        current = [_base_row(canonical_id="a"), _base_row(canonical_id="b")]
        previous: list[dict] = []
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        ids = [c.change_id for c in changes]
        assert len(ids) == len(set(ids)), "change_ids must be unique"

    def test_change_entry_fields_populated(self) -> None:
        current = [_base_row()]
        previous: list[dict] = []
        detector, _ = _make_detector(current, previous)

        changes = detector.detect_changes(_WATCH_ID, _CURRENT_RUN, _PREV_RUN)

        entry = changes[0]
        assert entry.watch_id == _WATCH_ID
        assert entry.run_id == _CURRENT_RUN
        assert entry.previous_run_id == _PREV_RUN
        assert isinstance(entry.created_at, datetime)


# ---------------------------------------------------------------------------
# write_changes
# ---------------------------------------------------------------------------


class TestWriteChanges:
    def test_write_changes_calls_insert_rows(self) -> None:
        client = MagicMock()
        detector = ChangeDetector(client, _DATASET)

        entry = ChangeEntry(
            change_id="cid-001",
            watch_id=_WATCH_ID,
            run_id=_CURRENT_RUN,
            previous_run_id=_PREV_RUN,
            change_type=ChangeType.NEW_CANDIDATE.value,
            canonical_id="drug-A",
            display_label="Drug A",
            detail="New candidate: Drug A",
            created_at=_NOW,
        )
        detector.write_changes([entry])

        client.insert_rows.assert_called_once()
        table_arg, rows_arg = client.insert_rows.call_args.args
        assert table_arg == f"{_DATASET}.change_log"
        assert len(rows_arg) == 1
        assert rows_arg[0]["change_id"] == "cid-001"
        assert rows_arg[0]["change_type"] == ChangeType.NEW_CANDIDATE.value

    def test_write_changes_empty_list_does_not_insert(self) -> None:
        client = MagicMock()
        detector = ChangeDetector(client, _DATASET)

        detector.write_changes([])

        client.insert_rows.assert_not_called()

    def test_write_changes_serializes_datetime(self) -> None:
        client = MagicMock()
        detector = ChangeDetector(client, _DATASET)

        entry = ChangeEntry(
            change_id="cid-002",
            watch_id=_WATCH_ID,
            run_id=_CURRENT_RUN,
            previous_run_id=_PREV_RUN,
            change_type=ChangeType.SCORE_CHANGE.value,
            canonical_id="drug-B",
            display_label="Drug B",
            detail="Score changed",
            created_at=_NOW,
        )
        detector.write_changes([entry])

        _, rows_arg = client.insert_rows.call_args.args
        # created_at must be a string (ISO format) for BigQuery streaming insert
        assert isinstance(rows_arg[0]["created_at"], str)


# ---------------------------------------------------------------------------
# get_changes
# ---------------------------------------------------------------------------


class TestGetChanges:
    def _sample_change_row(self, **overrides: object) -> dict:
        row: dict = {
            "change_id": "cid-001",
            "watch_id": _WATCH_ID,
            "run_id": _CURRENT_RUN,
            "previous_run_id": _PREV_RUN,
            "change_type": ChangeType.NEW_CANDIDATE.value,
            "canonical_id": "drug-A",
            "display_label": "Drug A",
            "detail": "New candidate: Drug A",
            "created_at": _NOW.isoformat(),
        }
        row.update(overrides)
        return row

    def test_get_changes_returns_entries(self) -> None:
        client = MagicMock()
        client.query_with_params.return_value = [self._sample_change_row()]
        detector = ChangeDetector(client, _DATASET)

        results = detector.get_changes(_WATCH_ID)

        assert len(results) == 1
        assert isinstance(results[0], ChangeEntry)
        assert results[0].change_id == "cid-001"
        assert results[0].watch_id == _WATCH_ID

    def test_get_changes_passes_watch_id_and_limit(self) -> None:
        client = MagicMock()
        client.query_with_params.return_value = []
        detector = ChangeDetector(client, _DATASET)

        detector.get_changes(_WATCH_ID, limit=10)

        _, params_arg = client.query_with_params.call_args.args
        assert params_arg["watch_id"] == _WATCH_ID
        assert params_arg["limit"] == 10

    def test_get_changes_default_limit_50(self) -> None:
        client = MagicMock()
        client.query_with_params.return_value = []
        detector = ChangeDetector(client, _DATASET)

        detector.get_changes(_WATCH_ID)

        _, params_arg = client.query_with_params.call_args.args
        assert params_arg["limit"] == 50

    def test_get_changes_returns_empty_list_when_no_rows(self) -> None:
        client = MagicMock()
        client.query_with_params.return_value = []
        detector = ChangeDetector(client, _DATASET)

        results = detector.get_changes(_WATCH_ID)

        assert results == []

    def test_get_changes_parses_datetime_string(self) -> None:
        client = MagicMock()
        client.query_with_params.return_value = [
            self._sample_change_row(created_at=_NOW.isoformat())
        ]
        detector = ChangeDetector(client, _DATASET)

        results = detector.get_changes(_WATCH_ID)

        assert isinstance(results[0].created_at, datetime)

    def test_get_changes_passes_datetime_object_through(self) -> None:
        client = MagicMock()
        client.query_with_params.return_value = [
            self._sample_change_row(created_at=_NOW)
        ]
        detector = ChangeDetector(client, _DATASET)

        results = detector.get_changes(_WATCH_ID)

        assert isinstance(results[0].created_at, datetime)
