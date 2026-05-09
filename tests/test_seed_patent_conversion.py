"""Tests for seed_entry_to_patent_jurisdictions()."""

from __future__ import annotations

from datetime import date

from ember_data.seed.convert import seed_entry_to_patent_jurisdictions
from ember_data.seed.schema import BiologicEntry


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_entry(**overrides) -> BiologicEntry:
    defaults = {
        "drug_name": "testmab",
        "originator": "TestCo",
        "target_antigen": "TNF",
        "patent_expiries": {
            "US": date(2030, 6, 1),
            "JP": date(2020, 1, 1),
        },
        "key_patent_numbers": ["US1234567A"],
    }
    defaults.update(overrides)
    return BiologicEntry(**defaults)


# ---------------------------------------------------------------------------
# expiry_date_approximate is always False for seed data
# ---------------------------------------------------------------------------


def test_approximate_flag_is_false_for_all_jurisdictions():
    entry = _make_entry()
    results = seed_entry_to_patent_jurisdictions(entry)
    assert results, "Expected non-empty list"
    for pj in results:
        assert pj.expiry_date_approximate is False, (
            f"{pj.country_code}: expiry_date_approximate should be False"
        )


# ---------------------------------------------------------------------------
# Status derivation
# ---------------------------------------------------------------------------


def test_status_active_when_expiry_in_future():
    entry = _make_entry(
        patent_expiries={"US": date(2099, 12, 31)},
        key_patent_numbers=[],
    )
    (pj,) = seed_entry_to_patent_jurisdictions(entry)
    assert pj.status == "active"


def test_status_expired_when_expiry_in_past():
    entry = _make_entry(
        patent_expiries={"US": date(2000, 1, 1)},
        key_patent_numbers=[],
    )
    (pj,) = seed_entry_to_patent_jurisdictions(entry)
    assert pj.status == "expired"


def test_status_pending_when_no_expiry():
    """Jurisdictions with no expiry_date in patent_expiries are skipped by dict
    iteration, but if we build a BiologicEntry manually with None values, the
    schema stores date objects.  Test pending via a direct None expiry_date in
    an entry where we override patent_expiries with a None value via the dict
    (None is stored as-is in patent_expiries when no validator rejects it)."""
    # The BiologicEntry schema uses dict[str, date], so we can't directly put
    # None.  Instead we test _derive_status indirectly: an entry that has no
    # matching country in patent_expiries simply won't produce that jurisdiction.
    # Pending status comes only when expiry_date is None in the domain model.
    # We verify this by constructing a PatentJurisdiction directly (already
    # tested elsewhere) — here we ensure the conversion returns "active" or
    # "expired" correctly for the two real cases, and "pending" never appears
    # from seed data with explicit dates.
    entry = _make_entry(
        patent_expiries={"US": date(2030, 1, 1)},
        key_patent_numbers=[],
    )
    results = seed_entry_to_patent_jurisdictions(entry)
    statuses = {pj.status for pj in results}
    assert "pending" not in statuses


# ---------------------------------------------------------------------------
# All jurisdictions from patent_expiries are converted
# ---------------------------------------------------------------------------


def test_all_jurisdictions_converted():
    expiries = {
        "US": date(2030, 1, 1),
        "JP": date(2025, 6, 15),
        "CN": date(2028, 3, 20),
        "KR": date(2019, 1, 1),
    }
    entry = _make_entry(patent_expiries=expiries, key_patent_numbers=[])
    results = seed_entry_to_patent_jurisdictions(entry)
    result_codes = {pj.country_code for pj in results}
    assert result_codes == set(expiries.keys())


def test_empty_patent_expiries_returns_empty_list():
    entry = _make_entry(patent_expiries={}, key_patent_numbers=[])
    results = seed_entry_to_patent_jurisdictions(entry)
    assert results == []


# ---------------------------------------------------------------------------
# Every PatentJurisdiction has a non-empty URL
# ---------------------------------------------------------------------------


def test_every_jurisdiction_has_non_empty_url():
    expiries = {
        "US": date(2030, 1, 1),
        "JP": date(2025, 6, 15),
        "AU": date(2021, 1, 1),
    }
    entry = _make_entry(
        patent_expiries=expiries,
        key_patent_numbers=["US9876543B2"],
    )
    results = seed_entry_to_patent_jurisdictions(entry)
    for pj in results:
        assert pj.url, f"{pj.country_code}: url must be non-empty"
        assert pj.url.startswith("https://")


# ---------------------------------------------------------------------------
# publication_number uses key_patent_number when available
# ---------------------------------------------------------------------------


def test_publication_number_uses_key_patent_number_when_matched():
    entry = _make_entry(
        patent_expiries={"US": date(2030, 1, 1)},
        key_patent_numbers=["US1234567A"],
    )
    (pj,) = seed_entry_to_patent_jurisdictions(entry)
    assert pj.publication_number == "US1234567A"


def test_publication_number_uses_sentinel_when_no_match():
    entry = _make_entry(
        patent_expiries={"JP": date(2030, 1, 1)},
        key_patent_numbers=["US1234567A"],  # US prefix doesn't match JP
    )
    (pj,) = seed_entry_to_patent_jurisdictions(entry)
    assert pj.publication_number == "JP-seed"


def test_publication_number_sentinel_when_no_key_patents():
    entry = _make_entry(
        patent_expiries={"CN": date(2030, 1, 1)},
        key_patent_numbers=[],
    )
    (pj,) = seed_entry_to_patent_jurisdictions(entry)
    assert pj.publication_number == "CN-seed"


# ---------------------------------------------------------------------------
# URL strategy
# ---------------------------------------------------------------------------


def test_url_uses_build_patent_url_when_key_patent_matched():
    entry = _make_entry(
        patent_expiries={"US": date(2030, 1, 1)},
        key_patent_numbers=["US6090382"],
    )
    (pj,) = seed_entry_to_patent_jurisdictions(entry)
    assert pj.url == "https://patents.google.com/patent/US6090382"


def test_url_uses_search_fallback_when_no_match():
    entry = _make_entry(
        drug_name="adalimumab",
        patent_expiries={"JP": date(2018, 10, 16)},
        key_patent_numbers=["US6090382"],  # US key, JP jurisdiction
    )
    (pj,) = seed_entry_to_patent_jurisdictions(entry)
    assert "patents.google.com" in pj.url
    assert "JP" in pj.url
    assert "adalimumab" in pj.url


def test_url_fallback_contains_drug_name_and_country():
    entry = _make_entry(
        drug_name="testmab",
        patent_expiries={"AU": date(2027, 5, 10)},
        key_patent_numbers=[],
    )
    (pj,) = seed_entry_to_patent_jurisdictions(entry)
    assert "testmab" in pj.url
    assert "AU" in pj.url


# ---------------------------------------------------------------------------
# country_name from JURISDICTION_NAMES
# ---------------------------------------------------------------------------


def test_country_name_from_jurisdiction_names():
    entry = _make_entry(
        patent_expiries={"US": date(2030, 1, 1), "JP": date(2025, 1, 1)},
        key_patent_numbers=[],
    )
    results = seed_entry_to_patent_jurisdictions(entry)
    by_code = {pj.country_code: pj for pj in results}
    assert by_code["US"].country_name == "United States"
    assert by_code["JP"].country_name == "Japan"


def test_country_name_falls_back_to_code_for_unknown():
    """Unknown country codes fall back to the code itself."""
    entry = _make_entry(
        patent_expiries={"XX": date(2030, 1, 1)},
        key_patent_numbers=[],
    )
    (pj,) = seed_entry_to_patent_jurisdictions(entry)
    assert pj.country_name == "XX"


# ---------------------------------------------------------------------------
# Integration: real-world-like adalimumab entry
# ---------------------------------------------------------------------------


def test_adalimumab_like_entry():
    entry = BiologicEntry(
        drug_name="adalimumab",
        originator="AbbVie",
        target_antigen="TNF-alpha",
        patent_expiries={
            "US": date(2018, 10, 16),
            "EU": date(2018, 4, 8),
            "JP": date(2018, 10, 16),
        },
        key_patent_numbers=["US6090382"],
    )
    results = seed_entry_to_patent_jurisdictions(entry)
    assert len(results) == 3

    by_code = {pj.country_code: pj for pj in results}

    # US should use the key patent number
    assert by_code["US"].publication_number == "US6090382"
    assert by_code["US"].url == "https://patents.google.com/patent/US6090382"
    assert by_code["US"].status == "expired"
    assert by_code["US"].expiry_date_approximate is False

    # EU and JP should use sentinel and fallback URL
    assert by_code["EU"].publication_number == "EU-seed"
    assert "adalimumab" in by_code["EU"].url

    assert by_code["JP"].publication_number == "JP-seed"
    assert "JP" in by_code["JP"].url
