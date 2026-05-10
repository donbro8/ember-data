"""Tests for canary watch configuration and health check logic."""

from __future__ import annotations

import pytest

from ember_data.bigquery.canary import (
    CANARY_BASELINES,
    CANARY_WATCH_CONFIG,
    _is_populated,
    check_canary_results,
)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class _FakeResult:
    """Dict-like object with attribute access for testing."""

    def __init__(self, **kwargs):
        self._data = kwargs
        for k, v in kwargs.items():
            setattr(self, k, v)

    def get(self, key, default=None):
        return self._data.get(key, default)


def _make_full_result(**overrides):
    """Return a result with all CANARY_BASELINES fields populated."""
    defaults = {
        "canonical_id": "drug-001",
        "display_label": "Adalimumab",
        "drug_name": "adalimumab",
        "target": "TNF-alpha",
        "indication": "rheumatoid arthritis",
        "patents": ["US1234567"],
        "trials": ["NCT00000001"],
        "articles": ["pmid:12345"],
        "source_urls": ["https://example.com"],
        "overall_score": 0.85,
    }
    defaults.update(overrides)
    return _FakeResult(**defaults)


# ---------------------------------------------------------------------------
# CANARY_WATCH_CONFIG tests
# ---------------------------------------------------------------------------


def test_canary_watch_config_shape():
    assert CANARY_WATCH_CONFIG["name"] == "system-canary"
    assert CANARY_WATCH_CONFIG["query"] == "adalimumab"
    assert CANARY_WATCH_CONFIG["schedule"] == "weekly"
    assert CANARY_WATCH_CONFIG["schedule_day"] == 0  # Monday
    assert CANARY_WATCH_CONFIG["enabled"] is True
    assert CANARY_WATCH_CONFIG["notify_on_change"] is True


def test_canary_baselines_coverage():
    """All expected fields present with sensible thresholds."""
    assert "canonical_id" in CANARY_BASELINES
    assert "overall_score" in CANARY_BASELINES
    for field, threshold in CANARY_BASELINES.items():
        assert 0 <= threshold <= 100, f"{field} threshold {threshold} out of range"


# ---------------------------------------------------------------------------
# check_canary_results — empty / no results
# ---------------------------------------------------------------------------


def test_check_canary_empty_list():
    result = check_canary_results([])
    assert result["passed"] is False
    assert "no_results" in result["alerts"]
    assert result["rates"] == {}


# ---------------------------------------------------------------------------
# check_canary_results — all fields passing
# ---------------------------------------------------------------------------


def test_check_canary_all_passing():
    results = [_make_full_result() for _ in range(10)]
    outcome = check_canary_results(results)
    assert outcome["passed"] is True
    assert outcome["alerts"] == []
    # Every required field should have a rate
    for field in CANARY_BASELINES:
        assert field in outcome["rates"]


def test_check_canary_rates_are_percentages():
    results = [_make_full_result() for _ in range(5)]
    outcome = check_canary_results(results)
    for field, rate in outcome["rates"].items():
        assert 0 <= rate <= 100, f"{field} rate {rate} out of percentage range"


# ---------------------------------------------------------------------------
# check_canary_results — field drops below threshold
# ---------------------------------------------------------------------------


def test_check_canary_field_drop_triggers_alert():
    """If >10pp of results are missing 'target', it should alert."""
    # target baseline=60; with rate=0 it is well below the 50pp threshold
    # Create results where target is missing in most records so rate < 50
    results = [_make_full_result(target=None) for _ in range(10)]
    outcome = check_canary_results(results)
    assert outcome["passed"] is False
    assert "target" in outcome["alerts"]
    assert outcome["rates"]["target"] == 0


def test_check_canary_within_threshold_does_not_alert():
    """A drop within the threshold window must not alert."""
    # target baseline=60, threshold_drop=10 → alert if rate < 50
    # We want rate = 55 → 55% populated
    n = 20
    populated_count = 11  # 55%
    results = (
        [_make_full_result() for _ in range(populated_count)]
        + [_make_full_result(target=None) for _ in range(n - populated_count)]
    )
    outcome = check_canary_results(results)
    assert "target" not in outcome["alerts"]


def test_check_canary_custom_threshold_drop():
    """A stricter threshold_drop should catch shallower drops."""
    # target baseline=60, threshold_drop=5 → alert if rate < 55
    # Use 10/20 = 50%, which is below 55 but above 50 (default threshold)
    n = 20
    populated_count = 10  # 50% — triggers at threshold_drop=5 (need <55), safe at default 10pp (need <50)
    results = (
        [_make_full_result() for _ in range(populated_count)]
        + [_make_full_result(target=None) for _ in range(n - populated_count)]
    )
    outcome = check_canary_results(results, threshold_drop=5)
    assert "target" in outcome["alerts"]
    # Confirm default threshold_drop=10 does NOT alert at this rate (50 < 50 is false)
    outcome_default = check_canary_results(results)
    assert "target" not in outcome_default["alerts"]


def test_check_canary_multiple_alerts():
    """Multiple failing fields all appear in alerts."""
    results = [_make_full_result(target=None, indication=None) for _ in range(10)]
    outcome = check_canary_results(results)
    assert "target" in outcome["alerts"]
    assert "indication" in outcome["alerts"]
    assert outcome["passed"] is False


# ---------------------------------------------------------------------------
# _is_populated
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "value,expected",
    [
        (None, False),
        ("", False),
        ([], False),
        (0, False),
        (0.0, False),
        ("adalimumab", True),
        (["US1234567"], True),
        (0.85, True),
        (1, True),
        ({"key": "val"}, True),
    ],
)
def test_is_populated_attribute(value, expected):
    result = _FakeResult(field=value)
    assert _is_populated(result, "field") is expected


def test_is_populated_dict_style():
    result = {"field": "present", "empty": ""}
    assert _is_populated(result, "field") is True
    assert _is_populated(result, "empty") is False
    assert _is_populated(result, "missing") is False


def test_is_populated_missing_attribute():
    result = _FakeResult()
    assert _is_populated(result, "nonexistent") is False
