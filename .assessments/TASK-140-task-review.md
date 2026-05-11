---
task_id: TASK-140
review_status: pass
reviewer: ember-data-reviewer
reviewed_at: 2026-05-11
---

# TASK-140 Task Review: Support ClinicalTrials.gov Optional Condition and Term Searches

## Findings

### Signature & Parameter Handling

- `search()` signature at `src/ember_data/clients/clinicaltrials.py:183-191` correctly declares `condition: str | None = None`, `intervention: str | None = None`, and `term: str | None = None`.
- Query parameters `query.cond`, `query.intr`, `query.term` are conditionally included only when the corresponding input is truthy (`clinicaltrials.py:226-231`). Empty strings and `None` are both correctly excluded.

### Input Validation

- `clinicaltrials.py:217-219`: `ValueError` raised before any network call when all three inputs are falsy. Confirmed by tests at `test_clients.py:475-489` which also assert `_retry_get` was never called.

### Backward Compatibility

- `condition` remains the first positional parameter with default `None`. Existing callers using `client.search(condition="...")` are unaffected.
- `test_condition_only_backward_compatible` (`test_clients.py:426-438`) explicitly verifies this.

### Matched Fields / Provenance

- `clinicaltrials.py:255-259`: `matched_fields` correctly reflects which query inputs were provided. Tests at `test_clients.py:440-473` verify all combinations.

### Pre-existing Note (not blocking)

- `clinicaltrials.py:76`: `exc.code >= 429 or exc.code >= 500` — the second condition is redundant (subsumed by the first). This means HTTP 4xx codes 430-499 are retried when they likely shouldn't be. This is **pre-existing** and outside TASK-140 scope, but worth a future fix.

## Acceptance Criteria Coverage

| Criterion | Status | Evidence |
|---|---|---|
| `search()` accepts `condition`, `intervention`, `term` as `str \| None` | **Pass** | `clinicaltrials.py:183-191` |
| Params included only when present | **Pass** | `clinicaltrials.py:226-231`, `test_clients.py:376-505` |
| At least one query input required; empty rejected pre-network | **Pass** | `clinicaltrials.py:217-219`, `test_clients.py:475-489` |
| `adalimumab` queryable via `query.intr` with no `query.cond` | **Pass** | `test_clients.py:376-390` |
| Existing condition-based searches backward compatible | **Pass** | `test_clients.py:426-438` |
| Tests cover all six scenarios | **Pass** | `TestClinicalTrialsOptionalParams` class, 9 test methods |

## Verification Evidence

- Task file reports 54 tests passing via `uv run pytest tests/clients/test_clients.py -v --tb=short`.
- Task file reports `ruff check` passing on both touched files.

## Residual Risks

- **Low**: The pre-existing retry condition (`>= 429 or >= 500`) retries more 4xx errors than intended. Not introduced by this change.
- **None identified** for TASK-140 scope.
