"""Data models for seed enrichment logging and reporting."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum


class EnrichmentAction(str, Enum):
    """Types of enrichment changes."""

    NEW_ENTRY = "new_entry"
    UPDATED_COMPETITORS = "updated_competitors"
    UPDATED_PATENT_JURISDICTION = "updated_patent_jurisdiction"
    FLAGGED_STALE_REVENUE = "flagged_stale_revenue"
    UPDATED_BIOSIMILAR_STATUS = "updated_biosimilar_status"


@dataclass
class EnrichmentLogEntry:
    """A single enrichment change record."""

    timestamp: datetime
    action: EnrichmentAction
    drug_name: str
    field_changed: str
    old_value: str | None
    new_value: str
    source: str  # e.g. "bigquery_fda", "clinicaltrials", "bigquery_patents"
    confidence: str  # "high" or "medium"


@dataclass
class EnrichmentReport:
    """Summary report for an enrichment run."""

    run_id: str
    started_at: datetime
    completed_at: datetime
    entries_scanned: int
    entries_updated: int
    new_entries_added: int
    stale_revenue_flagged: int
    log: list[EnrichmentLogEntry] = field(default_factory=list)
