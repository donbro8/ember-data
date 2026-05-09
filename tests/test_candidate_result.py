"""Tests for CandidateResult, ResultType, and build_canonical_id."""

from ember_data.models.result import (
    CandidateResult,
    ResultType,
    build_canonical_id,
)


# ---------------------------------------------------------------------------
# ResultType assignment
# ---------------------------------------------------------------------------


def test_result_type_drug_when_drug_name_present():
    result = CandidateResult(drug_name="Humira")
    assert result.result_type == ResultType.DRUG


def test_result_type_drug_when_fda_generic_name_present():
    result = CandidateResult(fda_generic_name="adalimumab")
    assert result.result_type == ResultType.DRUG


def test_result_type_drug_when_both_names_present():
    result = CandidateResult(drug_name="Humira", fda_generic_name="adalimumab")
    assert result.result_type == ResultType.DRUG


def test_result_type_target_when_only_target():
    result = CandidateResult(target="TNF-alpha")
    assert result.result_type == ResultType.TARGET


def test_result_type_target_when_no_fields():
    result = CandidateResult(sources_contributed=["src-1"])
    assert result.result_type == ResultType.TARGET


# ---------------------------------------------------------------------------
# canonical_id stability (tier 1: fda_generic_name)
# ---------------------------------------------------------------------------


def test_canonical_id_fda_generic_name_normalized():
    """adalimumab and Humira produce the same canonical_id when fda_generic_name is set."""
    result_by_brand = CandidateResult(
        drug_name="Humira", fda_generic_name="adalimumab"
    )
    result_by_generic = CandidateResult(fda_generic_name="adalimumab")
    assert result_by_brand.canonical_id == result_by_generic.canonical_id
    assert result_by_brand.canonical_id == "adalimumab"


def test_canonical_id_fda_generic_name_strips_spaces():
    result = CandidateResult(fda_generic_name="adali mumab")
    assert result.canonical_id == "adalimumab"


def test_canonical_id_fda_generic_name_lowercased():
    result = CandidateResult(fda_generic_name="Adalimumab")
    assert result.canonical_id == "adalimumab"


# ---------------------------------------------------------------------------
# canonical_id tier 2: drug_name + target
# ---------------------------------------------------------------------------


def test_canonical_id_drug_and_target():
    result = CandidateResult(drug_name="Humira", target="TNF-alpha")
    assert result.canonical_id == "humira_tnf-alpha"


def test_canonical_id_drug_and_target_normalized():
    result_a = CandidateResult(drug_name="Humira", target="TNF alpha")
    result_b = CandidateResult(drug_name="HUMIRA", target="tnf alpha")
    assert result_a.canonical_id == result_b.canonical_id


# ---------------------------------------------------------------------------
# canonical_id tier 3: hash of source IDs
# ---------------------------------------------------------------------------


def test_canonical_id_hash_is_deterministic():
    sources = ["src-b", "src-a", "src-c"]
    result_a = CandidateResult(sources_contributed=sources)
    result_b = CandidateResult(sources_contributed=sources)
    assert result_a.canonical_id == result_b.canonical_id


def test_canonical_id_hash_is_order_independent():
    result_a = CandidateResult(sources_contributed=["src-a", "src-b"])
    result_b = CandidateResult(sources_contributed=["src-b", "src-a"])
    assert result_a.canonical_id == result_b.canonical_id


def test_canonical_id_hash_is_sha256_hex():
    result = CandidateResult(sources_contributed=["src-1"])
    assert len(result.canonical_id) == 64
    assert all(c in "0123456789abcdef" for c in result.canonical_id)


# ---------------------------------------------------------------------------
# display_label always populated
# ---------------------------------------------------------------------------


def test_display_label_drug_prefers_fda_generic():
    result = CandidateResult(drug_name="Humira", fda_generic_name="adalimumab")
    assert result.display_label == "adalimumab"


def test_display_label_drug_falls_back_to_drug_name():
    result = CandidateResult(drug_name="Humira")
    assert result.display_label == "Humira"


def test_display_label_target():
    result = CandidateResult(target="TNF-alpha")
    assert result.display_label == "TNF-alpha"


def test_display_label_never_none_for_drug():
    result = CandidateResult(drug_name="SomeDrug")
    assert result.display_label is not None
    assert len(result.display_label) > 0


def test_display_label_never_none_for_target():
    result = CandidateResult(target="EGFR")
    assert result.display_label is not None
    assert len(result.display_label) > 0


# ---------------------------------------------------------------------------
# build_canonical_id function directly
# ---------------------------------------------------------------------------


def test_build_canonical_id_called_directly():
    result = CandidateResult(fda_generic_name="trastuzumab")
    assert build_canonical_id(result) == "trastuzumab"


# ---------------------------------------------------------------------------
# Import sanity
# ---------------------------------------------------------------------------


def test_import_from_result_module():
    from ember_data.models.result import CandidateResult, ResultType, build_canonical_id  # noqa: F401


def test_import_from_models_package():
    from ember_data.models import CandidateResult, ResultType, build_canonical_id  # noqa: F401
