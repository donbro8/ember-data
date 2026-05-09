"""Tests for seed dataset loading."""

from ember_data.seed import load_biologic_reference


def test_load_returns_entries():
    entries = load_biologic_reference()
    assert len(entries) >= 150


def test_all_categories_represented():
    entries = load_biologic_reference()
    categories = {e.category for e in entries}
    expected = {
        "mAb", "fusion_protein", "insulin", "epo", "gcsf",
        "interferon", "adc", "bispecific", "enzyme", "other",
    }
    assert categories == expected
    assert len(categories) >= 9


def test_entries_have_required_fields():
    entries = load_biologic_reference()
    for entry in entries:
        assert entry.drug_name
        assert entry.originator
        assert entry.category
        assert "US" in entry.patent_expiries or entry.patent_expiry_us is not None


def test_revenue_data_present():
    entries = load_biologic_reference()
    with_revenue = [e for e in entries if e.annual_revenue_usd_millions > 0]
    assert len(with_revenue) >= 100


def test_patent_expiries_have_us_and_eu():
    entries = load_biologic_reference()
    for entry in entries:
        assert "US" in entry.patent_expiries, f"{entry.drug_name} missing US patent expiry"
        assert "EU" in entry.patent_expiries, f"{entry.drug_name} missing EU patent expiry"


def test_cell_line_class_valid():
    entries = load_biologic_reference()
    valid_classes = {"mammalian", "microbial"}
    for entry in entries:
        assert entry.cell_line_class in valid_classes, (
            f"{entry.drug_name} has invalid cell_line_class: {entry.cell_line_class}"
        )
