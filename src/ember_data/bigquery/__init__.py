"""BigQuery access for Ember Bio."""

from ember_data.bigquery.client import BigQueryClient
from ember_data.bigquery.change_detector import ChangeDetector, ChangeEntry
from ember_data.bigquery.datasets import (
    FDA_DRUG_DATASET,
    NIH_CITATIONS_DATASET,
    PATENTS_DATASET,
    DatasetConfig,
)
from ember_data.bigquery.result_schema import RUN_RESULTS_SCHEMA, RUN_SUMMARY_SCHEMA
from ember_data.bigquery.result_store import CachedRun, ResultReader, ResultWriter
from ember_data.bigquery.watch_schema import (
    CHANGE_LOG_SCHEMA,
    WATCH_CONFIGS_SCHEMA,
    ChangeType,
    WatchConfig,
)
from ember_data.bigquery.watch_store import WatchStore

__all__ = [
    "BigQueryClient",
    "CHANGE_LOG_SCHEMA",
    "CachedRun",
    "ChangeDetector",
    "ChangeEntry",
    "ChangeType",
    "DatasetConfig",
    "FDA_DRUG_DATASET",
    "NIH_CITATIONS_DATASET",
    "PATENTS_DATASET",
    "RUN_RESULTS_SCHEMA",
    "RUN_SUMMARY_SCHEMA",
    "ResultReader",
    "ResultWriter",
    "WATCH_CONFIGS_SCHEMA",
    "WatchConfig",
    "WatchStore",
]
