"""BigQuery client wrapper for Ember Bio data access."""

from __future__ import annotations

import logging

from google.cloud import bigquery

from ember_data.bigquery.queries import fda_drug_events_query, patent_search_query
from ember_data.classification.spec import DateWindow

logger = logging.getLogger(__name__)

_ONE_GIGABYTE = 1_000_000_000
_FIVE_GIGABYTES = 5_000_000_000


class QueryTooExpensiveError(Exception):
    """Raised when a query's estimated scan exceeds the configured threshold."""

    def __init__(self, estimated_bytes: int, threshold_bytes: int) -> None:
        self.estimated_bytes = estimated_bytes
        self.threshold_bytes = threshold_bytes
        super().__init__(
            f"Query estimated {estimated_bytes:,} bytes, exceeds threshold of {threshold_bytes:,} bytes"
        )


class BigQueryClient:
    """Client for querying BigQuery public datasets.

    Wraps the Google Cloud BigQuery client with domain-specific
    query methods for FDA drug data and patent searches.
    """

    def __init__(
        self,
        project_id: str,
        maximum_bytes_billed: int = _ONE_GIGABYTE,
        managed_dataset: str | None = None,
        dry_run_threshold_bytes: int = _FIVE_GIGABYTES,
    ) -> None:
        self.project_id = project_id
        self.maximum_bytes_billed = maximum_bytes_billed
        self.managed_dataset = managed_dataset
        self.dry_run_threshold_bytes = dry_run_threshold_bytes
        self._client = bigquery.Client(project=project_id)

    def query_fda_drug_events(
        self,
        drug_names: list[str] | str,
        therapeutic_area: str | None = None,
        limit: int = 100,
    ) -> list[dict]:
        """Query FDA drug label records.

        Args:
            drug_names: Drug names to search for.
            therapeutic_area: Optional therapeutic area filter.
            limit: Maximum results to return.

        Returns:
            List of result rows as dictionaries.
        """
        logger.info(
            "Executing FDA drug events query: drug_names=%r, limit=%d",
            drug_names,
            limit,
        )
        try:
            if self.managed_dataset is not None:
                query = fda_drug_events_query(
                    drug_names,
                    therapeutic_area,
                    limit,
                    use_managed_table=True,
                    managed_dataset=self.managed_dataset,
                )
            else:
                query = fda_drug_events_query(drug_names, therapeutic_area, limit)
            job_config = bigquery.QueryJobConfig(
                maximum_bytes_billed=self.maximum_bytes_billed
            )
            job = self._client.query(query, job_config=job_config)
            results = [dict(row.items()) for row in job.result()]
            logger.info("FDA drug events query returned %d results", len(results))
            return results
        except Exception as exc:
            logger.error("FDA drug events query failed: %s", exc)
            return []

    def search_patents(
        self,
        query: str,
        limit: int = 100,
        date_window: DateWindow | None = None,
        jurisdictions: list[str] | None = None,
    ) -> list[dict]:
        """Search Google Patents public dataset.

        Patent expiry is derived as filing date + 20 years.  Each result row
        includes ``derived_expiry`` and ``expiry_approximate = True`` to
        record this in provenance.  Date-window and jurisdiction filters are
        applied at query time.

        Args:
            query: Search terms for patent title/abstract.
            limit: Maximum results to return.
            date_window: Optional DateWindow applied to the derived expiry date.
            jurisdictions: Optional list of Jurisdiction values to filter on.

        Returns:
            List of result rows as dictionaries, each containing
            ``derived_expiry`` and ``expiry_approximate``.
        """
        logger.info("Executing patent search: query=%r, limit=%d", query, limit)
        try:
            if self.managed_dataset is not None:
                sql = patent_search_query(
                    query,
                    limit,
                    date_window,
                    jurisdictions,
                    use_managed_table=True,
                    managed_dataset=self.managed_dataset,
                )
            else:
                sql = patent_search_query(query, limit, date_window, jurisdictions)
                estimated_bytes = self.dry_run_estimate(sql)
                if estimated_bytes > self.dry_run_threshold_bytes:
                    raise QueryTooExpensiveError(estimated_bytes, self.dry_run_threshold_bytes)
            job_config = bigquery.QueryJobConfig(
                maximum_bytes_billed=self.maximum_bytes_billed
            )
            job = self._client.query(sql, job_config=job_config)
            results = [dict(row.items()) for row in job.result()]
            logger.info("Patent search returned %d results", len(results))
            return results
        except QueryTooExpensiveError:
            raise
        except Exception as exc:
            logger.error("Patent search failed: %s", exc)
            return []

    def dry_run_estimate(self, sql: str, params: dict | None = None) -> int:
        """Estimate bytes that would be processed without executing the query.

        Args:
            sql: The SQL query string to estimate.
            params: Optional mapping of parameter names to values (unused for
                dry-run; included for API consistency with parameterised queries).

        Returns:
            Estimated number of bytes that would be processed.
        """
        job_config = bigquery.QueryJobConfig(dry_run=True, use_query_cache=False)
        job = self._client.query(sql, job_config=job_config)
        bytes_processed: int = job.total_bytes_processed or 0
        logger.info("Dry-run estimate: %d bytes for sql=%.80r", bytes_processed, sql)
        return bytes_processed

    def insert_rows(self, table: str, rows: list[dict]) -> None:
        """Insert rows into a BigQuery table using the streaming insert API.

        Args:
            table: Fully-qualified table reference (``dataset.table``).
            rows: List of row dicts to insert.
        """
        errors = self._client.insert_rows_json(table, rows)
        if errors:
            logger.error("insert_rows errors for %s: %s", table, errors)
        else:
            logger.debug("Inserted %d rows into %s", len(rows), table)

    def query_with_params(self, sql: str, params: dict | None = None) -> list[dict]:
        """Execute a SQL query with named parameters and return rows as dicts.

        Args:
            sql: The SQL query string (may contain ``@param_name`` placeholders).
            params: Mapping of parameter names to scalar values.

        Returns:
            List of result rows as dicts.
        """
        query_params = []
        for name, value in (params or {}).items():
            if value is None:
                # BigQuery needs a typed NULL; default to STRING for untyped nulls
                query_params.append(
                    bigquery.ScalarQueryParameter(name, "STRING", None)
                )
            elif isinstance(value, bool):
                # Must check bool before int (bool is a subclass of int)
                query_params.append(
                    bigquery.ScalarQueryParameter(name, "BOOL", value)
                )
            elif isinstance(value, int):
                param_type = "INT64"
                query_params.append(
                    bigquery.ScalarQueryParameter(name, param_type, value)
                )
            elif isinstance(value, float):
                query_params.append(
                    bigquery.ScalarQueryParameter(name, "FLOAT64", value)
                )
            else:
                query_params.append(
                    bigquery.ScalarQueryParameter(name, "STRING", value)
                )

        job_config = bigquery.QueryJobConfig(
            query_parameters=query_params,
            maximum_bytes_billed=self.maximum_bytes_billed,
        )
        try:
            job = self._client.query(sql, job_config=job_config)
            return [dict(row.items()) for row in job.result()]
        except Exception as exc:
            logger.error("query_with_params failed: %s", exc)
            return []
