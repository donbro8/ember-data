"""BigQuery table schema definitions and models for watch configs and change logs."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Literal

from pydantic import BaseModel, field_validator


# ---------------------------------------------------------------------------
# WatchConfig model
# ---------------------------------------------------------------------------


class WatchConfig(BaseModel):
    watch_id: str
    name: str
    query: str
    schedule: Literal["weekly", "monthly"]
    schedule_day: int | None = None
    enabled: bool = True
    created_at: datetime
    updated_at: datetime
    last_run_id: str | None = None
    last_run_at: datetime | None = None
    notify_on_change: bool = False

    @field_validator("schedule_day")
    @classmethod
    def validate_schedule_day(cls, v: int | None, info: object) -> int | None:
        if v is None:
            return v
        schedule = info.data.get("schedule")
        if schedule == "weekly" and not (0 <= v <= 6):
            raise ValueError("schedule_day must be 0-6 for weekly")
        if schedule == "monthly" and not (1 <= v <= 28):
            raise ValueError("schedule_day must be 1-28 for monthly")
        return v


# ---------------------------------------------------------------------------
# ChangeType enum
# ---------------------------------------------------------------------------


class ChangeType(str, Enum):
    NEW_CANDIDATE = "new_candidate"
    REMOVED_CANDIDATE = "removed_candidate"
    SCORE_CHANGE = "score_change"
    PATENT_EXPIRY_UPDATE = "patent_expiry_update"
    NEW_TRIAL = "new_trial"
    NEW_BIOSIMILAR_COMPETITOR = "new_biosimilar_competitor"
    NEW_JURISDICTION = "new_jurisdiction"


# ---------------------------------------------------------------------------
# WATCH_CONFIGS_SCHEMA
# ---------------------------------------------------------------------------

WATCH_CONFIGS_SCHEMA: list[dict] = [
    {"name": "watch_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "name", "type": "STRING", "mode": "REQUIRED"},
    {"name": "query", "type": "STRING", "mode": "REQUIRED"},
    {"name": "schedule", "type": "STRING", "mode": "REQUIRED"},
    {"name": "schedule_day", "type": "INT64", "mode": "NULLABLE"},
    {"name": "enabled", "type": "BOOLEAN", "mode": "REQUIRED"},
    {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "updated_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "last_run_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "last_run_at", "type": "TIMESTAMP", "mode": "NULLABLE"},
    {"name": "notify_on_change", "type": "BOOLEAN", "mode": "REQUIRED"},
]

# ---------------------------------------------------------------------------
# CHANGE_LOG_SCHEMA
# ---------------------------------------------------------------------------

CHANGE_LOG_SCHEMA: list[dict] = [
    {"name": "change_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "watch_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "run_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "previous_run_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "change_type", "type": "STRING", "mode": "REQUIRED"},
    {"name": "canonical_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "display_label", "type": "STRING", "mode": "REQUIRED"},
    {"name": "detail", "type": "STRING", "mode": "NULLABLE"},
    {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
]
