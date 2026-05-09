"""Seed data loaders for Ember Bio reference datasets."""

from __future__ import annotations

import json
from importlib import resources

from ember_data.seed.schema import BiologicEntry


def load_biologic_reference() -> list[BiologicEntry]:
    """Load the curated biologic reference seed dataset."""
    seed_file = resources.files("ember_data.seed").joinpath("biologic_reference.json")
    raw = json.loads(seed_file.read_text(encoding="utf-8"))
    return [BiologicEntry.model_validate(entry) for entry in raw]


# Backward-compatible aliases
MabEntry = BiologicEntry
load_mab_reference = load_biologic_reference

__all__ = [
    "BiologicEntry",
    "MabEntry",
    "load_biologic_reference",
    "load_mab_reference",
]
