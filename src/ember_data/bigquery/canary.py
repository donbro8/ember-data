"""Canary watch configuration for production health monitoring."""

CANARY_WATCH_CONFIG = {
    "name": "system-canary",
    "query": "adalimumab",
    "schedule": "weekly",
    "schedule_day": 0,  # Monday
    "enabled": True,
    "notify_on_change": True,
}

# Baseline completeness thresholds (populated from integration test baselines)
# If a field's population rate drops >10pp below these values, alert CRITICAL
CANARY_BASELINES = {
    "canonical_id": 100,
    "display_label": 100,
    "drug_name": 80,
    "target": 60,
    "indication": 70,
    "patents": 90,
    "trials": 40,
    "articles": 60,
    "source_urls": 90,
    "overall_score": 100,
}


def check_canary_results(results: list, *, threshold_drop: int = 10) -> dict:
    """Check canary run results against baseline thresholds.

    Returns a dict with:
        - passed: bool
        - alerts: list of field names that dropped below threshold
        - rates: dict of field -> population rate percentage
    """
    if not results:
        return {"passed": False, "alerts": ["no_results"], "rates": {}}

    total = len(results)
    rates: dict[str, int] = {}
    alerts: list[str] = []

    for field, baseline in CANARY_BASELINES.items():
        populated = sum(1 for r in results if _is_populated(r, field))
        rate = int((populated / total) * 100)
        rates[field] = rate
        if rate < baseline - threshold_drop:
            alerts.append(field)

    return {"passed": len(alerts) == 0, "alerts": alerts, "rates": rates}


def _is_populated(result, field: str) -> bool:
    """Check if a field is meaningfully populated on a result."""
    val = getattr(result, field, None) if hasattr(result, field) else result.get(field)
    if val is None:
        return False
    if isinstance(val, (list, str)) and len(val) == 0:
        return False
    if isinstance(val, (int, float)) and val == 0:
        return False
    return True
