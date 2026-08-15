-- delete_labsheet_rows.sql — one-shot remediation, hand-run, not a migration.
--
-- Incident (see issue #113): rows were written directly to hp.fact_measurement
-- via raw duck.connect() + INSERT, bypassing every sanctioned load path. They
-- carry the unregistered source_kind 'labsheet', which no parser or loader
-- ever emits. Several are unit-corrupted (values stored under the wrong
-- canonical unit) because the bypass skipped the loader's convert-or-refuse
-- step entirely.
--
-- Rule: delete these rows, then re-enter the same data through the paved
-- road — the `ingest_row` MCP tool (op=suggest_metric, then op=load, with
-- mandatory source_ref provenance). Do not hand-fix values in place. Deleting
-- and re-entering through the loader is what re-applies unit conversion and
-- provenance correctly.
--
-- HOW TO RUN: this file is reviewed and run by hand against the real
-- warehouse, in two passes.
--   1. Run the DRY-RUN section first (SELECT COUNT(*) only). Confirm the
--      counts match what you expect from the incident before touching
--      anything.
--   2. Only then run the DELETE section. Re-run the dry-run section
--      afterward — every count should be 0.
--
-- Idempotent by construction: a second run of the DELETE section matches and
-- deletes nothing, because the first run already removed the matching rows.
--
-- Defensive by construction: the bypass may or may not have created
-- hp.dim_source / hp.ingest_run descriptor rows for its writes. The deletes
-- below do not assume either shape — they delete fact rows by the
-- dim_source.source_kind = 'labsheet' join, then clean up the descriptor
-- rows themselves, whether or not they exist.

-- =========================================================================
-- 1. DRY RUN — run this first. Read the counts before running any DELETE.
-- =========================================================================

-- dim_source rows under the unregistered kind.
SELECT COUNT(*) AS labsheet_dim_source_rows
FROM hp.dim_source
WHERE source_kind = 'labsheet';

-- fact_measurement rows attributed to those sources.
SELECT COUNT(*) AS labsheet_fact_measurement_rows
FROM hp.fact_measurement
WHERE source_id IN (SELECT source_id FROM hp.dim_source WHERE source_kind = 'labsheet');

-- fact_interval rows attributed to those sources (none expected per the
-- incident, but the bypass wrote raw SQL — check rather than assume).
SELECT COUNT(*) AS labsheet_fact_interval_rows
FROM hp.fact_interval
WHERE source_id IN (SELECT source_id FROM hp.dim_source WHERE source_kind = 'labsheet');

-- ingest_run bookkeeping under the same kind, if the bypass created any.
SELECT COUNT(*) AS labsheet_ingest_run_rows
FROM hp.ingest_run
WHERE source_kind = 'labsheet';

-- fact_measurement rows that point at one of those ingest_run rows via
-- ingest_batch, even if their source_id doesn't resolve to a labsheet
-- dim_source row (the two bookkeeping trails can diverge under a bypass).
SELECT COUNT(*) AS labsheet_fact_measurement_rows_by_batch
FROM hp.fact_measurement
WHERE ingest_batch IN (SELECT batch_id FROM hp.ingest_run WHERE source_kind = 'labsheet');

-- =========================================================================
-- 2. DELETE — run only after reviewing the dry-run counts above.
-- =========================================================================

-- Fact rows first, by source_id (covers the shape where dim_source rows
-- exist for the bypass writes).
DELETE FROM hp.fact_measurement
WHERE source_id IN (SELECT source_id FROM hp.dim_source WHERE source_kind = 'labsheet');

DELETE FROM hp.fact_interval
WHERE source_id IN (SELECT source_id FROM hp.dim_source WHERE source_kind = 'labsheet');

-- Fact rows again, by ingest_batch (covers the shape where a bypass write
-- recorded an ingest_run row but used a source_id that doesn't resolve to a
-- labsheet dim_source row).
DELETE FROM hp.fact_measurement
WHERE ingest_batch IN (SELECT batch_id FROM hp.ingest_run WHERE source_kind = 'labsheet');

DELETE FROM hp.fact_interval
WHERE ingest_batch IN (SELECT batch_id FROM hp.ingest_run WHERE source_kind = 'labsheet');

-- Skip-bucket rows tied to a labsheet ingest_run (may not exist — the bypass
-- never went through the loader that populates this table — delete anyway
-- so the ingest_run rows below have no remaining dependents).
DELETE FROM hp.ingest_skip
WHERE batch_id IN (SELECT batch_id FROM hp.ingest_run WHERE source_kind = 'labsheet');

-- Descriptor/bookkeeping rows last, now that no fact rows reference them.
DELETE FROM hp.dim_source
WHERE source_kind = 'labsheet';

DELETE FROM hp.ingest_run
WHERE source_kind = 'labsheet';
