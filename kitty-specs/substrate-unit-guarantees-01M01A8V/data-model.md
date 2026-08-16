# Phase 1 Data Model

## New table: `hp.ingest_skip` (migration `009_ingest_skip.sql`)

Durable, queryable record of everything the load boundary refused or a parser skipped. Mirrors the append-only idempotent shape of `005_trace_audit.sql`.

| Column      | Type                                | Notes                                                                                           |
| ----------- | ----------------------------------- | ----------------------------------------------------------------------------------------------- |
| skip_id     | VARCHAR PK                          | generated per record                                                                            |
| batch_id    | VARCHAR NOT NULL FK → hp.ingest_run | joins refusals to their run                                                                     |
| kind        | VARCHAR NOT NULL                    | `unit_unconvertible` \| `unmapped_metric` \| `parser_skip` (`dup_priority` count-only, stretch) |
| raw_field   | VARCHAR                             | vendor field / column label as seen                                                             |
| metric_id   | VARCHAR                             | nullable — unmapped rows have none yet                                                          |
| from_unit   | VARCHAR                             | observed (normalized) unit                                                                      |
| to_unit     | VARCHAR                             | the metric's canonical unit                                                                     |
| reason      | VARCHAR NOT NULL                    | human/agent-readable refusal reason                                                             |
| recorded_at | TIMESTAMP DEFAULT now()             |                                                                                                 |

Indexes on `batch_id` and `kind`.

## Changed semantics (no schema change)

- `hp.fact_measurement.unit`: now always equals `dim_metric.canonical_unit` (loader-enforced; the parser-supplied value is input, not truth). Observed unit preserved in `raw_payload`.
- `parsers/base.py Measurement.unit`: documented as **unit as observed** — what the source stated, never a converted claim.
- `LoadStats`: gains `rows_skipped_unit`.

## Modified rows (migration `010_unit_spelling_backfill.sql`)

One-time idempotent relabel of legacy `fact_measurement.unit` values that differ from canonical **only in spelling** — allowlist of vetted (stored, canonical) pairs baked into the SQL at authorship time; values never rescaled; magnitude-wrong rows excluded by construction.

## Vocabulary constants

- `MANUAL_LOAD_SOURCE_KIND` — defined once (store layer), imported by the loader rail and the MCP tool. Membership rule at the boundary: `source_kind ∈ registered_source_kinds() ∪ {MANUAL_LOAD_SOURCE_KIND}`.
