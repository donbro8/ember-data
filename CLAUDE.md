# ember-data

## What this package does

All data access for the Ember Bio platform. Provides BigQuery client and query
builders, Pydantic domain models (Target, Trial, Patent, Article, Candidate),
Vertex AI vector search integration, and document parsing/ingestion pipeline.

## Key modules

- `bigquery/` — BigQuery client wrapper, dataset configs, query builders
- `vector/` — Vertex AI Vector Search integration
- `models/` — Domain models (trials, patents, articles)
- `ingest/` — PDF/doc parsing pipeline

## How to run tests

```bash
uv sync --extra dev
uv run pytest --cov
```

## Conventions

- All domain models are Pydantic BaseModel subclasses
- BigQuery queries use parameterized queries — never string interpolation
- Depends on ember-shared for settings and base models
- For local dev, ember-shared is editable via [tool.uv.sources]
- Lint with ruff: `uv run ruff check src/ tests/`

## Agent Routing (3 agents)

| Role | Agent File | Tier Class | When to Use |
|---|---|---|---|
| module-architect | `.claude/agents/module-architect.md` | architect | Data layer design, query architecture, model structure |
| implementer | `.claude/agents/implementer.md` | implementer | Query implementation, model coding, tests |
| reviewer | `.claude/agents/reviewer.md` | reviewer | Query safety review, model correctness, cost analysis |

Selection rule: SMA dispatches the appropriate agent based on task type. Module-architect for design tasks, implementer for coding tasks, reviewer for review tasks.
