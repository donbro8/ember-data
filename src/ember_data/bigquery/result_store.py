"""ResultWriter, ResultReader, and CachedRun for BigQuery-backed run persistence."""

from __future__ import annotations

import dataclasses
import json
import logging
from dataclasses import dataclass
from datetime import datetime, timezone

from ember_data.models.result import CandidateResult

logger = logging.getLogger(__name__)

_RUN_RESULTS_TABLE = "run_results"
_RUN_SUMMARY_TABLE = "run_summary"


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


def _normalize_query(query: str) -> str:
    """Normalize a query string for cache matching: lowercase + strip."""
    return query.lower().strip()


# ---------------------------------------------------------------------------
# CachedRun
# ---------------------------------------------------------------------------


@dataclass
class CachedRun:
    """A previously-computed run retrieved from the BigQuery cache."""

    run_id: str
    markdown: str
    results: list
    created_at: datetime
    query_type: str
    change_summary: str | None = None


# ---------------------------------------------------------------------------
# ResultWriter
# ---------------------------------------------------------------------------


class ResultWriter:
    """Writes run results and summaries to BigQuery."""

    def __init__(self, client: object, dataset: str) -> None:
        """Initialise the writer.

        Args:
            client: A BigQueryClient instance.
            dataset: The BigQuery dataset name (e.g. ``ember_results``).
        """
        self._client = client
        self._dataset = dataset

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def write_run(
        self,
        run_id: str,
        query: str,
        query_type: str,
        results: list[CandidateResult],
        trace: object,
        markdown: str,
        watch_id: str | None = None,
        bytes_scanned: int | None = None,
        change_summary: str | None = None,
    ) -> None:
        """Persist a completed run to BigQuery.

        Writes one row per ``CandidateResult`` to ``run_results``, and a
        single summary row to ``run_summary``.

        Args:
            run_id: Unique identifier for this run.
            query: The original query string.
            query_type: Classification of the query (e.g. ``"drug"``, ``"target"``).
            results: List of CandidateResult objects produced by the run.
            trace: Execution trace (any JSON-serialisable object).
            markdown: Full markdown report string.
            watch_id: Optional watch alert identifier.
            bytes_scanned: Optional BigQuery bytes billed for cost tracking.
            change_summary: Optional natural-language summary of changes from the previous run.
        """
        created_at = _now_utc()

        # Build per-result rows
        result_rows = self._build_result_rows(
            run_id=run_id,
            query=query,
            query_type=query_type,
            watch_id=watch_id,
            created_at=created_at,
            results=results,
        )

        # Build summary row
        summary_row = self._build_summary_row(
            run_id=run_id,
            query=query,
            query_type=query_type,
            watch_id=watch_id,
            markdown=markdown,
            bytes_scanned=bytes_scanned,
            trace=trace,
            created_at=created_at,
            change_summary=change_summary,
        )

        results_table = f"{self._dataset}.{_RUN_RESULTS_TABLE}"
        summary_table = f"{self._dataset}.{_RUN_SUMMARY_TABLE}"

        if result_rows:
            self._client.insert_rows(results_table, result_rows)
            logger.info(
                "Inserted %d result rows for run_id=%s into %s",
                len(result_rows),
                run_id,
                results_table,
            )

        self._client.insert_rows(summary_table, [summary_row])
        logger.info("Inserted summary row for run_id=%s into %s", run_id, summary_table)

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _build_result_rows(
        self,
        run_id: str,
        query: str,
        query_type: str,
        watch_id: str | None,
        created_at: datetime,
        results: list[CandidateResult],
    ) -> list[dict]:
        rows = []
        for result in results:
            row = result.model_dump(mode="json")
            row.update(
                {
                    "run_id": run_id,
                    "watch_id": watch_id,
                    "query": query,
                    "query_type": query_type,
                    "created_at": created_at.isoformat(),
                }
            )
            rows.append(row)
        return rows

    def _build_summary_row(
        self,
        run_id: str,
        query: str,
        query_type: str,
        watch_id: str | None,
        markdown: str,
        bytes_scanned: int | None,
        trace: object,
        created_at: datetime,
        change_summary: str | None = None,
    ) -> dict:
        return {
            "run_id": run_id,
            "query": query,
            "query_type": query_type,
            "watch_id": watch_id,
            "full_markdown": markdown,
            "bytes_scanned": bytes_scanned,
            "execution_trace": json.dumps(dataclasses.asdict(trace) if dataclasses.is_dataclass(trace) else trace) if trace is not None else None,
            "created_at": created_at.isoformat(),
            "change_summary": change_summary,
        }

    def update_summary(self, run_id: str, change_summary: str) -> None:
        """Update the change_summary field on an existing run_summary row.

        Args:
            run_id: The run identifier whose summary should be updated.
            change_summary: Natural-language summary of changes.
        """
        table = f"{self._dataset}.{_RUN_SUMMARY_TABLE}"
        sql = f"""
            UPDATE `{table}`
            SET change_summary = @change_summary
            WHERE run_id = @run_id
        """
        params = {"run_id": run_id, "change_summary": change_summary}
        self._client.query_with_params(sql, params)
        logger.info("Updated change_summary for run_id=%s", run_id)


# ---------------------------------------------------------------------------
# ResultReader
# ---------------------------------------------------------------------------


class ResultReader:
    """Reads run results and summaries from BigQuery."""

    def __init__(self, client: object, dataset: str) -> None:
        """Initialise the reader.

        Args:
            client: A BigQueryClient instance.
            dataset: The BigQuery dataset name.
        """
        self._client = client
        self._dataset = dataset

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def get_cached(self, query: str, ttl_hours: int = 24) -> CachedRun | None:
        """Return the most recent cached run for *query* if it is within TTL.

        The query is matched exactly after normalisation (lowercase + strip).
        Only rows whose ``created_at`` is within ``ttl_hours`` hours of now
        are considered.

        Args:
            query: The query string to look up.
            ttl_hours: How many hours back to search.

        Returns:
            A ``CachedRun`` if a fresh match exists, otherwise ``None``.
        """
        normalized = _normalize_query(query)
        sql = f"""
            SELECT run_id, full_markdown, created_at, query_type, change_summary
            FROM `{self._dataset}.{_RUN_SUMMARY_TABLE}`
            WHERE LOWER(TRIM(query)) = @query_normalized
              AND created_at >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {int(ttl_hours)} HOUR)
            ORDER BY created_at DESC
            LIMIT 1
        """
        params = {"query_normalized": normalized}
        rows = self._client.query_with_params(sql, params)
        if not rows:
            return None

        row = rows[0]
        run_id = row["run_id"]
        results = self.get_run(run_id)
        return CachedRun(
            run_id=run_id,
            markdown=row.get("full_markdown", ""),
            results=results,
            created_at=row["created_at"],
            query_type=row.get("query_type", ""),
            change_summary=row.get("change_summary"),
        )

    def get_run(self, run_id: str) -> list[CandidateResult]:
        """Fetch all CandidateResult rows for a specific run.

        Args:
            run_id: The run identifier to retrieve.

        Returns:
            List of ``CandidateResult`` objects reconstructed from BigQuery rows.
        """
        sql = f"""
            SELECT *
            FROM `{self._dataset}.{_RUN_RESULTS_TABLE}`
            WHERE run_id = @run_id
            ORDER BY canonical_id
        """
        params = {"run_id": run_id}
        rows = self._client.query_with_params(sql, params)
        results = []
        for row in rows:
            # Strip run-metadata columns before reconstructing CandidateResult
            candidate_data = {
                k: v
                for k, v in row.items()
                if k not in ("run_id", "watch_id", "query", "query_type", "created_at")
            }
            try:
                results.append(CandidateResult.model_validate(candidate_data))
            except Exception as exc:
                logger.warning("Could not reconstruct CandidateResult: %s", exc)
        return results

    def list_runs(
        self, watch_id: str | None = None, limit: int | None = 20
    ) -> list[dict]:
        """List recent runs from the summary table.

        Args:
            watch_id: Optional filter — only return runs for this watch alert.
            limit: Maximum number of runs to return (default 20).

        Returns:
            List of dicts with run summary fields.
        """
        where_clause = ""
        params: dict = {}
        if watch_id is not None:
            where_clause = "WHERE watch_id = @watch_id"
            params["watch_id"] = watch_id

        effective_limit = int(limit) if limit is not None else 20

        sql = f"""
            SELECT run_id, query, query_type, watch_id, created_at, bytes_scanned
            FROM `{self._dataset}.{_RUN_SUMMARY_TABLE}`
            {where_clause}
            ORDER BY created_at DESC
            LIMIT {effective_limit}
        """
        return self._client.query_with_params(sql, params)
