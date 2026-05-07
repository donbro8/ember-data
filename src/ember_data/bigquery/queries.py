"""SQL query builders for BigQuery public datasets."""

from __future__ import annotations

from ember_data.bigquery.datasets import FDA_DRUG_DATASET, PATENTS_DATASET

# Map SearchSpec Jurisdiction enum values to BigQuery country codes.
_JURISDICTION_TO_COUNTRY_CODE: dict[str, str] = {
    "US": "US",
    "EU": "EP",
    "JP": "JP",
    "CN": "CN",
    "CA": "CA",
    "AU": "AU",
    "GB": "GB",
    "IN": "IN",
    "BR": "BR",
    "KR": "KR",
    "WIPO": "WO",
}

# BigQuery SQL expression for derived patent expiry (US utility: filing + 20 years).
# filing_date is stored as INT64 in YYYYMMDD format in the patents public dataset.
_DERIVED_EXPIRY_EXPR = (
    "DATE_ADD("
    "PARSE_DATE('%Y%m%d', CAST(p.filing_date AS STRING)), "
    "INTERVAL 20 YEAR)"
)


def _enum_value(value: object) -> str:
    """Return enum values as strings while preserving plain strings."""
    return str(getattr(value, "value", value))


def fda_drug_events_query(
    drug_names: list[str] | str,
    therapeutic_area: object | None = None,
    limit: int = 100,
) -> str:
    """Build a query for FDA drug label records.

    Args:
        drug_names: Drug names to search for (matched against generic and brand name).
        therapeutic_area: Optional therapeutic area filter matched against pharm class fields.
        limit: Maximum number of results.

    Returns:
        SQL query string.
    """
    where_parts: list[str] = []

    if isinstance(drug_names, str):
        normalized_drug_names = [drug_names]
    else:
        normalized_drug_names = drug_names

    if normalized_drug_names:
        name_clauses = []
        for name in normalized_drug_names:
            safe = name.replace("'", "\\'")
            name_clauses.append(
                f"(LOWER(openfda_generic_name) LIKE LOWER('%{safe}%')"
                f" OR LOWER(openfda_brand_name) LIKE LOWER('%{safe}%'))"
            )
        where_parts.append(f"({' OR '.join(name_clauses)})")

    if therapeutic_area is not None:
        safe_ta = _enum_value(therapeutic_area).replace("'", "\\'")
        where_parts.append(
            f"(LOWER(openfda_pharm_class_epc) LIKE LOWER('%{safe_ta}%')"
            f" OR LOWER(openfda_pharm_class_cs) LIKE LOWER('%{safe_ta}%'))"
        )

    where_clause = f"WHERE {' AND '.join(where_parts)}" if where_parts else ""

    return f"""SELECT
    openfda_product_ndc,
    openfda_generic_name,
    openfda_brand_name,
    openfda_manufacturer_name,
    openfda_product_type
FROM `{FDA_DRUG_DATASET.dataset_id}.drug_label`
{where_clause}
LIMIT {limit}""".strip()


def patent_search_query(
    query: str,
    limit: int = 100,
    date_window: object | None = None,
    jurisdictions: list[str] | None = None,
) -> str:
    """Build a query for Google Patents public dataset.

    Patent expiry is derived as US utility filing date + 20 years when
    authoritative term-adjustment data is unavailable.  Every result row
    includes ``derived_expiry`` and ``expiry_approximate = TRUE`` to flag
    this provenance.

    Args:
        query: Search terms for patent title/abstract.
        limit: Maximum number of results.
        date_window: Optional DateWindow applied to the derived expiry date.
            ``not_yet_expired`` windows use the execution date as the start.
        jurisdictions: Optional list of Jurisdiction enum values or strings (e.g. ``["US"]``).
            Rows are filtered to matching country codes at query time.

    Returns:
        SQL query string.
    """
    safe_query = query.replace("'", "\\'")

    where_parts: list[str] = [
        "t.language = 'en'",
        "a.language = 'en'",
        "p.filing_date > 0",
        f"(LOWER(t.text) LIKE LOWER('%{safe_query}%')"
        f" OR LOWER(a.text) LIKE LOWER('%{safe_query}%'))",
    ]

    if jurisdictions:
        normalized_jurisdictions = [_enum_value(j) for j in jurisdictions]
        codes = [
            _JURISDICTION_TO_COUNTRY_CODE.get(j, j)
            for j in normalized_jurisdictions
        ]
        code_list = ", ".join(f"'{c}'" for c in codes)
        where_parts.append(f"p.country_code IN ({code_list})")

    if date_window is not None:
        start = getattr(date_window, "start", None)
        end = getattr(date_window, "end", None)
        if start is not None:
            where_parts.append(
                f"{_DERIVED_EXPIRY_EXPR} >= DATE '{start.isoformat()}'"
            )
        if end is not None:
            where_parts.append(
                f"{_DERIVED_EXPIRY_EXPR} <= DATE '{end.isoformat()}'"
            )

    where_clause = "WHERE " + "\n  AND ".join(where_parts)

    return f"""SELECT
    p.publication_number,
    t.text AS title,
    a.text AS abstract,
    p.filing_date,
    p.grant_date,
    p.country_code,
    {_DERIVED_EXPIRY_EXPR} AS derived_expiry,
    TRUE AS expiry_approximate
FROM `{PATENTS_DATASET.dataset_id}.publications` p,
     UNNEST(p.title_localized) AS t,
     UNNEST(p.abstract_localized) AS a
{where_clause}
ORDER BY p.filing_date DESC
LIMIT {limit}""".strip()
