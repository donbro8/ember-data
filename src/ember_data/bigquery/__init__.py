"""BigQuery access for Ember Bio."""

from ember_data.bigquery.client import BigQueryClient
from ember_data.bigquery.datasets import (
    FDA_DRUG_DATASET,
    NIH_CITATIONS_DATASET,
    PATENTS_DATASET,
    DatasetConfig,
)

__all__ = [
    "BigQueryClient",
    "DatasetConfig",
    "FDA_DRUG_DATASET",
    "NIH_CITATIONS_DATASET",
    "PATENTS_DATASET",
]
