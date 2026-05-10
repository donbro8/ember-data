"""Seed data loaders for Ember Bio reference datasets."""

from __future__ import annotations

import json
from importlib import resources

from ember_data.seed.schema import BiologicEntry, VersionedSeedFile


def _load_raw_seed() -> dict | list:
    """Load the raw JSON content from the seed file."""
    seed_file = resources.files("ember_data.seed").joinpath("biologic_reference.json")
    return json.loads(seed_file.read_text(encoding="utf-8"))


def load_biologic_reference() -> list[BiologicEntry]:
    """Load the curated biologic reference seed dataset.

    Handles both legacy bare-array format and versioned dict format.
    """
    raw = _load_raw_seed()
    if isinstance(raw, dict):
        entries = raw["entries"]
    elif isinstance(raw, list):
        entries = raw
    else:
        msg = f"Expected a JSON array or versioned object, got {type(raw).__name__}"
        raise ValueError(msg)
    return [BiologicEntry.model_validate(entry) for entry in entries]


def load_versioned_seed() -> VersionedSeedFile:
    """Load the versioned seed file, returning the full wrapper."""
    raw = _load_raw_seed()
    if isinstance(raw, dict):
        return VersionedSeedFile.model_validate(raw)
    if isinstance(raw, list):
        # Legacy format: wrap in a VersionedSeedFile with sensible defaults.
        entries = [BiologicEntry.model_validate(entry) for entry in raw]
        return VersionedSeedFile(
            data_version=0,
            last_enrichment_run=None,
            entry_count=len(entries),
            entries=entries,
        )
    msg = f"Expected a JSON array or versioned object, got {type(raw).__name__}"
    raise ValueError(msg)


# Backward-compatible aliases
MabEntry = BiologicEntry
load_mab_reference = load_biologic_reference

__all__ = [
    "BiologicEntry",
    "MabEntry",
    "VersionedSeedFile",
    "load_biologic_reference",
    "load_mab_reference",
    "load_versioned_seed",
]
