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
    return f"""
SELECT
    openfda_generic_name,
    openfda_brand_name,
    serious,
    receivedate,
    patient_drug_indication
FROM `{FDA_DRUG_DATASET.dataset_id}.drug_label`
WHERE LOWER(openfda_generic_name) LIKE LOWER('%{drug_name}%')
   OR LOWER(openfda_brand_name) LIKE LOWER('%{drug_name}%')
ORDER BY receivedate DESC
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
    return f"""
SELECT
    publication_number,
    title_localized,
    abstract_localized,
    assignee_harmonized,
    filing_date,
    grant_date,
    citation
FROM `{PATENTS_DATASET.dataset_id}.publications`
WHERE LOWER(title_localized.text) LIKE LOWER('%{query}%')
   OR LOWER(abstract_localized.text) LIKE LOWER('%{query}%')
ORDER BY filing_date DESC
LIMIT {limit}
""".strip()
