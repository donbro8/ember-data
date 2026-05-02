"""Tests for BigQuery client and dataset configs."""

from unittest.mock import MagicMock, patch


from ember_data.bigquery import BigQueryClient
from ember_data.bigquery.datasets import (
    FDA_DRUG_DATASET,
    NIH_CITATIONS_DATASET,
    PATENTS_DATASET,
)


class TestDatasetConfig:
    def test_fda_drug_dataset(self):
        assert FDA_DRUG_DATASET.dataset_id == "bigquery-public-data.fda_drug"

    def test_patents_dataset(self):
        assert PATENTS_DATASET.dataset_id == "patents-public-data.patents"

    def test_nih_citations_dataset(self):
        assert (
            NIH_CITATIONS_DATASET.dataset_id == "bigquery-public-data.nih_open_citation"
        )


class TestBigQueryClient:
    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_initialization(self, mock_bq_class):
        client = BigQueryClient(project_id="test-project")
        assert client.project_id == "test-project"
        mock_bq_class.assert_called_once_with(project="test-project")

    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_query_fda_drug_events(self, mock_bq_class):
        mock_client = MagicMock()
        mock_bq_class.return_value = mock_client

        mock_row = MagicMock()
        mock_row.items.return_value = [
            ("drug_name", "aspirin"),
            ("event_count", 42),
        ]
        mock_job = MagicMock()
        mock_job.result.return_value = [mock_row]
        mock_client.query.return_value = mock_job

        client = BigQueryClient(project_id="test-project")
        results = client.query_fda_drug_events("aspirin", limit=10)

        mock_client.query.assert_called_once()
        query_arg = mock_client.query.call_args[0][0]
        assert "aspirin" in query_arg
        assert "10" in query_arg
        assert len(results) == 1
        assert results[0]["drug_name"] == "aspirin"

    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_search_patents(self, mock_bq_class):
        mock_client = MagicMock()
        mock_bq_class.return_value = mock_client

        mock_row = MagicMock()
        mock_row.items.return_value = [
            ("publication_number", "US-123-B2"),
            ("title", "KRAS inhibitor"),
        ]
        mock_job = MagicMock()
        mock_job.result.return_value = [mock_row]
        mock_client.query.return_value = mock_job

        client = BigQueryClient(project_id="test-project")
        results = client.search_patents("KRAS inhibitor", limit=5)

        mock_client.query.assert_called_once()
        query_arg = mock_client.query.call_args[0][0]
        assert "KRAS inhibitor" in query_arg
        assert "5" in query_arg
        assert len(results) == 1
        assert results[0]["publication_number"] == "US-123-B2"
