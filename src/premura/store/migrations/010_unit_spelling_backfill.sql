-- 010_unit_spelling_backfill.sql — one-time relabel of legacy spelling-only
-- unit variants in hp.fact_measurement to their canonical spelling.
--
-- Why: parser/backfill history left some rows with a unit spelling that
-- premura.units.normalize_unit would map to the metric's dim_metric.canonical_unit
-- today, but that never got applied at load time. `premura audit-integrity`
-- (T017) surfaces these as unit != canonical_unit mismatches; this migration
-- clears the spelling-only subset.
--
-- Vetting rule: a (stored, canonical) pair is in the allowlist below iff
-- units.normalize_unit(stored) == canonical — i.e. the row's numeric value
-- does NOT change, only how the unit is spelled. Pairs are the literal
-- entries of units._ALIASES / _CASE_SENSITIVE_ALIASES (the reviewed alias
-- table) whose target differs from the raw key, plus the µg/l unicode
-- variant named explicitly in the mission spec (normalize_unit ASCII-folds
-- µ/μ before lookup, so the literal "µg/l" spelling never appears as an
-- _ALIASES key even though it normalizes to ug_per_l).
--
-- Deliberately NOT relabeled: any pair where the stored unit is a genuine
-- *different magnitude* under the metric's canonical unit (e.g. mg/dl stored
-- for a metric whose canonical_unit is mmol_per_l) — that requires a value
-- conversion via units.convert, not a relabel, and is out of scope here.
-- Values are never rescaled by this migration.
--
-- Idempotent: the UPDATE only touches rows where fact_measurement.unit is
-- still a stored (non-canonical) spelling; once relabeled, unit = canonical
-- and the WHERE clause no longer matches, so re-running is a no-op.

UPDATE hp.fact_measurement AS fm
SET unit = allowlist.canonical
FROM hp.dim_metric AS dm,
     (VALUES
        ('%', 'pct'),
        ('/nl', '10^9_per_l'),
        ('/pl', '10^12_per_l'),
        ('10^12/l', '10^12_per_l'),
        ('10^9/l', '10^9_per_l'),
        ('10e12/l', '10^12_per_l'),
        ('10e9/l', '10^9_per_l'),
        ('G/l', '10^9_per_l'),
        ('T/l', '10^12_per_l'),
        ('eu/dl', 'EU_per_dl'),
        ('f', 'fl'),
        ('g/100g', 'g_per_100g'),
        ('g/dl', 'g_per_dl'),
        ('g/g', 'ug_per_g'),
        ('g/l', 'g_per_l'),
        ('gr/dl', 'g_per_dl'),
        ('inch', 'in'),
        ('inches', 'in'),
        ('iu/ml', 'IU_per_ml'),
        ('k/microl', '10^9_per_l'),
        ('k/microl.', '10^9_per_l'),
        ('k/ul', '10^9_per_l'),
        ('lbs', 'lb'),
        ('m/ul', '10^12_per_l'),
        ('meq/l', 'mEq_per_l'),
        ('mg/1', 'mg_per_l'),
        ('mg/dl', 'mg_per_dl'),
        ('mg/l', 'mg_per_l'),
        ('microiu/ml', 'mIU_per_ml'),
        ('microu/ml', 'microU_per_ml'),
        ('mila/mmc', '10^9_per_l'),
        ('miu/l', 'mIU_per_l'),
        ('miu/ml', 'mIU_per_ml'),
        ('ml/min/1.73m2', 'ml_per_min_per_173m2'),
        ('mm/h', 'mm_per_h'),
        ('mmol/l', 'mmol_per_l'),
        ('mmol/mol', 'mmol_per_mol'),
        ('molli', 'umol_per_l'),
        ('mu/l', 'mU_per_l'),
        ('mu/ml', 'mU_per_ml'),
        ('ng/dl', 'ng_per_dl'),
        ('ng/ml', 'ng_per_ml'),
        ('pg/eritr', 'pg'),
        ('pg/eritr.', 'pg'),
        ('pg/ml', 'pg_per_ml'),
        ('pmol/l', 'pmol_per_l'),
        ('sec', 's'),
        ('sek', 's'),
        ('t/l', '10^12_per_l'),
        ('u/', 'U_per_l'),
        ('u/l', 'U_per_l'),
        ('ug/dl', 'ug_per_dl'),
        ('ug/g', 'ug_per_g'),
        ('ug/l', 'ug_per_l'),
        ('ug/ml', 'ug_per_ml'),
        ('umol/l', 'umol_per_l'),
        ('µg/l', 'ug_per_l')
     ) AS allowlist(stored, canonical)
WHERE fm.metric_id = dm.metric_id
  AND fm.unit = allowlist.stored
  AND dm.canonical_unit = allowlist.canonical;
