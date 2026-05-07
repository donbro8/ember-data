"""Tests for ModalityResolver — covers all exit criteria from TASK-013."""

from __future__ import annotations

import pytest

from ember_data.classification.modality_resolver import ModalityResolver
from ember_data.classification.spec import DisambiguationRequest, ResolvedTerm


@pytest.fixture
def resolver() -> ModalityResolver:
    return ModalityResolver()


# ---------------------------------------------------------------------------
# resolve() — drug modality
# ---------------------------------------------------------------------------


class TestResolveMab:
    def test_mab_exact(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("mab")
        assert results, "resolve('mab') returned empty list"
        assert results[0].taxonomy == "Modality"
        assert results[0].identifier == "mab"
        assert results[0].confidence == 1.0

    def test_monoclonal_antibody(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("monoclonal antibody")
        assert results
        assert results[0].taxonomy == "Modality"
        assert results[0].identifier in {"mab", "monoclonal_antibody"}
        assert results[0].confidence == 1.0

    def test_case_insensitive(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("MAb")
        assert results
        assert results[0].taxonomy == "Modality"


class TestResolveBispecific:
    def test_bispecific_exact(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("bispecific")
        assert results
        assert results[0].taxonomy == "Modality"
        assert results[0].identifier in {"bispecific", "bispecific_antibody"}
        assert results[0].confidence == 1.0

    def test_bispecific_antibody(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("bispecific antibody")
        assert results
        ids = {t.identifier for t in results}
        assert "bispecific_antibody" in ids

    def test_bsab_synonym(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("bsab")
        assert results
        assert results[0].identifier == "bispecific_antibody"


class TestResolveADC:
    def test_adc_exact(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("adc")
        assert results
        assert results[0].identifier == "adc"
        assert results[0].confidence == 1.0

    def test_full_name(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("antibody-drug conjugate")
        assert results
        assert results[0].identifier == "adc"
        assert results[0].confidence == 1.0

    def test_plural_full_name(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("antibody drug conjugates")
        assert results
        assert results[0].identifier == "adc"


class TestResolveFcFusion:
    def test_fc_fusion_hyphen(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("fc-fusion")
        assert results
        assert results[0].identifier == "fc_fusion"
        assert results[0].confidence == 1.0

    def test_fc_fusion_space(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("fc fusion")
        assert results
        assert results[0].identifier == "fc_fusion"

    def test_fc_fusion_protein(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("fc fusion protein")
        assert results
        assert results[0].identifier == "fc_fusion"


# ---------------------------------------------------------------------------
# resolve() — cell line class
# ---------------------------------------------------------------------------


class TestResolveMammalian:
    def test_mammalian_exact(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("mammalian")
        assert results
        assert results[0].taxonomy == "CellLineClass"
        assert results[0].identifier == "mammalian"
        assert results[0].confidence == 1.0

    def test_cho_synonym(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("CHO")
        assert results
        assert results[0].identifier == "mammalian"


class TestResolveMicrobial:
    def test_microbial_exact(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("microbial")
        assert results
        assert results[0].taxonomy == "CellLineClass"
        assert results[0].identifier == "microbial"
        assert results[0].confidence == 1.0

    def test_ecoli_synonym(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("e. coli")
        assert results
        assert results[0].identifier == "microbial"


class TestResolveInsect:
    def test_insect_exact(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("insect")
        assert results
        assert results[0].taxonomy == "CellLineClass"
        assert results[0].identifier == "insect"
        assert results[0].confidence == 1.0

    def test_sf9_synonym(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("Sf9")
        assert results
        assert results[0].identifier == "insect"

    def test_baculovirus_synonym(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("baculovirus")
        assert results
        assert results[0].identifier == "insect"


class TestResolveOther:
    def test_other_exact(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("other")
        assert results
        # 'other' maps to CellLineClass.OTHER
        cl_results = [t for t in results if t.taxonomy == "CellLineClass"]
        assert cl_results
        assert cl_results[0].identifier == "other"

    def test_unknown_returns_empty(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("xyzzy_not_a_modality_99")
        assert isinstance(results, list)
        assert results == []

    def test_empty_string_returns_empty(self, resolver: ModalityResolver) -> None:
        assert resolver.resolve("") == []


# ---------------------------------------------------------------------------
# ResolvedTerm structure
# ---------------------------------------------------------------------------


class TestResolvedTermStructure:
    def test_modality_term_has_correct_taxonomy(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("adc")
        assert results[0].taxonomy == "Modality"

    def test_cell_line_term_has_correct_taxonomy(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("mammalian")
        assert results[0].taxonomy == "CellLineClass"

    def test_confidence_within_bounds(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("adc")
        for term in results:
            assert 0.0 <= term.confidence <= 1.0

    def test_synonyms_populated(self, resolver: ModalityResolver) -> None:
        results = resolver.resolve("adc")
        assert results
        assert len(results[0].synonyms) > 0

    def test_label_is_nonempty(self, resolver: ModalityResolver) -> None:
        for query in ["mab", "adc", "fc-fusion", "bispecific", "mammalian", "insect"]:
            results = resolver.resolve(query)
            assert results, f"resolve('{query}') returned empty"
            assert results[0].label


# ---------------------------------------------------------------------------
# narrow() and broaden() — flat enum, always empty
# ---------------------------------------------------------------------------


class TestNarrowBroaden:
    def test_narrow_returns_empty(self, resolver: ModalityResolver) -> None:
        term = ResolvedTerm(
            taxonomy="Modality", identifier="adc", label="ADC", confidence=1.0
        )
        assert resolver.narrow(term) == []

    def test_broaden_returns_empty(self, resolver: ModalityResolver) -> None:
        term = ResolvedTerm(
            taxonomy="Modality", identifier="adc", label="ADC", confidence=1.0
        )
        assert resolver.broaden(term) == []


# ---------------------------------------------------------------------------
# disambiguate()
# ---------------------------------------------------------------------------


class TestDisambiguate:
    def test_single_candidate_returns_none(self, resolver: ModalityResolver) -> None:
        term = ResolvedTerm(
            taxonomy="Modality", identifier="adc", label="ADC", confidence=1.0
        )
        assert resolver.disambiguate([term]) is None

    def test_empty_candidates_returns_none(self, resolver: ModalityResolver) -> None:
        assert resolver.disambiguate([]) is None

    def test_multiple_candidates_returns_request(
        self, resolver: ModalityResolver
    ) -> None:
        terms = [
            ResolvedTerm(
                taxonomy="Modality", identifier="mab", label="mAb", confidence=0.9
            ),
            ResolvedTerm(
                taxonomy="Modality",
                identifier="bispecific_antibody",
                label="Bispecific Antibody",
                confidence=0.8,
            ),
        ]
        result = resolver.disambiguate(terms)
        assert isinstance(result, DisambiguationRequest)
        assert len(result.options) == 2


# ---------------------------------------------------------------------------
# estimate_count()
# ---------------------------------------------------------------------------


class TestEstimateCount:
    def test_adc_returns_positive(self, resolver: ModalityResolver) -> None:
        term = ResolvedTerm(
            taxonomy="Modality", identifier="adc", label="ADC", confidence=1.0
        )
        assert resolver.estimate_count(term) > 0

    def test_mammalian_returns_positive(self, resolver: ModalityResolver) -> None:
        term = ResolvedTerm(
            taxonomy="CellLineClass",
            identifier="mammalian",
            label="Mammalian",
            confidence=1.0,
        )
        assert resolver.estimate_count(term) > 0

    def test_unknown_modality_returns_0(self, resolver: ModalityResolver) -> None:
        term = ResolvedTerm(
            taxonomy="Modality", identifier="unknown", label="Unknown", confidence=0.0
        )
        assert resolver.estimate_count(term) == 0

    def test_unrecognised_taxonomy_returns_0(self, resolver: ModalityResolver) -> None:
        term = ResolvedTerm(
            taxonomy="Bogus", identifier="foo", label="Foo", confidence=1.0
        )
        assert resolver.estimate_count(term) == 0

    def test_small_molecule_has_highest_count(self, resolver: ModalityResolver) -> None:
        sm_term = ResolvedTerm(
            taxonomy="Modality",
            identifier="small_molecule",
            label="Small Molecule",
            confidence=1.0,
        )
        adc_term = ResolvedTerm(
            taxonomy="Modality", identifier="adc", label="ADC", confidence=1.0
        )
        assert resolver.estimate_count(sm_term) > resolver.estimate_count(adc_term)
