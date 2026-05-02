"""Ember Bio data access library.

Provides domain models, BigQuery client, and query builders
for biotech data intelligence.
"""

from ember_data.bigquery import BigQueryClient
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
    "Article",
    "BigQueryClient",
    "Candidate",
    "CandidateScores",
    "Patent",
    "Target",
    "TargetType",
    "Trial",
    "TrialPhase",
]
