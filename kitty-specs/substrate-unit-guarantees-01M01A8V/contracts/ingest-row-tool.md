# Contract: `ingest_row` MCP tool (the paved road)

One collapsed-parameterized tool on the **default** agent surface (per the existing convention; +1 tool total). The only sanctioned path for manually-transcribed data.

## Ops

### `op="suggest_metric"`

- Input: `field_name` (raw column/test label).
- Behavior: same resolution a parser author gets from `parsers.lookup.suggest_metric`; no new matching logic.
- Output: `metric_id` or null (caller then follows the standards-first ladder or stops).

### `op="load"`

- Input: `metric_id`, `ts_utc` (ISO 8601), `value_num` or `value_text`, `unit` (as observed — what the source states), `source_ref` (mandatory plain-text provenance, e.g. "operator spreadsheet row 14").
- Behavior: builds a single-row `IngestBatch(source_kind=MANUAL_LOAD_SOURCE_KIND)` via `store.manual_load` and calls `loader.load()` — the same boundary as every parser; unit convert-or-refuse and skip persistence apply with zero special-casing.
- Output: `status='loaded'` with the stored canonical unit, or `status='refused'` with the reason (also queryable in `hp.ingest_skip`).

## Refusal rules (before the loader)

- Missing `source_ref` → refused; provenance is not optional and never fabricated.
- `op="load"` may only use the manual source kind; arbitrary `source_kind` values are rejected by the tool AND would raise at the boundary rail regardless.

## Anti-goals

- Not a bulk importer: one row per call, by design — batches of real source artifacts deserve a parser (build-and-use remains the documented route for recurring formats).
- No unit conversion logic in the tool; it delegates entirely.
