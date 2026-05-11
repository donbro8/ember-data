"""BigQuery table schema definitions for run results and summaries."""

from __future__ import annotations

# ---------------------------------------------------------------------------
# Patent sub-record fields (PatentJurisdiction)
# ---------------------------------------------------------------------------

_PATENT_FIELDS = [
    {"name": "country_code", "type": "STRING", "mode": "NULLABLE"},
    {"name": "country_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "publication_number", "type": "STRING", "mode": "NULLABLE"},
    {"name": "filing_date", "type": "DATE", "mode": "NULLABLE"},
    {"name": "grant_date", "type": "DATE", "mode": "NULLABLE"},
    {"name": "expiry_date", "type": "DATE", "mode": "NULLABLE"},
    {"name": "expiry_date_approximate", "type": "BOOLEAN", "mode": "NULLABLE"},
    {"name": "expiry_derivation_method", "type": "STRING", "mode": "NULLABLE"},
    {"name": "expiry_derivation_provenance", "type": "STRING", "mode": "NULLABLE"},
    {"name": "status", "type": "STRING", "mode": "NULLABLE"},
    {"name": "title", "type": "STRING", "mode": "NULLABLE"},
    {"name": "url", "type": "STRING", "mode": "NULLABLE"},
]

# ---------------------------------------------------------------------------
# Trial sub-record fields (TrialSummary)
# ---------------------------------------------------------------------------

_TRIAL_FIELDS = [
    {"name": "nct_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "phase", "type": "STRING", "mode": "NULLABLE"},
    {"name": "status", "type": "STRING", "mode": "NULLABLE"},
    {"name": "indication", "type": "STRING", "mode": "NULLABLE"},
    {"name": "sponsor", "type": "STRING", "mode": "NULLABLE"},
    {"name": "url", "type": "STRING", "mode": "NULLABLE"},
]

# ---------------------------------------------------------------------------
# Article sub-record fields (ArticleSummary)
# ---------------------------------------------------------------------------

_ARTICLE_FIELDS = [
    {"name": "pmid", "type": "STRING", "mode": "NULLABLE"},
    {"name": "title", "type": "STRING", "mode": "NULLABLE"},
    {"name": "journal", "type": "STRING", "mode": "NULLABLE"},
    {"name": "year", "type": "INT64", "mode": "NULLABLE"},
    {"name": "doi", "type": "STRING", "mode": "NULLABLE"},
    {"name": "url", "type": "STRING", "mode": "NULLABLE"},
]

# ---------------------------------------------------------------------------
# RUN_RESULTS_SCHEMA
# Covers all CandidateResult fields plus run-level metadata.
# ---------------------------------------------------------------------------

RUN_RESULTS_SCHEMA: list[dict] = [
    # Run metadata
    {"name": "run_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "watch_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "query", "type": "STRING", "mode": "REQUIRED"},
    {"name": "query_type", "type": "STRING", "mode": "REQUIRED"},
    {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    # Core identity
    {"name": "drug_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "fda_generic_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "target", "type": "STRING", "mode": "NULLABLE"},
    # Computed fields
    {"name": "result_type", "type": "STRING", "mode": "NULLABLE"},
    {"name": "canonical_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "display_label", "type": "STRING", "mode": "NULLABLE"},
    # Patent sub-records (PatentJurisdiction)
    {
        "name": "patents",
        "type": "RECORD",
        "mode": "REPEATED",
        "fields": _PATENT_FIELDS,
    },
    # Patent-level aggregates
    {"name": "earliest_patent_expiry", "type": "DATE", "mode": "NULLABLE"},
    {"name": "earliest_expiry_jurisdiction", "type": "STRING", "mode": "NULLABLE"},
    {
        "name": "earliest_patent_expiry_derivation_method",
        "type": "STRING",
        "mode": "NULLABLE",
    },
    {"name": "earliest_patent_expiry_verified_date", "type": "DATE", "mode": "NULLABLE"},
    {"name": "data_exclusivity_expiry", "type": "DATE", "mode": "NULLABLE"},
    {"name": "data_exclusivity_regime", "type": "STRING", "mode": "NULLABLE"},
    {"name": "framework_regulatory_context", "type": "JSON", "mode": "NULLABLE"},
    # Scoring
    {"name": "overall_score", "type": "FLOAT64", "mode": "NULLABLE"},
    # Provenance
    {"name": "sources_contributed", "type": "STRING", "mode": "REPEATED"},
    {"name": "source_urls", "type": "STRING", "mode": "REPEATED"},
    # Optional enrichment
    {"name": "indication", "type": "STRING", "mode": "REPEATED"},
    {"name": "mechanism_of_action", "type": "STRING", "mode": "NULLABLE"},
    {"name": "clinical_stage", "type": "STRING", "mode": "NULLABLE"},
    {"name": "risk_flags", "type": "STRING", "mode": "REPEATED"},
    {"name": "synthesis_summary", "type": "STRING", "mode": "NULLABLE"},
    # Score breakdown
    {"name": "structured_score", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "semantic_score", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "evidence_score", "type": "FLOAT64", "mode": "NULLABLE"},
    # Identity enrichment
    {"name": "brand_names", "type": "STRING", "mode": "REPEATED"},
    {"name": "originator", "type": "STRING", "mode": "NULLABLE"},
    {"name": "target_aliases", "type": "STRING", "mode": "REPEATED"},
    {"name": "modality", "type": "STRING", "mode": "NULLABLE"},
    {"name": "category", "type": "STRING", "mode": "NULLABLE"},
    # Evidence — trial sub-records (TrialSummary)
    {
        "name": "trials",
        "type": "RECORD",
        "mode": "REPEATED",
        "fields": _TRIAL_FIELDS,
    },
    {"name": "trial_count", "type": "INT64", "mode": "NULLABLE"},
    {"name": "latest_trial_phase", "type": "STRING", "mode": "NULLABLE"},
    # Evidence — article sub-records (ArticleSummary)
    {
        "name": "articles",
        "type": "RECORD",
        "mode": "REPEATED",
        "fields": _ARTICLE_FIELDS,
    },
    {"name": "article_count", "type": "INT64", "mode": "NULLABLE"},
    # Commercial
    {"name": "annual_revenue_usd_millions", "type": "FLOAT64", "mode": "NULLABLE"},
    {"name": "revenue_year", "type": "INT64", "mode": "NULLABLE"},
    {"name": "biosimilar_competitors", "type": "STRING", "mode": "REPEATED"},
    {"name": "biosimilar_competitor_count", "type": "INT64", "mode": "NULLABLE"},
    {"name": "has_approved_biosimilar", "type": "BOOLEAN", "mode": "NULLABLE"},
    # FDA
    {"name": "fda_brand_name", "type": "STRING", "mode": "NULLABLE"},
    {"name": "fda_manufacturer", "type": "STRING", "mode": "NULLABLE"},
    {"name": "fda_therapeutic_area", "type": "STRING", "mode": "NULLABLE"},
]

# ---------------------------------------------------------------------------
# RUN_SUMMARY_SCHEMA
# One row per run — stores aggregated markdown, cost, and trace.
# ---------------------------------------------------------------------------

RUN_SUMMARY_SCHEMA: list[dict] = [
    {"name": "run_id", "type": "STRING", "mode": "REQUIRED"},
    {"name": "query", "type": "STRING", "mode": "REQUIRED"},
    {"name": "query_type", "type": "STRING", "mode": "REQUIRED"},
    {"name": "watch_id", "type": "STRING", "mode": "NULLABLE"},
    {"name": "full_markdown", "type": "STRING", "mode": "NULLABLE"},
    {"name": "bytes_scanned", "type": "INT64", "mode": "NULLABLE"},
    {"name": "execution_trace", "type": "STRING", "mode": "NULLABLE"},
    {"name": "created_at", "type": "TIMESTAMP", "mode": "REQUIRED"},
    {"name": "change_summary", "type": "STRING", "mode": "NULLABLE"},
]
