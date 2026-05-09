"""Tests for PatentJurisdiction model, JURISDICTION_NAMES, and build_patent_url."""

from datetime import date

import pytest

from ember_data.models.result import (
    JURISDICTION_NAMES,
    PatentJurisdiction,
    build_patent_url,
)


# ---------------------------------------------------------------------------
# build_patent_url
# ---------------------------------------------------------------------------


def test_build_patent_url_returns_google_patents_url():
    url = build_patent_url("US1234567A")
    assert url == "https://patents.google.com/patent/US1234567A"


def test_build_patent_url_ep():
    url = build_patent_url("EP3456789B1")
    assert url.startswith("https://patents.google.com/patent/")
    assert "EP3456789B1" in url


# ---------------------------------------------------------------------------
# JURISDICTION_NAMES
# ---------------------------------------------------------------------------


def test_jurisdiction_names_contains_all_required_codes():
    required = {"US", "EP", "JP", "CN", "KR", "CA", "AU", "GB", "IN", "BR"}
    assert required.issubset(JURISDICTION_NAMES.keys())


def test_jurisdiction_names_values():
    assert JURISDICTION_NAMES["US"] == "United States"
    assert JURISDICTION_NAMES["EP"] == "European Patent Office"
    assert JURISDICTION_NAMES["JP"] == "Japan"
    assert JURISDICTION_NAMES["CN"] == "China"
    assert JURISDICTION_NAMES["KR"] == "South Korea"
    assert JURISDICTION_NAMES["CA"] == "Canada"
    assert JURISDICTION_NAMES["AU"] == "Australia"
    assert JURISDICTION_NAMES["GB"] == "United Kingdom"
    assert JURISDICTION_NAMES["IN"] == "India"
    assert JURISDICTION_NAMES["BR"] == "Brazil"


# ---------------------------------------------------------------------------
# PatentJurisdiction model validation
# ---------------------------------------------------------------------------


def _make_jurisdiction(**overrides):
    defaults = {
        "country_code": "US",
        "country_name": "United States",
        "publication_number": "US1234567A",
        "status": "active",
        "url": build_patent_url("US1234567A"),
    }
    defaults.update(overrides)
    return PatentJurisdiction(**defaults)


def test_model_minimal_valid():
    pj = _make_jurisdiction()
    assert pj.country_code == "US"
    assert pj.country_name == "United States"
    assert pj.publication_number == "US1234567A"
    assert pj.status == "active"
    assert pj.filing_date is None
    assert pj.grant_date is None
    assert pj.expiry_date is None
    assert pj.expiry_date_approximate is False
    assert pj.title is None


def test_model_with_all_dates():
    pj = _make_jurisdiction(
        filing_date=date(2000, 1, 15),
        grant_date=date(2003, 6, 10),
        expiry_date=date(2020, 1, 15),
        expiry_date_approximate=True,
        title="A useful invention",
        status="expired",
    )
    assert pj.filing_date == date(2000, 1, 15)
    assert pj.grant_date == date(2003, 6, 10)
    assert pj.expiry_date == date(2020, 1, 15)
    assert pj.expiry_date_approximate is True
    assert pj.title == "A useful invention"
    assert pj.status == "expired"


def test_model_status_pending():
    pj = _make_jurisdiction(status="pending", grant_date=None)
    assert pj.status == "pending"


def test_model_invalid_status():
    with pytest.raises(Exception):
        _make_jurisdiction(status="unknown")


def test_model_url_field():
    url = build_patent_url("JP2021012345A")
    pj = _make_jurisdiction(
        country_code="JP",
        country_name="Japan",
        publication_number="JP2021012345A",
        url=url,
    )
    assert pj.url == "https://patents.google.com/patent/JP2021012345A"


# ---------------------------------------------------------------------------
# Status derivation (caller-computed; model stores the value)
# ---------------------------------------------------------------------------


def test_status_active_when_expiry_in_future():
    """Caller derives status; model stores it faithfully."""
    pj = _make_jurisdiction(
        expiry_date=date(2099, 1, 1),
        status="active",
    )
    assert pj.status == "active"


def test_status_expired_when_expiry_in_past():
    pj = _make_jurisdiction(
        expiry_date=date(2000, 1, 1),
        status="expired",
    )
    assert pj.status == "expired"


def test_expiry_date_approximate_defaults_false():
    pj = _make_jurisdiction()
    assert pj.expiry_date_approximate is False


def test_expiry_date_approximate_true_flag():
    pj = _make_jurisdiction(
        expiry_date=date(2024, 6, 1),
        expiry_date_approximate=True,
        status="expired",
    )
    assert pj.expiry_date_approximate is True
