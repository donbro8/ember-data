"""Tests for ResultWriter, ResultReader, and CachedRun."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from unittest.mock import MagicMock

from ember_data.bigquery.result_store import CachedRun, ResultReader, ResultWriter
from ember_data.models.result import CandidateResult


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_client(**kwargs) -> MagicMock:
    """Return a mock BigQueryClient."""
    client = MagicMock()
    for attr, val in kwargs.items():
        setattr(client, attr, val)
    return client


def _make_result(**kwargs) -> CandidateResult:
    defaults = {"drug_name": "Humira", "fda_generic_name": "adalimumab"}
    defaults.update(kwargs)
    return CandidateResult(**defaults)


# ---------------------------------------------------------------------------
# CachedRun
# ---------------------------------------------------------------------------


class TestCachedRun:
    def test_fields_accessible(self):
        now = datetime.now(tz=timezone.utc)
        cr = CachedRun(
            run_id="r1",
            markdown="# Report",
            results=[],
            created_at=now,
            query_type="drug",
        )
        assert cr.run_id == "r1"
        assert cr.markdown == "# Report"
        assert cr.results == []
        assert cr.created_at == now
        assert cr.query_type == "drug"

    def test_change_summary_defaults_to_none(self):
        now = datetime.now(tz=timezone.utc)
        cr = CachedRun(
            run_id="r1",
            markdown="",
            results=[],
            created_at=now,
            query_type="drug",
        )
        assert cr.change_summary is None

    def test_change_summary_accepted(self):
        now = datetime.now(tz=timezone.utc)
        cr = CachedRun(
            run_id="r1",
            markdown="",
            results=[],
            created_at=now,
            query_type="drug",
            change_summary="New biosimilar detected",
        )
        assert cr.change_summary == "New biosimilar detected"


# ---------------------------------------------------------------------------
# ResultWriter
# ---------------------------------------------------------------------------


class TestResultWriter:
    def test_write_run_calls_insert_rows_for_results(self):
        client = _make_client()
        writer = ResultWriter(client, "my_dataset")
        results = [_make_result(), _make_result(drug_name="Keytruda", fda_generic_name="pembrolizumab")]

        writer.write_run(
            run_id="run-001",
            query="adalimumab",
            query_type="drug",
            results=results,
            trace={"step": "done"},
            markdown="# Report",
        )

        # insert_rows should be called twice: once for results, once for summary
        assert client.insert_rows.call_count == 2

    def test_write_run_result_rows_contain_metadata(self):
        client = _make_client()
        writer = ResultWriter(client, "my_dataset")
        result = _make_result()

        writer.write_run(
            run_id="run-002",
            query="humira",
            query_type="drug",
            results=[result],
            trace=None,
            markdown="report",
            watch_id="watch-1",
            bytes_scanned=500_000,
        )

        # First call is for result_rows
        result_rows_call = client.insert_rows.call_args_list[0]
        _table, rows = result_rows_call[0]
        assert len(rows) == 1
        row = rows[0]
        assert row["run_id"] == "run-002"
        assert row["query"] == "humira"
        assert row["query_type"] == "drug"
        assert row["watch_id"] == "watch-1"
        assert "created_at" in row

    def test_write_run_summary_row_structure(self):
        client = _make_client()
        writer = ResultWriter(client, "my_dataset")

        writer.write_run(
            run_id="run-003",
            query="trastuzumab",
            query_type="drug",
            results=[],
            trace={"a": 1},
            markdown="# Markdown",
            bytes_scanned=12345,
        )

        # Second call (or first if no results) is for summary
        summary_call = client.insert_rows.call_args_list[-1]
        _table, rows = summary_call[0]
        assert len(rows) == 1
        summary = rows[0]
        assert summary["run_id"] == "run-003"
        assert summary["full_markdown"] == "# Markdown"
        assert summary["bytes_scanned"] == 12345
        assert summary["execution_trace"] == json.dumps({"a": 1})

    def test_write_run_no_results_still_inserts_summary(self):
        client = _make_client()
        writer = ResultWriter(client, "ds")

        writer.write_run(
            run_id="run-004",
            query="q",
            query_type="t",
            results=[],
            trace=None,
            markdown="",
        )

        # Only summary insert (no result rows)
        assert client.insert_rows.call_count == 1

    def test_write_run_trace_none_serializes_to_none(self):
        client = _make_client()
        writer = ResultWriter(client, "ds")

        writer.write_run(
            run_id="run-005",
            query="q",
            query_type="t",
            results=[],
            trace=None,
            markdown="",
        )

        summary_call = client.insert_rows.call_args_list[-1]
        _table, rows = summary_call[0]
        assert rows[0]["execution_trace"] is None

    def test_write_run_includes_change_summary_in_summary_row(self):
        client = _make_client()
        writer = ResultWriter(client, "my_dataset")

        writer.write_run(
            run_id="run-cs",
            query="adalimumab",
            query_type="drug",
            results=[],
            trace=None,
            markdown="# Report",
            change_summary="New biosimilar approved",
        )

        summary_call = client.insert_rows.call_args_list[-1]
        _table, rows = summary_call[0]
        assert rows[0]["change_summary"] == "New biosimilar approved"

    def test_write_run_change_summary_defaults_to_none(self):
        client = _make_client()
        writer = ResultWriter(client, "my_dataset")

        writer.write_run(
            run_id="run-no-cs",
            query="adalimumab",
            query_type="drug",
            results=[],
            trace=None,
            markdown="# Report",
        )

        summary_call = client.insert_rows.call_args_list[-1]
        _table, rows = summary_call[0]
        assert rows[0]["change_summary"] is None

    def test_update_summary_calls_query_with_params(self):
        client = _make_client()
        writer = ResultWriter(client, "my_dataset")

        writer.update_summary("run-42", "Two new competitors found")

        client.query_with_params.assert_called_once()
        sql, params = client.query_with_params.call_args[0]
        assert "change_summary" in sql
        assert params["run_id"] == "run-42"
        assert params["change_summary"] == "Two new competitors found"

    def test_write_run_result_uses_model_dump(self):
        """Rows built from model_dump should not include raw Pydantic model instances."""
        client = _make_client()
        writer = ResultWriter(client, "ds")
        result = _make_result(
            indication=["RA", "Crohn's"],
            sources_contributed=["pubmed"],
        )

        writer.write_run(
            run_id="run-006",
            query="humira",
            query_type="drug",
            results=[result],
            trace=None,
            markdown="",
        )

        result_rows_call = client.insert_rows.call_args_list[0]
        _table, rows = result_rows_call[0]
        row = rows[0]
        # indication should be a plain list of strings
        assert isinstance(row["indication"], list)
        assert "RA" in row["indication"]


# ---------------------------------------------------------------------------
# ResultReader
# ---------------------------------------------------------------------------


class TestResultReader:
    def test_get_cached_returns_none_when_no_rows(self):
        client = _make_client()
        client.query_with_params.return_value = []
        reader = ResultReader(client, "ds")

        result = reader.get_cached("some query")
        assert result is None

    def test_get_cached_returns_cached_run(self):
        now = datetime.now(tz=timezone.utc)
        client = _make_client()
        client.query_with_params.side_effect = [
            # First call: summary lookup
            [
                {
                    "run_id": "run-100",
                    "full_markdown": "# Report",
                    "created_at": now,
                    "query_type": "drug",
                }
            ],
            # Second call: get_run rows
            [],
        ]
        reader = ResultReader(client, "ds")

        cached = reader.get_cached("humira")
        assert cached is not None
        assert cached.run_id == "run-100"
        assert cached.markdown == "# Report"
        assert cached.query_type == "drug"

    def test_get_cached_returns_change_summary(self):
        now = datetime.now(tz=timezone.utc)
        client = _make_client()
        client.query_with_params.side_effect = [
            [
                {
                    "run_id": "run-cs",
                    "full_markdown": "# Report",
                    "created_at": now,
                    "query_type": "drug",
                    "change_summary": "New competitor launched",
                }
            ],
            [],
        ]
        reader = ResultReader(client, "ds")

        cached = reader.get_cached("humira")
        assert cached is not None
        assert cached.change_summary == "New competitor launched"

    def test_get_cached_normalizes_query(self):
        """Ensures query is lowercased and stripped before lookup."""
        client = _make_client()
        client.query_with_params.return_value = []
        reader = ResultReader(client, "ds")

        reader.get_cached("  HUMIRA  ")

        call_args = client.query_with_params.call_args
        params = call_args[0][1]
        assert params["query_normalized"] == "humira"

    def test_get_run_returns_candidate_results(self):
        client = _make_client()
        # Return a minimal valid CandidateResult row
        client.query_with_params.return_value = [
            {
                "drug_name": "adalimumab",
                "fda_generic_name": None,
                "target": None,
                "result_type": "DRUG",
                "canonical_id": "fda:adalimumab",
                "display_label": "adalimumab",
                "patents": [],
                "earliest_patent_expiry": None,
                "earliest_expiry_jurisdiction": None,
                "overall_score": None,
                "sources_contributed": [],
                "source_urls": [],
                "indication": [],
                "mechanism_of_action": None,
                "clinical_stage": None,
                "risk_flags": [],
                "synthesis_summary": None,
                "structured_score": None,
                "semantic_score": None,
                "evidence_score": None,
                "brand_names": [],
                "originator": None,
                "target_aliases": [],
                "modality": None,
                "category": None,
                "trials": [],
                "trial_count": 0,
                "latest_trial_phase": None,
                "articles": [],
                "article_count": 0,
                "annual_revenue_usd_millions": None,
                "revenue_year": None,
                "biosimilar_competitors": [],
                "biosimilar_competitor_count": 0,
                "has_approved_biosimilar": False,
                "fda_brand_name": None,
                "fda_manufacturer": None,
                "fda_therapeutic_area": None,
            }
        ]
        reader = ResultReader(client, "ds")

        results = reader.get_run("run-200")
        assert len(results) == 1
        assert isinstance(results[0], CandidateResult)
        assert results[0].drug_name == "adalimumab"

    def test_get_run_strips_run_metadata_keys(self):
        """run_id, watch_id, query, query_type, created_at must not be passed to CandidateResult."""
        client = _make_client()
        client.query_with_params.return_value = [
            {
                "run_id": "run-300",
                "watch_id": "w1",
                "query": "adalimumab",
                "query_type": "drug",
                "created_at": "2026-01-01T00:00:00Z",
                "drug_name": "adalimumab",
                "fda_generic_name": None,
                "target": None,
                "patents": [],
                "sources_contributed": [],
                "source_urls": [],
                "indication": [],
                "risk_flags": [],
                "brand_names": [],
                "target_aliases": [],
                "biosimilar_competitors": [],
                "trials": [],
                "articles": [],
            }
        ]
        reader = ResultReader(client, "ds")
        # Should not raise a validation error about unexpected keys
        results = reader.get_run("run-300")
        assert len(results) == 1

    def test_list_runs_no_filter(self):
        client = _make_client()
        client.query_with_params.return_value = [
            {"run_id": "r1", "query": "q", "query_type": "drug", "watch_id": None,
             "created_at": "2026-01-01", "bytes_scanned": 100},
        ]
        reader = ResultReader(client, "ds")

        runs = reader.list_runs()
        assert len(runs) == 1
        assert runs[0]["run_id"] == "r1"

    def test_list_runs_with_watch_id_filter(self):
        client = _make_client()
        client.query_with_params.return_value = []
        reader = ResultReader(client, "ds")

        reader.list_runs(watch_id="watch-abc")

        call_args = client.query_with_params.call_args
        sql = call_args[0][0]
        params = call_args[0][1]
        assert "watch_id" in sql
        assert params.get("watch_id") == "watch-abc"

    def test_list_runs_limit_respected(self):
        client = _make_client()
        client.query_with_params.return_value = []
        reader = ResultReader(client, "ds")

        reader.list_runs(limit=5)

        call_args = client.query_with_params.call_args
        sql = call_args[0][0]
        assert "5" in sql
