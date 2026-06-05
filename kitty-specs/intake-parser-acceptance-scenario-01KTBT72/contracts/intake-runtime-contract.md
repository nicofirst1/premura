# Contract — intake `runtime_valid` (the bounded runtime subset)

> Satisfies FR-010 / SC-008. `runtime_valid` is a **bounded runtime-checkable subset**,
> explicitly **NOT** the full parser-review contract (`src/premura/parsers/CONTRACT.md`).

## Observation form (UNCHANGED — `check_runtime_contract`, verbatim)

The four shipped clauses, recomputed by the grader (pinned to the live function):

1. `no_derived_emitted` — no emitted metric_id is in the reserved `derived:` namespace.
2. `declared_equals_emitted` — the declared metric set equals the emitted metric set.
3. `declared_exist_in_dim_metric` — every declared metric exists in `dim_metric`.
4. `produced_batch_without_raising` — the ingest produced a batch (the run did not fail).

## Intake form (NEW — `check_intake_runtime_contract`)

The analogue, defined against `IntakeBatch` (which has **no** metric_id / `dim_metric` /
emitted-metric surface; it has nutrition/supplement events, `source_descriptors`,
`unmapped_metrics`, `skipped_rows`, and `validate()`):

1. `parser_imports_and_parses` — the parser module imports and `parse()` returns an
   `IntakeBatch` (or a `ParseOutput` carrying one) **without raising**.
2. `batch_validates` — `IntakeBatch.validate()` passes: every event `source_id` has a
   matching `source_descriptor`, and there are no duplicate dedupe_keys.
3. `persisted_without_raising` — `persist_intake_batch` loads the batch without raising.

`runtime_valid = (no violations)`; `violations` is a sorted list of `"<clause>: <detail>"`
strings (same shape as the observation result, feeding the unchanged verdict schema).

## Invariants

- The clause **names and count** in this contract MUST match the implementation; a test
  asserts this so the spec cannot drift from the checker (FR-010).
- `runtime_valid` MUST NOT be widened to any clause from the full parser-review contract.
- The grader's persisted `contract_pass` is this recomputed `runtime_valid`, never an
  operator/runner self-report (FR-005).
