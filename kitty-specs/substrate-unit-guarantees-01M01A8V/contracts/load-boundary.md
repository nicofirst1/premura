# Contract: the load boundary (units + vocabulary)

Applies to `premura.store.loader.load(conn, batch)` — the single write seam for `hp.fact_*`.

## Guarantees (mechanically enforced here, nowhere else)

1. **Canonical units**: every persisted `fact_measurement` row's `unit` equals its metric's `dim_metric.canonical_unit`. The loader converts the value via `premura.units.convert` when the observed unit differs; if no rule exists, the row is refused — never relabeled, never passed through.
2. **Row-level refusal**: an unconvertible row is skipped and recorded in `hp.ingest_skip` (`kind='unit_unconvertible'`, with from/to units and reason); the rest of the batch commits. Batch-level contract violations (undeclared metric, unknown source kind, missing descriptor) still fail the whole batch atomically.
3. **Vocabulary rail**: `validate_batch_against_warehouse` raises `ValueError` before any write when `batch.source_kind` is not a registered parser source kind or `MANUAL_LOAD_SOURCE_KIND` — unless the caller passes the explicit `allow_unregistered_source_kind=True` capability. Only the harness's build-and-use entry (`ingest_runner`, the sanctioned runtime-parser door per ADR 0010) passes it; the flag is greppable, and unregistered kinds remain visible to `audit-integrity` via `ingest_run.source_kind`. Hand-crafted `load()` calls without the flag still raise.
4. **Closed loop**: `batch.skipped_rows` and `batch.unmapped_metrics` are persisted to `hp.ingest_skip` before the run finishes — nothing computed is dropped.

## Obligations on writers (parsers, manual load)

- Emit `Measurement.unit` **as observed** in the source; never pre-convert.
- Preserve the original unit string in `raw_payload`.
- Never open the warehouse read-write outside `loader.load()`; `duck.connect` defaults to read-only.

## Non-guarantees

- The boundary does not validate clinical plausibility (out-of-range values are data, not errors).
- BMT wide-format's config-declared unit is a parser-level assumption (no per-row unit exists in that format) — documented scope exception.
