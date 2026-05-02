"""SQL query builders for BigQuery public datasets."""

from ember_data.bigquery.datasets import FDA_DRUG_DATASET, PATENTS_DATASET


def fda_drug_events_query(drug_name: str, limit: int = 100) -> str:
    """Build a query for FDA drug adverse event reports.

    Args:
        drug_name: The drug name to search for.
        limit: Maximum number of results.

    Returns:
        SQL query string.
    """
    safe_name = drug_name.replace("'", "\\'")
    return f"""
SELECT
    openfda_product_ndc,
    openfda_generic_name,
    openfda_brand_name,
    openfda_manufacturer_name,
    openfda_product_type
FROM `{FDA_DRUG_DATASET.dataset_id}.drug_label`
WHERE LOWER(openfda_generic_name) LIKE LOWER('%{safe_name}%')
   OR LOWER(openfda_brand_name) LIKE LOWER('%{safe_name}%')
LIMIT {limit}
""".strip()


def patent_search_query(query: str, limit: int = 100) -> str:
    """Build a query for Google Patents public dataset.

    Args:
        query: Search terms for patent title/abstract.
        limit: Maximum number of results.

    Returns:
        SQL query string.
    """
    safe_query = query.replace("'", "\\'")
    return f"""
SELECT
    p.publication_number,
    t.text AS title,
    a.text AS abstract,
    p.filing_date,
    p.grant_date
FROM `{PATENTS_DATASET.dataset_id}.publications` p,
     UNNEST(p.title_localized) AS t,
     UNNEST(p.abstract_localized) AS a
WHERE t.language = 'en'
  AND a.language = 'en'
  AND (LOWER(t.text) LIKE LOWER('%{safe_query}%')
       OR LOWER(a.text) LIKE LOWER('%{safe_query}%'))
ORDER BY p.filing_date DESC
LIMIT {limit}
""".strip()
