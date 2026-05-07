"""Tests for UniProtResolver — covers exit criteria from TASK-017."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ember_data.classification.spec import DisambiguationRequest, ResolvedTerm
from ember_data.classification.uniprot_resolver import UniProtResolver

# ---------------------------------------------------------------------------
# Mock API response fixtures
# ---------------------------------------------------------------------------

# Minimal UniProt search result entry for ERBB2/HER2 (P04626)
_ERBB2_ENTRY: dict = {
    "primaryAccession": "P04626",
    "uniProtkbId": "ERBB2_HUMAN",
    "genes": [
        {
            "geneName": {"value": "ERBB2"},
            "synonyms": [
                {"value": "HER2"},
                {"value": "NEU"},
            ],
        }
    ],
    "proteinDescription": {
        "recommendedName": {
            "fullName": {
                "value": "Receptor tyrosine-protein kinase erbB-2"
            }
        }
    },
    "comments": [
        {
            "commentType": "SIMILARITY",
            "texts": [
                {"value": "Belongs to the protein kinase superfamily. Tyr protein kinase family. EGF receptor subfamily."}
            ],
        }
    ],
    "dbReferences": [
        {
            "type": "GO",
            "id": "GO:0007169",
            "properties": {"term": "P:transmembrane receptor protein tyrosine kinase signaling pathway"},
        },
        {
            "type": "GO",
            "id": "GO:0005524",
            "properties": {"term": "F:ATP binding"},
        },
    ],
    "organism": {"taxonId": 9606},
}

# A second entry to test multi-result confidence ordering
_EGFR_ENTRY: dict = {
    "primaryAccession": "P00533",
    "uniProtkbId": "EGFR_HUMAN",
    "genes": [
        {
            "geneName": {"value": "EGFR"},
            "synonyms": [{"value": "HER1"}],
        }
    ],
    "proteinDescription": {
        "recommendedName": {
            "fullName": {"value": "Epidermal growth factor receptor"}
        }
    },
    "comments": [
        {
            "commentType": "SIMILARITY",
            "texts": [{"value": "Belongs to the protein kinase superfamily. Tyr protein kinase family. EGF receptor subfamily."}],
        }
    ],
    "dbReferences": [
        {
            "type": "GO",
            "id": "GO:0007169",
            "properties": {"term": "P:transmembrane receptor protein tyrosine kinase signaling pathway"},
        },
    ],
    "organism": {"taxonId": 9606},
}

_SEARCH_SINGLE = {"results": [_ERBB2_ENTRY]}
_SEARCH_TWO = {"results": [_ERBB2_ENTRY, _EGFR_ENTRY]}
_SEARCH_EMPTY = {"results": []}

_COUNT_RESPONSE = {"results": [_ERBB2_ENTRY]}
_COUNT_HEADERS = {"x-total-results": "1", "content-type": "application/json"}


def _make_get(body_dict: dict, headers: dict | None = None):
    """Return a mock _get function that yields (json_body, headers)."""
    import json as _json

    _headers = headers or {"content-type": "application/json"}

    def _get(url: str) -> tuple[str, dict]:
        return _json.dumps(body_dict), _headers

    return _get


# ---------------------------------------------------------------------------
# resolve() — exit criteria
# ---------------------------------------------------------------------------


class TestResolveHER2:
    """Exit criterion: resolve('HER2') → P04626 / ERBB2."""

    def test_resolves_her2_to_P04626(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_SINGLE)):
            results = resolver.resolve("HER2")
        assert results, "resolve('HER2') returned empty list"
        assert results[0].identifier == "P04626"

    def test_resolved_label_is_ERBB2(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_SINGLE)):
            results = resolver.resolve("HER2")
        assert results[0].label == "ERBB2"

    def test_taxonomy_is_UniProt(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_SINGLE)):
            results = resolver.resolve("HER2")
        assert results[0].taxonomy == "UniProt"

    def test_first_result_confidence_is_1(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_SINGLE)):
            results = resolver.resolve("HER2")
        assert results[0].confidence == 1.0

    def test_synonyms_include_HER2(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_SINGLE)):
            results = resolver.resolve("HER2")
        assert "HER2" in results[0].synonyms

    def test_synonyms_include_go_annotations(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_SINGLE)):
            results = resolver.resolve("HER2")
        # At least one GO annotation should appear in synonyms
        go_synonyms = [s for s in results[0].synonyms if s.startswith("GO:")]
        assert go_synonyms, "No GO annotations in synonyms"

    def test_synonyms_include_family(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_SINGLE)):
            results = resolver.resolve("HER2")
        family_synonyms = [s for s in results[0].synonyms if "kinase" in s.lower()]
        assert family_synonyms, "Protein family not in synonyms"

    def test_parent_id_is_go_biological_process(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_SINGLE)):
            results = resolver.resolve("HER2")
        # GO:0007169 is a biological process (P: prefix term)
        assert results[0].parent_id == "GO:0007169"

    def test_alias_resolution_her2_to_erbb2(self) -> None:
        """HER2 is resolved to ERBB2 via the alias map before querying."""
        resolver = UniProtResolver()
        captured_urls: list[str] = []

        def mock_get(url: str) -> tuple[str, dict]:
            captured_urls.append(url)
            import json as _json
            return _json.dumps(_SEARCH_SINGLE), {"content-type": "application/json"}

        with patch.object(resolver, "_get", mock_get):
            resolver.resolve("HER2")

        # The URL should use ERBB2 (the canonical alias), not HER2
        assert any("ERBB2" in url for url in captured_urls), (
            f"Expected ERBB2 in query URL, got: {captured_urls}"
        )

    def test_empty_input_returns_empty(self) -> None:
        assert UniProtResolver().resolve("") == []

    def test_no_results_returns_empty(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_EMPTY)):
            results = resolver.resolve("xyzzy_not_a_protein")
        assert results == []

    def test_multiple_results_have_descending_confidence(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_TWO)):
            results = resolver.resolve("ERBB2")
        assert len(results) == 2
        assert results[0].confidence >= results[1].confidence

    def test_second_result_confidence_below_1(self) -> None:
        resolver = UniProtResolver()
        with patch.object(resolver, "_get", _make_get(_SEARCH_TWO)):
            results = resolver.resolve("ERBB2")
        assert results[1].confidence < 1.0


# ---------------------------------------------------------------------------
# narrow() — protein family siblings
# ---------------------------------------------------------------------------


class TestNarrow:
    def test_narrow_returns_related_proteins(self) -> None:
        resolver = UniProtResolver()
        term = ResolvedTerm(
            taxonomy="UniProt",
            identifier="P04626",
            label="ERBB2",
            confidence=1.0,
        )

        # _fetch_entry returns ERBB2 entry; _search returns EGFR as sibling
        def mock_get(url: str) -> tuple[str, dict]:
            import json as _json
            if "/P04626" in url:
                return _json.dumps(_ERBB2_ENTRY), {}
            return _json.dumps({"results": [_EGFR_ENTRY]}), {}

        with patch.object(resolver, "_get", mock_get):
            siblings = resolver.narrow(term)

        assert isinstance(siblings, list)
        assert all(isinstance(s, ResolvedTerm) for s in siblings)

    def test_narrow_excludes_source_term(self) -> None:
        resolver = UniProtResolver()
        term = ResolvedTerm(
            taxonomy="UniProt",
            identifier="P04626",
            label="ERBB2",
            confidence=1.0,
        )

        def mock_get(url: str) -> tuple[str, dict]:
            import json as _json
            if "/P04626" in url:
                return _json.dumps(_ERBB2_ENTRY), {}
            # Return ERBB2 itself + EGFR in search
            return _json.dumps(_SEARCH_TWO), {}

        with patch.object(resolver, "_get", mock_get):
            siblings = resolver.narrow(term)

        ids = [s.identifier for s in siblings]
        assert "P04626" not in ids, "narrow() should not include source term itself"

    def test_narrow_unknown_term_returns_empty(self) -> None:
        resolver = UniProtResolver()
        term = ResolvedTerm(
            taxonomy="UniProt", identifier="X99999", label="Unknown", confidence=1.0
        )

        def mock_get(url: str) -> tuple[str, dict]:
            import json as _json
            # fetch_entry returns entry without SIMILARITY comment
            entry_no_family = {**_ERBB2_ENTRY, "comments": []}
            return _json.dumps(entry_no_family), {}

        with patch.object(resolver, "_get", mock_get):
            result = resolver.narrow(term)

        assert result == []

    def test_narrow_non_uniprot_term_returns_empty(self) -> None:
        resolver = UniProtResolver()
        term = ResolvedTerm(
            taxonomy="MeSH", identifier="D001943", label="Breast Neoplasms", confidence=1.0
        )
        result = resolver.narrow(term)
        assert result == []


# ---------------------------------------------------------------------------
# broaden()
# ---------------------------------------------------------------------------


class TestBroaden:
    def test_broaden_returns_empty_list(self) -> None:
        """broaden() is simplified — always returns empty list."""
        resolver = UniProtResolver()
        term = ResolvedTerm(
            taxonomy="UniProt", identifier="P04626", label="ERBB2", confidence=1.0
        )
        assert resolver.broaden(term) == []


# ---------------------------------------------------------------------------
# disambiguate()
# ---------------------------------------------------------------------------


class TestDisambiguate:
    def test_single_candidate_returns_none(self) -> None:
        resolver = UniProtResolver()
        term = ResolvedTerm(
            taxonomy="UniProt", identifier="P04626", label="ERBB2", confidence=1.0
        )
        assert resolver.disambiguate([term]) is None

    def test_empty_candidates_returns_none(self) -> None:
        assert UniProtResolver().disambiguate([]) is None

    def test_multiple_candidates_returns_request(self) -> None:
        resolver = UniProtResolver()
        terms = [
            ResolvedTerm(taxonomy="UniProt", identifier="P04626", label="ERBB2", confidence=1.0),
            ResolvedTerm(taxonomy="UniProt", identifier="P00533", label="EGFR", confidence=0.9),
        ]
        result = resolver.disambiguate(terms)
        assert isinstance(result, DisambiguationRequest)
        assert len(result.options) == 2

    def test_disambiguation_rationale_mentions_uniprot(self) -> None:
        resolver = UniProtResolver()
        terms = [
            ResolvedTerm(taxonomy="UniProt", identifier="P04626", label="ERBB2", confidence=1.0),
            ResolvedTerm(taxonomy="UniProt", identifier="P00533", label="EGFR", confidence=0.9),
        ]
        result = resolver.disambiguate(terms)
        assert result is not None
        assert "UniProt" in result.rationale


# ---------------------------------------------------------------------------
# estimate_count()
# ---------------------------------------------------------------------------


class TestEstimateCount:
    def test_returns_total_results_from_header(self) -> None:
        resolver = UniProtResolver()
        term = ResolvedTerm(
            taxonomy="UniProt", identifier="P04626", label="ERBB2", confidence=1.0
        )
        with patch.object(resolver, "_get", _make_get(_COUNT_RESPONSE, _COUNT_HEADERS)):
            count = resolver.estimate_count(term)
        assert count == 1

    def test_falls_back_to_results_length_without_header(self) -> None:
        resolver = UniProtResolver()
        term = ResolvedTerm(
            taxonomy="UniProt", identifier="P04626", label="ERBB2", confidence=1.0
        )
        # No x-total-results header → falls back to len(results)
        with patch.object(resolver, "_get", _make_get(_SEARCH_SINGLE, {})):
            count = resolver.estimate_count(term)
        assert count == 1

    def test_non_uniprot_taxonomy_returns_0(self) -> None:
        resolver = UniProtResolver()
        term = ResolvedTerm(
            taxonomy="MeSH", identifier="D001943", label="Breast Neoplasms", confidence=1.0
        )
        assert resolver.estimate_count(term) == 0


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_default_rate_is_5_per_sec(self) -> None:
        resolver = UniProtResolver()
        assert resolver._min_interval == pytest.approx(1.0 / 5, rel=1e-3)

    def test_default_organism_is_human(self) -> None:
        resolver = UniProtResolver()
        assert resolver._organism_id == 9606

    def test_custom_organism_id(self) -> None:
        resolver = UniProtResolver(organism_id=10090)  # mouse
        assert resolver._organism_id == 10090


# ---------------------------------------------------------------------------
# Alias map coverage
# ---------------------------------------------------------------------------


class TestAliasResolution:
    @pytest.mark.parametrize("alias,expected_canonical", [
        ("HER2", "ERBB2"),
        ("HER-2", "ERBB2"),
        ("NEU", "ERBB2"),
        ("PD-1", "PDCD1"),
        ("PD-L1", "CD274"),
        ("PDL1", "CD274"),
        ("CTLA-4", "CTLA4"),
    ])
    def test_alias_resolves_to_canonical(
        self, alias: str, expected_canonical: str
    ) -> None:
        resolver = UniProtResolver()
        assert resolver._resolve_alias(alias) == expected_canonical

    def test_unknown_alias_returns_input_unchanged(self) -> None:
        resolver = UniProtResolver()
        assert resolver._resolve_alias("MYUNKNOWNGENE") == "MYUNKNOWNGENE"
