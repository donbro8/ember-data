"""Tests for SearchSpec, DateWindow, ResolvedTerm, and DisambiguationRequest."""

from __future__ import annotations

from datetime import date

import pytest
from pydantic import ValidationError

from ember_data.classification.enums import (
    ATCNode,
    Jurisdiction,
    ModalityClassification,
    TargetClassification,
)
from ember_data.classification.spec import (
    DateWindow,
    DisambiguationRequest,
    ResolvedTerm,
    SearchSpec,
)


# ---------------------------------------------------------------------------
# DateWindow
# ---------------------------------------------------------------------------


class TestDateWindowConstructors:
    def test_before_sets_end_only(self) -> None:
        cutoff = date(2025, 12, 31)
        window = DateWindow.before(cutoff)
        assert window.end == cutoff
        assert window.start is None

    def test_after_sets_start_only(self) -> None:
        cutoff = date(2024, 1, 1)
        window = DateWindow.after(cutoff)
        assert window.start == cutoff
        assert window.end is None

    def test_between_sets_both_bounds(self) -> None:
        start = date(2020, 1, 1)
        end = date(2025, 12, 31)
        window = DateWindow.between(start, end)
        assert window.start == start
        assert window.end == end

    def test_not_yet_expired_defaults_to_today(self) -> None:
        today = date.today()
        window = DateWindow.not_yet_expired()
        assert window.start == today
        assert window.end is None

    def test_not_yet_expired_uses_provided_as_of(self) -> None:
        as_of = date(2026, 6, 1)
        window = DateWindow.not_yet_expired(as_of=as_of)
        assert window.start == as_of
        assert window.end is None

    def test_direct_construction_with_no_fields(self) -> None:
        window = DateWindow()
        assert window.start is None
        assert window.end is None


# ---------------------------------------------------------------------------
# ResolvedTerm
# ---------------------------------------------------------------------------


class TestResolvedTerm:
    def test_basic_construction(self) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L04AB04",
            label="adalimumab",
            confidence=0.95,
        )
        assert term.taxonomy == "ATC"
        assert term.identifier == "L04AB04"
        assert term.label == "adalimumab"
        assert term.confidence == 0.95

    def test_synonyms_default_empty(self) -> None:
        term = ResolvedTerm(
            taxonomy="ATC", identifier="L04", label="Immunosuppressants", confidence=1.0
        )
        assert term.synonyms == []

    def test_synonyms_populated(self) -> None:
        term = ResolvedTerm(
            taxonomy="MeSH",
            identifier="D009369",
            label="Neoplasms",
            confidence=0.9,
            synonyms=["Cancer", "Tumor"],
        )
        assert "Cancer" in term.synonyms

    def test_parent_id_optional(self) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L04AB04",
            label="adalimumab",
            confidence=0.8,
            parent_id="L04AB",
        )
        assert term.parent_id == "L04AB"

    def test_confidence_at_zero(self) -> None:
        term = ResolvedTerm(
            taxonomy="ATC", identifier="X", label="unknown", confidence=0.0
        )
        assert term.confidence == 0.0

    def test_confidence_at_one(self) -> None:
        term = ResolvedTerm(
            taxonomy="ATC", identifier="X", label="exact", confidence=1.0
        )
        assert term.confidence == 1.0

    def test_confidence_below_zero_raises(self) -> None:
        with pytest.raises(ValidationError):
            ResolvedTerm(
                taxonomy="ATC", identifier="X", label="bad", confidence=-0.1
            )

    def test_confidence_above_one_raises(self) -> None:
        with pytest.raises(ValidationError):
            ResolvedTerm(
                taxonomy="ATC", identifier="X", label="bad", confidence=1.01
            )


# ---------------------------------------------------------------------------
# DisambiguationRequest
# ---------------------------------------------------------------------------


class TestDisambiguationRequest:
    def _make_term(self, identifier: str, label: str) -> ResolvedTerm:
        return ResolvedTerm(
            taxonomy="ATC", identifier=identifier, label=label, confidence=0.7
        )

    def test_construction_with_options_list(self) -> None:
        options = [
            self._make_term("L04AB04", "adalimumab"),
            self._make_term("L04AB02", "infliximab"),
        ]
        req = DisambiguationRequest(
            raw_input="anti-TNF",
            options=options,
            rationale="Multiple anti-TNF agents found",
        )
        assert req.raw_input == "anti-TNF"
        assert len(req.options) == 2
        assert req.rationale == "Multiple anti-TNF agents found"

    def test_options_are_resolved_terms(self) -> None:
        opt = self._make_term("L04AB04", "adalimumab")
        req = DisambiguationRequest(
            raw_input="adalimumab",
            options=[opt],
            rationale="Single match found",
        )
        assert isinstance(req.options[0], ResolvedTerm)

    def test_empty_options_list_allowed(self) -> None:
        req = DisambiguationRequest(
            raw_input="unknown compound",
            options=[],
            rationale="No matches found",
        )
        assert req.options == []


# ---------------------------------------------------------------------------
# SearchSpec — construction
# ---------------------------------------------------------------------------


class TestSearchSpecConstruction:
    def test_minimal_construction_defaults(self) -> None:
        spec = SearchSpec()
        assert spec.query == ""
        assert spec.target is None
        assert spec.therapeutic_area is None
        assert spec.drug_names == []
        assert spec.modality is None
        assert spec.patent_expiry_window is None
        assert spec.approval_date_range is None
        assert spec.min_revenue_millions is None
        assert spec.jurisdictions == []
        assert spec.max_results == 500
        assert spec.resolved_terms == []
        assert spec.pending_disambiguations == []

    def test_domains_default_all_four(self) -> None:
        spec = SearchSpec()
        assert set(spec.domains) == {"trials", "patents", "articles", "candidates"}

    def test_full_construction(self) -> None:
        spec = SearchSpec(
            query="PD-1 inhibitor oncology",
            target=TargetClassification.CHECKPOINT_PROTEIN,
            therapeutic_area=ATCNode.L,
            drug_names=["pembrolizumab", "nivolumab"],
            modality=ModalityClassification.MAB,
            patent_expiry_window=DateWindow.not_yet_expired(),
            approval_date_range=DateWindow.after(date(2015, 1, 1)),
            min_revenue_millions=500.0,
            jurisdictions=[Jurisdiction.US, Jurisdiction.EU],
            max_results=100,
            domains=["trials", "patents"],
        )
        assert spec.query == "PD-1 inhibitor oncology"
        assert spec.target == TargetClassification.CHECKPOINT_PROTEIN
        assert spec.therapeutic_area == ATCNode.L
        assert "pembrolizumab" in spec.drug_names
        assert spec.modality == ModalityClassification.MAB
        assert spec.max_results == 100
        assert Jurisdiction.US in spec.jurisdictions
        assert spec.domains == ["trials", "patents"]

    def test_target_as_resolved_term(self) -> None:
        term = ResolvedTerm(
            taxonomy="UniProt",
            identifier="P04637",
            label="TP53",
            confidence=0.99,
        )
        spec = SearchSpec(target=term)
        assert isinstance(spec.target, ResolvedTerm)
        assert spec.target.identifier == "P04637"

    def test_therapeutic_area_as_resolved_term(self) -> None:
        term = ResolvedTerm(
            taxonomy="ATC",
            identifier="L04",
            label="Immunosuppressants",
            confidence=0.85,
        )
        spec = SearchSpec(therapeutic_area=term)
        assert isinstance(spec.therapeutic_area, ResolvedTerm)


# ---------------------------------------------------------------------------
# SearchSpec — validation
# ---------------------------------------------------------------------------


class TestSearchSpecValidation:
    def test_max_results_default_500(self) -> None:
        spec = SearchSpec()
        assert spec.max_results == 500

    def test_max_results_at_minimum(self) -> None:
        spec = SearchSpec(max_results=1)
        assert spec.max_results == 1

    def test_max_results_at_maximum(self) -> None:
        spec = SearchSpec(max_results=1000)
        assert spec.max_results == 1000

    def test_max_results_below_minimum_raises(self) -> None:
        with pytest.raises(ValidationError):
            SearchSpec(max_results=0)

    def test_max_results_above_maximum_raises(self) -> None:
        with pytest.raises(ValidationError):
            SearchSpec(max_results=1001)

    def test_min_revenue_millions_zero_is_valid(self) -> None:
        spec = SearchSpec(min_revenue_millions=0.0)
        assert spec.min_revenue_millions == 0.0

    def test_min_revenue_millions_positive_is_valid(self) -> None:
        spec = SearchSpec(min_revenue_millions=100.0)
        assert spec.min_revenue_millions == 100.0

    def test_min_revenue_millions_negative_raises(self) -> None:
        with pytest.raises(ValidationError):
            SearchSpec(min_revenue_millions=-1.0)

    def test_min_revenue_millions_none_is_valid(self) -> None:
        spec = SearchSpec(min_revenue_millions=None)
        assert spec.min_revenue_millions is None


# ---------------------------------------------------------------------------
# SearchSpec — resolved terms and pending disambiguations
# ---------------------------------------------------------------------------


class TestSearchSpecResolvedTerms:
    def test_resolved_terms_populated(self) -> None:
        terms = [
            ResolvedTerm(
                taxonomy="ATC",
                identifier="L04AB04",
                label="adalimumab",
                confidence=0.95,
            ),
            ResolvedTerm(
                taxonomy="MeSH",
                identifier="D001172",
                label="Arthritis, Rheumatoid",
                confidence=0.9,
            ),
        ]
        spec = SearchSpec(resolved_terms=terms)
        assert len(spec.resolved_terms) == 2
        assert spec.resolved_terms[0].identifier == "L04AB04"

    def test_pending_disambiguations_populated(self) -> None:
        option = ResolvedTerm(
            taxonomy="ATC", identifier="L04AB04", label="adalimumab", confidence=0.7
        )
        req = DisambiguationRequest(
            raw_input="humira",
            options=[option],
            rationale="Brand name lookup",
        )
        spec = SearchSpec(pending_disambiguations=[req])
        assert len(spec.pending_disambiguations) == 1
        assert spec.pending_disambiguations[0].raw_input == "humira"

    def test_both_resolved_and_pending_coexist(self) -> None:
        resolved = ResolvedTerm(
            taxonomy="ATC", identifier="L04", label="Immunosuppressants", confidence=1.0
        )
        option = ResolvedTerm(
            taxonomy="MeSH", identifier="D001172", label="RA", confidence=0.6
        )
        req = DisambiguationRequest(
            raw_input="rheumatoid",
            options=[option],
            rationale="Ambiguous term",
        )
        spec = SearchSpec(resolved_terms=[resolved], pending_disambiguations=[req])
        assert len(spec.resolved_terms) == 1
        assert len(spec.pending_disambiguations) == 1
