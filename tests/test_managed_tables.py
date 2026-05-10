"""Tests for managed BigQuery table definitions (patent_search_cache and fda_drug_labels_cache)."""

from __future__ import annotations

from ember_data.bigquery.managed_tables import (
    FDA_CACHE_CONFIG,
    FDA_CACHE_SCHEMA,
    FDA_CACHE_TABLE,
    PATENT_CACHE_CONFIG,
    PATENT_CACHE_SCHEMA,
    PATENT_CACHE_TABLE,
    fda_cache_refresh_sql,
    patent_cache_refresh_sql,
)


class TestPatentCacheTableConstant:
    def test_table_id_value(self):
        assert PATENT_CACHE_TABLE == "patent_search_cache"


class TestPatentCacheSchema:
    def _field_names(self) -> set[str]:
        return {f.name for f in PATENT_CACHE_SCHEMA}

    def test_expected_field_names_present(self):
        names = self._field_names()
        assert "publication_number" in names
        assert "country_code" in names
        assert "title" in names
        assert "abstract" in names
        assert "filing_date_parsed" in names
        assert "grant_date" in names
        assert "derived_expiry" in names
        assert "assignee_harmonized" in names

    def test_publication_number_is_string(self):
        field = next(f for f in PATENT_CACHE_SCHEMA if f.name == "publication_number")
        assert field.field_type == "STRING"

    def test_filing_date_parsed_is_date(self):
        field = next(f for f in PATENT_CACHE_SCHEMA if f.name == "filing_date_parsed")
        assert field.field_type == "DATE"

    def test_grant_date_is_int64(self):
        field = next(f for f in PATENT_CACHE_SCHEMA if f.name == "grant_date")
        assert field.field_type == "INT64"

    def test_derived_expiry_is_date(self):
        field = next(f for f in PATENT_CACHE_SCHEMA if f.name == "derived_expiry")
        assert field.field_type == "DATE"

    def test_assignee_harmonized_is_repeated_record(self):
        field = next(f for f in PATENT_CACHE_SCHEMA if f.name == "assignee_harmonized")
        assert field.field_type == "RECORD"
        assert field.mode == "REPEATED"

    def test_assignee_harmonized_has_expected_sub_fields(self):
        field = next(f for f in PATENT_CACHE_SCHEMA if f.name == "assignee_harmonized")
        sub_names = {sf.name for sf in field.fields}
        assert "name" in sub_names
        assert "country_code" in sub_names

    def test_assignee_harmonized_sub_fields_are_string(self):
        field = next(f for f in PATENT_CACHE_SCHEMA if f.name == "assignee_harmonized")
        for sub in field.fields:
            assert sub.field_type == "STRING", (
                f"Expected STRING for sub-field {sub.name}, got {sub.field_type}"
            )


class TestPatentCacheRefreshSql:
    _SOURCE_PROJECT = "patents-public-data"

    def _sql(self) -> str:
        return patent_cache_refresh_sql(self._SOURCE_PROJECT)

    def test_sql_contains_correct_table_reference(self):
        assert "`patents-public-data.patents.publications`" in self._sql()

    def test_sql_filters_english_title(self):
        assert "t.language = 'en'" in self._sql()

    def test_sql_filters_english_abstract(self):
        assert "a.language = 'en'" in self._sql()

    def test_sql_filters_positive_filing_date(self):
        assert "filing_date > 0" in self._sql()

    def test_sql_contains_derived_expiry_expression(self):
        sql = self._sql()
        assert "INTERVAL 20 YEAR" in sql
        assert "DATE_ADD" in sql

    def test_sql_selects_publication_number(self):
        assert "p.publication_number" in self._sql()

    def test_sql_selects_assignee_harmonized(self):
        assert "p.assignee_harmonized" in self._sql()

    def test_sql_source_project_is_interpolated(self):
        sql = patent_cache_refresh_sql("my-gcp-project")
        assert "`my-gcp-project.patents.publications`" in sql


class TestPatentCacheConfig:
    def test_table_id(self):
        assert PATENT_CACHE_CONFIG.table_id == "patent_search_cache"

    def test_partition_field(self):
        assert PATENT_CACHE_CONFIG.partition_field == "derived_expiry"

    def test_cluster_fields(self):
        assert PATENT_CACHE_CONFIG.cluster_fields == ["country_code"]

    def test_schema_is_set(self):
        assert PATENT_CACHE_CONFIG.schema is PATENT_CACHE_SCHEMA

    def test_refresh_sql_fn_is_callable(self):
        assert callable(PATENT_CACHE_CONFIG.refresh_sql_fn)

    def test_refresh_sql_fn_returns_string(self):
        sql = PATENT_CACHE_CONFIG.refresh_sql_fn("patents-public-data")
        assert isinstance(sql, str)
        assert len(sql) > 0

    def test_partition_type_is_set(self):
        assert PATENT_CACHE_CONFIG.partition_type is not None


# ---------------------------------------------------------------------------
# FDA drug labels cache tests
# ---------------------------------------------------------------------------

_FDA_EXPECTED_FIELDS = [
    "openfda_product_ndc",
    "openfda_generic_name",
    "openfda_brand_name",
    "openfda_manufacturer_name",
    "openfda_product_type",
    "openfda_pharm_class_epc",
    "openfda_pharm_class_cs",
]


class TestFdaCacheTableConstant:
    def test_table_id_value(self):
        assert FDA_CACHE_TABLE == "fda_drug_labels_cache"


class TestFdaCacheSchema:
    def _field_names(self) -> set[str]:
        return {f.name for f in FDA_CACHE_SCHEMA}

    def test_expected_field_names_present(self):
        names = self._field_names()
        for field_name in _FDA_EXPECTED_FIELDS:
            assert field_name in names, f"Expected field '{field_name}' not found in FDA_CACHE_SCHEMA"

    def test_all_fields_are_string(self):
        for f in FDA_CACHE_SCHEMA:
            assert f.field_type == "STRING", (
                f"Expected STRING for field {f.name}, got {f.field_type}"
            )

    def test_schema_has_seven_fields(self):
        assert len(FDA_CACHE_SCHEMA) == 7


class TestFdaCacheRefreshSql:
    _SOURCE_PROJECT = "bigquery-public-data"

    def _sql(self) -> str:
        return fda_cache_refresh_sql(self._SOURCE_PROJECT)

    def test_sql_contains_correct_table_reference(self):
        assert "`bigquery-public-data.fda_drug.drug_label`" in self._sql()

    def test_sql_source_project_is_interpolated(self):
        sql = fda_cache_refresh_sql("my-gcp-project")
        assert "`my-gcp-project.fda_drug.drug_label`" in sql

    def test_sql_selects_all_expected_columns(self):
        sql = self._sql()
        for field_name in _FDA_EXPECTED_FIELDS:
            assert field_name in sql, f"Expected column '{field_name}' not found in SQL"


class TestFdaCacheConfig:
    def test_table_id(self):
        assert FDA_CACHE_CONFIG.table_id == "fda_drug_labels_cache"

    def test_partition_field_is_none(self):
        assert FDA_CACHE_CONFIG.partition_field is None

    def test_partition_type_is_none(self):
        assert FDA_CACHE_CONFIG.partition_type is None

    def test_cluster_fields(self):
        assert FDA_CACHE_CONFIG.cluster_fields == ["openfda_generic_name"]

    def test_schema_is_set(self):
        assert FDA_CACHE_CONFIG.schema is FDA_CACHE_SCHEMA

    def test_refresh_sql_fn_is_callable(self):
        assert callable(FDA_CACHE_CONFIG.refresh_sql_fn)

    def test_refresh_sql_fn_returns_string(self):
        sql = FDA_CACHE_CONFIG.refresh_sql_fn("bigquery-public-data")
        assert isinstance(sql, str)
        assert len(sql) > 0
