"""SeedEnrichmentOrchestrator — coordinates all enrichment providers."""

from __future__ import annotations

import logging
import uuid
from datetime import UTC, date, datetime

from ember_data.seed.enrichment_log import (
    EnrichmentAction,
    EnrichmentLogEntry,
    EnrichmentReport,
)
from ember_data.seed.enrichment.fda_discovery import FDABiologicDiscovery
from ember_data.seed.enrichment.patent_enricher import PatentJurisdictionEnricher
from ember_data.seed.enrichment.trial_enricher import BiosimilarTrialEnricher
from ember_data.seed.schema import VersionedSeedFile

logger = logging.getLogger(__name__)


class SeedEnrichmentOrchestrator:
    """Coordinates FDA discovery, trial enrichment, and patent enrichment.

    Each provider is optional (pass ``None`` to skip). If a provider raises
    an exception the orchestrator logs the error and continues with the
    remaining providers. Stale-revenue flagging always runs regardless of
    provider configuration.
    """

    def __init__(
        self,
        fda_discovery: FDABiologicDiscovery | None = None,
        trial_enricher: BiosimilarTrialEnricher | None = None,
        patent_enricher: PatentJurisdictionEnricher | None = None,
    ) -> None:
        self._fda_discovery = fda_discovery
        self._trial_enricher = trial_enricher
        self._patent_enricher = patent_enricher

    def run(self, seed: VersionedSeedFile) -> EnrichmentReport:
        """Execute the full enrichment pipeline against *seed* (mutated in place).

        Returns an :class:`EnrichmentReport` summarising the run.
        """
        started_at = datetime.now(UTC)
        all_logs: list[EnrichmentLogEntry] = []
        new_entries_added = 0

        # 1. FDA discovery -------------------------------------------------
        if self._fda_discovery is not None:
            try:
                new_entries, fda_logs = self._fda_discovery.discover(seed.entries)
                seed.entries.extend(new_entries)
                new_entries_added = len(new_entries)
                all_logs.extend(fda_logs)
            except Exception:
                logger.exception("FDA discovery provider failed")

        # 2. Trial enrichment -----------------------------------------------
        if self._trial_enricher is not None:
            try:
                trial_logs = self._trial_enricher.enrich(seed.entries)
                all_logs.extend(trial_logs)
            except Exception:
                logger.exception("Trial enricher provider failed")

        # 3. Patent enrichment ----------------------------------------------
        if self._patent_enricher is not None:
            try:
                patent_logs = self._patent_enricher.enrich(seed.entries)
                all_logs.extend(patent_logs)
            except Exception:
                logger.exception("Patent enricher provider failed")

        # 4. Stale revenue flagging -----------------------------------------
        current_year = date.today().year
        stale_count = 0
        for entry in seed.entries:
            if entry.revenue_year is not None and entry.revenue_year < current_year - 1:
                stale_count += 1
                all_logs.append(
                    EnrichmentLogEntry(
                        timestamp=datetime.now(UTC),
                        action=EnrichmentAction.FLAGGED_STALE_REVENUE,
                        drug_name=entry.drug_name,
                        field_changed="revenue_year",
                        old_value=str(entry.revenue_year),
                        new_value="stale",
                        source="system",
                        confidence="high",
                    )
                )

        # 5. Update seed metadata -------------------------------------------
        seed.data_version += 1
        seed.last_enrichment_run = datetime.now(UTC)
        seed.entry_count = len(seed.entries)

        # 6. Count entries updated today ------------------------------------
        today = date.today()
        entries_updated = sum(
            1 for e in seed.entries if e.last_updated == today
        )

        completed_at = datetime.now(UTC)

        return EnrichmentReport(
            run_id=str(uuid.uuid4()),
            started_at=started_at,
            completed_at=completed_at,
            entries_scanned=len(seed.entries),
            entries_updated=entries_updated,
            new_entries_added=new_entries_added,
            stale_revenue_flagged=stale_count,
            log=all_logs,
        )
