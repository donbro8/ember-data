"""Jurisdiction mapping utilities for patent publication numbers."""

from __future__ import annotations

PREFIX_TO_JURISDICTION: dict[str, str] = {
    "US": "US",
    "EP": "EU",
    "JP": "JP",
    "CN": "CN",
    "KR": "KR",
    "CA": "CA",
    "AU": "AU",
    "GB": "GB",
    "IN": "IN",
    "BR": "BR",
    "WO": "WIPO",
}


def extract_jurisdiction(publication_number: str) -> str | None:
    """Extract jurisdiction code from a patent publication number prefix.

    Args:
        publication_number: Patent publication number (e.g. "US-1234567", "EP9876543").

    Returns:
        Jurisdiction code (e.g. "US", "EU", "JP") or None if unrecognized.
    """
    if not publication_number:
        return None
    prefix = ""
    for ch in publication_number:
        if ch.isalpha() and ch.isupper():
            prefix += ch
            if len(prefix) == 2:
                break
        elif prefix:
            break
    return PREFIX_TO_JURISDICTION.get(prefix)
