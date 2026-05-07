"""Ember Bio data access library.

Provides domain models, BigQuery client, and query builders
for biotech data intelligence.
"""

from ember_data.bigquery import BigQueryClient
from ember_data.classification import (
    ATCNode,
    CellLineClass,
    DateWindow,
    DisambiguationRequest,
    Jurisdiction,
    MeSHTerm,
    ModalityClassification,
    ResolvedTerm,
    SearchSpec,
    TargetClassification,
)
from ember_data.models import (
    Article,
    Candidate,
    CandidateScores,
    Patent,
    Target,
    TargetType,
    Trial,
    TrialPhase,
)

__all__ = [
    "ATCNode",
    "Article",
    "BigQueryClient",
    "Candidate",
    "CandidateScores",
    "CellLineClass",
    "DateWindow",
    "DisambiguationRequest",
    "Jurisdiction",
    "MeSHTerm",
    "ModalityClassification",
    "Patent",
    "ResolvedTerm",
    "SearchSpec",
    "Target",
    "TargetClassification",
    "TargetType",
    "Trial",
    "TrialPhase",
]
