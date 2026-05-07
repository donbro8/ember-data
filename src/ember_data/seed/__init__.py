"""Seed data loaders for Ember Bio reference datasets."""

from __future__ import annotations

from ember_data.seed.schema import MabEntry


def load_mab_reference() -> list[MabEntry]:
    """Load the curated mAb reference seed dataset.

    Returns an empty list when no seed file is configured (e.g. local dev
    without the BigQuery-backed seed).
    """
    # TODO: load from JSON/CSV seed file or BigQuery materialised view
    return []


__all__ = ["MabEntry", "load_mab_reference"]
