"""BigQuery public dataset configurations."""

from dataclasses import dataclass


@dataclass(frozen=True)
class DatasetConfig:
    """Configuration for a BigQuery public dataset."""

    dataset_id: str
    description: str


FDA_DRUG_DATASET = DatasetConfig(
    dataset_id="bigquery-public-data.fda_drug",
    description="FDA Drug Labels - safety signals, competitive landscape",
)

PATENTS_DATASET = DatasetConfig(
    dataset_id="patents-public-data.patents",
    description="Google Patents - IP landscape, prior art, freedom-to-operate",
)

NIH_CITATIONS_DATASET = DatasetConfig(
    dataset_id="bigquery-public-data.nih_open_citation",
    description="NIH Open Citations - influence scoring, citation networks",
)
