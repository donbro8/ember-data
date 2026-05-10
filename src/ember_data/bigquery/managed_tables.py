"""Managed BigQuery table configurations for pre-computed patent and FDA drug label caches."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from google.cloud import bigquery

# ---------------------------------------------------------------------------
# Table identifier constant
# ---------------------------------------------------------------------------

PATENT_CACHE_TABLE = "patent_search_cache"

# ---------------------------------------------------------------------------
# Assignee sub-record fields
# ---------------------------------------------------------------------------

_ASSIGNEE_HARMONIZED_FIELDS = [
    bigquery.SchemaField("name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("country_code", "STRING", mode="NULLABLE"),
]

# ---------------------------------------------------------------------------
# PATENT_CACHE_SCHEMA
# Schema for the pre-flattened patent cache table.
# ---------------------------------------------------------------------------

PATENT_CACHE_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("publication_number", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("country_code", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("title", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("abstract", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("filing_date_parsed", "DATE", mode="NULLABLE"),
    bigquery.SchemaField("grant_date", "INT64", mode="NULLABLE"),
    bigquery.SchemaField("derived_expiry", "DATE", mode="NULLABLE"),
    bigquery.SchemaField(
        "assignee_harmonized",
        "RECORD",
        mode="REPEATED",
        fields=_ASSIGNEE_HARMONIZED_FIELDS,
    ),
]

# ---------------------------------------------------------------------------
# Refresh SQL
# ---------------------------------------------------------------------------


def patent_cache_refresh_sql(source_project: str) -> str:
    """Return the SQL used to refresh the patent_search_cache table.

    The query unnests localized title and abstract arrays, retaining only
    English-language rows, and pre-computes derived_expiry as filing date
    plus 20 years.  This refresh runs once per week at fixed cost; the
    resulting flat cache table avoids UNNEST at query time.

    Args:
        source_project: GCP project that hosts the patents public dataset
            (e.g. ``"patents-public-data"``).

    Returns:
        SQL string ready for submission to BigQuery.
    """
    return f"""SELECT
  p.publication_number,
  p.country_code,
  t.text AS title,
  a.text AS abstract,
  PARSE_DATE('%Y%m%d', CAST(p.filing_date AS STRING)) AS filing_date_parsed,
  p.grant_date,
  DATE_ADD(PARSE_DATE('%Y%m%d', CAST(p.filing_date AS STRING)), INTERVAL 20 YEAR) AS derived_expiry,
  p.assignee_harmonized
FROM `{source_project}.patents.publications` p,
     UNNEST(p.title_localized) AS t,
     UNNEST(p.abstract_localized) AS a
WHERE p.filing_date > 0
  AND t.language = 'en'
  AND a.language = 'en'"""


# ---------------------------------------------------------------------------
# ManagedTableConfig dataclass
# ---------------------------------------------------------------------------


@dataclass
class ManagedTableConfig:
    """Configuration for a managed BigQuery table with scheduled refresh.

    Attributes:
        table_id: Short table name within the destination dataset.
        schema: List of ``bigquery.SchemaField`` defining the table schema.
        refresh_sql_fn: Callable that accepts a source project string and
            returns the SQL used to populate the table on refresh.
        partition_field: Column to use for time-based partitioning, or
            ``None`` if the table is not partitioned.
        partition_type: Partition granularity, e.g. ``"DAY"`` or ``"MONTH"``.
            Ignored when ``partition_field`` is ``None``.
        cluster_fields: Ordered list of columns to use for clustering.
    """

    table_id: str
    schema: list[bigquery.SchemaField]
    refresh_sql_fn: Callable[[str], str]
    partition_field: str | None = None
    partition_type: str | None = None
    cluster_fields: list[str] = field(default_factory=list)


# ---------------------------------------------------------------------------
# PATENT_CACHE_CONFIG
# ---------------------------------------------------------------------------

PATENT_CACHE_CONFIG = ManagedTableConfig(
    table_id=PATENT_CACHE_TABLE,
    schema=PATENT_CACHE_SCHEMA,
    refresh_sql_fn=patent_cache_refresh_sql,
    partition_field="derived_expiry",
    partition_type="DAY",
    cluster_fields=["country_code"],
)

# ---------------------------------------------------------------------------
# FDA drug labels cache
# ---------------------------------------------------------------------------

FDA_CACHE_TABLE = "fda_drug_labels_cache"

FDA_CACHE_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("openfda_product_ndc", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("openfda_generic_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("openfda_brand_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("openfda_manufacturer_name", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("openfda_product_type", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("openfda_pharm_class_epc", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("openfda_pharm_class_cs", "STRING", mode="NULLABLE"),
]


def fda_cache_refresh_sql(source_project: str) -> str:
    """Return the SQL used to refresh the fda_drug_labels_cache table.

    Selects all OpenFDA label columns from the public FDA drug label dataset.
    Clustering on ``openfda_generic_name`` eliminates full-table LIKE scans at
    query time.

    Args:
        source_project: GCP project that hosts the FDA drug dataset
            (e.g. ``"bigquery-public-data"``).

    Returns:
        SQL string ready for submission to BigQuery.
    """
    return f"""SELECT
  openfda_product_ndc,
  openfda_generic_name,
  openfda_brand_name,
  openfda_manufacturer_name,
  openfda_product_type,
  openfda_pharm_class_epc,
  openfda_pharm_class_cs
FROM `{source_project}.fda_drug.drug_label`"""


FDA_CACHE_CONFIG = ManagedTableConfig(
    table_id=FDA_CACHE_TABLE,
    schema=FDA_CACHE_SCHEMA,
    refresh_sql_fn=fda_cache_refresh_sql,
    partition_field=None,
    partition_type=None,
    cluster_fields=["openfda_generic_name"],
)

# ---------------------------------------------------------------------------
# Biologic seed table
# ---------------------------------------------------------------------------

BIOLOGIC_SEED_TABLE = "biologic_seed"

BIOLOGIC_SEED_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("drug_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("brand_names", "STRING", mode="REPEATED"),
    bigquery.SchemaField("originator", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("target_antigen", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("modality", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("category", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("cell_line", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("cell_line_class", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("indications", "STRING", mode="REPEATED"),
    bigquery.SchemaField("annual_revenue_usd_millions", "FLOAT64", mode="NULLABLE"),
    bigquery.SchemaField("revenue_year", "INT64", mode="NULLABLE"),
    bigquery.SchemaField("patent_expiries_json", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("biosimilar_competitors", "STRING", mode="REPEATED"),
    bigquery.SchemaField("has_approved_biosimilar", "BOOL", mode="REQUIRED"),
    bigquery.SchemaField("last_updated", "DATE", mode="NULLABLE"),
    bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("data_version", "INT64", mode="REQUIRED"),
    bigquery.SchemaField("key_patent_numbers", "STRING", mode="REPEATED"),
]

# ---------------------------------------------------------------------------
# Enrichment log table
# ---------------------------------------------------------------------------

ENRICHMENT_LOG_TABLE = "enrichment_log"

ENRICHMENT_LOG_SCHEMA: list[bigquery.SchemaField] = [
    bigquery.SchemaField("run_id", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("timestamp", "TIMESTAMP", mode="REQUIRED"),
    bigquery.SchemaField("action", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("drug_name", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("field_changed", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("old_value", "STRING", mode="NULLABLE"),
    bigquery.SchemaField("new_value", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("source", "STRING", mode="REQUIRED"),
    bigquery.SchemaField("confidence", "STRING", mode="REQUIRED"),
]
