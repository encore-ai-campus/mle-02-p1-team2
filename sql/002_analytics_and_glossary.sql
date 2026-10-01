-- Relational tables for dashboard metrics and query-expansion vocabulary.
-- These tables are kept separate from the SIF vector corpus.

CREATE TABLE IF NOT EXISTS industry_statistics (
    dataset_id TEXT NOT NULL,
    reference_date DATE NOT NULL,
    industry_major TEXT NOT NULL,
    industry_mid TEXT NOT NULL,
    business_size TEXT NOT NULL,
    metric TEXT NOT NULL,
    value NUMERIC,
    industry_major_raw TEXT,
    industry_mid_raw TEXT,
    source_size_column TEXT,
    source_row INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    source_url TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_id, source_row, business_size)
);

CREATE INDEX IF NOT EXISTS ix_industry_statistics_filter
    ON industry_statistics (metric, industry_mid, business_size);
CREATE INDEX IF NOT EXISTS ix_industry_statistics_date
    ON industry_statistics (reference_date);

CREATE TABLE IF NOT EXISTS fatality_trends (
    dataset_id TEXT NOT NULL,
    year SMALLINT NOT NULL,
    business_size TEXT NOT NULL,
    metric TEXT NOT NULL,
    value NUMERIC,
    source_category TEXT,
    source_year_column TEXT,
    source_row INTEGER NOT NULL,
    source_file TEXT NOT NULL,
    source_url TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dataset_id, year, business_size)
);

CREATE INDEX IF NOT EXISTS ix_fatality_trends_year_size
    ON fatality_trends (year, business_size);

CREATE TABLE IF NOT EXISTS safety_glossary_pairs (
    dictionary_type TEXT NOT NULL,
    canonical_term TEXT NOT NULL,
    variant TEXT NOT NULL,
    variant_position INTEGER,
    source_member TEXT NOT NULL,
    loaded_at TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (dictionary_type, canonical_term, variant, source_member)
);

CREATE INDEX IF NOT EXISTS ix_safety_glossary_variant
    ON safety_glossary_pairs (variant);
CREATE INDEX IF NOT EXISTS ix_safety_glossary_canonical
    ON safety_glossary_pairs (canonical_term);
