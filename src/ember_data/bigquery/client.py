"""BigQuery client wrapper for Ember Bio data access."""

from __future__ import annotations

import logging

from google.cloud import bigquery

from ember_data.bigquery.queries import fda_drug_events_query, patent_search_query
from ember_data.classification.spec import DateWindow

logger = logging.getLogger(__name__)

_ONE_GIGABYTE = 1_000_000_000


class BigQueryClient:
    """Client for querying BigQuery public datasets.

    Wraps the Google Cloud BigQuery client with domain-specific
    query methods for FDA drug data and patent searches.
    """

    def __init__(
        self,
        project_id: str,
        maximum_bytes_billed: int = _ONE_GIGABYTE,
    ) -> None:
        self.project_id = project_id
        self.maximum_bytes_billed = maximum_bytes_billed
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
            sql = patent_search_query(query, limit, date_window, jurisdictions)
            job_config = bigquery.QueryJobConfig(
                maximum_bytes_billed=self.maximum_bytes_billed
            )
            job = self._client.query(sql, job_config=job_config)
            results = [dict(row.items()) for row in job.result()]
            logger.info("Patent search returned %d results", len(results))
            return results
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
            if isinstance(value, int):
                param_type = "INT64"
            elif isinstance(value, float):
                param_type = "FLOAT64"
            else:
                param_type = "STRING"
            query_params.append(
                bigquery.ScalarQueryParameter(name, param_type, value)
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
