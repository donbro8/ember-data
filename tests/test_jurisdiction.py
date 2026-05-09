"""Tests for jurisdiction mapping utilities — TASK-052."""

from __future__ import annotations

import pytest

from ember_data.jurisdiction import PREFIX_TO_JURISDICTION, extract_jurisdiction


# ---------------------------------------------------------------------------
# All 11 prefix mappings
# ---------------------------------------------------------------------------


class TestPrefixMappings:
    @pytest.mark.parametrize(
        ("prefix", "expected"),
        [
            ("US", "US"),
            ("EP", "EU"),
            ("JP", "JP"),
            ("CN", "CN"),
            ("KR", "KR"),
            ("CA", "CA"),
            ("AU", "AU"),
            ("GB", "GB"),
            ("IN", "IN"),
            ("BR", "BR"),
            ("WO", "WIPO"),
        ],
    )
    def test_all_prefix_mappings(self, prefix: str, expected: str) -> None:
        assert PREFIX_TO_JURISDICTION[prefix] == expected

    def test_mapping_has_exactly_11_entries(self) -> None:
        assert len(PREFIX_TO_JURISDICTION) == 11


# ---------------------------------------------------------------------------
# extract_jurisdiction — format variants
# ---------------------------------------------------------------------------


class TestExtractJurisdiction:
    @pytest.mark.parametrize(
        ("pub_number", "expected"),
        [
            ("US-1234567", "US"),
            ("US1234567", "US"),
            ("EP 9876543", "EU"),
            ("EP9876543", "EU"),
            ("JP-2024001234", "JP"),
            ("CN112233445", "CN"),
            ("KR-1020230001", "KR"),
            ("CA-3123456", "CA"),
            ("AU-2023100123", "AU"),
            ("GB-2612345", "GB"),
            ("IN-202341001234", "IN"),
            ("BR-112023001234", "BR"),
            ("WO-2024001234", "WIPO"),
        ],
    )
    def test_known_formats(self, pub_number: str, expected: str) -> None:
        assert extract_jurisdiction(pub_number) == expected


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_string_returns_none(self) -> None:
        assert extract_jurisdiction("") is None

    def test_unrecognized_prefix_returns_none(self) -> None:
        assert extract_jurisdiction("XX-123") is None

    def test_none_input_returns_none(self) -> None:
        # Defensive: type hint says str but handle None gracefully
        assert extract_jurisdiction(None) is None  # type: ignore[arg-type]

    def test_lowercase_prefix_returns_none(self) -> None:
        # Only uppercase prefixes are recognized
        assert extract_jurisdiction("us-1234567") is None

    def test_single_letter_prefix_returns_none(self) -> None:
        assert extract_jurisdiction("U-1234567") is None
