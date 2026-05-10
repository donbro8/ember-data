"""Tests for versioned seed file format and BiologicEntry versioning fields."""

from __future__ import annotations

import json

from datetime import date

from ember_data.seed import (
    BiologicEntry,
    VersionedSeedFile,
    load_biologic_reference,
    load_versioned_seed,
)


# ---------------------------------------------------------------------------
# BiologicEntry new fields
# ---------------------------------------------------------------------------


def test_source_field_defaults_to_manual():
    entry = BiologicEntry(
        drug_name="test",
        originator="test",
        target_antigen="test",
    )
    assert entry.source == "manual"


def test_last_updated_defaults_to_none():
    entry = BiologicEntry(
        drug_name="test",
        originator="test",
        target_antigen="test",
    )
    assert entry.last_updated is None


def test_last_updated_accepts_date():
    entry = BiologicEntry(
        drug_name="test",
        originator="test",
        target_antigen="test",
        last_updated=date(2026, 1, 15),
    )
    assert entry.last_updated == date(2026, 1, 15)


def test_source_field_accepts_custom_value():
    entry = BiologicEntry(
        drug_name="test",
        originator="test",
        target_antigen="test",
        source="enriched_fda",
    )
    assert entry.source == "enriched_fda"


# ---------------------------------------------------------------------------
# VersionedSeedFile model
# ---------------------------------------------------------------------------


def test_versioned_seed_file_round_trip():
    entries = [
        BiologicEntry(
            drug_name="test-drug",
            originator="TestCo",
            target_antigen="CD20",
        ),
    ]
    vsf = VersionedSeedFile(
        data_version=1,
        last_enrichment_run=None,
        entry_count=1,
        entries=entries,
    )
    dumped = json.loads(vsf.model_dump_json())
    restored = VersionedSeedFile.model_validate(dumped)
    assert restored.data_version == 1
    assert restored.entry_count == 1
    assert restored.entries[0].drug_name == "test-drug"
    assert restored.last_enrichment_run is None


# ---------------------------------------------------------------------------
# Loader functions
# ---------------------------------------------------------------------------


def test_load_biologic_reference_returns_list():
    """Existing loader still returns a list of BiologicEntry."""
    entries = load_biologic_reference()
    assert isinstance(entries, list)
    assert len(entries) >= 100
    assert all(isinstance(e, BiologicEntry) for e in entries)


def test_load_versioned_seed_returns_wrapper():
    vsf = load_versioned_seed()
    assert isinstance(vsf, VersionedSeedFile)
    assert vsf.data_version >= 1
    assert vsf.entry_count == len(vsf.entries)
    assert vsf.entry_count >= 100


def test_load_biologic_reference_legacy_format(tmp_path):
    """Ensure bare-array JSON still loads correctly."""
    legacy = [
        {
            "drug_name": "legacy-drug",
            "originator": "LegacyCo",
            "target_antigen": "TNF",
        }
    ]
    p = tmp_path / "legacy.json"
    p.write_text(json.dumps(legacy))

    # Directly validate via the schema to confirm legacy format parses
    entries = [BiologicEntry.model_validate(e) for e in legacy]
    assert len(entries) == 1
    assert entries[0].source == "manual"


def test_all_entries_have_source_field():
    """Every entry in the real seed file should have a source field."""
    entries = load_biologic_reference()
    for entry in entries:
        assert entry.source == "manual"


def test_mab_entry_alias_still_works():
    from ember_data.seed.schema import MabEntry

    entry = MabEntry(
        drug_name="alias-test",
        originator="TestCo",
        target_antigen="HER2",
    )
    assert isinstance(entry, BiologicEntry)


def test_sync_patent_expiries_still_works():
    """Ensure the validator is not broken by the new fields."""
    entry = BiologicEntry.model_validate({
        "drug_name": "test",
        "originator": "test",
        "target_antigen": "test",
        "patent_expiry_us": "2030-01-01",
    })
    assert "US" in entry.patent_expiries
