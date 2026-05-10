"""BigQuery access for Ember Bio."""

from ember_data.bigquery.client import BigQueryClient
from ember_data.bigquery.datasets import (
    FDA_DRUG_DATASET,
    NIH_CITATIONS_DATASET,
    PATENTS_DATASET,
    DatasetConfig,
)
from ember_data.bigquery.result_schema import RUN_RESULTS_SCHEMA, RUN_SUMMARY_SCHEMA
from ember_data.bigquery.result_store import CachedRun, ResultReader, ResultWriter

__all__ = [
    "BigQueryClient",
    "CachedRun",
    "DatasetConfig",
    "FDA_DRUG_DATASET",
    "NIH_CITATIONS_DATASET",
    "PATENTS_DATASET",
    "RUN_RESULTS_SCHEMA",
    "RUN_SUMMARY_SCHEMA",
    "ResultReader",
    "ResultWriter",
]
