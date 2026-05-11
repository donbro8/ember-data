---
task_id: TASK-138
review_status: pass
reviewer: ember-data-reviewer
reviewed: 2026-05-11
---

# TASK-138 Review: Add SearchSpec Query Type and Signal Fields

## Findings

### enums.py — CellLineClass additions

- `CellLineClass` (`enums.py:22-41`) correctly enumerates all eight values required by the acceptance criteria: `MAMMALIAN`, `CHO`, `HEK`, `MICROBIAL`, `E_COLI`, `YEAST`, `PLANT`, `INSECT`.
- Additional values (`HUMAN_PRIMARY`, `HUMAN_IMMORTALIZED`, `MURINE`, `NON_HUMAN_PRIMATE`, `BACTERIAL`, `STEM_CELL_DERIVED`, `ORGANOID`, `OTHER`, `UNKNOWN`) are additive and do not break backward compatibility.
- `Jurisdiction` (`enums.py:6-19`) and `ModalityClassification` (`enums.py:44-62`) include all required values (`MAB`, `MONOCLONAL_ANTIBODY` for mAb variants; standard jurisdiction codes).
- All enums use `StrEnum`, consistent with project conventions.

### spec.py — SearchSpec field additions

- `query_type: str | None = None` (`spec.py:75`) — satisfies AC for explicit opportunity query type. Optional, backward-compatible default.
- `cell_line_class: CellLineClass | None = None` (`spec.py:89`) — optional, satisfies AC.
- `patent_expiry_window: DateWindow | None = None` (`spec.py:92`) — preserves start and end via `DateWindow`, satisfies AC.
- `min_revenue_millions: float | None = Field(default=None, ge=0)` (`spec.py:96`) — optional with non-negative constraint, satisfies AC.
- `jurisdictions: list[Jurisdiction] = Field(default_factory=list)` (`spec.py:97`) — defaults to empty list, backward-compatible, satisfies AC.
- All new fields are optional or have backward-compatible defaults. No existing field signatures were changed.
- Imports in `__init__.py` correctly re-export `CellLineClass` and `Jurisdiction` in `__all__`.

### tests/test_search_spec.py — Test coverage

- **query_type**: `TestSearchSpecQueryType` (lines 353-370) covers default `None`, explicit `"opportunity"`, arbitrary string, and backward-compat with existing callers. (4 tests)
- **cell_line_class**: `TestCellLineClassDIR007` (lines 378-419) covers CHO, HEK, E_COLI, PLANT, and confirms existing MAMMALIAN/MICROBIAL/YEAST/INSECT still accepted. String value assertions verify enum serialization. (12 tests)
- **mAb modality**: `TestModalityMABVariants` (lines 429-442) covers both `MAB` and `MONOCLONAL_ANTIBODY` enum values and string representations. (4 tests)
- **Revenue and jurisdiction**: `TestRevenueAndJurisdiction` (lines 450-466) covers high-value signal (500M), explicit value (250M), US/EU jurisdiction, explicit list. (4 tests)
- **Patent window**: `TestPatentExpiryWindowDIR007` (lines 475-487) covers 2025-2028 window and start/end preservation. (2 tests)
- **Composite DIR-007 query**: `TestDIR007CompositeQuery` (lines 495-536) covers full opportunity spec (mAb + mammalian + revenue + patent + jurisdictions), CHO-specific variant, and backward-compat with no new fields. (3 tests)
- **Validation**: `TestSearchSpecValidation` (lines 255-290) covers `min_revenue_millions` zero, positive, negative (raises), and None.
- **Backward compatibility**: Confirmed via `test_minimal_construction_defaults` (line 186), `test_existing_callers_unaffected` (line 366), and `test_backward_compat_no_new_fields` (line 525).

Total reported: 63 tests. Coverage of all nine acceptance criteria is confirmed.

## Acceptance Criteria Coverage

| Criterion | Status | Evidence |
|---|---|---|
| `query_type: str \| None = None` | Covered | `spec.py:75`, tests lines 354-370 |
| Patent expiry window start/end | Covered | `spec.py:92`, `DateWindow` model, tests lines 476-487 |
| `cell_line_class` for all 8 classes | Covered | `enums.py:22-41`, `spec.py:89`, tests lines 379-419 |
| `min_revenue_millions: float \| None` | Covered | `spec.py:96`, tests lines 276-290, 451-457 |
| `jurisdictions: list[Jurisdiction]` | Covered | `spec.py:97`, `enums.py:6-19`, tests lines 459-466 |
| mAb/monoclonal antibody variants | Covered | `enums.py:48-49`, tests lines 430-442 |
| All new fields optional/backward-compatible | Covered | All default to `None` or `[]`, tests lines 186-199, 366-370, 525-536 |
| DIR-007 example composite query | Covered | Test line 496-512 |
| Revenue, jurisdiction, cell-line explicit tests | Covered | Tests lines 451-466, 379-419 |

## Verification Evidence

- Task notes report 63 tests passed and ruff clean. Reviewer was unable to independently execute `uv run pytest` or `uv run ruff check` during this session due to tool permission constraints; verification relies on implementer-reported results in the task file.
- Code inspection confirms no syntax errors, correct Pydantic field definitions, and proper enum inheritance.

## Residual Risks

- **Low**: `query_type` is typed as `str | None` rather than a constrained enum. This is intentional per the AC ("preferably `query_type: str | None = None`") and allows downstream consumers to define their own type vocabulary. If type safety becomes a concern later, a `Literal` or enum can be introduced without breaking changes.
- **Low**: The `CellLineClass` enum includes values beyond the eight required (e.g., `ORGANOID`, `STEM_CELL_DERIVED`). These are additive and pose no backward-compatibility risk, but downstream consumers should be aware of the full value set.
- **None identified**: No security, performance, or correctness issues found.
