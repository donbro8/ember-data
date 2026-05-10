"""PatentJurisdictionEnricher — enriches seed entries from BigQuery patents."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from ember_data.bigquery.client import BigQueryClient
from ember_data.seed.enrichment_log import EnrichmentAction, EnrichmentLogEntry
from ember_data.seed.schema import BiologicEntry, _VALID_JURISDICTIONS

logger = logging.getLogger(__name__)


class PatentJurisdictionEnricher:
    """Enrich biologic entries with patent jurisdiction data from BigQuery.

    Queries the Google Patents public dataset (or managed cache) for each
    drug and adds new jurisdiction entries to ``patent_expiries``.
    """

    def __init__(
        self,
        client: BigQueryClient,
        managed_dataset: str | None = None,
    ) -> None:
        self._client = client
        self._managed_dataset = managed_dataset

    def enrich(
        self,
        entries: list[BiologicEntry],
        max_entries: int = 50,
    ) -> list[EnrichmentLogEntry]:
        """Enrich entries in-place with patent jurisdiction data.

        Entries are sorted by number of existing jurisdictions ascending
        (fewest first) and only the top *max_entries* are processed.

        Returns a list of :class:`EnrichmentLogEntry` records describing every
        mutation applied.
        """
        sorted_entries = sorted(
            entries,
            key=lambda e: len(e.patent_expiries),
        )
        log_entries: list[EnrichmentLogEntry] = []

        for entry in sorted_entries[:max_entries]:
            try:
                entry_logs = self._enrich_one(entry)
                log_entries.extend(entry_logs)
            except Exception:
                logger.warning(
                    "Failed to enrich %s from BigQuery patents",
                    entry.drug_name,
                    exc_info=True,
                )

        return log_entries

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _enrich_one(self, entry: BiologicEntry) -> list[EnrichmentLogEntry]:
        """Process a single entry, returning any log entries produced."""
        results = self._client.search_patents(
            query=entry.drug_name,
        )

        log_entries: list[EnrichmentLogEntry] = []
        modified = False

        for row in results:
            country_code: str = row.get("country_code", "")
            derived_expiry = row.get("derived_expiry")

            if not country_code or derived_expiry is None:
                continue

            # Only add valid jurisdictions not already present
            if country_code not in _VALID_JURISDICTIONS:
                continue
            if country_code in entry.patent_expiries:
                continue

            # Convert to date if needed
            if isinstance(derived_expiry, datetime):
                expiry_date = derived_expiry.date()
            elif isinstance(derived_expiry, date):
                expiry_date = derived_expiry
            elif isinstance(derived_expiry, str):
                expiry_date = date.fromisoformat(derived_expiry[:10])
            else:
                continue

            old_value = str(dict(entry.patent_expiries)) if entry.patent_expiries else None
            entry.patent_expiries[country_code] = expiry_date
            modified = True

            log_entries.append(
                EnrichmentLogEntry(
                    timestamp=datetime.now(UTC),
                    action=EnrichmentAction.UPDATED_PATENT_JURISDICTION,
                    drug_name=entry.drug_name,
                    field_changed=f"patent_expiries.{country_code}",
                    old_value=old_value,
                    new_value=str(expiry_date),
                    source="bigquery_patents",
                    confidence="medium",
                )
            )

        if modified:
            entry.last_updated = date.today()
            # Sync flat fields (patent_expiry_us / patent_expiry_eu) by
            # rebuilding via model_validate so the @model_validator fires.
            synced = BiologicEntry.model_validate(entry.model_dump())
            if synced.patent_expiry_us and entry.patent_expiry_us is None:
                entry.patent_expiry_us = synced.patent_expiry_us
            if synced.patent_expiry_eu and entry.patent_expiry_eu is None:
                entry.patent_expiry_eu = synced.patent_expiry_eu

        return log_entries
