"""BigQuery client wrapper for Ember Bio data access."""

from __future__ import annotations

from google.cloud import bigquery

from ember_data.bigquery.queries import fda_drug_events_query, patent_search_query


class BigQueryClient:
    """Client for querying BigQuery public datasets.

    Wraps the Google Cloud BigQuery client with domain-specific
    query methods for FDA drug data and patent searches.
    """

    def __init__(self, project_id: str) -> None:
        self.project_id = project_id
        self._client = bigquery.Client(project=project_id)

    def query_fda_drug_events(self, drug_name: str, limit: int = 100) -> list[dict]:
        """Query FDA drug adverse event reports.

        Args:
            drug_name: Drug name to search for.
            limit: Maximum results to return.

        Returns:
            List of result rows as dictionaries.
        """
        query = fda_drug_events_query(drug_name, limit)
        job = self._client.query(query)
        return [dict(row.items()) for row in job.result()]

    def search_patents(self, query: str, limit: int = 100) -> list[dict]:
        """Search Google Patents public dataset.

        Args:
            query: Search terms for patent title/abstract.
            limit: Maximum results to return.

        Returns:
            List of result rows as dictionaries.
        """
        sql = patent_search_query(query, limit)
        job = self._client.query(sql)
        return [dict(row.items()) for row in job.result()]
