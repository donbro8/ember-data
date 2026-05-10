"""ChangeDetector: compares two BigQuery run results and emits ChangeEntry records."""

from __future__ import annotations

import logging
import uuid
from dataclasses import asdict, dataclass
from datetime import datetime, timezone

from ember_data.bigquery.watch_schema import ChangeType

logger = logging.getLogger(__name__)

_CHANGE_LOG_TABLE = "change_log"
_RUN_RESULTS_TABLE = "run_results"

_SCORE_DELTA_THRESHOLD = 0.1


def _now_utc() -> datetime:
    return datetime.now(tz=timezone.utc)


# ---------------------------------------------------------------------------
# ChangeEntry dataclass
# ---------------------------------------------------------------------------


@dataclass
class ChangeEntry:
    """A single detected change between two run results."""

    change_id: str
    watch_id: str
    run_id: str
    previous_run_id: str
    change_type: str  # ChangeType value
    canonical_id: str
    display_label: str
    detail: str | None
    created_at: datetime


# ---------------------------------------------------------------------------
# ChangeDetector
# ---------------------------------------------------------------------------


class ChangeDetector:
    """Detects changes between two BigQuery run results and persists them.

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
    def _change_log_table(self) -> str:
        return f"{self._dataset}.{_CHANGE_LOG_TABLE}"

    def _fetch_run(self, run_id: str) -> list[dict]:
        """Fetch all result rows for a given run_id."""
        sql = f"""
            SELECT
                canonical_id,
                display_label,
                overall_score,
                trial_count,
                biosimilar_competitor_count,
                patent_country_codes,
                patent_expiry_dates
            FROM `{self._dataset}.{_RUN_RESULTS_TABLE}`
            WHERE run_id = @run_id
        """
        return self._client.query_with_params(sql, {"run_id": run_id})

    def _make_entry(
        self,
        watch_id: str,
        run_id: str,
        previous_run_id: str,
        change_type: ChangeType,
        canonical_id: str,
        display_label: str,
        detail: str | None,
        created_at: datetime,
    ) -> ChangeEntry:
        return ChangeEntry(
            change_id=str(uuid.uuid4()),
            watch_id=watch_id,
            run_id=run_id,
            previous_run_id=previous_run_id,
            change_type=change_type.value,
            canonical_id=canonical_id,
            display_label=display_label,
            detail=detail,
            created_at=created_at,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def detect_changes(
        self,
        watch_id: str,
        current_run_id: str,
        previous_run_id: str,
    ) -> list[ChangeEntry]:
        """Compare two runs and return a list of detected changes.

        Queries run_results for both run IDs, builds dicts keyed by
        canonical_id, and checks for all 7 change types.

        Args:
            watch_id: The watch alert identifier.
            current_run_id: The newer run to treat as current.
            previous_run_id: The older run to treat as baseline.

        Returns:
            List of ``ChangeEntry`` objects, one per detected change.
        """
        current_rows = self._fetch_run(current_run_id)
        previous_rows = self._fetch_run(previous_run_id)

        current_by_id: dict[str, dict] = {r["canonical_id"]: r for r in current_rows}
        previous_by_id: dict[str, dict] = {r["canonical_id"]: r for r in previous_rows}

        now = _now_utc()
        changes: list[ChangeEntry] = []

        # new_candidate — in current but not previous
        for cid, row in current_by_id.items():
            if cid not in previous_by_id:
                changes.append(
                    self._make_entry(
                        watch_id=watch_id,
                        run_id=current_run_id,
                        previous_run_id=previous_run_id,
                        change_type=ChangeType.NEW_CANDIDATE,
                        canonical_id=cid,
                        display_label=row["display_label"],
                        detail=f"New candidate: {row['display_label']}",
                        created_at=now,
                    )
                )

        # removed_candidate — in previous but not current
        for cid, row in previous_by_id.items():
            if cid not in current_by_id:
                changes.append(
                    self._make_entry(
                        watch_id=watch_id,
                        run_id=current_run_id,
                        previous_run_id=previous_run_id,
                        change_type=ChangeType.REMOVED_CANDIDATE,
                        canonical_id=cid,
                        display_label=row["display_label"],
                        detail=f"Removed: {row['display_label']}",
                        created_at=now,
                    )
                )

        # Per-candidate comparison for shared candidates
        for cid in current_by_id.keys() & previous_by_id.keys():
            cur = current_by_id[cid]
            prev = previous_by_id[cid]
            label = cur["display_label"]

            # score_change
            cur_score = cur.get("overall_score") or 0.0
            prev_score = prev.get("overall_score") or 0.0
            if abs(cur_score - prev_score) > _SCORE_DELTA_THRESHOLD:
                changes.append(
                    self._make_entry(
                        watch_id=watch_id,
                        run_id=current_run_id,
                        previous_run_id=previous_run_id,
                        change_type=ChangeType.SCORE_CHANGE,
                        canonical_id=cid,
                        display_label=label,
                        detail=f"Score changed from {prev_score} to {cur_score}",
                        created_at=now,
                    )
                )

            # new_trial
            cur_trials = cur.get("trial_count") or 0
            prev_trials = prev.get("trial_count") or 0
            if cur_trials > prev_trials:
                changes.append(
                    self._make_entry(
                        watch_id=watch_id,
                        run_id=current_run_id,
                        previous_run_id=previous_run_id,
                        change_type=ChangeType.NEW_TRIAL,
                        canonical_id=cid,
                        display_label=label,
                        detail=f"Trial count increased from {prev_trials} to {cur_trials}",
                        created_at=now,
                    )
                )

            # new_biosimilar_competitor
            cur_bio = cur.get("biosimilar_competitor_count") or 0
            prev_bio = prev.get("biosimilar_competitor_count") or 0
            if cur_bio > prev_bio:
                changes.append(
                    self._make_entry(
                        watch_id=watch_id,
                        run_id=current_run_id,
                        previous_run_id=previous_run_id,
                        change_type=ChangeType.NEW_BIOSIMILAR_COMPETITOR,
                        canonical_id=cid,
                        display_label=label,
                        detail=f"New biosimilar competitor (now {cur_bio} total)",
                        created_at=now,
                    )
                )

            # patent_expiry_update — any expiry date changed for a shared jurisdiction
            cur_expiry: dict[str, str] = cur.get("patent_expiry_dates") or {}
            prev_expiry: dict[str, str] = prev.get("patent_expiry_dates") or {}
            for jurisdiction, cur_date in cur_expiry.items():
                if jurisdiction in prev_expiry and prev_expiry[jurisdiction] != cur_date:
                    changes.append(
                        self._make_entry(
                            watch_id=watch_id,
                            run_id=current_run_id,
                            previous_run_id=previous_run_id,
                            change_type=ChangeType.PATENT_EXPIRY_UPDATE,
                            canonical_id=cid,
                            display_label=label,
                            detail=f"Patent expiry updated in {jurisdiction}",
                            created_at=now,
                        )
                    )

            # new_jurisdiction — patent country_codes expanded
            cur_codes: set[str] = set(cur.get("patent_country_codes") or [])
            prev_codes: set[str] = set(prev.get("patent_country_codes") or [])
            new_codes = cur_codes - prev_codes
            if new_codes:
                new_codes_str = ", ".join(sorted(new_codes))
                changes.append(
                    self._make_entry(
                        watch_id=watch_id,
                        run_id=current_run_id,
                        previous_run_id=previous_run_id,
                        change_type=ChangeType.NEW_JURISDICTION,
                        canonical_id=cid,
                        display_label=label,
                        detail=f"New patent jurisdiction: {new_codes_str}",
                        created_at=now,
                    )
                )

        logger.info(
            "detect_changes: watch_id=%s current=%s previous=%s -> %d changes",
            watch_id,
            current_run_id,
            previous_run_id,
            len(changes),
        )
        return changes

    def write_changes(self, changes: list[ChangeEntry]) -> None:
        """Insert ChangeEntry rows into the change_log table.

        Args:
            changes: List of ``ChangeEntry`` objects to persist.
        """
        if not changes:
            return
        rows = []
        for entry in changes:
            row = asdict(entry)
            row["created_at"] = entry.created_at.isoformat()
            rows.append(row)
        self._client.insert_rows(self._change_log_table, rows)
        logger.info(
            "write_changes: inserted %d rows into %s", len(rows), self._change_log_table
        )

    def get_changes(self, watch_id: str, limit: int = 50) -> list[ChangeEntry]:
        """Retrieve recent change entries for a watch alert.

        Args:
            watch_id: The watch alert identifier.
            limit: Maximum number of entries to return (default 50).

        Returns:
            List of ``ChangeEntry`` objects ordered by created_at DESC.
        """
        sql = f"""
            SELECT
                change_id,
                watch_id,
                run_id,
                previous_run_id,
                change_type,
                canonical_id,
                display_label,
                detail,
                created_at
            FROM `{self._change_log_table}`
            WHERE watch_id = @watch_id
            ORDER BY created_at DESC
            LIMIT @limit
        """
        rows = self._client.query_with_params(sql, {"watch_id": watch_id, "limit": limit})
        entries = []
        for row in rows:
            created_at = row["created_at"]
            if not isinstance(created_at, datetime):
                created_at = datetime.fromisoformat(str(created_at))
            entries.append(
                ChangeEntry(
                    change_id=row["change_id"],
                    watch_id=row["watch_id"],
                    run_id=row["run_id"],
                    previous_run_id=row["previous_run_id"],
                    change_type=row["change_type"],
                    canonical_id=row["canonical_id"],
                    display_label=row["display_label"],
                    detail=row.get("detail"),
                    created_at=created_at,
                )
            )
        return entries
