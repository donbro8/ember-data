"""MeSHResolver — resolves biomedical condition/indication terms via PubMed E-utilities."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
import xml.etree.ElementTree as ET
from typing import Any

from ember_data.classification.resolver import ClassificationResolver
from ember_data.classification.spec import DisambiguationRequest, ResolvedTerm

_EUTILS_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils"

_RATE_ANON = 3   # requests/sec without API key
_RATE_KEY = 10   # requests/sec with API key


class MeSHResolver(ClassificationResolver):
    """Resolves biomedical condition and indication terms to MeSH descriptors.

    Uses NCBI PubMed E-utilities for live descriptor lookup.

    Rate limits
    -----------
    - Without API key: 3 requests/sec (NCBI policy)
    - With API key: 10 requests/sec (NCBI policy for registered users)

    Parameters
    ----------
    api_key:
        Optional NCBI API key.  Register at https://www.ncbi.nlm.nih.gov/account/
        to raise the rate limit from 3 to 10 requests/sec.
    """

    def __init__(self, api_key: str | None = None) -> None:
        self._api_key = api_key
        rate_limit = _RATE_KEY if api_key else _RATE_ANON
        self._min_interval: float = 1.0 / rate_limit
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

    def _build_url(self, endpoint: str, params: dict[str, str]) -> str:
        """Build a full E-utilities URL, injecting api_key when present."""
        all_params: dict[str, str] = dict(params)
        if self._api_key:
            all_params["api_key"] = self._api_key
        query = urllib.parse.urlencode(all_params)
        return f"{_EUTILS_BASE}/{endpoint}?{query}"

    def _get(self, url: str) -> str:
        """Perform a throttled GET request and return the response body."""
        self._throttle()
        with urllib.request.urlopen(url, timeout=10) as response:
            return response.read().decode("utf-8")

    # ------------------------------------------------------------------
    # E-utilities wrappers
    # ------------------------------------------------------------------

    def _esearch(self, term: str, retmax: int = 10) -> list[str]:
        """Search the MeSH database and return a list of numeric UIDs."""
        url = self._build_url("esearch.fcgi", {
            "db": "mesh",
            "term": term,
            "retmode": "json",
            "retmax": str(retmax),
        })
        data = json.loads(self._get(url))
        return data.get("esearchresult", {}).get("idlist", [])

    def _efetch(self, uid: str) -> str:
        """Fetch raw XML for a MeSH descriptor by its numeric UID."""
        url = self._build_url("efetch.fcgi", {
            "db": "mesh",
            "id": uid,
            "retmode": "xml",
        })
        return self._get(url)

    # ------------------------------------------------------------------
    # Parsing and term building
    # ------------------------------------------------------------------

    def _parse_descriptor(self, xml_text: str) -> dict[str, Any] | None:
        """Parse efetch XML into a descriptor dict.

        Returns keys: ``identifier``, ``label``, ``synonyms``,
        ``tree_numbers``, ``parent_id``.  Returns ``None`` on parse failure.
        """
        try:
            root = ET.fromstring(xml_text)
        except ET.ParseError:
            return None

        record = root.find(".//DescriptorRecord")
        if record is None:
            return None

        uid_elem = record.find("DescriptorUI")
        if uid_elem is None or not uid_elem.text:
            return None
        identifier = uid_elem.text.strip()

        name_elem = record.find(".//DescriptorName/String")
        if name_elem is None or not name_elem.text:
            return None
        label = name_elem.text.strip()

        synonyms: list[str] = []
        for term_elem in record.findall(".//Term/String"):
            text = term_elem.text
            if text and text.strip() != label:
                synonyms.append(text.strip())

        tree_numbers: list[str] = [
            tn.text.strip()
            for tn in record.findall(".//TreeNumber")
            if tn.text
        ]

        # Derive parent_id as the tree-number prefix of the first tree number.
        parent_id: str | None = None
        if tree_numbers:
            parts = tree_numbers[0].rsplit(".", 1)
            if len(parts) == 2:
                parent_id = parts[0]

        return {
            "identifier": identifier,
            "label": label,
            "synonyms": synonyms,
            "tree_numbers": tree_numbers,
            "parent_id": parent_id,
        }

    def _uid_to_term(self, uid: str, confidence: float = 1.0) -> ResolvedTerm | None:
        """Fetch a descriptor by numeric UID and return a ``ResolvedTerm``."""
        xml_text = self._efetch(uid)
        record = self._parse_descriptor(xml_text)
        if record is None:
            return None
        return ResolvedTerm(
            taxonomy="MeSH",
            identifier=record["identifier"],
            label=record["label"],
            confidence=round(confidence, 4),
            synonyms=record["synonyms"],
            parent_id=record.get("parent_id"),
        )

    def _fetch_by_mesh_id(self, mesh_id: str) -> dict[str, Any] | None:
        """Fetch and parse the full descriptor record for a MeSH UI (e.g. ``D001943``)."""
        uids = self._esearch(f"{mesh_id}[MeSH Unique ID]", retmax=1)
        if not uids:
            return None
        xml_text = self._efetch(uids[0])
        return self._parse_descriptor(xml_text)

    def _search_tree_children(self, tree_num: str) -> list[ResolvedTerm]:
        """Return direct children of *tree_num* in the MeSH hierarchy.

        Queries descendants via wildcard, then filters to terms whose tree
        numbers contain exactly one additional dot-segment (direct children).
        """
        uids = self._esearch(f"{tree_num}.*[Tree Number]", retmax=50)
        terms: list[ResolvedTerm] = []
        seen_ids: set[str] = set()
        for uid in uids:
            xml_text = self._efetch(uid)
            record = self._parse_descriptor(xml_text)
            if record is None or record["identifier"] in seen_ids:
                continue
            # Accept only direct children (one segment deeper than tree_num).
            suffix_start = len(tree_num) + 1  # skip the dot
            is_direct_child = any(
                tn.startswith(tree_num + ".")
                and "." not in tn[suffix_start:]
                for tn in record["tree_numbers"]
            )
            if is_direct_child:
                seen_ids.add(record["identifier"])
                terms.append(ResolvedTerm(
                    taxonomy="MeSH",
                    identifier=record["identifier"],
                    label=record["label"],
                    confidence=1.0,
                    synonyms=record["synonyms"],
                    parent_id=record.get("parent_id"),
                ))
        return terms

    def _search_by_tree_number(self, tree_num: str) -> list[ResolvedTerm]:
        """Return descriptors whose tree number exactly equals *tree_num*."""
        uids = self._esearch(f"{tree_num}[Tree Number]", retmax=5)
        terms: list[ResolvedTerm] = []
        seen_ids: set[str] = set()
        for uid in uids:
            xml_text = self._efetch(uid)
            record = self._parse_descriptor(xml_text)
            if record is None or record["identifier"] in seen_ids:
                continue
            seen_ids.add(record["identifier"])
            terms.append(ResolvedTerm(
                taxonomy="MeSH",
                identifier=record["identifier"],
                label=record["label"],
                confidence=1.0,
                synonyms=record["synonyms"],
                parent_id=record.get("parent_id"),
            ))
        return terms

    # ------------------------------------------------------------------
    # ClassificationResolver interface
    # ------------------------------------------------------------------

    def resolve(self, raw_input: str) -> list[ResolvedTerm]:
        """Resolve *raw_input* to MeSH descriptor terms, highest-confidence first.

        Queries E-utilities esearch for matching descriptors, then fetches up
        to 5 full records.  The first result receives confidence 1.0; subsequent
        results are stepped down by 0.1 (minimum 0.5).
        """
        query = raw_input.strip()
        if not query:
            return []

        uids = self._esearch(query, retmax=10)
        if not uids:
            return []

        terms: list[ResolvedTerm] = []
        for i, uid in enumerate(uids[:5]):
            confidence = 1.0 if i == 0 else max(0.5, 1.0 - i * 0.1)
            term = self._uid_to_term(uid, confidence=confidence)
            if term is not None:
                terms.append(term)
        return terms

    def narrow(self, term: ResolvedTerm) -> list[ResolvedTerm]:
        """Return child terms in the MeSH hierarchy.

        Fetches the term's tree numbers via E-utilities and searches for
        direct children in each branch.  Returns an empty list if the term
        has no children or cannot be looked up.
        """
        record = self._fetch_by_mesh_id(term.identifier)
        if record is None:
            return []

        tree_numbers: list[str] = record.get("tree_numbers", [])
        if not tree_numbers:
            return []

        children: list[ResolvedTerm] = []
        seen_ids: set[str] = set()
        for tree_num in tree_numbers:
            for child in self._search_tree_children(tree_num):
                if child.identifier not in seen_ids:
                    seen_ids.add(child.identifier)
                    children.append(child)
        return children

    def broaden(self, term: ResolvedTerm) -> list[ResolvedTerm]:
        """Return parent terms in the MeSH hierarchy.

        Strips the last segment from each tree number of *term* and looks up
        the corresponding parent descriptor(s).  Returns an empty list if
        *term* is already at the top level or cannot be looked up.
        """
        record = self._fetch_by_mesh_id(term.identifier)
        if record is None:
            return []

        tree_numbers: list[str] = record.get("tree_numbers", [])

        parents: list[ResolvedTerm] = []
        seen_ids: set[str] = set()
        for tree_num in tree_numbers:
            parts = tree_num.rsplit(".", 1)
            if len(parts) < 2:
                continue  # top-level node (e.g. "C04") — no parent
            parent_tree = parts[0]
            for parent in self._search_by_tree_number(parent_tree):
                if parent.identifier not in seen_ids:
                    seen_ids.add(parent.identifier)
                    parents.append(parent)
        return parents

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
                f"Multiple MeSH descriptors matched ({len(candidates)} candidates). "
                "Please select the intended indication."
            ),
        )

    def estimate_count(self, term: ResolvedTerm) -> int:
        """Estimate PubMed article count for *term*.

        Searches PubMed using the MeSH identifier as a MeSH Major Topic.
        Returns 0 for non-MeSH terms or when the request fails.
        """
        if term.taxonomy != "MeSH":
            return 0
        url = self._build_url("esearch.fcgi", {
            "db": "pubmed",
            "term": f"{term.identifier}[MeSH Major Topic]",
            "retmode": "json",
            "retmax": "0",
        })
        try:
            data = json.loads(self._get(url))
            count_str = data.get("esearchresult", {}).get("count", "0")
            return int(count_str)
        except (urllib.error.URLError, ValueError, KeyError):
            return 0
