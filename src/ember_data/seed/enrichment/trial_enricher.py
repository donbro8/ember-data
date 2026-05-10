"""BiosimilarTrialEnricher — enriches seed entries from ClinicalTrials.gov."""

from __future__ import annotations

import logging
from datetime import UTC, date, datetime

from ember_data.clients.clinicaltrials import ClinicalTrialsClient
from ember_data.models.trial import TrialPhase
from ember_data.seed.enrichment_log import EnrichmentAction, EnrichmentLogEntry
from ember_data.seed.schema import BiologicEntry

logger = logging.getLogger(__name__)

_PHASE_III_PLUS = {TrialPhase.III, TrialPhase.IV}


class BiosimilarTrialEnricher:
    """Enrich biologic entries with biosimilar competitor data from ClinicalTrials.gov.

    Searches for biosimilar trials referencing each drug, adding new sponsor
    names to ``biosimilar_competitors`` and updating ``has_approved_biosimilar``
    when phase III+ trials are found.
    """

    def __init__(self, client: ClinicalTrialsClient) -> None:
        self._client = client

    def enrich(
        self,
        entries: list[BiologicEntry],
        max_entries: int = 50,
    ) -> list[EnrichmentLogEntry]:
        """Enrich entries in-place with ClinicalTrials.gov biosimilar data.

        Entries are sorted by ``annual_revenue_usd_millions`` descending and
        only the top *max_entries* are processed.

        Returns a list of :class:`EnrichmentLogEntry` records describing every
        mutation applied.
        """
        sorted_entries = sorted(
            entries,
            key=lambda e: e.annual_revenue_usd_millions,
            reverse=True,
        )
        log_entries: list[EnrichmentLogEntry] = []

        for entry in sorted_entries[:max_entries]:
            try:
                entry_logs = self._enrich_one(entry)
                log_entries.extend(entry_logs)
            except Exception:
                logger.warning(
                    "Failed to enrich %s from ClinicalTrials.gov",
                    entry.drug_name,
                    exc_info=True,
                )

        return log_entries

    # ------------------------------------------------------------------
    # Internal
    # ------------------------------------------------------------------

    def _enrich_one(self, entry: BiologicEntry) -> list[EnrichmentLogEntry]:
        """Process a single entry, returning any log entries produced."""
        results = self._client.search(
            condition=f"{entry.drug_name} biosimilar",
        )

        log_entries: list[EnrichmentLogEntry] = []
        modified = False
        has_phase_iii_plus = False

        for trial, _provenance in results:
            sponsor = trial.sponsor.strip()

            # Track phase III+
            if trial.phase in _PHASE_III_PLUS:
                has_phase_iii_plus = True

            # Add new competitors
            if sponsor and sponsor not in entry.biosimilar_competitors:
                old_value = ",".join(entry.biosimilar_competitors) or None
                entry.biosimilar_competitors.append(sponsor)
                modified = True
                log_entries.append(
                    EnrichmentLogEntry(
                        timestamp=datetime.now(UTC),
                        action=EnrichmentAction.UPDATED_COMPETITORS,
                        drug_name=entry.drug_name,
                        field_changed="biosimilar_competitors",
                        old_value=old_value,
                        new_value=",".join(entry.biosimilar_competitors),
                        source="clinicaltrials",
                        confidence="high",
                    )
                )

        # Update biosimilar status if phase III+ found
        if has_phase_iii_plus and not entry.has_approved_biosimilar:
            entry.has_approved_biosimilar = True
            modified = True
            log_entries.append(
                EnrichmentLogEntry(
                    timestamp=datetime.now(UTC),
                    action=EnrichmentAction.UPDATED_BIOSIMILAR_STATUS,
                    drug_name=entry.drug_name,
                    field_changed="has_approved_biosimilar",
                    old_value="False",
                    new_value="True",
                    source="clinicaltrials",
                    confidence="high",
                )
            )

        if modified:
            entry.last_updated = date.today()

        return log_entries
