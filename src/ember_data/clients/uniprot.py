"""UniProtClient — searches UniProt for biological target records."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, datetime
from typing import Any

from ember_data.models.provenance import SourceProvenance
from ember_data.models.target import Target, TargetType

_UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"

_RATE_LIMIT = 5  # requests/sec


class UniProtClient:
    """Client for the UniProt REST API (uniprotkb).

    Returns :class:`~ember_data.models.target.Target` domain objects. This is
    distinct from :class:`~ember_data.classification.uniprot_resolver.UniProtResolver`
    which returns classification terms for disambiguation.

    Rate limits
    -----------
    - 5 requests/sec (conservative; UniProt allows ~10/sec anonymous).

    Retry
    -----
    - 3 attempts max, exponential backoff: 1s, 2s, 4s.

    Parameters
    ----------
    organism_id:
        NCBI taxonomy ID to restrict searches. Defaults to 9606 (Homo sapiens).
    """

    def __init__(self, organism_id: int = 9606) -> None:
        self._organism_id = organism_id
        self._min_interval: float = 1.0 / _RATE_LIMIT
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Sleep if needed to stay within the configured rate limit."""
        elapsed = time.monotonic() - self._last_request_time
        wait = self._min_interval - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.monotonic()

    def _get(self, url: str) -> tuple[str, dict[str, str]]:
        """Perform a throttled GET and return (body, headers) tuple."""
        self._throttle()
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            headers = {k.lower(): v for k, v in response.headers.items()}
        return body, headers

    def _retry_get(self, url: str, max_attempts: int = 3) -> tuple[str, dict[str, str]]:
        """Call _get with exponential backoff retry on transient errors.

        Retries on URLError or HTTPError with status >= 429 or >= 500.
        Raises the final exception if all attempts fail.
        """
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                return self._get(url)
            except urllib.error.HTTPError as exc:
                if exc.code >= 429 or exc.code >= 500:
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        time.sleep(2 ** attempt)
                    continue
                raise
            except urllib.error.URLError as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
                continue
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _extract_gene_info(
        self, entry: dict[str, Any]
    ) -> tuple[str, list[str]]:
        """Extract primary gene name and synonyms from a UniProt entry.

        Returns (gene_name, synonyms).
        """
        genes = entry.get("genes", [])
        gene_name = ""
        synonyms: list[str] = []
        if genes:
            gene_name_obj = genes[0].get("geneName", {})
            gene_name = gene_name_obj.get("value", "")
            for syn in genes[0].get("synonyms", []):
                val = syn.get("value", "")
                if val:
                    synonyms.append(val)
        return gene_name, synonyms

    def _extract_protein_name(self, entry: dict[str, Any]) -> str:
        """Extract the recommended full protein name from a UniProt entry."""
        protein_desc = entry.get("proteinDescription", {})
        rec_name = protein_desc.get("recommendedName", {})
        full_name_obj = rec_name.get("fullName", {})
        return full_name_obj.get("value", "")

    def _extract_organism(self, entry: dict[str, Any]) -> str:
        """Extract organism scientific name from a UniProt entry."""
        organism = entry.get("organism", {})
        sci_names = organism.get("scientificName", "")
        if sci_names:
            return sci_names
        # Fallback for human
        tax_id = organism.get("taxonId")
        if tax_id == 9606:
            return "Homo sapiens"
        return ""

    def _entry_to_target(self, entry: dict[str, Any]) -> Target | None:
        """Convert a UniProt entry dict to a Target domain object."""
        accession: str = entry.get("primaryAccession", "")
        if not accession:
            return None

        gene_name, gene_synonyms = self._extract_gene_info(entry)
        protein_name = self._extract_protein_name(entry)

        name = gene_name or protein_name or accession
        organism = self._extract_organism(entry) or "Unknown"

        # aliases: gene synonyms; add protein name if different from primary name
        aliases = list(gene_synonyms)
        if protein_name and protein_name != name:
            aliases.append(protein_name)

        return Target(
            id=accession,
            name=name,
            type=TargetType.PROTEIN,
            organism=organism,
            aliases=aliases,
            gene_id=None,
            uniprot_id=accession,
        )

    def _make_provenance(self, accession: str) -> SourceProvenance:
        """Build a SourceProvenance for a UniProt accession."""
        return SourceProvenance(
            source_name="UniProt",
            source_id=accession,
            source_url=f"https://www.uniprot.org/uniprot/{accession}",
            retrieved_at=datetime.now(UTC),
            matched_fields=["gene_name"],
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search_targets(
        self,
        query: str,
        organism_id: int = 9606,
        max_results: int = 10,
    ) -> list[tuple[Target, SourceProvenance]]:
        """Search UniProt for protein targets matching *query*.

        Parameters
        ----------
        query:
            Free-text search string (gene symbol, protein name, etc.).
        organism_id:
            NCBI taxonomy ID. Defaults to 9606 (Homo sapiens).
        max_results:
            Maximum number of results to return.

        Returns
        -------
        list of (Target, SourceProvenance) tuples.
        """
        search_query = f"({query}) AND (organism_id:{organism_id})"
        params = urllib.parse.urlencode({
            "query": search_query,
            "format": "json",
            "size": str(max_results),
        })
        url = f"{_UNIPROT_BASE}/search?{params}"

        try:
            body, _ = self._retry_get(url)
            data = json.loads(body)
        except (urllib.error.URLError, ValueError):
            return []

        results: list[tuple[Target, SourceProvenance]] = []
        for entry in data.get("results", []):
            target = self._entry_to_target(entry)
            if target is None:
                continue
            provenance = self._make_provenance(target.id)
            results.append((target, provenance))

        return results

    def get_target(self, accession: str) -> tuple[Target, SourceProvenance] | None:
        """Fetch a single UniProt entry by accession and return a Target.

        Parameters
        ----------
        accession:
            UniProt accession (e.g. ``"P04626"``).

        Returns
        -------
        (Target, SourceProvenance) tuple, or None if not found.
        """
        url = f"{_UNIPROT_BASE}/{urllib.parse.quote(accession)}?format=json"

        try:
            body, _ = self._retry_get(url)
            entry = json.loads(body)
        except (urllib.error.URLError, urllib.error.HTTPError, ValueError):
            return None

        target = self._entry_to_target(entry)
        if target is None:
            return None

        provenance = self._make_provenance(accession)
        return target, provenance
