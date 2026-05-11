# DIR-007 One-Time Patent Jurisdiction Coverage Remediation

- Dispatch: `0001N03MCACXE90Y`
- Plan: `PLAN-012`
- Task: `TASK-147`
- Enrichment date: `2026-05-11`
- Coverage source: `manual_seed_snapshot` (from `src/ember_data/seed/biologic_reference.json`)
- Entry count: `150`

## High-Priority Jurisdiction Coverage

| Jurisdiction | Covered entries | Unknown/unavailable entries | Status |
|---|---:|---:|---|
| US | 150 | 0 | covered |
| EU | 150 | 0 | covered |
| JP | 33 | 117 | covered |
| IN | 0 | 150 | unknown_or_unavailable |
| KR | 0 | 150 | unknown_or_unavailable |
| BR | 0 | 150 | unknown_or_unavailable |
| CN | 0 | 150 | unknown_or_unavailable |
| CA | 0 | 150 | unknown_or_unavailable |
| AU | 0 | 150 | unknown_or_unavailable |
| GB | 0 | 150 | unknown_or_unavailable |

## Interpretation

This remediation records current coverage and explicitly marks missing high-priority jurisdiction data as `unknown_or_unavailable`. These unknown/unavailable values are not evidence that no patent exists; they indicate that further enrichment would require additional source integrations and is left to scheduled scope (DIR-006).
