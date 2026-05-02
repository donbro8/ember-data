"""Trial domain model."""

from datetime import date
from enum import StrEnum

from pydantic import BaseModel


class TrialPhase(StrEnum):
    """Clinical trial phase."""

    I = "I"  # noqa: E741
    II = "II"
    III = "III"
    IV = "IV"


class Trial(BaseModel):
    """A clinical trial record."""

    nct_id: str
    title: str
    phase: TrialPhase
    status: str
    conditions: list[str]
    interventions: list[str]
    sponsor: str
    start_date: date
    primary_endpoints: list[str]
    results_summary: str | None = None
