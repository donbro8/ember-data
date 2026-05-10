"""BigQuery schema for the digests table."""

DIGESTS_SCHEMA: list[dict] = [
    {"name": "digest_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "period_start", "type": "DATE", "mode": "REQUIRED"},
    {"name": "period_end", "type": "DATE", "mode": "REQUIRED"},
    {"name": "summary", "type": "STRING", "mode": "NULLABLE"},
    {"name": "per_watch_json", "type": "STRING", "mode": "NULLABLE"},
    {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
]
