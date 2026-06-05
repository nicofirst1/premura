# Contract — drawer-parametric grading

> How `grade()` becomes drawer-aware without a per-source branch (NFR-005), while
> preserving observation behavior byte-for-byte (C-004).

## The grader orchestrates; the strategy supplies drawer specifics

`grade(...)` computes the three rules generically and emits the **unchanged** verdict
schema. It obtains all drawer-specific behavior from the scenario's
`DrawerGradingStrategy`:

| Rule | Strategy responsibility | Truth source |
|---|---|---|
| `loaded` | `boundary_truth(warehouse_conn)` → loaded count + present keys | the drawer's warehouse tables (FR-006) |
| `runtime_valid` | `runtime_check(provenance, warehouse_conn)` → `ContractCheckResult` | the drawer's bounded clause set (intake-runtime-contract.md) |
| `honest_about_gaps` | `gap_set(manifest, provenance, boundary_truth)` → silent-drop fields | manifest-derived truth vs (loaded ∪ declared) |

## Hard rules

- **No per-drawer branch in the orchestrator.** The shared `grade()` body MUST NOT
  contain `if observation/elif intake` (or table/scenario names). All divergence lives
  behind the strategy (NFR-005; `test_scenario_no_fork.py`).
- **Boundary truth is warehouse-recomputed**, never the parser's report. A
  nutrition/supplement row landing in `hp.fact_*` is absent from the intake boundary
  truth → `loaded` fails (FR-006 / SC-002).
- **Declared gaps are evidence to verify, never proof.** `gap_set` derives the true gap
  set from the manifest; a source field neither truly loaded nor declared is a
  silent-drop failure of `honest_about_gaps` (FR-005 / SC-004).
- **Observation behavior preserved.** The observation strategy reproduces the current
  grader's verdict byte-for-byte over the committed fixture
  (`test_observation_scenario_golden.py`; C-004 / SC-006).

## Live-trial self-reconciliation is drawer-aware too (FR-008)

The layer-2 self-reconciliation gate must produce the **same** structured record for an
intake run as for an observation run. Two pieces:

- **The in-sandbox probe (`_PROBE_TEMPLATE`)** is today observation-only — it discards
  intake, requires an observation batch, and fails on zero `measurements`. It MUST be
  generalized to the scenario's target drawer: keep the scenario's batch (do not discard
  intake), require that batch type, apply the drawer's non-empty check (intake → ≥1
  nutrition/supplement event), and feed that batch to `self_reconcile`.
- **`self_reconcile`** changes by **type only** — it already consults solely
  `batch.unmapped_metrics` and `batch.skipped_rows[*].raw_field`, which `IntakeBatch` also
  exposes, so it accepts `IngestBatch | IntakeBatch` with no logic change.
- The gate stays **manifest-blind** (C-005): mapped columns come from the parser's
  module-level `MAPPED_SOURCE_COLUMNS`, never inferred from the manifest.

## Verdict schema

Unchanged: `{ passed, rules: { loaded, runtime_valid: {passed, violations}, honest_about_gaps } }`,
arrays sorted, no ids, no timestamps.
