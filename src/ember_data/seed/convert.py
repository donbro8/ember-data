"""Conversion utilities for biologic seed entries."""

from __future__ import annotations

from datetime import date

from ember_data.models.result import (
    JURISDICTION_NAMES,
    PatentJurisdiction,
    build_patent_url,
)
from ember_data.seed.schema import BiologicEntry


def _derive_status(expiry_date: date | None) -> str:
    """Derive patent status from expiry date relative to today."""
    if expiry_date is None:
        return "pending"
    today = date.today()
    return "active" if expiry_date > today else "expired"


def _find_patent_number(country_code: str, key_patent_numbers: list[str]) -> str | None:
    """Return first patent number whose prefix matches the country code, or None."""
    for pn in key_patent_numbers:
        if pn.upper().startswith(country_code.upper()):
            return pn
    return None


def seed_entry_to_patent_jurisdictions(entry: BiologicEntry) -> list[PatentJurisdiction]:
    """Convert a BiologicEntry into a list of PatentJurisdiction objects.

    One PatentJurisdiction is created per entry in ``patent_expiries``.
    ``expiry_date_approximate`` is always ``False`` for seed data (manually
    researched).  Status is derived by comparing the expiry date to today.
    A non-empty URL is always populated: a specific Google Patents URL when a
    matching key patent number is found, or a Google Patents search URL
    otherwise.
    """
    jurisdictions: list[PatentJurisdiction] = []

    for country_code, expiry_date in entry.patent_expiries.items():
        matched_pn = _find_patent_number(country_code, entry.key_patent_numbers)

        if matched_pn:
            publication_number = matched_pn
            url = build_patent_url(matched_pn)
        else:
            publication_number = f"{country_code}-seed"
            drug_name_encoded = entry.drug_name.replace(" ", "+")
            url = (
                f"https://patents.google.com/?q={drug_name_encoded}"
                f"&country={country_code}"
            )

        country_name = JURISDICTION_NAMES.get(country_code, country_code)
        status = _derive_status(expiry_date)

        jurisdictions.append(
            PatentJurisdiction(
                country_code=country_code,
                country_name=country_name,
                publication_number=publication_number,
                expiry_date=expiry_date,
                expiry_date_approximate=False,
                status=status,
                url=url,
            )
        )

    return jurisdictions
