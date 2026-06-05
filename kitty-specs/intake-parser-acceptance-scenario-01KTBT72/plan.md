# Implementation Plan: Intake Parser Acceptance Scenario

**Branch**: `master` | **Date**: 2026-06-05 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/intake-parser-acceptance-scenario-01KTBT72/spec.md`

## Summary

Turn the live-trial harness's implicit "one hardcoded observation source" into an
explicit **`Scenario`** abstraction, then prove it generalizes by running both the
existing observation source and a new, deliberately-alien synthetic intake source
through one generic grader. The grader's three rules (`loaded`, `runtime_valid`,
`honest_about_gaps`) stay recomputed from ground truth, but *which warehouse tables
are boundary truth* and *which runtime-valid clause set applies* are **carried by
the scenario**, not hardwired. Two layers ship: a deterministic default-suite floor
(reference intake parser) and an opt-in live cheap-model run (qwen authors the
parser); the answer+judge step (layer 3) is a named follow-up the scenario record is
shaped to accept later.

The central engineering move is generalizing the **shipped** observation grader
(`src/premura/harness/grader.py`) into a drawer-parametric grader without a per-source
branch (NFR-005), with the observation scenario injecting exactly today's behavior so
observation verdicts stay byte-identical (C-004).

## Technical Context

**Language/Version**: Python 3.11 (repo standard; `uv`-managed)
**Primary Dependencies**: existing in-repo only — `premura.harness` (grader, sandbox,
ingest_runner, self_reconcile, live_trial, scoreboard), `premura.session_log.store`,
`premura.parsers` (base/`ParseOutput`/`IntakeBatch`/`contract_check`), `premura.store.profile_intake`
(`persist_intake_batch`). No new third-party dependency.
**Storage**: DuckDB — observation `hp.fact_*` and intake `hp.nutrition_intake_*` /
`hp.supplement_intake_*` (drawers); session-log store (its own local DuckDB file).
**Testing**: `pytest`. Default suite stays offline/deterministic (layer 1 + failure
path). Layer 2 is collected only under the `live_trial` marker (local Ollama).
**Target Platform**: maintainer's local macOS workstation (same as existing live trial).
**Project Type**: single (library + test harness).
**Performance Goals**: not a perf feature; default-suite additions stay within normal
test timing (no model server, no network).
**Constraints**: local-only (`OLLAMA_URL` guard inherited); synthetic-only data and
synthetic-only sandbox retention; layer 2 can never block CI; observation grading
behavior preserved byte-for-byte.
**Scale/Scope**: one new scenario abstraction; one alien intake source + manifest; one
reference intake parser; one intake runtime-valid checker; grader generalization;
deterministic failure-path + reconciliation tests; one opt-in live-trial intake test.

## Charter Check

*GATE: Must pass before Phase 0. Re-checked after Phase 1.*

Charter present (compact, `software-dev-default`). Relevant directives from
`spec-kitty charter context`:

- **DIRECTIVE_010 (named follow-up, not silent waiver):** layer 3 (answer+judge) is a
  named, scoped follow-up (FR-011 / Out of scope), not an unstated gap. **Pass.**
- **Agent-first + design-a-level-above (DOCTRINE):** the deliverable is agent-graded
  (no human form); the `Scenario` is a bounded abstraction with a rule for adding the
  next source, not an intake special case. **Pass.**
- **Standards-first / privacy:** synthetic-only alien source, no PHI, no new outbound
  network, local-only model backend. **Pass.**
- **No-fork / measurable gates (NFR-005/006, C-004):** generalize the shipped grader,
  prove ≥2 scenarios over one path, pin observation regression with a golden verdict.
  **Pass (enforced by tests, not prose).**

No charter conflicts. Re-check after Phase 1: still pass (no design choice introduces a
human surface, an enumerated domain list, an off-machine path, or a parallel grader).

## Project Structure

### Documentation (this feature)

```
kitty-specs/intake-parser-acceptance-scenario-01KTBT72/
├── plan.md              # This file
├── research.md          # Phase 0 — decisions + rationale
├── data-model.md        # Phase 1 — Scenario, manifest, provenance, verdict entities
├── quickstart.md        # Phase 1 — how to run both layers
├── contracts/           # Phase 1 — scenario, intake-runtime, drawer-grading, alien-source contracts
└── tasks.md             # /spec-kitty.tasks output — NOT created here
```

### Source Code (repository root)

```
src/premura/harness/
├── scenario.py          # NEW — Scenario abstraction + registry (source, manifest,
│                        #        reference parser, drawer-grading strategy)
├── grader.py            # CHANGED — grade() becomes drawer-parametric via the
│                        #           scenario's injected strategy; observation
│                        #           behavior preserved (golden verdict)
├── intake_contract_check.py  # NEW — check_intake_runtime_contract over IntakeBatch's
│                        #             real surface: source_descriptors vs event
│                        #             source_id + dedupe_key (via validate()) + persist;
│                        #             NO canonical declared/emitted metric clause (D3)
├── self_reconcile.py    # CHANGED (type only) — accept IngestBatch | IntakeBatch; it
│                        #             already consults only .unmapped_metrics +
│                        #             .skipped_rows, which both batches expose (D9)
├── live_trial.py        # CHANGED — drive a Scenario (observation or intake); capture
│                        #           intake provenance; failure path persists a record
├── live_trial_ollama.py # CHANGED — generalize the in-sandbox self-reconcile PROBE
│                        #           (_PROBE_TEMPLATE) off its observation-only gate:
│                        #           keep the scenario's batch (not discard intake),
│                        #           require that batch type, apply the drawer's
│                        #           non-empty check, reconcile via the same gate (D9)
└── (sandbox.py, ingest_runner.py, scoreboard.py — REUSED as-is; additive only)

tests/fixtures/intake_scenario/        # NEW — synthetic, obviously-fake
├── alien_intake.csv                    #   the alien meals+supplements source
├── alien_intake_manifest.yaml          #   grader-only ground-truth field map (C-005)
└── reference_intake_parser.py          #   the layer-1 known-good parser

tests/
├── test_intake_scenario_grading.py     # NEW — layer-1 e2e: full pass (SC-001)
├── test_intake_scenario_drawer.py      # NEW — mis-filed row fails loaded (SC-002),
│                                        #        unmappable field declared (SC-004)
├── test_intake_reconcile_renamed.py    # NEW — e2e: a consumed-but-renamed source column
│                                        #        (logged_at_us -> event timestamp) is
│                                        #        ACCOUNTED, not flagged unaccounted
│                                        #        (spec edge case "renamed-but-consumed")
├── test_scenario_drawer_targets.py     # NEW — e2e: parser returns intake-ONLY is graded
│                                        #        on the intake drawer; parser returns
│                                        #        BOTH is graded on each target drawer
│                                        #        (spec edge case "intake-only vs both")
├── test_intake_runtime_contract.py     # NEW — intake runtime-valid clauses (SC-008)
├── test_scenario_no_fork.py            # NEW — structural: no per-source branch,
│                                        #        ≥2 scenarios over one path (SC-003)
├── test_failure_path_record.py         # NEW — stub op → completed failing record (SC-007)
├── test_observation_scenario_golden.py # NEW — observation verdict unchanged (SC-006/C-004)
└── test_live_trial_intake.py           # NEW — live_trial-marked layer-2 run (SC-005)
```

> Exact WP-to-file ownership is decided by `/spec-kitty.tasks`; the tree above is the
> intended shape, not a lane assignment.

## Phase 0 — Outline & Research

See [research.md](research.md). It resolves: the `Scenario` shape and how the grader
is generalized without a per-source branch; the exact intake runtime-valid clause set
(grounded in `IntakeBatch.validate()`); how `loaded` boundary truth is read per drawer;
the alien-source format + manifest schema; the stub-operator failure path; and how the
observation regression is pinned. No `[NEEDS CLARIFICATION]` remain — the two product
forks (scope, alien source) were settled at specify; the architecture forks were
settled in the Engineering Alignment.

## Phase 1 — Design & Contracts

- [data-model.md](data-model.md) — `Scenario`, `DrawerGradingStrategy`, alien-source
  manifest, captured intake provenance, the (unchanged) three-rule verdict.
- [contracts/](contracts/) — `scenario-contract.md`, `intake-runtime-contract.md`,
  `drawer-grading-contract.md`, `alien-source-and-manifest-contract.md`.
- [quickstart.md](quickstart.md) — run layer 1 (default suite), the failure-path test,
  and layer 2 (opt-in, local Ollama).

## Complexity / risk notes

- **Highest risk: regressing observation grading** while generalizing `grade()`.
  Mitigation: capture a golden observation verdict from current `master` first, then
  refactor until it is reproduced byte-for-byte (C-004 test is written before the
  refactor lands).
- **Second risk: a sneaky per-drawer branch** creeping into the shared path.
  Mitigation: a structural test (`test_scenario_no_fork.py`) that fails if the shared
  grade path names a drawer/scenario, plus the ≥2-scenarios-over-one-path assertion.
- **Containment:** the alien source + manifest are synthetic; the manifest is never on
  any operator-visible path (C-005); layer 2 stays behind the marker and the local-only
  guard.

## Branch contract (restated)

- Current branch at plan start: **master**
- Planning/base branch: **master**
- Final merge target: **master**
- `branch_matches_target`: **true**

## STOP

Planning ends here (Phase 1). Work packages are generated by `/spec-kitty.tasks`.
