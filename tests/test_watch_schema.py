"""Tests for WatchConfig model, WATCH_CONFIGS_SCHEMA, ChangeType, and CHANGE_LOG_SCHEMA."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from ember_data.bigquery.watch_schema import (
    CHANGE_LOG_SCHEMA,
    WATCH_CONFIGS_SCHEMA,
    ChangeType,
    WatchConfig,
)

_NOW = datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _field_names(schema: list[dict]) -> set[str]:
    return {f["name"] for f in schema}


def _field_map(schema: list[dict]) -> dict[str, dict]:
    return {f["name"]: f for f in schema}


def _valid_weekly(**overrides: object) -> WatchConfig:
    defaults = dict(
        watch_id="abc-123",
        name="My Watch",
        query="adalimumab biosimilars",
        schedule="weekly",
        schedule_day=1,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return WatchConfig(**defaults)  # type: ignore[arg-type]


def _valid_monthly(**overrides: object) -> WatchConfig:
    defaults = dict(
        watch_id="abc-456",
        name="Monthly Watch",
        query="bevacizumab biosimilars",
        schedule="monthly",
        schedule_day=15,
        created_at=_NOW,
        updated_at=_NOW,
    )
    defaults.update(overrides)
    return WatchConfig(**defaults)  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# WatchConfig — construction and defaults
# ---------------------------------------------------------------------------


class TestWatchConfigDefaults:
    def test_enabled_defaults_true(self):
        config = _valid_weekly()
        assert config.enabled is True

    def test_notify_on_change_defaults_false(self):
        config = _valid_weekly()
        assert config.notify_on_change is False

    def test_last_run_id_defaults_none(self):
        config = _valid_weekly()
        assert config.last_run_id is None

    def test_last_run_at_defaults_none(self):
        config = _valid_weekly()
        assert config.last_run_at is None

    def test_schedule_day_defaults_none(self):
        config = WatchConfig(
            watch_id="x",
            name="no-day",
            query="q",
            schedule="weekly",
            created_at=_NOW,
            updated_at=_NOW,
        )
        assert config.schedule_day is None


# ---------------------------------------------------------------------------
# WatchConfig — schedule_day validation
# ---------------------------------------------------------------------------


class TestWatchConfigScheduleDayValidation:
    def test_weekly_valid_day_zero(self):
        config = _valid_weekly(schedule_day=0)
        assert config.schedule_day == 0

    def test_weekly_valid_day_six(self):
        config = _valid_weekly(schedule_day=6)
        assert config.schedule_day == 6

    def test_weekly_rejects_day_seven(self):
        with pytest.raises(ValidationError, match="schedule_day must be 0-6 for weekly"):
            _valid_weekly(schedule_day=7)

    def test_weekly_rejects_negative_day(self):
        with pytest.raises(ValidationError, match="schedule_day must be 0-6 for weekly"):
            _valid_weekly(schedule_day=-1)

    def test_monthly_valid_day_one(self):
        config = _valid_monthly(schedule_day=1)
        assert config.schedule_day == 1

    def test_monthly_valid_day_28(self):
        config = _valid_monthly(schedule_day=28)
        assert config.schedule_day == 28

    def test_monthly_rejects_day_zero(self):
        with pytest.raises(ValidationError, match="schedule_day must be 1-28 for monthly"):
            _valid_monthly(schedule_day=0)

    def test_monthly_rejects_day_29(self):
        with pytest.raises(ValidationError, match="schedule_day must be 1-28 for monthly"):
            _valid_monthly(schedule_day=29)

    def test_none_is_always_valid_weekly(self):
        config = _valid_weekly(schedule_day=None)
        assert config.schedule_day is None

    def test_none_is_always_valid_monthly(self):
        config = _valid_monthly(schedule_day=None)
        assert config.schedule_day is None


# ---------------------------------------------------------------------------
# WATCH_CONFIGS_SCHEMA
# ---------------------------------------------------------------------------


class TestWatchConfigsSchema:
    def test_all_expected_fields_present(self):
        names = _field_names(WATCH_CONFIGS_SCHEMA)
        expected = {
            "watch_id",
            "name",
            "query",
            "schedule",
            "schedule_day",
            "enabled",
            "created_at",
            "updated_at",
            "last_run_id",
            "last_run_at",
            "notify_on_change",
        }
        assert expected == names

    def test_required_fields_have_required_mode(self):
        fm = _field_map(WATCH_CONFIGS_SCHEMA)
        required_fields = ["watch_id", "name", "query", "schedule", "enabled", "created_at", "updated_at", "notify_on_change"]
        for field in required_fields:
            assert fm[field]["mode"] == "REQUIRED", f"{field} should be REQUIRED"

    def test_nullable_fields_have_nullable_mode(self):
        fm = _field_map(WATCH_CONFIGS_SCHEMA)
        nullable_fields = ["schedule_day", "last_run_id", "last_run_at"]
        for field in nullable_fields:
            assert fm[field]["mode"] == "NULLABLE", f"{field} should be NULLABLE"

    def test_schedule_day_is_int64(self):
        fm = _field_map(WATCH_CONFIGS_SCHEMA)
        assert fm["schedule_day"]["type"] == "INT64"

    def test_timestamp_fields_are_timestamp_type(self):
        fm = _field_map(WATCH_CONFIGS_SCHEMA)
        for field in ["created_at", "updated_at", "last_run_at"]:
            assert fm[field]["type"] == "TIMESTAMP", f"{field} should be TIMESTAMP"

    def test_boolean_fields_are_boolean_type(self):
        fm = _field_map(WATCH_CONFIGS_SCHEMA)
        for field in ["enabled", "notify_on_change"]:
            assert fm[field]["type"] == "BOOLEAN", f"{field} should be BOOLEAN"


# ---------------------------------------------------------------------------
# ChangeType enum
# ---------------------------------------------------------------------------


class TestChangeType:
    def test_all_expected_values_present(self):
        values = {ct.value for ct in ChangeType}
        expected = {
            "new_candidate",
            "removed_candidate",
            "score_change",
            "patent_expiry_update",
            "new_trial",
            "new_biosimilar_competitor",
            "new_jurisdiction",
        }
        assert expected == values

    def test_change_type_is_str_enum(self):
        assert isinstance(ChangeType.NEW_CANDIDATE, str)
        assert ChangeType.NEW_CANDIDATE == "new_candidate"

    def test_individual_values(self):
        assert ChangeType.NEW_CANDIDATE.value == "new_candidate"
        assert ChangeType.REMOVED_CANDIDATE.value == "removed_candidate"
        assert ChangeType.SCORE_CHANGE.value == "score_change"
        assert ChangeType.PATENT_EXPIRY_UPDATE.value == "patent_expiry_update"
        assert ChangeType.NEW_TRIAL.value == "new_trial"
        assert ChangeType.NEW_BIOSIMILAR_COMPETITOR.value == "new_biosimilar_competitor"
        assert ChangeType.NEW_JURISDICTION.value == "new_jurisdiction"


# ---------------------------------------------------------------------------
# CHANGE_LOG_SCHEMA
# ---------------------------------------------------------------------------


class TestChangeLogSchema:
    def test_all_expected_fields_present(self):
        names = _field_names(CHANGE_LOG_SCHEMA)
        expected = {
            "change_id",
            "watch_id",
            "run_id",
            "previous_run_id",
            "change_type",
            "canonical_id",
            "display_label",
            "detail",
            "created_at",
        }
        assert expected == names

    def test_required_fields_have_required_mode(self):
        fm = _field_map(CHANGE_LOG_SCHEMA)
        required_fields = [
            "change_id",
            "watch_id",
            "run_id",
            "previous_run_id",
            "change_type",
            "canonical_id",
            "display_label",
            "created_at",
        ]
        for field in required_fields:
            assert fm[field]["mode"] == "REQUIRED", f"{field} should be REQUIRED"

    def test_detail_is_nullable(self):
        fm = _field_map(CHANGE_LOG_SCHEMA)
        assert fm["detail"]["mode"] == "NULLABLE"

    def test_created_at_is_timestamp(self):
        fm = _field_map(CHANGE_LOG_SCHEMA)
        assert fm["created_at"]["type"] == "TIMESTAMP"

    def test_string_fields_are_string_type(self):
        fm = _field_map(CHANGE_LOG_SCHEMA)
        for field in ["change_id", "watch_id", "run_id", "previous_run_id", "change_type", "canonical_id", "display_label", "detail"]:
            assert fm[field]["type"] == "STRING", f"{field} should be STRING"

    def test_field_count(self):
        assert len(CHANGE_LOG_SCHEMA) == 9
