"""FDA biologic discovery provider.

Queries BigQuery FDA drug labels to find recently approved biologics
not already present in the seed dataset.
"""

from __future__ import annotations

import logging
import unicodedata
from datetime import UTC, date, datetime

from ember_data.bigquery.client import BigQueryClient
from ember_data.bigquery.datasets import FDA_DRUG_DATASET, MANAGED_FDA_TABLE
from ember_data.seed.enrichment_log import EnrichmentAction, EnrichmentLogEntry
from ember_data.seed.schema import BiologicEntry

logger = logging.getLogger(__name__)


def _normalize_name(name: str) -> str:
    """NFC-normalize and lowercase a drug name for comparison."""
    return unicodedata.normalize("NFC", name).strip().lower()


def _build_fda_biologics_query(
    managed_dataset: str | None = None,
    limit: int = 500,
) -> str:
    """Build a SQL query to find biologic products in FDA drug labels.

    Args:
        managed_dataset: If provided, query the managed cache table instead
            of the public dataset.
        limit: Maximum number of results.

    Returns:
        SQL query string.
    """
    if managed_dataset is not None:
        table = f"`{managed_dataset}.{MANAGED_FDA_TABLE}`"
    else:
        table = f"`{FDA_DRUG_DATASET.dataset_id}.drug_label`"

    return f"""\
SELECT
    openfda_generic_name,
    openfda_brand_name,
    openfda_manufacturer_name,
    openfda_product_type
FROM {table}
WHERE LOWER(openfda_product_type) LIKE '%bla%'
   OR LOWER(openfda_product_type) LIKE '%biologic%'
LIMIT {limit}"""


def _infer_category(generic_name: str) -> str:
    """Infer biologic category from the generic name where possible."""
    lower = generic_name.lower()
    # mAb suffix convention: -mab
    if lower.endswith("mab") or "-mab" in lower:
        return "mAb"
    # ADC keywords
    if "vedotin" in lower or "emtansine" in lower or "ozogamicin" in lower:
        return "adc"
    # Fusion proteins: -cept suffix
    if lower.endswith("cept") or "-cept" in lower:
        return "fusion_protein"
    # Insulins
    if "insulin" in lower:
        return "insulin"
    # Interferons
    if "interferon" in lower or lower.startswith("peginterferon"):
        return "interferon"
    # EPO
    if "epoetin" in lower or "darbepoetin" in lower:
        return "epo"
    # G-CSF
    if "filgrastim" in lower or "pegfilgrastim" in lower:
        return "gcsf"
    # Enzymes: -ase suffix
    if lower.endswith("ase"):
        return "enzyme"
    return "other"


class FDABiologicDiscovery:
    """Discovers new biologics from FDA drug label data via BigQuery.

    Queries FDA drug labels for products approved under BLA (Biologics
    License Application) and returns entries not already present in the
    seed dataset.

    Args:
        client: BigQuery client instance for executing queries.
        managed_dataset: Optional managed dataset name. When provided,
            queries the pre-flattened cache table instead of the public
            dataset.
    """

    def __init__(
        self,
        client: BigQueryClient,
        managed_dataset: str | None = None,
    ) -> None:
        self._client = client
        self._managed_dataset = managed_dataset

    def discover(
        self,
        existing_entries: list[BiologicEntry],
    ) -> tuple[list[BiologicEntry], list[EnrichmentLogEntry]]:
        """Discover new biologics not in the existing seed dataset.

        Args:
            existing_entries: Current seed dataset entries used to
                deduplicate results.

        Returns:
            A tuple of (new_entries, log_entries) where new_entries are
            BiologicEntry objects for newly discovered biologics and
            log_entries record each discovery action.
        """
        existing_names: set[str] = {
            _normalize_name(e.drug_name) for e in existing_entries
        }

        sql = _build_fda_biologics_query(
            managed_dataset=self._managed_dataset,
        )

        try:
            rows = self._client.query_with_params(sql)
        except Exception:
            logger.warning("FDA biologic discovery query failed", exc_info=True)
            return [], []

        if not rows:
            return [], []

        new_entries: list[BiologicEntry] = []
        log_entries: list[EnrichmentLogEntry] = []

        for row in rows:
            generic_name: str = row.get("openfda_generic_name", "") or ""
            if not generic_name.strip():
                continue

            normalized = _normalize_name(generic_name)
            if normalized in existing_names:
                continue

            # Avoid duplicates within the same discovery batch.
            existing_names.add(normalized)

            brand_raw: str = row.get("openfda_brand_name", "") or ""
            brand_names = (
                [b.strip() for b in brand_raw.split(", ") if b.strip()]
                if brand_raw
                else []
            )

            manufacturer: str = row.get("openfda_manufacturer_name", "") or ""
            category = _infer_category(generic_name)

            entry = BiologicEntry(
                drug_name=generic_name.strip(),
                brand_names=brand_names,
                originator=manufacturer.strip(),
                target_antigen="",
                modality=category,
                category=category,
                last_updated=date.today(),
                source="enriched_fda",
                revenue_year=None,
            )
            new_entries.append(entry)

            log_entries.append(
                EnrichmentLogEntry(
                    timestamp=datetime.now(UTC),
                    action=EnrichmentAction.NEW_ENTRY,
                    drug_name=generic_name.strip(),
                    field_changed="drug_name",
                    old_value=None,
                    new_value=generic_name.strip(),
                    source="bigquery_fda",
                    confidence="medium",
                )
            )

        logger.info(
            "FDA biologic discovery found %d new entries", len(new_entries)
        )
        return new_entries, log_entries
