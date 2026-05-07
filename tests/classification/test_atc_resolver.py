"""Tests for ATCResolver — covers all exit criteria from TASK-012."""

from __future__ import annotations

import pytest

from ember_data.classification.atc_resolver import ATCResolver
from ember_data.classification.spec import DisambiguationRequest, ResolvedTerm


@pytest.fixture(scope="module")
def resolver() -> ATCResolver:
    return ATCResolver()


# ---------------------------------------------------------------------------
# resolve() — exit criteria
# ---------------------------------------------------------------------------


class TestResolveAdalimumab:
    def test_top_result_is_L04AB04(self, resolver: ATCResolver) -> None:
        results = resolver.resolve("adalimumab")
        assert results, "resolve('adalimumab') returned empty list"
        assert results[0].identifier == "L04AB04"

    def test_taxonomy_is_ATC(self, resolver: ATCResolver) -> None:
        result = resolver.resolve("adalimumab")[0]
        assert result.taxonomy == "ATC"

    def test_confidence_is_1(self, resolver: ATCResolver) -> None:
        result = resolver.resolve("adalimumab")[0]
        assert result.confidence == 1.0

    def test_brand_name_humira_resolves(self, resolver: ATCResolver) -> None:
        results = resolver.resolve("humira")
        assert results, "resolve('humira') returned empty list"
        assert results[0].identifier == "L04AB04"

    def test_case_insensitive(self, resolver: ATCResolver) -> None:
        results = resolver.resolve("ADALIMUMAB")
        assert results, "resolve('ADALIMUMAB') returned empty list"
        assert results[0].identifier == "L04AB04"


class TestResolveMonoclonalAntibody:
    def test_top_result_is_L01XC(self, resolver: ATCResolver) -> None:
        results = resolver.resolve("monoclonal antibody")
        assert results, "resolve('monoclonal antibody') returned empty list"
        assert results[0].identifier == "L01XC"

    def test_plural_resolves(self, resolver: ATCResolver) -> None:
        results = resolver.resolve("monoclonal antibodies")
        assert results, "resolve('monoclonal antibodies') returned empty list"
        assert results[0].identifier == "L01XC"

    def test_confidence_is_1(self, resolver: ATCResolver) -> None:
        result = resolver.resolve("monoclonal antibody")[0]
        assert result.confidence == 1.0


class TestResolveEmpty:
    def test_empty_string_returns_empty(self, resolver: ATCResolver) -> None:
        assert resolver.resolve("") == []

    def test_unknown_input_returns_empty_or_partial(
        self, resolver: ATCResolver
    ) -> None:
        # An unrecognised nonsense string should not raise and should return []
        result = resolver.resolve("xyzzy_not_a_drug_000")
        assert isinstance(result, list)


# ---------------------------------------------------------------------------
# narrow() — exit criteria
# ---------------------------------------------------------------------------


class TestNarrow:
    def test_narrow_L01XC_returns_children(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L01XC",
            label="Monoclonal antibodies",
            confidence=1.0,
        )
        children = resolver.narrow(term)
        assert children, "narrow(L01XC) returned empty list"
        child_codes = {t.identifier for t in children}
        # L01XC01 (trastuzumab) and L01XC02 (rituximab) must be present.
        assert "L01XC01" in child_codes, f"L01XC01 not in children: {child_codes}"
        assert "L01XC02" in child_codes, f"L01XC02 not in children: {child_codes}"

    def test_narrow_returns_resolved_terms(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L01XC",
            label="Monoclonal antibodies",
            confidence=1.0,
        )
        children = resolver.narrow(term)
        for child in children:
            assert isinstance(child, ResolvedTerm)
            assert child.taxonomy == "ATC"

    def test_narrow_level5_returns_empty(self, resolver: ATCResolver) -> None:
        # A leaf node (level 5) should have no children.
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L04AB04",
            label="adalimumab",
            confidence=1.0,
        )
        children = resolver.narrow(term)
        assert children == []

    def test_narrow_children_are_correct_parent(
        self, resolver: ATCResolver
    ) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L04AB",
            label="TNF-alpha inhibitors",
            confidence=1.0,
        )
        children = resolver.narrow(term)
        child_codes = {t.identifier for t in children}
        assert "L04AB04" in child_codes


# ---------------------------------------------------------------------------
# broaden() — exit criteria
# ---------------------------------------------------------------------------


class TestBroaden:
    def test_broaden_L04AB04_returns_L04AB(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L04AB04",
            label="adalimumab",
            confidence=1.0,
        )
        parents = resolver.broaden(term)
        assert parents, "broaden(L04AB04) returned empty list"
        assert parents[0].identifier == "L04AB"

    def test_broaden_returns_resolved_term(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L04AB04",
            label="adalimumab",
            confidence=1.0,
        )
        parents = resolver.broaden(term)
        assert isinstance(parents[0], ResolvedTerm)
        assert parents[0].taxonomy == "ATC"

    def test_broaden_level1_returns_empty(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L",
            label="Antineoplastic and immunomodulating agents",
            confidence=1.0,
        )
        parents = resolver.broaden(term)
        assert parents == []

    def test_broaden_L01XC_returns_L01X(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L01XC",
            label="Monoclonal antibodies",
            confidence=1.0,
        )
        parents = resolver.broaden(term)
        assert parents, "broaden(L01XC) returned empty list"
        assert parents[0].identifier == "L01X"


# ---------------------------------------------------------------------------
# disambiguate()
# ---------------------------------------------------------------------------


class TestDisambiguate:
    def test_single_candidate_returns_none(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC", identifier="L04AB04", label="adalimumab", confidence=1.0
        )
        assert resolver.disambiguate([term]) is None

    def test_empty_candidates_returns_none(self, resolver: ATCResolver) -> None:
        assert resolver.disambiguate([]) is None

    def test_multiple_candidates_returns_request(
        self, resolver: ATCResolver
    ) -> None:
        terms = [
            ResolvedTerm(
                taxonomy="ATC", identifier="L04AB04", label="adalimumab", confidence=0.9
            ),
            ResolvedTerm(
                taxonomy="ATC", identifier="L04AB02", label="infliximab", confidence=0.8
            ),
        ]
        result = resolver.disambiguate(terms)
        assert isinstance(result, DisambiguationRequest)
        assert len(result.options) == 2


# ---------------------------------------------------------------------------
# estimate_count()
# ---------------------------------------------------------------------------


class TestEstimateCount:
    def test_level5_returns_1(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC", identifier="L04AB04", label="adalimumab", confidence=1.0
        )
        assert resolver.estimate_count(term) == 1

    def test_level4_returns_more_than_1(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC", identifier="L04AB", label="TNF-alpha inhibitors", confidence=1.0
        )
        assert resolver.estimate_count(term) > 1

    def test_level1_returns_large_count(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L",
            label="Antineoplastic and immunomodulating agents",
            confidence=1.0,
        )
        assert resolver.estimate_count(term) >= 5000

    def test_unknown_code_returns_0(self, resolver: ATCResolver) -> None:
        term = ResolvedTerm(
            taxonomy="ATC", identifier="ZZZZZZ", label="unknown", confidence=0.0
        )
        assert resolver.estimate_count(term) == 0
