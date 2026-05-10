"""Tests for BigQuery table schema definitions."""

from ember_data.bigquery.result_schema import RUN_RESULTS_SCHEMA, RUN_SUMMARY_SCHEMA


class TestRunResultsSchema:
    def _field_names(self, schema: list[dict]) -> set[str]:
        return {f["name"] for f in schema}

    def test_run_metadata_fields_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "run_id" in names
        assert "watch_id" in names
        assert "query" in names
        assert "query_type" in names
        assert "created_at" in names

    def test_candidate_result_core_fields_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "drug_name" in names
        assert "fda_generic_name" in names
        assert "target" in names
        assert "result_type" in names
        assert "canonical_id" in names
        assert "display_label" in names

    def test_scoring_fields_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "overall_score" in names
        assert "structured_score" in names
        assert "semantic_score" in names
        assert "evidence_score" in names

    def test_provenance_fields_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "sources_contributed" in names
        assert "source_urls" in names

    def test_enrichment_fields_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "indication" in names
        assert "mechanism_of_action" in names
        assert "clinical_stage" in names
        assert "risk_flags" in names
        assert "synthesis_summary" in names

    def test_identity_fields_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "brand_names" in names
        assert "originator" in names
        assert "target_aliases" in names
        assert "modality" in names
        assert "category" in names

    def test_commercial_fields_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "annual_revenue_usd_millions" in names
        assert "revenue_year" in names
        assert "biosimilar_competitors" in names
        assert "biosimilar_competitor_count" in names
        assert "has_approved_biosimilar" in names

    def test_fda_fields_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "fda_brand_name" in names
        assert "fda_manufacturer" in names
        assert "fda_therapeutic_area" in names

    def test_patent_evidence_fields_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "earliest_patent_expiry" in names
        assert "earliest_expiry_jurisdiction" in names

    def test_trial_aggregate_fields_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "trial_count" in names
        assert "latest_trial_phase" in names

    def test_article_aggregate_field_present(self):
        names = self._field_names(RUN_RESULTS_SCHEMA)
        assert "article_count" in names

    def test_patents_is_repeated_record(self):
        field = next(f for f in RUN_RESULTS_SCHEMA if f["name"] == "patents")
        assert field["type"] == "RECORD"
        assert field["mode"] == "REPEATED"
        sub_names = {sf["name"] for sf in field["fields"]}
        assert "country_code" in sub_names
        assert "publication_number" in sub_names
        assert "filing_date" in sub_names
        assert "grant_date" in sub_names
        assert "expiry_date" in sub_names
        assert "expiry_date_approximate" in sub_names
        assert "status" in sub_names
        assert "title" in sub_names
        assert "url" in sub_names

    def test_trials_is_repeated_record(self):
        field = next(f for f in RUN_RESULTS_SCHEMA if f["name"] == "trials")
        assert field["type"] == "RECORD"
        assert field["mode"] == "REPEATED"
        sub_names = {sf["name"] for sf in field["fields"]}
        assert "nct_id" in sub_names
        assert "phase" in sub_names
        assert "status" in sub_names
        assert "indication" in sub_names
        assert "sponsor" in sub_names
        assert "url" in sub_names

    def test_articles_is_repeated_record(self):
        field = next(f for f in RUN_RESULTS_SCHEMA if f["name"] == "articles")
        assert field["type"] == "RECORD"
        assert field["mode"] == "REPEATED"
        sub_names = {sf["name"] for sf in field["fields"]}
        assert "pmid" in sub_names
        assert "title" in sub_names
        assert "journal" in sub_names
        assert "year" in sub_names
        assert "doi" in sub_names
        assert "url" in sub_names

    def test_run_id_is_required(self):
        field = next(f for f in RUN_RESULTS_SCHEMA if f["name"] == "run_id")
        assert field["mode"] == "REQUIRED"

    def test_watch_id_is_nullable(self):
        field = next(f for f in RUN_RESULTS_SCHEMA if f["name"] == "watch_id")
        assert field["mode"] == "NULLABLE"

    def test_indication_is_repeated_string(self):
        field = next(f for f in RUN_RESULTS_SCHEMA if f["name"] == "indication")
        assert field["type"] == "STRING"
        assert field["mode"] == "REPEATED"


class TestRunSummarySchema:
    def _field_names(self, schema: list[dict]) -> set[str]:
        return {f["name"] for f in schema}

    def test_required_fields_present(self):
        names = self._field_names(RUN_SUMMARY_SCHEMA)
        assert "run_id" in names
        assert "query" in names
        assert "query_type" in names
        assert "watch_id" in names
        assert "full_markdown" in names
        assert "bytes_scanned" in names
        assert "execution_trace" in names
        assert "created_at" in names

    def test_run_id_is_required(self):
        field = next(f for f in RUN_SUMMARY_SCHEMA if f["name"] == "run_id")
        assert field["mode"] == "REQUIRED"

    def test_watch_id_is_nullable(self):
        field = next(f for f in RUN_SUMMARY_SCHEMA if f["name"] == "watch_id")
        assert field["mode"] == "NULLABLE"

    def test_bytes_scanned_is_int64(self):
        field = next(f for f in RUN_SUMMARY_SCHEMA if f["name"] == "bytes_scanned")
        assert field["type"] == "INT64"

    def test_execution_trace_is_string(self):
        field = next(f for f in RUN_SUMMARY_SCHEMA if f["name"] == "execution_trace")
        assert field["type"] == "STRING"

    def test_created_at_is_timestamp_required(self):
        field = next(f for f in RUN_SUMMARY_SCHEMA if f["name"] == "created_at")
        assert field["type"] == "TIMESTAMP"
        assert field["mode"] == "REQUIRED"
