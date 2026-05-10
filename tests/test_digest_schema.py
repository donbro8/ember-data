"""Tests for BigQuery digest schema definition."""

from ember_data.bigquery.digest_schema import DIGESTS_SCHEMA
from ember_data.bigquery import DIGESTS_SCHEMA as DIGESTS_SCHEMA_REEXPORT


class TestDigestsSchema:
    def _field_names(self, schema: list[dict]) -> set[str]:
        return {f["name"] for f in schema}

    def test_all_fields_present(self):
        names = self._field_names(DIGESTS_SCHEMA)
        assert "digest_id" in names
        assert "period_start" in names
        assert "period_end" in names
        assert "summary" in names
        assert "per_watch_json" in names
        assert "created_at" in names

    def test_digest_id_is_required_string(self):
        field = next(f for f in DIGESTS_SCHEMA if f["name"] == "digest_id")
        assert field["type"] == "STRING"
        assert field["mode"] == "REQUIRED"

    def test_period_start_is_required_date(self):
        field = next(f for f in DIGESTS_SCHEMA if f["name"] == "period_start")
        assert field["type"] == "DATE"
        assert field["mode"] == "REQUIRED"

    def test_period_end_is_required_date(self):
        field = next(f for f in DIGESTS_SCHEMA if f["name"] == "period_end")
        assert field["type"] == "DATE"
        assert field["mode"] == "REQUIRED"

    def test_summary_is_nullable_string(self):
        field = next(f for f in DIGESTS_SCHEMA if f["name"] == "summary")
        assert field["type"] == "STRING"
        assert field["mode"] == "NULLABLE"

    def test_per_watch_json_is_nullable_string(self):
        field = next(f for f in DIGESTS_SCHEMA if f["name"] == "per_watch_json")
        assert field["type"] == "STRING"
        assert field["mode"] == "NULLABLE"

    def test_created_at_is_required_timestamp(self):
        field = next(f for f in DIGESTS_SCHEMA if f["name"] == "created_at")
        assert field["type"] == "TIMESTAMP"
        assert field["mode"] == "REQUIRED"

    def test_exported_from_package(self):
        assert DIGESTS_SCHEMA_REEXPORT is DIGESTS_SCHEMA
