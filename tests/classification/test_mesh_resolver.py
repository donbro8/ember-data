"""Tests for MeSHResolver — covers all exit criteria from TASK-016."""

from __future__ import annotations

from unittest.mock import patch

import pytest

from ember_data.classification.mesh_resolver import MeSHResolver
from ember_data.classification.spec import DisambiguationRequest, ResolvedTerm

# ---------------------------------------------------------------------------
# Mock XML fixtures
# ---------------------------------------------------------------------------

_BREAST_CANCER_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<DescriptorRecordSet>
  <DescriptorRecord DescriptorClass="1">
    <DescriptorUI>D001943</DescriptorUI>
    <DescriptorName>
      <String>Breast Neoplasms</String>
    </DescriptorName>
    <TreeNumberList>
      <TreeNumber>C04.588.180</TreeNumber>
    </TreeNumberList>
    <ConceptList>
      <Concept PreferredConceptYN="Y">
        <ConceptUI>M0002751</ConceptUI>
        <ConceptName>
          <String>Breast Neoplasms</String>
        </ConceptName>
        <TermList>
          <Term ConceptPreferredTermYN="Y">
            <TermUI>T003767</TermUI>
            <String>Breast Neoplasms</String>
          </Term>
          <Term>
            <TermUI>T003768</TermUI>
            <String>Breast Cancer</String>
          </Term>
        </TermList>
      </Concept>
    </ConceptList>
  </DescriptorRecord>
</DescriptorRecordSet>
"""

# D009369 — Neoplasms (parent of Breast Neoplasms' grandparent tree branch)
_NEOPLASMS_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<DescriptorRecordSet>
  <DescriptorRecord DescriptorClass="1">
    <DescriptorUI>D009369</DescriptorUI>
    <DescriptorName>
      <String>Neoplasms</String>
    </DescriptorName>
    <TreeNumberList>
      <TreeNumber>C04</TreeNumber>
    </TreeNumberList>
    <ConceptList>
      <Concept PreferredConceptYN="Y">
        <ConceptUI>M0014457</ConceptUI>
        <ConceptName>
          <String>Neoplasms</String>
        </ConceptName>
        <TermList>
          <Term ConceptPreferredTermYN="Y">
            <TermUI>T026527</TermUI>
            <String>Neoplasms</String>
          </Term>
          <Term>
            <TermUI>T026528</TermUI>
            <String>Tumors</String>
          </Term>
        </TermList>
      </Concept>
    </ConceptList>
  </DescriptorRecord>
</DescriptorRecordSet>
"""

# D001301 — Breast Neoplasms, Male (direct child of D001943 in C04.588.180)
_BREAST_MALE_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<DescriptorRecordSet>
  <DescriptorRecord DescriptorClass="1">
    <DescriptorUI>D001301</DescriptorUI>
    <DescriptorName>
      <String>Breast Neoplasms, Male</String>
    </DescriptorName>
    <TreeNumberList>
      <TreeNumber>C04.588.180.390</TreeNumber>
    </TreeNumberList>
    <ConceptList>
      <Concept PreferredConceptYN="Y">
        <ConceptUI>M0002499</ConceptUI>
        <ConceptName>
          <String>Breast Neoplasms, Male</String>
        </ConceptName>
        <TermList>
          <Term ConceptPreferredTermYN="Y">
            <TermUI>T003266</TermUI>
            <String>Breast Neoplasms, Male</String>
          </Term>
        </TermList>
      </Concept>
    </ConceptList>
  </DescriptorRecord>
</DescriptorRecordSet>
"""

# A top-level descriptor with no parent tree segment.
_TOP_LEVEL_XML = """\
<?xml version="1.0" encoding="UTF-8"?>
<DescriptorRecordSet>
  <DescriptorRecord DescriptorClass="1">
    <DescriptorUI>D009369</DescriptorUI>
    <DescriptorName>
      <String>Neoplasms</String>
    </DescriptorName>
    <TreeNumberList>
      <TreeNumber>C04</TreeNumber>
    </TreeNumberList>
    <ConceptList>
      <Concept PreferredConceptYN="Y">
        <ConceptUI>M0014457</ConceptUI>
        <ConceptName><String>Neoplasms</String></ConceptName>
        <TermList>
          <Term ConceptPreferredTermYN="Y">
            <TermUI>T026527</TermUI>
            <String>Neoplasms</String>
          </Term>
        </TermList>
      </Concept>
    </ConceptList>
  </DescriptorRecord>
</DescriptorRecordSet>
"""

_ESEARCH_PUBMED_COUNT = '{"esearchresult": {"count": "150000", "idlist": []}}'


# ---------------------------------------------------------------------------
# resolve() — exit criteria
# ---------------------------------------------------------------------------


class TestResolveBreastCancer:
    def test_resolves_to_D001943(self) -> None:
        resolver = MeSHResolver()
        with patch.object(resolver, "_esearch", return_value=["68007980"]), \
             patch.object(resolver, "_efetch", return_value=_BREAST_CANCER_XML):
            results = resolver.resolve("breast cancer")
        assert results, "resolve('breast cancer') returned empty list"
        assert results[0].identifier == "D001943"

    def test_taxonomy_is_MeSH(self) -> None:
        resolver = MeSHResolver()
        with patch.object(resolver, "_esearch", return_value=["68007980"]), \
             patch.object(resolver, "_efetch", return_value=_BREAST_CANCER_XML):
            results = resolver.resolve("breast cancer")
        assert results[0].taxonomy == "MeSH"

    def test_first_result_confidence_is_1(self) -> None:
        resolver = MeSHResolver()
        with patch.object(resolver, "_esearch", return_value=["68007980"]), \
             patch.object(resolver, "_efetch", return_value=_BREAST_CANCER_XML):
            results = resolver.resolve("breast cancer")
        assert results[0].confidence == 1.0

    def test_label_contains_breast(self) -> None:
        resolver = MeSHResolver()
        with patch.object(resolver, "_esearch", return_value=["68007980"]), \
             patch.object(resolver, "_efetch", return_value=_BREAST_CANCER_XML):
            results = resolver.resolve("breast cancer")
        assert "breast" in results[0].label.lower()

    def test_synonyms_include_breast_cancer(self) -> None:
        resolver = MeSHResolver()
        with patch.object(resolver, "_esearch", return_value=["68007980"]), \
             patch.object(resolver, "_efetch", return_value=_BREAST_CANCER_XML):
            results = resolver.resolve("breast cancer")
        synonyms_lower = [s.lower() for s in results[0].synonyms]
        assert "breast cancer" in synonyms_lower

    def test_empty_input_returns_empty(self) -> None:
        assert MeSHResolver().resolve("") == []

    def test_no_matches_returns_empty(self) -> None:
        resolver = MeSHResolver()
        with patch.object(resolver, "_esearch", return_value=[]):
            assert resolver.resolve("xyzzy_not_a_condition") == []

    def test_multiple_results_have_descending_confidence(self) -> None:
        resolver = MeSHResolver()
        with patch.object(resolver, "_esearch", return_value=["68007980", "68009369"]), \
             patch.object(resolver, "_efetch", side_effect=[_BREAST_CANCER_XML, _NEOPLASMS_XML]):
            results = resolver.resolve("breast cancer")
        assert len(results) == 2
        assert results[0].confidence >= results[1].confidence


# ---------------------------------------------------------------------------
# narrow() — exit criteria
# ---------------------------------------------------------------------------


class TestNarrow:
    def test_narrow_returns_child_terms(self) -> None:
        resolver = MeSHResolver()
        term = ResolvedTerm(
            taxonomy="MeSH",
            identifier="D001943",
            label="Breast Neoplasms",
            confidence=1.0,
        )

        def mock_esearch(query: str, retmax: int = 10) -> list[str]:
            if "MeSH Unique ID" in query:
                return ["68007980"]
            if ".*[Tree Number]" in query:
                return ["68001234"]
            return []

        def mock_efetch(uid: str) -> str:
            return _BREAST_CANCER_XML if uid == "68007980" else _BREAST_MALE_XML

        with patch.object(resolver, "_esearch", side_effect=mock_esearch), \
             patch.object(resolver, "_efetch", side_effect=mock_efetch):
            children = resolver.narrow(term)

        assert children, "narrow() returned empty list"
        assert all(isinstance(c, ResolvedTerm) for c in children)
        assert all(c.taxonomy == "MeSH" for c in children)

    def test_narrow_returns_correct_child_id(self) -> None:
        resolver = MeSHResolver()
        term = ResolvedTerm(
            taxonomy="MeSH",
            identifier="D001943",
            label="Breast Neoplasms",
            confidence=1.0,
        )

        def mock_esearch(query: str, retmax: int = 10) -> list[str]:
            if "MeSH Unique ID" in query:
                return ["68007980"]
            if ".*[Tree Number]" in query:
                return ["68001234"]
            return []

        def mock_efetch(uid: str) -> str:
            return _BREAST_CANCER_XML if uid == "68007980" else _BREAST_MALE_XML

        with patch.object(resolver, "_esearch", side_effect=mock_esearch), \
             patch.object(resolver, "_efetch", side_effect=mock_efetch):
            children = resolver.narrow(term)

        child_ids = [c.identifier for c in children]
        assert "D001301" in child_ids

    def test_narrow_unknown_term_returns_empty(self) -> None:
        resolver = MeSHResolver()
        term = ResolvedTerm(
            taxonomy="MeSH", identifier="D999999", label="Unknown", confidence=1.0
        )
        with patch.object(resolver, "_esearch", return_value=[]):
            children = resolver.narrow(term)
        assert children == []


# ---------------------------------------------------------------------------
# broaden() — exit criteria
# ---------------------------------------------------------------------------


class TestBroaden:
    def test_broaden_returns_parent_term(self) -> None:
        resolver = MeSHResolver()
        term = ResolvedTerm(
            taxonomy="MeSH",
            identifier="D001943",
            label="Breast Neoplasms",
            confidence=1.0,
        )

        def mock_esearch(query: str, retmax: int = 10) -> list[str]:
            if "MeSH Unique ID" in query:
                return ["68007980"]
            if "[Tree Number]" in query:
                return ["68009369"]
            return []

        def mock_efetch(uid: str) -> str:
            return _BREAST_CANCER_XML if uid == "68007980" else _NEOPLASMS_XML

        with patch.object(resolver, "_esearch", side_effect=mock_esearch), \
             patch.object(resolver, "_efetch", side_effect=mock_efetch):
            parents = resolver.broaden(term)

        assert parents, "broaden() returned empty list"
        assert all(isinstance(p, ResolvedTerm) for p in parents)
        assert all(p.taxonomy == "MeSH" for p in parents)

    def test_broaden_returns_correct_parent_id(self) -> None:
        resolver = MeSHResolver()
        term = ResolvedTerm(
            taxonomy="MeSH",
            identifier="D001943",
            label="Breast Neoplasms",
            confidence=1.0,
        )

        def mock_esearch(query: str, retmax: int = 10) -> list[str]:
            if "MeSH Unique ID" in query:
                return ["68007980"]
            if "[Tree Number]" in query and ".*" not in query:
                return ["68009369"]
            return []

        def mock_efetch(uid: str) -> str:
            return _BREAST_CANCER_XML if uid == "68007980" else _NEOPLASMS_XML

        with patch.object(resolver, "_esearch", side_effect=mock_esearch), \
             patch.object(resolver, "_efetch", side_effect=mock_efetch):
            parents = resolver.broaden(term)

        parent_ids = [p.identifier for p in parents]
        assert "D009369" in parent_ids

    def test_broaden_top_level_returns_empty(self) -> None:
        resolver = MeSHResolver()
        term = ResolvedTerm(
            taxonomy="MeSH", identifier="D009369", label="Neoplasms", confidence=1.0
        )
        with patch.object(resolver, "_esearch", return_value=["68009369"]), \
             patch.object(resolver, "_efetch", return_value=_TOP_LEVEL_XML):
            parents = resolver.broaden(term)
        assert parents == []

    def test_broaden_unknown_term_returns_empty(self) -> None:
        resolver = MeSHResolver()
        term = ResolvedTerm(
            taxonomy="MeSH", identifier="D999999", label="Unknown", confidence=1.0
        )
        with patch.object(resolver, "_esearch", return_value=[]):
            parents = resolver.broaden(term)
        assert parents == []


# ---------------------------------------------------------------------------
# disambiguate()
# ---------------------------------------------------------------------------


class TestDisambiguate:
    def test_single_candidate_returns_none(self) -> None:
        resolver = MeSHResolver()
        term = ResolvedTerm(
            taxonomy="MeSH", identifier="D001943", label="Breast Neoplasms", confidence=1.0
        )
        assert resolver.disambiguate([term]) is None

    def test_empty_candidates_returns_none(self) -> None:
        assert MeSHResolver().disambiguate([]) is None

    def test_multiple_candidates_returns_request(self) -> None:
        resolver = MeSHResolver()
        terms = [
            ResolvedTerm(taxonomy="MeSH", identifier="D001943", label="Breast Neoplasms", confidence=1.0),
            ResolvedTerm(taxonomy="MeSH", identifier="D009369", label="Neoplasms", confidence=0.9),
        ]
        result = resolver.disambiguate(terms)
        assert isinstance(result, DisambiguationRequest)
        assert len(result.options) == 2


# ---------------------------------------------------------------------------
# estimate_count()
# ---------------------------------------------------------------------------


class TestEstimateCount:
    def test_returns_pubmed_count(self) -> None:
        resolver = MeSHResolver()
        term = ResolvedTerm(
            taxonomy="MeSH", identifier="D001943", label="Breast Neoplasms", confidence=1.0
        )
        with patch.object(resolver, "_get", return_value=_ESEARCH_PUBMED_COUNT):
            count = resolver.estimate_count(term)
        assert count == 150_000

    def test_non_mesh_taxonomy_returns_0(self) -> None:
        resolver = MeSHResolver()
        term = ResolvedTerm(
            taxonomy="ATC", identifier="L04AB04", label="adalimumab", confidence=1.0
        )
        assert resolver.estimate_count(term) == 0


# ---------------------------------------------------------------------------
# Rate limiting
# ---------------------------------------------------------------------------


class TestRateLimiting:
    def test_default_rate_is_3_per_sec(self) -> None:
        resolver = MeSHResolver()
        assert resolver._min_interval == pytest.approx(1.0 / 3, rel=1e-3)

    def test_api_key_rate_is_10_per_sec(self) -> None:
        resolver = MeSHResolver(api_key="test-key")
        assert resolver._min_interval == pytest.approx(1.0 / 10, rel=1e-3)

    def test_api_key_included_in_url(self) -> None:
        resolver = MeSHResolver(api_key="my-api-key")
        url = resolver._build_url("esearch.fcgi", {"db": "mesh", "term": "test"})
        assert "api_key=my-api-key" in url

    def test_no_api_key_omitted_from_url(self) -> None:
        resolver = MeSHResolver()
        url = resolver._build_url("esearch.fcgi", {"db": "mesh", "term": "test"})
        assert "api_key" not in url
