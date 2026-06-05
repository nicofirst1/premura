# Phase 1 Data Model — Intake Parser Acceptance Scenario

These are harness/test-side entities, not warehouse schema changes. No migration is
added by this mission (the intake `hp.*` tables already exist from migration 004).

## Scenario (NEW — `premura.harness.scenario.Scenario`)

A frozen value object; the bounded abstraction the mission introduces.

| Field | Type | Meaning |
|---|---|---|
| `name` | `str` | Stable scenario id (e.g. `"observation_hr"`, `"intake_alien"`). |
| `source_path` | `Path` | The synthetic source artifact dropped into the sandbox. |
| `manifest_path` | `Path` | Ground-truth field map (grader-only; never operator-visible — C-005). |
| `reference_parser` | import target | The layer-1 known-good parser for this source. |
| `strategy` | `DrawerGradingStrategy` | Injected drawer behavior (below). |

**Validation rules.** `name` unique in the registry; `source_path` / `manifest_path`
exist; `strategy` non-null. Registry returns ≥ 2 scenarios (observation + intake) for
SC-003 / NFR-006.

## DrawerGradingStrategy (NEW — injected behavior)

The seam that makes `grade()` drawer-parametric with no per-source branch (NFR-005).
Three responsibilities, each a pure function over captured evidence + warehouse:

| Responsibility | Input | Output | Used by rule |
|---|---|---|---|
| `boundary_truth` | warehouse conn | loaded row count + present keys from the drawer's tables | `loaded` |
| `runtime_check` | captured provenance + warehouse conn | `ContractCheckResult` (`runtime_valid` + `violations`) | `runtime_valid` |
| `gap_set` | manifest + captured provenance + boundary truth | source fields neither loaded nor declared (silent drops) | `honest_about_gaps` |

- **Observation strategy** wraps today's behavior verbatim: `_BOUNDARY` fact tables,
  `check_runtime_contract`, current honesty reconcile. (C-004: golden verdict preserved.)
- **Intake strategy**: nutrition/supplement tables for boundary truth (D4);
  `check_intake_runtime_contract` for the runtime check (D3); manifest reconcile over the
  intake declared-gap surface (`unmapped_metrics` / `skipped_rows`). The intake
  `runtime_valid` evidence seam is `source_descriptors` / event `source_id` / event
  `dedupe_key` via `IntakeBatch.validate()` (there is **no** canonical declared/emitted
  *metric* surface on `IntakeBatch` — see intake-runtime-contract.md).

## self_reconcile (CHANGED — type only)

`self_reconcile(source_path, batch, mapped_columns)` consults **only**
`batch.unmapped_metrics` and `batch.skipped_rows[*].raw_field` — both present on
`IngestBatch` **and** `IntakeBatch`. Widen its accepted type to `IngestBatch | IntakeBatch`
(or a small `HasDeclaredGaps` protocol); **no logic change**. The observation-only
coupling lives in the in-sandbox **probe** (`_PROBE_TEMPLATE`), which is generalized to
the scenario's target drawer (D9 / drawer-grading-contract.md), not in the reconciler.

## Captured provenance (CHANGED — widened, transport only)

Today's `_CapturedProvenance` is observation-shaped (`rows_inserted`,
`declared_metrics`, `emitted_metric_ids`, `unmapped_metrics`, `skipped_rows`). Widen so
the runner envelope can also carry the intake surface:

| Field | Type | Drawer |
|---|---|---|
| `rows_inserted` | `int` | both |
| `declared_metrics` / `emitted_metric_ids` | `list[str]` | observation |
| `nutrition_dedupe_keys` / `supplement_dedupe_keys` | `list[str]` | intake |
| `source_descriptor_ids` | `list[str]` | intake (descriptor completeness) |
| `unmapped_metrics` | `list[str]` | both (declared gaps) |
| `skipped_rows` | `list[SkippedRow]` | both (declared gaps) |

> Provenance is **captured evidence to verify**, never trusted self-report (FR-005). The
> grader still recomputes `loaded` from the warehouse and `honest_about_gaps` from the
> manifest.

## Alien-source manifest (NEW — `alien_intake_manifest.yaml`, grader-only)

Ground-truth map the grader reconciles against. Per source column:

| Key | Meaning |
|---|---|
| `source_column` | the alien column name (e.g. `qty_uom`) |
| `drawer` | `intake` / `observation` (which home it belongs in) |
| `canonical_home` | the expected canonical field/home, or `null` if it is the intended gap |
| `expected_outcome` | `loaded` \| `declared_gap` |

At least one row has `expected_outcome: declared_gap` (the `note` column) for SC-004.

## Three-rule verdict (UNCHANGED — `contracts/grader-verdict.schema.json`)

`{ "passed": bool, "rules": { "loaded": {...}, "runtime_valid": {"passed": bool,
"violations": [...]}, "honest_about_gaps": {...} } }` — arrays sorted, **no ids, no
timestamps**. The schema is not changed; only how `runtime_valid` / `loaded` /
`honest_about_gaps` are *computed* (via the strategy) changes.

## Session-log run record (UNCHANGED shape; intake-tagged)

Existing fields used as-is: `run_kind` (`"live_trial"`), `operator_model`,
`driver_model`, per-attempt `SelfReconciliationResult`, `contract_pass` (= grader's
recomputed `runtime_valid`). FR-009: a completed record with `passed=False` is written
even on import/parse failure.
