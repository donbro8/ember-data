"""UniProtResolver — resolves protein and gene targets via UniProt REST API."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from typing import Any

from ember_data.classification.resolver import ClassificationResolver
from ember_data.classification.spec import DisambiguationRequest, ResolvedTerm

_UNIPROT_BASE = "https://rest.uniprot.org/uniprotkb"

# Rate limit: 5 requests/sec (conservative; UniProt allows ~10/sec anonymous)
_RATE_LIMIT = 5

# Common alias map: well-known name → canonical gene symbol used in UniProt queries
_ALIAS_MAP: dict[str, str] = {
    "HER2": "ERBB2",
    "HER-2": "ERBB2",
    "NEU": "ERBB2",
    "EGFR": "EGFR",
    "HER1": "EGFR",
    "HER3": "ERBB3",
    "HER4": "ERBB4",
    "VEGFR2": "KDR",
    "CD20": "MS4A1",
    "PD-1": "PDCD1",
    "PDL1": "CD274",
    "PD-L1": "CD274",
    "CTLA4": "CTLA4",
    "CTLA-4": "CTLA4",
    "BCR-ABL": "ABL1",
    "p53": "TP53",
    "RB": "RB1",
    "BRCA": "BRCA1",
}


class UniProtResolver(ClassificationResolver):
    """Resolves protein and gene targets to UniProt accessions.

    Uses the UniProt REST API (https://rest.uniprot.org/uniprotkb/) for
    live protein lookup.  Supports alias resolution for common target names
    (e.g. ``"HER2"`` → ``"ERBB2"`` / ``"P04626"``).

    Rate limits
    -----------
    - 5 requests/sec (anonymous; conservative relative to UniProt's ~10/sec
      allowance to avoid hammering the service).

    Parameters
    ----------
    organism_id:
        NCBI taxonomy ID to restrict searches to a specific organism.
        Defaults to ``9606`` (human).
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

    def _search(self, query: str, size: int = 5) -> tuple[list[dict[str, Any]], int]:
        """Query the UniProt search endpoint.

        Returns a ``(results, total_count)`` tuple where ``total_count``
        comes from the ``x-total-results`` response header when available.
        """
        params = urllib.parse.urlencode({
            "query": query,
            "format": "json",
            "size": str(size),
        })
        url = f"{_UNIPROT_BASE}/search?{params}"
        try:
            body, headers = self._get(url)
            data = json.loads(body)
            results: list[dict[str, Any]] = data.get("results", [])
            total_str = headers.get("x-total-results", "")
            total = int(total_str) if total_str.isdigit() else len(results)
            return results, total
        except (urllib.error.URLError, ValueError, KeyError):
            return [], 0

    def _fetch_entry(self, accession: str) -> dict[str, Any] | None:
        """Fetch a full UniProt entry by accession."""
        url = f"{_UNIPROT_BASE}/{urllib.parse.quote(accession)}?format=json"
        try:
            body, _ = self._get(url)
            return json.loads(body)
        except (urllib.error.URLError, ValueError):
            return None

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _resolve_alias(self, name: str) -> str:
        """Map a common alias to its canonical gene symbol, if known."""
        return _ALIAS_MAP.get(name, _ALIAS_MAP.get(name.upper(), name))

    def _build_query(self, gene_name: str, exact: bool = True) -> str:
        """Build a UniProt query string for a gene name."""
        field = "gene_exact" if exact else "gene"
        organism_clause = f" AND (organism_id:{self._organism_id})"
        return f"({field}:{gene_name}){organism_clause}"

    def _extract_go_terms(self, entry: dict[str, Any]) -> list[str]:
        """Extract GO annotation strings from a UniProt entry."""
        go_terms: list[str] = []
        for ref in entry.get("dbReferences", []):
            if ref.get("type") == "GO":
                term = ref.get("properties", {}).get("term", "")
                go_id = ref.get("id", "")
                if term and go_id:
                    go_terms.append(f"{go_id}: {term}")
        return go_terms

    def _extract_family(self, entry: dict[str, Any]) -> str | None:
        """Extract protein family string from a UniProt entry's comments."""
        for comment in entry.get("comments", []):
            if comment.get("commentType") == "SIMILARITY":
                texts = comment.get("texts", [])
                if texts:
                    return texts[0].get("value")
        return None

    def _find_go_biological_process_id(self, entry: dict[str, Any]) -> str | None:
        """Return the first GO Biological Process term ID, or None."""
        for ref in entry.get("dbReferences", []):
            if ref.get("type") == "GO":
                term = ref.get("properties", {}).get("term", "")
                if term.startswith("P:"):  # Biological Process prefix
                    return ref.get("id")
        return None

    def _entry_to_term(
        self,
        entry: dict[str, Any],
        confidence: float = 1.0,
    ) -> ResolvedTerm | None:
        """Convert a UniProt search result entry to a ``ResolvedTerm``."""
        accession = entry.get("primaryAccession", "")
        if not accession:
            return None

        # Primary gene name
        genes = entry.get("genes", [])
        gene_name = ""
        gene_synonyms: list[str] = []
        if genes:
            gene_name_obj = genes[0].get("geneName", {})
            gene_name = gene_name_obj.get("value", "")
            for syn in genes[0].get("synonyms", []):
                val = syn.get("value", "")
                if val:
                    gene_synonyms.append(val)

        # Protein name
        protein_desc = entry.get("proteinDescription", {})
        rec_name = protein_desc.get("recommendedName", {})
        full_name_obj = rec_name.get("fullName", {})
        protein_name = full_name_obj.get("value", "")

        label = gene_name or protein_name or accession

        # Synonyms: gene synonyms + GO annotations + family
        synonyms: list[str] = list(gene_synonyms)
        if protein_name and protein_name != label:
            synonyms.append(protein_name)

        # GO annotations
        go_terms = self._extract_go_terms(entry)
        synonyms.extend(go_terms[:5])  # cap to keep synonyms manageable

        # Protein family
        family = self._extract_family(entry)
        if family:
            synonyms.append(family)

        # parent_id: first GO Biological Process term ID if available
        parent_id = self._find_go_biological_process_id(entry)

        return ResolvedTerm(
            taxonomy="UniProt",
            identifier=accession,
            label=label,
            confidence=round(confidence, 4),
            synonyms=synonyms,
            parent_id=parent_id,
        )

    # ------------------------------------------------------------------
    # ClassificationResolver interface
    # ------------------------------------------------------------------

    def resolve(self, raw_input: str) -> list[ResolvedTerm]:
        """Resolve *raw_input* to UniProt protein terms, highest-confidence first.

        Applies alias resolution (e.g. ``"HER2"`` → ``"ERBB2"``), then tries
        ``gene_exact:{name}`` first, falling back to ``gene:{name}`` when no
        exact results are found.  Returns an ordered list (highest-confidence
        first); empty when no match is found.
        """
        query = raw_input.strip()
        if not query:
            return []

        canonical = self._resolve_alias(query)

        # Try exact gene name first, then broad gene search
        results, _ = self._search(self._build_query(canonical, exact=True), size=5)
        if not results:
            results, _ = self._search(self._build_query(canonical, exact=False), size=5)

        if not results:
            return []

        terms: list[ResolvedTerm] = []
        for i, entry in enumerate(results[:5]):
            confidence = 1.0 if i == 0 else max(0.5, 1.0 - i * 0.1)
            term = self._entry_to_term(entry, confidence=confidence)
            if term is not None:
                terms.append(term)
        return terms

    def narrow(self, term: ResolvedTerm) -> list[ResolvedTerm]:
        """Return related proteins in the same protein family as *term*.

        Fetches the full entry to extract its protein family, then searches
        UniProt for other proteins in that family.  Returns an empty list when
        the family cannot be determined or no siblings are found.
        """
        if term.taxonomy != "UniProt":
            return []

        entry = self._fetch_entry(term.identifier)
        if entry is None:
            return []

        family = self._extract_family(entry)
        if not family:
            return []

        # Search for proteins in the same family
        query = f'(family:"{family}") AND (organism_id:{self._organism_id})'
        results, _ = self._search(query, size=10)

        narrowed: list[ResolvedTerm] = []
        seen: set[str] = {term.identifier}
        for entry_item in results:
            accession = entry_item.get("primaryAccession", "")
            if accession in seen:
                continue
            seen.add(accession)
            child = self._entry_to_term(entry_item, confidence=1.0)
            if child is not None:
                narrowed.append(child)
        return narrowed

    def broaden(self, term: ResolvedTerm) -> list[ResolvedTerm]:
        """Return broader terms by organism or family level.

        For human proteins (organism_id=9606), returns an empty list —
        there is no simple parent hierarchy in UniProt to traverse.
        For non-human queries, also returns an empty list (simplified).
        """
        return []

    def disambiguate(self, candidates: list[ResolvedTerm]) -> DisambiguationRequest | None:
        """Return a :class:`DisambiguationRequest` when multiple candidates exist.

        Returns ``None`` for zero or one candidate.
        """
        if len(candidates) <= 1:
            return None
        return DisambiguationRequest(
            raw_input="",
            options=candidates,
            rationale=(
                f"Multiple UniProt entries matched ({len(candidates)} candidates). "
                "Please select the intended protein target."
            ),
        )

    def estimate_count(self, term: ResolvedTerm) -> int:
        """Estimate the number of UniProt entries related to *term*.

        Queries UniProt for the accession and returns the ``x-total-results``
        header count.  Returns 0 for non-UniProt terms or on request failure.
        """
        if term.taxonomy != "UniProt":
            return 0
        query = f"(accession:{term.identifier})"
        try:
            _, total = self._search(query, size=1)
            return total
        except Exception:
            return 0
