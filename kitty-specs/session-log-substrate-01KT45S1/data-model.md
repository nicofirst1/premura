# Phase 1 Data Model: Session Log Substrate (Slice One)

All session-log tables live in the session log's **own DuckDB file** (D1), never
in `health.duckdb` and never folded into `trace.*`. DDL is idempotent
(`CREATE ... IF NOT EXISTS`), applied on connect via the session-log package's
own `init_schema()`. Field names track the OpenTelemetry GenAI conventions where
they exist (hardcoded strings, not imported).

## Tables

### `log_session` — one row per operating run

| Column | Type | Notes |
| --- | --- | --- |
| `session_id` | VARCHAR PK | ULID/uuid string (python-ulid, as elsewhere) |
| `started_at` | TIMESTAMP | nondeterministic; not used by the grader (D5) |
| `finished_at` | TIMESTAMP | nullable until teardown |
| `operator_model` | VARCHAR | the operating AI's model id; sentinel for the fake scripted agent / fake operator |
| `driver_model` | VARCHAR | the driver AI's model id; sentinel in repeatable check |
| `premura_version` | VARCHAR | sandbox run identity |
| `isolation_tag` | VARCHAR | unique per-sandbox tag |
| `run_kind` | VARCHAR | `repeatable_check` \| `live_trial` |

### `log_step` — one row per captured unit of work (a tree)

| Column | Type | Notes |
| --- | --- | --- |
| `step_id` | VARCHAR PK | |
| `session_id` | VARCHAR FK → log_session | |
| `parent_step_id` | VARCHAR FK → log_step | nullable; builds the turn→call tree |
| `kind` | VARCHAR | `agent_turn` \| `model_call` \| `tool_call` |
| `name` | VARCHAR | e.g. the gen_ai tool name |
| `tool_name` | VARCHAR | named-tool convention: `edit_file`, `run_tests`, `parser_contract_check`, `skill:parser-generator`, `ingest_run` (FR-004) |
| `request_summary` | VARCHAR | PHI-safe envelope summary |
| `request_hash` | VARCHAR | |
| `result_status` | VARCHAR | `available`\|`missing`\|`stale`\|`insufficient`\|`refused`\|`error` (FR-003) |
| `result_summary` | VARCHAR | |
| `result_hash` | VARCHAR | |
| `started_at` | TIMESTAMP | not used by grader |
| `finished_at` | TIMESTAMP | not used by grader |

The **verdict-bearing** step is the one with `tool_name='ingest_run'`; its detail
lands in `log_ingest_provenance`.

### `log_ingest_provenance` — Premura-internal facts per ingest run

Mixed source-of-truth, explicitly distinguished (spec §"Pass" table). The harness
**writes** these; the grader **recomputes** the verdict from them + the sandbox
warehouse + the fixture. `contract_pass` is the grader's **output**, not an input.

| Column | Type | Origin / trust |
| --- | --- | --- |
| `step_id` | VARCHAR FK → log_step | the `ingest_run` step |
| `batch_id` | VARCHAR | from `LoadStats.batch_id` |
| `parser_kind` | VARCHAR | which parser ran |
| `rows_inserted` | INTEGER | **loader-measured** (authoritative) |
| `rows_skipped_dup` | INTEGER | **loader-measured** |
| `rows_skipped_priority` | INTEGER | **loader-measured** |
| `declared_metrics_json` | VARCHAR(JSON) | captured so grader recomputes "declared = emitted" |
| `emitted_metric_ids_json` | VARCHAR(JSON) | captured (the batch's emitted metric_ids) |
| `unmapped_metrics_json` | VARCHAR(JSON) | **parser claim** (not authoritative) |
| `skipped_rows_json` | VARCHAR(JSON) | **parser claim** (not authoritative) |
| `contract_pass` | BOOLEAN | **grader's recomputed** runtime-subset result, written back |

Source fields for the honesty reconciliation are **not** stored here — they come
from the committed fixture manifest (ground truth) compared against the sandbox
warehouse at grade time.

## Non-persisted structures (in-memory contracts)

### Ingest outcome envelope (subprocess → harness; JSON)

Emitted on stdout by `harness/ingest_runner.py` running inside the sandbox. Raw
**measured evidence only** — no verdict, no log writing. See
`contracts/ingest-outcome-envelope.schema.json`.

```
{
  "status": "ok" | "error",
  "error": null | { "kind": "...", "message": "..." },
  "parser_kind": "good_fitbit_hr",
  "batch_id": "...",
  "load_stats": { "rows_inserted": 0, "rows_skipped_dup": 0, "rows_skipped_priority": 0 },
  "declared_metrics": ["heart_rate"],
  "emitted_metric_ids": ["heart_rate"],
  "unmapped_metrics": ["confidence", "altitude_m"],
  "skipped_rows": [ { "reason": "...", "field": "..." } ]
}
```

### Fixture manifest (`tests/fixtures/session_log/fixture_fields.yaml`) — ground truth (D6)

```
source: fitbit_heart_rate
source_fields:
  - name: bpm
    canonical_metric: heart_rate      # mappable; distinct metric per mappable field
  - name: confidence
    canonical_metric: null            # inherently unmappable → honest = declared unmapped
  - name: altitude_m
    canonical_metric: null
```

Constraint: each non-null `canonical_metric` is **distinct** so "metric present
in warehouse" unambiguously witnesses that field (D6).

### Runtime contract check result (`parsers/contract_check.py`)

```
{ "runtime_valid": bool, "violations": [ "<clause>: <detail>", ... ] }
```
Clauses recomputed: `no_derived_emitted`, `declared_equals_emitted`,
`declared_exist_in_dim_metric`, `produced_batch_without_raising`.

### Grader verdict (`harness/grader.py`) — deterministic (D5)

Excludes ids/timestamps; all lists sorted. See `contracts/grader-verdict.schema.json`.

```
{
  "passed": false,
  "rules": {
    "loaded":            { "passed": true,  "warehouse_rows": 3, "logged_rows_inserted": 3 },
    "runtime_valid":     { "passed": true,  "violations": [] },
    "honest_about_gaps": { "passed": false, "silent_drops": ["altitude_m"] }
  }
}
```

`passed == (loaded.passed and runtime_valid.passed and honest_about_gaps.passed)`.

## Entity relationships

```
log_session 1───* log_step 1───* log_step (parent_step_id, the tree)
                       │
                       └──(ingest_run step) 1───1 log_ingest_provenance
fixture_fields.yaml (ground truth) ─┐
sandbox warehouse (boundary truth) ─┼─► grader ─► Verdict
log_ingest_provenance (claims+measured) ─┘
```

## Validation rules (from requirements)

- `result_status` ∈ the fixed six-value vocabulary (FR-003).
- `run_kind` ∈ {`repeatable_check`, `live_trial`} (FR-032).
- `tool_name` follows the named-tool convention; the verdict-bearing step is
  `ingest_run` (FR-004).
- `log_ingest_provenance.contract_pass` is **write-only by the grader**; never set
  from the parser/runner (FR-061/FR-065).
- Honesty reconciliation: a source field neither loaded (its distinct metric
  present) nor declared (in unmapped/skipped) ⇒ silent drop ⇒ fail (FR-064).
- Single-writer: only the parent harness opens the session-log file for writing
  (FR-021); the subprocess never opens it.
