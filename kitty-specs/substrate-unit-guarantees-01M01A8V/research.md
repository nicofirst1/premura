# Phase 0 Research: the labsheet incident and the unit landscape

Investigation ran 2026-08-14 (four independent passes: warehouse audit, code trace, GitHub archaeology, clean-room re-ingest of all raw source PDFs into an isolated scratch warehouse). Digest below; issues #111/#113 carry the public summary.

## Findings

1. **Corruption is real and magnitude-class.** All 20 `blood_glucose` measurement rows store mg/dl-scale values under canonical `mmol_per_l` (~18x misread); HbA1c IFCC (mmol/mol) values stored under `%` beside genuine percent rows; sodium/potassium/calcium rows mis-scaled beside correct siblings. Additionally 74 metrics carry spelling-only unit variants (`U/l` vs `U_per_l`) — harmless magnitude, but any `unit == canonical_unit` equality check silently misses them.
2. **The ingest pipeline is not the cause.** Re-ingesting every raw lab PDF through the real `lab_pdf` pipeline into an isolated warehouse produced zero wrong-unit rows: conversions fired correctly; rows with no conversion rule were refused as `unit_mismatch` skips. All polluted rows carry `source_kind='labsheet'` — a string with zero matches anywhere in the repo. The rows were written by raw `duck.connect()` + INSERT, outside every sanctioned surface.
3. **Why the bypass happened.** The only documented route for one-off data is authoring a full `PluginParser` (`docs/operating/RUNTIME_AGENT.md`; smallest real parser is ~160 lines) — heavy for a small spreadsheet. No MCP tool can load a measurement; `suggest_metric` is unreachable outside parser code; direct DB writes are neither offered nor forbidden. The sanctioned path was expensive, the bypass cheap and silent.
4. **The asymmetry.** `fact_interval.unit` is force-sourced from `dim_metric.canonical_unit` at load (`store/loader.py:164-187`; `Interval` has no unit field at all) — proven by `tests/intake/test_interval_unit_ingest.py`. `fact_measurement.unit` loads verbatim from the parser (`loader.py:147-162`), unchecked by `IngestBatch.validate()`, the loader, and the DDL. Conversion logic is duplicated per-parser: `lab_pdf.py:374-446` converts-or-refuses correctly; `bmt.py:75-109` silently passes unknown units through.
5. **Open loops.** `IngestBatch.skipped_rows` / `unmapped_metrics` are computed and dropped (never persisted); `rows_skipped_priority` is counted then discarded (`loader.py:74`). Issue #111 carried a drafted "wontfix" that never executed — its rebuttal only audited the guarded write paths.
6. **Migration reality.** `store/migrations/` replays every file on every bootstrap (no version ledger); all files must stay additive/idempotent. `store/UPDATE_STRATEGY.md` kind (e) rebuild-from-raw is designed but unbuilt — hence the locked decision to delete + re-enter rather than rebuild.

## Decisions carried into this mission (locked with the maintainer)

- Legacy labsheet rows: **delete + re-enter** via the paved road; no rebuild verb this mission.
- Paved road: **MCP tool** on the default agent surface (metric lookup + manual load).
- Conversion rules live in a **module dict**, not `dim_metric.yaml` (formula vs declared-attribute: different facts, different homes).
- Row-level refusal, not whole-batch failure (consistent with the existing skip buckets).
- The labsheet delete is an `ops/` one-shot, never a numbered migration (C-002).
- Every WP review runs the written over-engineering pass (C-005) — the mission exists because over-built process pushed agents into bypasses; it must not itself add mechanism beyond the rail.
