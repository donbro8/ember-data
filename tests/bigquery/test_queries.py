"""Tests for managed-table SQL path in patent_search_query() and fda_drug_events_query()."""

from __future__ import annotations

from datetime import date

from ember_data.bigquery.queries import fda_drug_events_query, patent_search_query


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _managed(query: str, **kwargs) -> str:
    """Shorthand: call patent_search_query with managed-table flags."""
    return patent_search_query(
        query,
        use_managed_table=True,
        managed_dataset="ember_dev",
        **kwargs,
    )


# ---------------------------------------------------------------------------
# Default path — must be completely unchanged
# ---------------------------------------------------------------------------


class TestDefaultPath:
    """Verify the public-dataset path is identical with and without new params."""

    def test_default_call_unchanged(self):
        sql_old = patent_search_query("test")
        sql_new = patent_search_query("test", use_managed_table=False, managed_dataset=None)
        assert sql_old == sql_new

    def test_default_uses_unnest(self):
        sql = patent_search_query("oncology")
        assert "UNNEST" in sql

    def test_default_uses_date_add_expr(self):
        sql = patent_search_query("oncology")
        assert "DATE_ADD" in sql
        assert "INTERVAL 20 YEAR" in sql

    def test_default_targets_public_dataset(self):
        sql = patent_search_query("oncology")
        assert "patents-public-data.patents.publications" in sql

    def test_default_includes_derivation_provenance_fields(self):
        sql = patent_search_query("oncology")
        assert "expiry_derivation_method" in sql
        assert "expiry_derivation_provenance" in sql
        assert "'filing_20yr'" in sql

    def test_managed_false_with_dataset_still_uses_public_path(self):
        """Setting managed_dataset without use_managed_table must not change the path."""
        sql_default = patent_search_query("oncology")
        sql_with_ds = patent_search_query(
            "oncology", use_managed_table=False, managed_dataset="ember_dev"
        )
        assert sql_default == sql_with_ds


# ---------------------------------------------------------------------------
# Managed-table path — target table
# ---------------------------------------------------------------------------


class TestManagedTableTarget:
    def test_targets_managed_dataset_table(self):
        sql = _managed("test")
        assert "ember_dev.patent_search_cache" in sql

    def test_does_not_target_public_dataset(self):
        sql = _managed("test")
        assert "patents-public-data" not in sql

    def test_no_unnest(self):
        sql = _managed("test")
        assert "UNNEST" not in sql

    def test_no_date_add(self):
        sql = _managed("test")
        assert "DATE_ADD" not in sql

    def test_uses_flat_title_column(self):
        sql = _managed("test")
        assert "title" in sql
        # Must NOT reference t.text (localized array element)
        assert "t.text" not in sql

    def test_uses_flat_abstract_column(self):
        sql = _managed("test")
        assert "abstract" in sql
        assert "a.text" not in sql

    def test_uses_filing_date_parsed(self):
        sql = _managed("test")
        assert "filing_date_parsed" in sql

    def test_uses_derived_expiry_column_directly(self):
        sql = _managed("test")
        assert "derived_expiry" in sql
        # No inline DATE_ADD computation
        assert "DATE_ADD" not in sql

    def test_includes_expiry_approximate_true(self):
        sql = _managed("test")
        assert "TRUE AS expiry_approximate" in sql

    def test_includes_derivation_provenance_fields(self):
        sql = _managed("test")
        assert "expiry_derivation_method" in sql
        assert "expiry_derivation_provenance" in sql
        assert "'filing_20yr'" in sql

    def test_includes_publication_number(self):
        sql = _managed("test")
        assert "publication_number" in sql

    def test_query_text_applied_to_flat_columns(self):
        sql = _managed("KRAS inhibitor")
        assert "KRAS inhibitor" in sql
        assert "LOWER(title)" in sql
        assert "LOWER(abstract)" in sql

    def test_limit_applied(self):
        sql = _managed("test", limit=42)
        assert "42" in sql


# ---------------------------------------------------------------------------
# Managed-table path — jurisdiction filter
# ---------------------------------------------------------------------------


class TestManagedTableJurisdiction:
    def test_single_jurisdiction(self):
        sql = _managed("inhibitor", jurisdictions=["US"])
        assert "country_code IN ('US')" in sql

    def test_multiple_jurisdictions(self):
        sql = _managed("inhibitor", jurisdictions=["US", "EU"])
        assert "country_code IN" in sql
        assert "'US'" in sql
        assert "'EP'" in sql  # EU maps to EP

    def test_wipo_mapping(self):
        sql = _managed("peptide", jurisdictions=["WIPO"])
        assert "'WO'" in sql

    def test_no_jurisdiction_no_country_filter(self):
        sql = _managed("oncology")
        assert "country_code IN" not in sql

    def test_jurisdiction_uses_bare_column_no_table_prefix(self):
        """Managed table has no join aliases, so no p.country_code."""
        sql = _managed("test", jurisdictions=["US"])
        # Should be plain country_code IN, not p.country_code IN
        assert "p.country_code IN" not in sql
        assert "country_code IN" in sql


# ---------------------------------------------------------------------------
# Managed-table path — date_window filter
# ---------------------------------------------------------------------------


class TestManagedTableDateWindow:
    def _make_window(self, start=None, end=None):
        class _Window:
            pass

        w = _Window()
        w.start = start
        w.end = end
        return w

    def test_before_window(self):
        window = self._make_window(end=date(2025, 1, 1))
        sql = _managed("kinase", date_window=window)
        assert "derived_expiry <= DATE '2025-01-01'" in sql
        assert ">=" not in sql.split("derived_expiry")[1].split("2025")[0]

    def test_after_window(self):
        window = self._make_window(start=date(2028, 6, 15))
        sql = _managed("kinase", date_window=window)
        assert "derived_expiry >= DATE '2028-06-15'" in sql

    def test_between_window(self):
        window = self._make_window(start=date(2026, 1, 1), end=date(2035, 12, 31))
        sql = _managed("mAb", date_window=window)
        assert "derived_expiry >= DATE '2026-01-01'" in sql
        assert "derived_expiry <= DATE '2035-12-31'" in sql

    def test_date_window_uses_derived_expiry_column_not_date_add(self):
        window = self._make_window(start=date(2030, 1, 1))
        sql = _managed("test", date_window=window)
        assert "DATE_ADD" not in sql
        assert "derived_expiry >= DATE '2030-01-01'" in sql

    def test_combined_window_and_jurisdiction(self):
        window = self._make_window(start=date(2030, 1, 1))
        sql = _managed("ADC", date_window=window, jurisdictions=["US", "JP"])
        assert "2030-01-01" in sql
        assert "'US'" in sql
        assert "'JP'" in sql
        assert "UNNEST" not in sql
        assert "DATE_ADD" not in sql


# ---------------------------------------------------------------------------
# Managed-table path — different dataset names
# ---------------------------------------------------------------------------


class TestManagedTableDatasetParam:
    def test_custom_dataset_name(self):
        sql = patent_search_query(
            "test",
            use_managed_table=True,
            managed_dataset="my_custom_dataset",
        )
        assert "my_custom_dataset.patent_search_cache" in sql

    def test_use_managed_true_without_dataset_falls_back_to_public(self):
        """If managed_dataset is None, fall back to the existing public path."""
        sql = patent_search_query("test", use_managed_table=True, managed_dataset=None)
        public_sql = patent_search_query("test")
        assert sql == public_sql


# ---------------------------------------------------------------------------
# FDA drug events — default path unchanged
# ---------------------------------------------------------------------------


class TestFdaDefaultPath:
    """Verify the public-dataset FDA path is identical with and without new params."""

    def test_default_call_unchanged(self):
        sql_old = fda_drug_events_query(["aspirin"])
        sql_new = fda_drug_events_query(
            ["aspirin"], use_managed_table=False, managed_dataset=None
        )
        assert sql_old == sql_new

    def test_default_targets_public_dataset(self):
        sql = fda_drug_events_query(["ibuprofen"])
        assert "bigquery-public-data.fda_drug.drug_label" in sql

    def test_default_select_five_columns(self):
        sql = fda_drug_events_query(["ibuprofen"])
        assert "openfda_pharm_class_epc" not in sql
        assert "openfda_pharm_class_cs" not in sql

    def test_managed_false_with_dataset_still_uses_public_path(self):
        sql_default = fda_drug_events_query(["aspirin"])
        sql_with_ds = fda_drug_events_query(
            ["aspirin"], use_managed_table=False, managed_dataset="ember_dev"
        )
        assert sql_default == sql_with_ds


# ---------------------------------------------------------------------------
# FDA drug events — managed-table path: target table
# ---------------------------------------------------------------------------


def _fda_managed(drug_names, **kwargs) -> str:
    """Shorthand: call fda_drug_events_query with managed-table flags."""
    return fda_drug_events_query(
        drug_names,
        use_managed_table=True,
        managed_dataset="ember_dev",
        **kwargs,
    )


class TestFdaManagedTableTarget:
    def test_targets_managed_dataset_table(self):
        sql = _fda_managed(["test"])
        assert "ember_dev.fda_drug_labels_cache" in sql

    def test_does_not_target_public_dataset(self):
        sql = _fda_managed(["test"])
        assert "bigquery-public-data" not in sql

    def test_includes_pharm_class_epc(self):
        sql = _fda_managed(["test"])
        assert "openfda_pharm_class_epc" in sql

    def test_includes_pharm_class_cs(self):
        sql = _fda_managed(["test"])
        assert "openfda_pharm_class_cs" in sql

    def test_still_includes_core_columns(self):
        sql = _fda_managed(["test"])
        assert "openfda_product_ndc" in sql
        assert "openfda_generic_name" in sql
        assert "openfda_brand_name" in sql
        assert "openfda_manufacturer_name" in sql
        assert "openfda_product_type" in sql

    def test_limit_applied(self):
        sql = _fda_managed(["test"], limit=42)
        assert "42" in sql

    def test_use_managed_true_without_dataset_falls_back_to_public(self):
        sql = fda_drug_events_query(["test"], use_managed_table=True, managed_dataset=None)
        public_sql = fda_drug_events_query(["test"])
        assert sql == public_sql


# ---------------------------------------------------------------------------
# FDA drug events — managed-table path: drug_names filter
# ---------------------------------------------------------------------------


class TestFdaManagedDrugNames:
    def test_single_drug_name_filter(self):
        sql = _fda_managed(["aspirin"])
        assert "aspirin" in sql
        assert "LOWER(openfda_generic_name)" in sql
        assert "LOWER(openfda_brand_name)" in sql

    def test_multiple_drug_names_joined_with_or(self):
        sql = _fda_managed(["aspirin", "ibuprofen"])
        assert "aspirin" in sql
        assert "ibuprofen" in sql
        assert " OR " in sql

    def test_string_drug_name_normalized(self):
        sql_list = _fda_managed(["paracetamol"])
        sql_str = fda_drug_events_query(
            "paracetamol", use_managed_table=True, managed_dataset="ember_dev"
        )
        assert sql_list == sql_str


# ---------------------------------------------------------------------------
# FDA drug events — managed-table path: therapeutic_area filter
# ---------------------------------------------------------------------------


class TestFdaManagedTherapeuticArea:
    def test_therapeutic_area_filter_applied(self):
        sql = _fda_managed(["test"], therapeutic_area="oncology")
        assert "oncology" in sql
        assert "LOWER(openfda_pharm_class_epc)" in sql
        assert "LOWER(openfda_pharm_class_cs)" in sql

    def test_therapeutic_area_and_drug_name_combined(self):
        sql = _fda_managed(["aspirin"], therapeutic_area="cardiovascular")
        assert "aspirin" in sql
        assert "cardiovascular" in sql
        assert " AND " in sql

    def test_no_therapeutic_area_no_pharm_class_filter(self):
        sql = _fda_managed(["test"])
        # pharm_class columns appear in SELECT but not in WHERE filter
        assert "WHERE" not in sql or "pharm_class_epc" not in sql.split("WHERE")[1]

    def test_custom_dataset_name(self):
        sql = fda_drug_events_query(
            ["test"],
            use_managed_table=True,
            managed_dataset="my_custom_dataset",
        )
        assert "my_custom_dataset.fda_drug_labels_cache" in sql
