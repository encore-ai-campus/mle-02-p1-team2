-- PostgreSQL + pgvector schema for the SIF case-retrieval track.
-- This creates an empty schema only; it does not read or transform the source XLSX.
-- Requires the pgvector PostgreSQL extension to be installed on the database server.

CREATE EXTENSION IF NOT EXISTS vector;

CREATE TABLE IF NOT EXISTS sif_cases (
    case_id TEXT PRIMARY KEY,
    source_file TEXT NOT NULL,
    source_sheet TEXT,
    source_row INTEGER CHECK (source_row > 0),
    source_serial INTEGER CHECK (source_serial > 0),

    industry_major TEXT,
    industry_mid TEXT,
    industry_small TEXT,

    construction_work TEXT,
    construction_task TEXT,
    unit_task TEXT,
    disaster_type TEXT,

    object_text TEXT,
    high_risk_work TEXT,
    incident_overview TEXT,
    precursor TEXT,
    control_measure TEXT,

    page_content TEXT NOT NULL,
    embedding_model TEXT NOT NULL,
    embedding vector(1536) NOT NULL,

    source_url TEXT NOT NULL,
    created_at TIMESTAMPTZ NOT NULL DEFAULT now(),

    CONSTRAINT uq_sif_source_case UNIQUE (source_sheet, source_serial)
);

CREATE INDEX IF NOT EXISTS ix_sif_cases_industry_major ON sif_cases (industry_major);
CREATE INDEX IF NOT EXISTS ix_sif_cases_industry_mid ON sif_cases (industry_mid);
CREATE INDEX IF NOT EXISTS ix_sif_cases_source_sheet ON sif_cases (source_sheet);
CREATE INDEX IF NOT EXISTS ix_sif_cases_disaster_type ON sif_cases (disaster_type);

-- Add the ANN index after the database server's pgvector version is confirmed.
-- For cosine distance on supported pgvector versions:
-- CREATE INDEX ix_sif_cases_embedding_hnsw
--     ON sif_cases USING hnsw (embedding vector_cosine_ops);
