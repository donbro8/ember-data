"""ClinicalTrialsClient — searches ClinicalTrials.gov API v2 for trial records."""

from __future__ import annotations

import json
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import UTC, date, datetime
from typing import Any

from ember_data.models.provenance import SourceProvenance
from ember_data.models.trial import Trial, TrialPhase

_CT_BASE = "https://clinicaltrials.gov/api/v2/studies"

_RATE_LIMIT = 3  # requests/sec

_PHASE_MAP: dict[str, str] = {
    "PHASE1": "I",
    "PHASE2": "II",
    "PHASE3": "III",
    "PHASE4": "IV",
}


class ClinicalTrialsClient:
    """Client for the ClinicalTrials.gov REST API v2.

    Rate limits
    -----------
    - 3 requests/sec (conservative; ClinicalTrials.gov allows more but we play safe).

    Retry
    -----
    - 3 attempts max, exponential backoff: 1s, 2s, 4s.
    """

    def __init__(self) -> None:
        self._min_interval: float = 1.0 / _RATE_LIMIT
        self._last_request_time: float = 0.0

    # ------------------------------------------------------------------
    # Internal HTTP helpers
    # ------------------------------------------------------------------

    def _throttle(self) -> None:
        """Sleep if needed to stay within the configured rate limit."""
        elapsed = time.monotonic() - self._last_request_time
        wait = self._min_interval - elapsed
        if wait > 0:
            time.sleep(wait)
        self._last_request_time = time.monotonic()

    def _get(self, url: str) -> tuple[str, dict[str, str]]:
        """Perform a throttled GET and return (body, headers) tuple."""
        self._throttle()
        req = urllib.request.Request(url, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=10) as response:
            body = response.read().decode("utf-8")
            headers = {k.lower(): v for k, v in response.headers.items()}
        return body, headers

    def _retry_get(self, url: str, max_attempts: int = 3) -> tuple[str, dict[str, str]]:
        """Call _get with exponential backoff retry on transient errors.

        Retries on URLError or HTTPError with status >= 429 or >= 500.
        Raises the final exception if all attempts fail.
        """
        last_exc: Exception | None = None
        for attempt in range(max_attempts):
            try:
                return self._get(url)
            except urllib.error.HTTPError as exc:
                if exc.code >= 429 or exc.code >= 500:
                    last_exc = exc
                    if attempt < max_attempts - 1:
                        time.sleep(2 ** attempt)
                    continue
                raise
            except urllib.error.URLError as exc:
                last_exc = exc
                if attempt < max_attempts - 1:
                    time.sleep(2 ** attempt)
                continue
        raise last_exc  # type: ignore[misc]

    # ------------------------------------------------------------------
    # Parsing helpers
    # ------------------------------------------------------------------

    def _parse_phase(self, phases: list[str]) -> TrialPhase | None:
        """Map ClinicalTrials.gov phase string to TrialPhase enum, or None."""
        if not phases:
            return None
        raw = phases[0]
        mapped = _PHASE_MAP.get(raw)
        if mapped is None:
            return None
        try:
            return TrialPhase(mapped)
        except ValueError:
            return None

    def _parse_date(self, date_str: str | None) -> date | None:
        """Parse YYYY-MM or YYYY-MM-DD date strings, returning None on failure."""
        if not date_str:
            return None
        try:
            if len(date_str) == 7:
                # YYYY-MM — use first day of month
                return date.fromisoformat(date_str + "-01")
            return date.fromisoformat(date_str[:10])
        except ValueError:
            return None

    def _study_to_trial(self, study: dict[str, Any]) -> Trial | None:
        """Convert a ClinicalTrials.gov v2 study dict to a Trial, or None if invalid."""
        protocol = study.get("protocolSection", {})

        id_mod = protocol.get("identificationModule", {})
        nct_id: str = id_mod.get("nctId", "")
        if not nct_id:
            return None

        title: str = id_mod.get("officialTitle") or id_mod.get("briefTitle", "")
        if not title:
            return None

        design_mod = protocol.get("designModule", {})
        phases_raw: list[str] = design_mod.get("phases", [])
        phase = self._parse_phase(phases_raw)
        if phase is None:
            return None

        status_mod = protocol.get("statusModule", {})
        status: str = status_mod.get("overallStatus", "")

        start_date_struct = status_mod.get("startDateStruct", {})
        start_date = self._parse_date(start_date_struct.get("date"))
        if start_date is None:
            return None

        conditions_mod = protocol.get("conditionsModule", {})
        conditions: list[str] = conditions_mod.get("conditions", [])

        arms_mod = protocol.get("armsInterventionsModule", {})
        interventions: list[str] = [
            iv.get("name", "")
            for iv in arms_mod.get("interventions", [])
            if iv.get("name")
        ]

        sponsor_mod = protocol.get("sponsorCollaboratorsModule", {})
        lead_sponsor = sponsor_mod.get("leadSponsor", {})
        sponsor: str = lead_sponsor.get("name", "")

        outcomes_mod = protocol.get("outcomesModule", {})
        primary_endpoints: list[str] = [
            o.get("measure", "")
            for o in outcomes_mod.get("primaryOutcomes", [])
            if o.get("measure")
        ]

        return Trial(
            nct_id=nct_id,
            title=title,
            phase=phase,
            status=status,
            conditions=conditions,
            interventions=interventions,
            sponsor=sponsor,
            start_date=start_date,
            primary_endpoints=primary_endpoints,
            results_summary=None,
        )

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def search(
        self,
        condition: str | None = None,
        intervention: str | None = None,
        term: str | None = None,
        from_date: date | None = None,
        to_date: date | None = None,
        max_results: int = 20,
    ) -> list[tuple[Trial, SourceProvenance]]:
        """Search ClinicalTrials.gov for studies matching the given criteria.

        At least one of ``condition``, ``intervention``, or ``term`` must be
        provided. An empty call raises ``ValueError`` before making any network
        request.

        Parameters
        ----------
        condition:
            Disease or condition to search for (``query.cond``).
        intervention:
            Drug or intervention name (``query.intr``).
        term:
            Broad free-text term (``query.term``).
        from_date:
            Optional start of the date range filter (by study start date).
        to_date:
            Optional end of the date range filter (by study start date).
        max_results:
            Maximum number of results to return.

        Returns
        -------
        list of (Trial, SourceProvenance) tuples.
        """
        if not condition and not intervention and not term:
            raise ValueError(
                "At least one of condition, intervention, or term must be provided."
            )

        params: dict[str, str] = {
            "format": "json",
            "pageSize": str(max_results),
        }
        if condition:
            params["query.cond"] = condition
        if intervention:
            params["query.intr"] = intervention
        if term:
            params["query.term"] = term
        if from_date:
            params["filter.advanced"] = f"AREA[StartDate]RANGE[{from_date.isoformat()},MAX]"
        if to_date:
            existing = params.get("filter.advanced", "")
            if existing:
                params["filter.advanced"] = (
                    f"AREA[StartDate]RANGE[{from_date.isoformat() if from_date else 'MIN'},"
                    f"{to_date.isoformat()}]"
                )
            else:
                params["filter.advanced"] = (
                    f"AREA[StartDate]RANGE[MIN,{to_date.isoformat()}]"
                )

        url = f"{_CT_BASE}?{urllib.parse.urlencode(params)}"

        try:
            body, _ = self._retry_get(url)
            data = json.loads(body)
        except (urllib.error.URLError, ValueError):
            return []

        studies: list[dict[str, Any]] = data.get("studies", [])
        matched_fields = (
            (["condition"] if condition else [])
            + (["intervention"] if intervention else [])
            + (["term"] if term else [])
        )

        results: list[tuple[Trial, SourceProvenance]] = []
        for study in studies:
            trial = self._study_to_trial(study)
            if trial is None:
                continue
            provenance = SourceProvenance(
                source_name="ClinicalTrials.gov",
                source_id=trial.nct_id,
                source_url=f"https://clinicaltrials.gov/study/{trial.nct_id}",
                retrieved_at=datetime.now(UTC),
                matched_fields=matched_fields,
            )
            results.append((trial, provenance))

        return results
