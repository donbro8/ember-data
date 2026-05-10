"""WatchStore: BigQuery-backed CRUD for WatchConfig records."""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone

from ember_data.bigquery.watch_schema import WatchConfig

logger = logging.getLogger(__name__)

_WATCH_CONFIGS_TABLE = "watch_configs"


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


class WatchStore:
    """CRUD operations for WatchConfig records stored in BigQuery.

    Args:
        client: A BigQueryClient instance.
        dataset: The BigQuery dataset name (e.g. ``ember_results``).
    """

    def __init__(self, client: object, dataset: str) -> None:
        self._client = client
        self._dataset = dataset

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    @property
    def _table(self) -> str:
        return f"{self._dataset}.{_WATCH_CONFIGS_TABLE}"

    def _row_to_watch_config(self, row: dict) -> WatchConfig:
        return WatchConfig.model_validate(row)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def create(
        self,
        name: str,
        query: str,
        schedule: str,
        schedule_day: int | None = None,
        notify_on_change: bool = False,
    ) -> WatchConfig:
        """Create a new WatchConfig and persist it to BigQuery.

        Uses DML INSERT (not streaming insert) so the row is immediately
        available for UPDATE/DELETE operations.

        Args:
            name: Human-readable name for the watch.
            query: The query string to watch.
            schedule: ``"weekly"`` or ``"monthly"``.
            schedule_day: Day of week (0-6) for weekly, day of month (1-28) for monthly.
            notify_on_change: Whether to notify when results change.

        Returns:
            The newly created ``WatchConfig``.
        """
        now = _now_utc()
        watch_id = str(uuid.uuid4())
        config = WatchConfig(
            watch_id=watch_id,
            name=name,
            query=query,
            schedule=schedule,  # type: ignore[arg-type]
            schedule_day=schedule_day,
            enabled=True,
            created_at=now,
            updated_at=now,
            notify_on_change=notify_on_change,
        )
        schedule_day_expr = "@schedule_day" if schedule_day is not None else "NULL"
        sql = f"""
            INSERT INTO `{self._table}`
            (watch_id, name, query, schedule, schedule_day, enabled,
             created_at, updated_at, last_run_id, last_run_at, notify_on_change)
            VALUES
            (@watch_id, @name, @query, @schedule, {schedule_day_expr}, @enabled,
             @created_at, @updated_at, NULL, NULL, @notify_on_change)
        """
        params: dict[str, object] = {
            "watch_id": watch_id,
            "name": name,
            "query": query,
            "schedule": schedule,
            "enabled": True,
            "created_at": now.isoformat(),
            "updated_at": now.isoformat(),
            "notify_on_change": notify_on_change,
        }
        if schedule_day is not None:
            params["schedule_day"] = schedule_day
        self._client.query_with_params(sql, params)
        logger.info("Created watch config watch_id=%s name=%r", watch_id, name)
        return config

    def get(self, watch_id: str) -> WatchConfig | None:
        """Fetch a WatchConfig by ID.

        Args:
            watch_id: The watch identifier.

        Returns:
            The ``WatchConfig`` if found, otherwise ``None``.
        """
        sql = f"""
            SELECT *
            FROM `{self._table}`
            WHERE watch_id = @watch_id
            LIMIT 1
        """
        rows = self._client.query_with_params(sql, {"watch_id": watch_id})
        if not rows:
            return None
        return self._row_to_watch_config(rows[0])

    def list(self, enabled_only: bool = False) -> list[WatchConfig]:
        """List watch configs, optionally filtering to enabled ones only.

        Args:
            enabled_only: If ``True``, only return configs where ``enabled = TRUE``.

        Returns:
            List of ``WatchConfig`` objects.
        """
        where_clause = "WHERE enabled = TRUE" if enabled_only else ""
        sql = f"""
            SELECT *
            FROM `{self._table}`
            {where_clause}
            ORDER BY created_at DESC
        """
        rows = self._client.query_with_params(sql, {})
        return [self._row_to_watch_config(row) for row in rows]

    def update(self, watch_id: str, **fields: object) -> WatchConfig:
        """Partially update a WatchConfig in BigQuery.

        Only the specified fields are modified; ``updated_at`` is always set
        to the current time.

        Args:
            watch_id: The watch identifier.
            **fields: Field names and new values to set.

        Returns:
            The updated ``WatchConfig``.

        Raises:
            ValueError: If the watch_id does not exist.
        """
        _ALLOWED_UPDATE_FIELDS = frozenset({
            "name", "query", "schedule", "schedule_day",
            "enabled", "notify_on_change", "updated_at",
        })
        now = _now_utc()
        fields["updated_at"] = now.isoformat()

        invalid = set(fields) - _ALLOWED_UPDATE_FIELDS
        if invalid:
            raise ValueError(f"Invalid update fields: {invalid}")

        set_clauses = ", ".join(f"{key} = @{key}" for key in fields)
        params: dict[str, object] = {"watch_id": watch_id}
        params.update(
            {k: v.isoformat() if isinstance(v, datetime) else v for k, v in fields.items()}
        )

        sql = f"""
            UPDATE `{self._table}`
            SET {set_clauses}
            WHERE watch_id = @watch_id
        """
        self._client.query_with_params(sql, params)
        logger.info("Updated watch config watch_id=%s fields=%s", watch_id, list(fields))

        updated = self.get(watch_id)
        if updated is None:
            raise ValueError(f"WatchConfig not found after update: {watch_id!r}")
        return updated

    def delete(self, watch_id: str) -> bool:
        """Delete a WatchConfig from BigQuery.

        Args:
            watch_id: The watch identifier to delete.

        Returns:
            ``True`` if the row existed and was deleted, ``False`` otherwise.
        """
        # Check existence first so we can return an accurate bool
        existing = self.get(watch_id)
        if existing is None:
            return False

        sql = f"""
            DELETE FROM `{self._table}`
            WHERE watch_id = @watch_id
        """
        self._client.query_with_params(sql, {"watch_id": watch_id})
        logger.info("Deleted watch config watch_id=%s", watch_id)
        return True

    def record_run(self, watch_id: str, run_id: str) -> None:
        """Update the last_run_id and last_run_at fields for a watch config.

        Args:
            watch_id: The watch identifier.
            run_id: The run identifier to record.
        """
        now = _now_utc()
        sql = f"""
            UPDATE `{self._table}`
            SET last_run_id = @run_id,
                last_run_at = @last_run_at,
                updated_at = @updated_at
            WHERE watch_id = @watch_id
        """
        params = {
            "watch_id": watch_id,
            "run_id": run_id,
            "last_run_at": now.isoformat(),
            "updated_at": now.isoformat(),
        }
        self._client.query_with_params(sql, params)
        logger.info("Recorded run run_id=%s for watch_id=%s", run_id, watch_id)
