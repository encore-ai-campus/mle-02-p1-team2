-- API records have no XLSX sheet, row number, or source serial.
-- Keep those fields NULL rather than inventing provenance values.
ALTER TABLE sif_cases ALTER COLUMN source_sheet DROP NOT NULL;
ALTER TABLE sif_cases ALTER COLUMN source_row DROP NOT NULL;
ALTER TABLE sif_cases ALTER COLUMN source_serial DROP NOT NULL;
