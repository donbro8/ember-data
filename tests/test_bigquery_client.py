"""Tests for BigQuery client and dataset configs."""

from datetime import date
from unittest.mock import MagicMock, patch

from ember_data.bigquery import BigQueryClient
from ember_data.bigquery.datasets import (
    FDA_DRUG_DATASET,
    NIH_CITATIONS_DATASET,
    PATENTS_DATASET,
)
from ember_data.bigquery.queries import fda_drug_events_query, patent_search_query
from ember_data.classification.spec import DateWindow


class TestDatasetConfig:
    def test_fda_drug_dataset(self):
        assert FDA_DRUG_DATASET.dataset_id == "bigquery-public-data.fda_drug"

    def test_patents_dataset(self):
        assert PATENTS_DATASET.dataset_id == "patents-public-data.patents"

    def test_nih_citations_dataset(self):
        assert (
            NIH_CITATIONS_DATASET.dataset_id == "bigquery-public-data.nih_open_citation"
        )


class TestFdaDrugEventsQuery:
    def test_single_drug_name(self):
        sql = fda_drug_events_query(["aspirin"])
        assert "aspirin" in sql
        assert "openfda_generic_name" in sql
        assert "openfda_brand_name" in sql

    def test_multiple_drug_names(self):
        sql = fda_drug_events_query(["aspirin", "ibuprofen"])
        assert "aspirin" in sql
        assert "ibuprofen" in sql
        # Multiple names should be ORed together
        assert sql.count("OR") >= 1

    def test_therapeutic_area_filter(self):
        sql = fda_drug_events_query(["aspirin"], therapeutic_area="analgesic")
        assert "analgesic" in sql
        assert "openfda_pharm_class_epc" in sql

    def test_no_drug_names_no_where(self):
        sql = fda_drug_events_query([])
        assert "WHERE" not in sql

    def test_limit_applied(self):
        sql = fda_drug_events_query(["aspirin"], limit=42)
        assert "42" in sql

    def test_sql_injection_prevention(self):
        sql = fda_drug_events_query(["drug'; DROP TABLE foo; --"])
        # Single quote must be escaped
        assert "\\'" in sql
        assert "DROP TABLE" in sql  # content present but quote escaped


class TestPatentSearchQuery:
    def test_basic_query(self):
        sql = patent_search_query("KRAS inhibitor")
        assert "KRAS inhibitor" in sql
        assert "publication_number" in sql
        assert "filing_date" in sql

    def test_includes_derived_expiry_columns(self):
        sql = patent_search_query("oncology")
        assert "derived_expiry" in sql
        assert "expiry_approximate" in sql
        assert "INTERVAL 20 YEAR" in sql

    def test_before_window(self):
        window = DateWindow.before(date(2025, 1, 1))
        sql = patent_search_query("kinase", date_window=window)
        assert "2025-01-01" in sql
        assert "<=" in sql
        # No start constraint
        assert ">= DATE '2025-01-01'" not in sql

    def test_after_window(self):
        window = DateWindow.after(date(2028, 6, 15))
        sql = patent_search_query("kinase", date_window=window)
        assert "2028-06-15" in sql
        assert ">=" in sql
        # No end constraint
        assert "<= DATE '2028-06-15'" not in sql

    def test_between_window(self):
        window = DateWindow.between(date(2026, 1, 1), date(2035, 12, 31))
        sql = patent_search_query("mAb", date_window=window)
        assert "2026-01-01" in sql
        assert "2035-12-31" in sql
        assert ">=" in sql
        assert "<=" in sql

    def test_not_yet_expired_window(self):
        today = date.today()
        window = DateWindow.not_yet_expired(as_of=today)
        sql = patent_search_query("biologics", date_window=window)
        assert today.isoformat() in sql
        assert ">=" in sql

    def test_single_jurisdiction_filter(self):
        sql = patent_search_query("inhibitor", jurisdictions=["US"])
        assert "country_code IN ('US')" in sql

    def test_multiple_jurisdiction_filter(self):
        sql = patent_search_query("inhibitor", jurisdictions=["US", "EU"])
        assert "country_code IN" in sql
        assert "'US'" in sql
        assert "'EP'" in sql  # EU maps to EP

    def test_wipo_jurisdiction_mapping(self):
        sql = patent_search_query("peptide", jurisdictions=["WIPO"])
        assert "'WO'" in sql

    def test_no_jurisdiction_no_country_filter(self):
        sql = patent_search_query("oncology")
        assert "country_code IN" not in sql

    def test_limit_applied(self):
        sql = patent_search_query("test", limit=25)
        assert "25" in sql

    def test_filing_date_guard(self):
        sql = patent_search_query("test")
        assert "p.filing_date > 0" in sql

    def test_combined_window_and_jurisdiction(self):
        window = DateWindow.after(date(2030, 1, 1))
        sql = patent_search_query("ADC", date_window=window, jurisdictions=["US", "JP"])
        assert "2030-01-01" in sql
        assert "'US'" in sql
        assert "'JP'" in sql


class TestBigQueryClient:
    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_initialization(self, mock_bq_class):
        client = BigQueryClient(project_id="test-project")
        assert client.project_id == "test-project"
        mock_bq_class.assert_called_once_with(project="test-project")

    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_query_fda_drug_events_single_name(self, mock_bq_class):
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
        results = client.query_fda_drug_events(["aspirin"], limit=10)

        mock_client.query.assert_called_once()
        query_arg = mock_client.query.call_args[0][0]
        assert "aspirin" in query_arg
        assert "10" in query_arg
        assert len(results) == 1
        assert results[0]["drug_name"] == "aspirin"

    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_query_fda_drug_events_with_therapeutic_area(self, mock_bq_class):
        mock_client = MagicMock()
        mock_bq_class.return_value = mock_client

        mock_job = MagicMock()
        mock_job.result.return_value = []
        mock_client.query.return_value = mock_job

        client = BigQueryClient(project_id="test-project")
        client.query_fda_drug_events(["ibuprofen"], therapeutic_area="anti-inflammatory")

        query_arg = mock_client.query.call_args[0][0]
        assert "ibuprofen" in query_arg
        assert "anti-inflammatory" in query_arg

    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_search_patents_basic(self, mock_bq_class):
        mock_client = MagicMock()
        mock_bq_class.return_value = mock_client

        mock_row = MagicMock()
        mock_row.items.return_value = [
            ("publication_number", "US-123-B2"),
            ("title", "KRAS inhibitor"),
            ("derived_expiry", "2035-01-01"),
            ("expiry_approximate", True),
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
        assert results[0]["expiry_approximate"] is True

    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_search_patents_with_date_window(self, mock_bq_class):
        mock_client = MagicMock()
        mock_bq_class.return_value = mock_client

        mock_job = MagicMock()
        mock_job.result.return_value = []
        mock_client.query.return_value = mock_job

        window = DateWindow.after(date(2030, 1, 1))
        client = BigQueryClient(project_id="test-project")
        client.search_patents("oncology", date_window=window)

        query_arg = mock_client.query.call_args[0][0]
        assert "2030-01-01" in query_arg
        assert "INTERVAL 20 YEAR" in query_arg

    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_search_patents_with_jurisdictions(self, mock_bq_class):
        mock_client = MagicMock()
        mock_bq_class.return_value = mock_client

        mock_job = MagicMock()
        mock_job.result.return_value = []
        mock_client.query.return_value = mock_job

        client = BigQueryClient(project_id="test-project")
        client.search_patents("antibody", jurisdictions=["US"])

        query_arg = mock_client.query.call_args[0][0]
        assert "country_code IN ('US')" in query_arg

    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_search_patents_expiry_provenance_in_results(self, mock_bq_class):
        mock_client = MagicMock()
        mock_bq_class.return_value = mock_client

        mock_row = MagicMock()
        mock_row.items.return_value = [
            ("publication_number", "US-999-A1"),
            ("derived_expiry", "2042-03-15"),
            ("expiry_approximate", True),
        ]
        mock_job = MagicMock()
        mock_job.result.return_value = [mock_row]
        mock_client.query.return_value = mock_job

        client = BigQueryClient(project_id="test-project")
        results = client.search_patents("gene therapy")

        assert results[0]["expiry_approximate"] is True
        assert results[0]["derived_expiry"] == "2042-03-15"

    @patch("ember_data.bigquery.client.bigquery.Client")
    def test_search_patents_not_yet_expired(self, mock_bq_class):
        mock_client = MagicMock()
        mock_bq_class.return_value = mock_client

        mock_job = MagicMock()
        mock_job.result.return_value = []
        mock_client.query.return_value = mock_job

        today = date.today()
        window = DateWindow.not_yet_expired(as_of=today)
        client = BigQueryClient(project_id="test-project")
        client.search_patents("RNA therapy", date_window=window)

        query_arg = mock_client.query.call_args[0][0]
        assert today.isoformat() in query_arg
        assert ">=" in query_arg
