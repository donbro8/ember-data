"""ATCResolver — resolves drug names and classes to ATC taxonomy terms."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from ember_data.classification.resolver import ClassificationResolver
from ember_data.classification.spec import DisambiguationRequest, ResolvedTerm

# Path to bundled ATC hierarchy JSON, relative to this file.
_DATA_FILE = Path(__file__).parent / "data" / "atc_hierarchy.json"

# Estimated drug counts by ATC hierarchy level.
_LEVEL_COUNT_ESTIMATES: dict[int, int] = {
    1: 6000,
    2: 2000,
    3: 500,
    4: 50,
    5: 1,
}


def _load_hierarchy() -> tuple[dict[str, dict[str, Any]], dict[str, str]]:
    """Load and index the ATC hierarchy from the bundled JSON file.

    Returns a tuple of:
      - nodes_by_code: dict mapping ATC code -> node dict
      - synonyms: dict mapping lowercase synonym -> ATC code
    """
    with _DATA_FILE.open("r", encoding="utf-8") as fh:
        data = json.load(fh)

    nodes_by_code: dict[str, dict[str, Any]] = {
        node["code"]: node for node in data["nodes"]
    }
    synonyms: dict[str, str] = {
        k.lower(): v for k, v in data.get("synonyms", {}).items()
    }
    return nodes_by_code, synonyms


class ATCResolver(ClassificationResolver):
    """Resolves free-text drug or drug-class names to ATC taxonomy terms.

    Data is loaded once at construction from the bundled
    ``classification/data/atc_hierarchy.json`` file.  No network access is
    performed.

    Resolution strategy
    -------------------
    1. Exact synonym match → confidence 1.0
    2. Exact name match (case-insensitive) → confidence 1.0
    3. Partial / substring match in names and synonyms → confidence 0.8+,
       scaled by how much of the query is covered.

    Results are sorted highest-confidence first.
    """

    def __init__(self) -> None:
        self._nodes, self._synonyms = _load_hierarchy()

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _node_to_term(self, code: str, confidence: float = 1.0) -> ResolvedTerm | None:
        """Convert an ATC code to a ResolvedTerm, or None if code unknown."""
        node = self._nodes.get(code)
        if node is None:
            return None
        return ResolvedTerm(
            taxonomy="ATC",
            identifier=code,
            label=node["name"],
            confidence=confidence,
            synonyms=[
                synonym
                for synonym, target_code in self._synonyms.items()
                if target_code == code
            ],
            parent_id=node.get("parent"),
        )

    def _children_of(self, code: str) -> list[str]:
        """Return direct child codes of a given ATC code."""
        return [
            c for c, node in self._nodes.items() if node.get("parent") == code
        ]

    # ------------------------------------------------------------------
    # ClassificationResolver interface
    # ------------------------------------------------------------------

    def resolve(self, raw_input: str) -> list[ResolvedTerm]:
        """Resolve *raw_input* to ATC terms, sorted by confidence descending.

        Performs case-insensitive exact synonym lookup first, then exact name
        match, then partial substring match across all node names and synonyms.
        """
        query = raw_input.strip().lower()
        if not query:
            return []

        results: dict[str, float] = {}  # code -> best confidence so far

        # 1. Exact synonym match → confidence 1.0
        if query in self._synonyms:
            code = self._synonyms[query]
            results[code] = 1.0

        # 2. Exact node name match (case-insensitive) → confidence 1.0
        for code, node in self._nodes.items():
            if node["name"].lower() == query:
                results[code] = max(results.get(code, 0.0), 1.0)

        # 3. Partial / substring matches → confidence 0.8+
        #    We search both node names and synonym keys.
        if not results:
            # Partial match in synonyms
            for synonym, code in self._synonyms.items():
                if query in synonym or synonym in query:
                    # Score: ratio of overlap
                    overlap = len(set(query.split()) & set(synonym.split()))
                    total = max(len(query.split()), len(synonym.split()))
                    score = 0.8 + 0.15 * (overlap / total if total else 0)
                    results[code] = max(results.get(code, 0.0), score)

            # Partial match in node names
            for code, node in self._nodes.items():
                name_lower = node["name"].lower()
                if query in name_lower or name_lower in query:
                    overlap = len(set(query.split()) & set(name_lower.split()))
                    total = max(len(query.split()), len(name_lower.split()))
                    score = 0.8 + 0.15 * (overlap / total if total else 0)
                    results[code] = max(results.get(code, 0.0), score)

        if not results:
            return []

        terms = []
        for code, confidence in results.items():
            term = self._node_to_term(code, confidence=round(confidence, 4))
            if term is not None:
                terms.append(term)

        # Sort by confidence descending, then by code for determinism.
        terms.sort(key=lambda t: (-t.confidence, t.identifier))
        return terms

    def narrow(self, term: ResolvedTerm) -> list[ResolvedTerm]:
        """Return direct children of *term* in the ATC hierarchy.

        For example, narrowing ``L01XC`` returns all individual monoclonal
        antibody entries (``L01XC01``, ``L01XC02``, …).
        """
        child_codes = self._children_of(term.identifier)
        terms = []
        for code in sorted(child_codes):
            child_term = self._node_to_term(code, confidence=1.0)
            if child_term is not None:
                terms.append(child_term)
        return terms

    def broaden(self, term: ResolvedTerm) -> list[ResolvedTerm]:
        """Return the parent term of *term* in the ATC hierarchy.

        For example, broadening ``L04AB04`` (adalimumab) returns ``L04AB``
        (TNF-alpha inhibitors).  Returns an empty list if already at level 1.
        """
        node = self._nodes.get(term.identifier)
        if node is None:
            return []
        parent_code = node.get("parent")
        if parent_code is None:
            return []
        parent_term = self._node_to_term(parent_code, confidence=1.0)
        if parent_term is None:
            return []
        return [parent_term]

    def disambiguate(
        self, candidates: list[ResolvedTerm]
    ) -> DisambiguationRequest | None:
        """Return a :class:`DisambiguationRequest` when multiple candidates exist.

        Returns ``None`` if zero or one candidate is provided (no ambiguity).
        """
        if len(candidates) <= 1:
            return None
        return DisambiguationRequest(
            raw_input="",
            options=candidates,
            rationale=(
                f"Multiple ATC terms matched ({len(candidates)} candidates). "
                "Please select the intended classification."
            ),
        )

    def estimate_count(self, term: ResolvedTerm) -> int:
        """Return an approximate number of drugs in the ATC subtree of *term*.

        The estimate is based on the hierarchy level of the node:
        level 5 (individual substance) = 1, level 1 (anatomical group) = ~6000.
        """
        node = self._nodes.get(term.identifier)
        if node is None:
            return 0
        level: int = node.get("level", 5)
        return _LEVEL_COUNT_ESTIMATES.get(level, 1)
