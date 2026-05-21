-- 002_dim_metric_ontology.sql — v2 architectural skeleton ontology extension.
--
-- Mission: v2-architectural-skeleton-01KS4SHA (WP01).
-- Purpose: extend hp.dim_metric with six new nullable columns so the engine,
-- parser, and MCP contracts can rely on richer per-metric metadata
-- (category, validity_window, missing_data_policy, multilingual aliases,
-- LOINC and IEEE 1752.1 cross-references).
--
-- DuckDB version expectation: ADD COLUMN IF NOT EXISTS is supported from
-- DuckDB >= 0.8. The project pins duckdb>=1.1,<2 so this is safe.
--
-- Backward compatibility: all six columns are nullable. Pre-existing rows
-- continue to work without any backfill. The seed loader (`seed_dim_metric`
-- in src/premura/store/duck.py) supplies values per row from
-- src/premura/dim_metric.yaml on every bootstrap, so rows missing the new
-- keys gracefully degrade to NULL.

ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS category VARCHAR;
ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS validity_window VARCHAR;
ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS missing_data_policy VARCHAR;
ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS aliases JSON;
ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS loinc VARCHAR;
ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS ieee1752 VARCHAR;
