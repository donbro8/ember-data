"""SeedWriter — persists enriched seed data to JSON and BigQuery."""

from __future__ import annotations

import json
import logging
import os
from datetime import date
from pathlib import Path
from typing import TYPE_CHECKING

from ember_data.bigquery.managed_tables import BIOLOGIC_SEED_TABLE, ENRICHMENT_LOG_TABLE

if TYPE_CHECKING:
    from ember_data.bigquery.client import BigQueryClient
    from ember_data.seed.enrichment_log import EnrichmentReport
    from ember_data.seed.schema import BiologicEntry, VersionedSeedFile

logger = logging.getLogger(__name__)


def _entry_to_row(entry: BiologicEntry, data_version: int) -> dict:
    """Convert a BiologicEntry to a BigQuery row dict."""
    patent_expiries_raw = entry.patent_expiries
    # JSON-encode patent_expiries dict since BigQuery doesn't support MAP type.
    patent_expiries_json = json.dumps(
        {k: v.isoformat() if isinstance(v, date) else str(v) for k, v in patent_expiries_raw.items()}
    )
    return {
        "drug_name": entry.drug_name,
        "brand_names": entry.brand_names,
        "originator": entry.originator,
        "target_antigen": entry.target_antigen,
        "modality": entry.modality,
        "category": entry.category,
        "cell_line": entry.cell_line,
        "cell_line_class": entry.cell_line_class,
        "indications": entry.indications,
        "annual_revenue_usd_millions": entry.annual_revenue_usd_millions,
        "revenue_year": entry.revenue_year,
        "patent_expiries_json": patent_expiries_json,
        "biosimilar_competitors": entry.biosimilar_competitors,
        "has_approved_biosimilar": entry.has_approved_biosimilar,
        "last_updated": entry.last_updated.isoformat() if entry.last_updated else None,
        "source": entry.source,
        "data_version": data_version,
        "key_patent_numbers": entry.key_patent_numbers,
    }


def _log_entry_to_row(entry, run_id: str) -> dict:  # noqa: ANN001
    """Convert an EnrichmentLogEntry to a BigQuery row dict."""
    return {
        "run_id": run_id,
        "timestamp": entry.timestamp.isoformat(),
        "action": entry.action.value if hasattr(entry.action, "value") else str(entry.action),
        "drug_name": entry.drug_name,
        "field_changed": entry.field_changed,
        "old_value": entry.old_value,
        "new_value": entry.new_value,
        "source": entry.source,
        "confidence": entry.confidence,
    }


class SeedWriter:
    """Persists enriched seed data to JSON (atomically) and BigQuery.

    Both JSON and BigQuery destinations are optional; when a destination is
    not configured, the corresponding write method is a no-op.
    """

    def __init__(
        self,
        json_path: Path | None = None,
        bq_client: BigQueryClient | None = None,
        bq_dataset: str | None = None,
    ) -> None:
        self.json_path = json_path
        self.bq_client = bq_client
        self.bq_dataset = bq_dataset

    def _bq_configured(self) -> bool:
        return self.bq_client is not None and self.bq_dataset is not None

    def write(self, seed: VersionedSeedFile, report: EnrichmentReport) -> None:
        """Write the seed file to JSON and/or BigQuery.

        Args:
            seed: The versioned seed file to persist.
            report: The enrichment report (unused for JSON, provides context).
        """
        if self.json_path is not None:
            self._write_json(seed)

        if self._bq_configured():
            self._write_bq(seed)

    def write_log(self, report: EnrichmentReport) -> None:
        """Write enrichment log entries to BigQuery.

        No-op when BigQuery is not configured.

        Args:
            report: The enrichment report containing log entries.
        """
        if not self._bq_configured():
            return

        if not report.log:
            return

        rows = [_log_entry_to_row(entry, report.run_id) for entry in report.log]
        table = f"{self.bq_dataset}.{ENRICHMENT_LOG_TABLE}"
        assert self.bq_client is not None  # guarded by _bq_configured  # noqa: S101
        self.bq_client.insert_rows(table, rows)
        logger.info("Wrote %d enrichment log rows to %s", len(rows), table)

    def _write_json(self, seed: VersionedSeedFile) -> None:
        """Atomically write seed data to JSON."""
        assert self.json_path is not None  # noqa: S101
        data = seed.model_dump(mode="json")
        tmp_path = self.json_path.with_suffix(".tmp")
        tmp_path.write_text(json.dumps(data, indent=2, default=str), encoding="utf-8")
        os.replace(tmp_path, self.json_path)
        logger.info("Wrote seed JSON to %s", self.json_path)

    def _write_bq(self, seed: VersionedSeedFile) -> None:
        """Write seed entries to BigQuery."""
        rows = [_entry_to_row(entry, seed.data_version) for entry in seed.entries]
        table = f"{self.bq_dataset}.{BIOLOGIC_SEED_TABLE}"
        assert self.bq_client is not None  # noqa: S101
        self.bq_client.insert_rows(table, rows)
        logger.info("Wrote %d seed rows to %s", len(rows), table)
