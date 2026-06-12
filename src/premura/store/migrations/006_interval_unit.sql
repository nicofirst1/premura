-- 006_interval_unit.sql — give hp.fact_interval a unit column sourced from the
-- metric registry (m7 WP3).
--
-- Why: STATUS.md Known-limitations called out "fact_interval has no unit column;
-- carried in memory only." In fact the in-memory Interval.unit was already
-- dropped silently in dedupe._interval_frame, so parser-supplied unit strings
-- never reached the warehouse. The fix makes the warehouse the single source of
-- unit truth via dim_metric.canonical_unit — never a parser-supplied string.
--
-- Shape: one nullable column plus an idempotent backfill. Re-running the normal
-- migration loader (premura.store.duck.run_migrations) must not error or churn:
--   * ADD COLUMN IF NOT EXISTS is a no-op once the column exists;
--   * the backfill UPDATE only touches rows whose unit IS NULL, so a second run
--     finds nothing to update and the values stay stable.
--
-- The companion mirror on hp.fact_measurement is intentionally NOT touched here
-- (measurement already persists its unit through the loader); this migration is
-- scoped to the interval seam named in the limitation.

ALTER TABLE hp.fact_interval ADD COLUMN IF NOT EXISTS unit VARCHAR;

-- Backfill from the owning metric's canonical_unit. Idempotent: only NULL units
-- are filled, and the value comes from the metric registry, so re-running is a
-- no-op once every joinable row is populated.
UPDATE hp.fact_interval AS fi
SET unit = dm.canonical_unit
FROM hp.dim_metric AS dm
WHERE fi.metric_id = dm.metric_id
  AND fi.unit IS NULL;
