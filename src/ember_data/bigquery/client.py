"""BigQuery client wrapper for Ember Bio data access."""

from __future__ import annotations

import logging

from google.cloud import bigquery

logger = logging.getLogger(__name__)

from ember_data.bigquery.queries import fda_drug_events_query, patent_search_query
from ember_data.classification.spec import DateWindow


class BigQueryClient:
    """Client for querying BigQuery public datasets.

    Wraps the Google Cloud BigQuery client with domain-specific
    query methods for FDA drug data and patent searches.
    """

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
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
            job = self._client.query(query)
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
            job = self._client.query(sql)
            results = [dict(row.items()) for row in job.result()]
            logger.info("Patent search returned %d results", len(results))
            return results
        except Exception as exc:
            logger.error("Patent search failed: %s", exc)
            return []
