# Phase 0 Research — Intake Parser Acceptance Scenario

All decisions below were grounded in the shipped code (`grader.py`,
`parsers/base.py`, `parsers/contract_check.py`, `live_trial.py`,
`store/profile_intake.py`) read during planning, not assumed. No
`[NEEDS CLARIFICATION]` remain.

## D1 — The `Scenario` abstraction (FR-001, NFR-005/006)

**Decision.** Introduce `premura.harness.scenario.Scenario`: a frozen value object
bundling `name`, `source_path`, `manifest_path`, `reference_parser` (import target),
and a `DrawerGradingStrategy`. A small registry exposes the registered scenarios
(observation + intake) for the no-fork / ≥2-scenarios tests.

**Rationale.** The harness today hardwires one observation source and one fact-table
boundary. Lifting that into a registered value object is the minimal "design a level
above" move: adding the next source becomes *register a scenario*, with no edit to the
shared grade path (the FR-001 failure clause).

**Alternatives considered.** (a) A second, parallel intake grader — rejected: that is
the exact fork NFR-005 forbids. (b) Pure-data scenarios (table lists + a clause-set
*enum*) with the grader switching on the enum — rejected: a switch is a per-source
branch in disguise, and intake's runtime-valid logic genuinely differs, so it needs an
injected checker, not a flag.

## D2 — Generalize the shipped grader; inject drawer behavior (C-004, NFR-005)

**Decision.** Refactor `grade(provenance, warehouse_conn, fixture_manifest)` so the
three rules are computed via a scenario-provided `DrawerGradingStrategy` with three
responsibilities: (1) **boundary-truth reader** — count loaded rows / present keys from
the drawer's tables; (2) **runtime-valid checker** — the clause function for the drawer;
(3) **gap reconciler** — produce the manifest-source-field-vs-(loaded ∪ declared) set.
The grader orchestrates the three rules generically and emits the unchanged verdict
schema. The **observation** strategy wraps exactly today's logic
(`_BOUNDARY` fact tables + `check_runtime_contract` + the current honesty reconcile).

**Rationale.** One generic orchestrator, drawer specifics injected — satisfies
no-fork while keeping the observation path behaviorally identical. The verdict schema
(`{passed, rules:{loaded,runtime_valid,honest_about_gaps}}`, no ids/timestamps) does
not change.

**Regression guard (C-004).** Before the refactor lands, capture a **golden
observation verdict** from current `master` over the committed synthetic fixture; the
refactored grader must reproduce it byte-for-byte (`test_observation_scenario_golden.py`).

## D3 — Intake `runtime_valid` clause set (FR-010, SC-008)

**Decision.** `check_intake_runtime_contract` enforces the analogue of the observation
clauses, defined against `IntakeBatch`. **Named evidence surface (the High-1 fix):**
`IntakeBatch` (`src/premura/parsers/base.py:282-330`) has `nutrition_events`,
`supplement_events`, `source_descriptors`, per-event `source_id` + `dedupe_key`,
`unmapped_metrics`, `skipped_rows`, and `validate()` — and **no** `declared_metrics` /
`emitted_metric_ids` / `dim_metric` (those exist only on `IngestBatch`). So the intake
runtime clause set is:

1. **`parser_imports_and_parses`** — the operator's parser module imports and `parse()`
   returns an `IntakeBatch` (or a `ParseOutput` carrying one) **without raising**.
2. **`batch_validates`** — `IntakeBatch.validate()` passes: every event `source_id` is
   covered by a declared `source_descriptor`, and there are **no duplicate `dedupe_key`s**
   within nutrition or supplement events.
3. **`persisted_without_raising`** — `persist_intake_batch` loads the batch without
   raising (the analogue of observation `produced_batch_without_raising`).

**Where declared/emitted lives for intake (explicit).** Observation's
`declared_equals_emitted` compares *canonical metric keys*. Intake has no such keys, so
that clause has **no intake counterpart by design**. The truthful analogue is on the
**source dimension**: the *declared* set is `source_descriptors`, the *emitted* set is
the `source_id`s actually used on events, and `validate()` enforces declared-covers-emitted
plus `dedupe_key` uniqueness. The seam carrying intake declared/emitted is therefore
`IntakeBatch.source_descriptors` / event `source_id` / event `dedupe_key` — not a new
primitive, and not a forced canonical-metric mirror.

**Observation clauses stay** exactly as `check_runtime_contract` defines them
(grounded, verbatim): `no_derived_emitted`, `declared_equals_emitted`,
`declared_exist_in_dim_metric`, `produced_batch_without_raising`.

**Rationale.** The observation clauses key on a metric/`dim_metric` surface intake does
not have; mirroring them would invent a fake canonical-key surface. The intake clauses
are the same *kind* of bounded runtime check over intake's real integrity surface.
Crucially this is **not** the full parser-review `CONTRACT.md` (the D5 drift FR-010 guards).

**Spec↔code agreement (FR-010 / SC-008).** `test_intake_runtime_contract.py` asserts the
clause *names/count* match the spec list, so the spec cannot silently drift from the checker.

## D4 — `loaded` boundary truth per drawer (FR-006)

**Decision.** The intake strategy's boundary-truth reader counts rows in
`hp.nutrition_intake_*` / `hp.supplement_intake_*` (the persisted event/item/quantity
homes) and derives "what landed" from those tables — never from the parser's report. A
nutrition/supplement row that landed in `hp.fact_*` instead is, by construction, absent
from the intake boundary truth → `loaded` **fails** (FR-006 / SC-002). The observation
reader keeps counting `_BOUNDARY` fact tables.

**Rationale.** `grader.py:48` hardwires fact tables as boundary truth today; making the
table set a strategy responsibility is the seam that lets a mis-filed row fail honestly
without a per-drawer branch in the orchestrator.

## D5 — The alien synthetic source + manifest (FR-002, C-005)

**Decision.** `alien_intake.csv`: one CSV holding **both** meals and supplements,
distinguished by a `kind` column, with deliberately-foreign encodings —
- column names unlike any built-in source (e.g. `logged_at_us`, `item`, `qty`, `qty_uom`,
  `kind`, `note`);
- timestamp as **epoch microseconds** (not ISO, not the built-in encodings);
- non-SI / mixed units in `qty_uom` (e.g. `oz`, `Cal`, `IU`, `mcg`) the parser must map;
- at least one nutrition row, one supplement row, one row crossing local midnight, and
  **one column with no canonical home** (e.g. `note`) to exercise the declared-gap path.

`alien_intake_manifest.yaml` is the **grader-only** ground-truth field map (source
column → canonical home / drawer / expected outcome, including which column is the
intended gap). It is read by the grader **only** and is never placed on any
operator-visible path (C-005).

**Rationale.** Issue #10 requires a structurally-alien source to genuinely test
"teach Premura to read something new"; reusing the existing JSON intake fixtures would
only prove plumbing. CSV-with-foreign-columns is maximally unlike both the built-in
sources and the existing JSON intake fixtures while staying trivially synthetic.

**Alternatives.** A second JSON shape (rejected: too close to existing intake fixtures);
a SQLite container (rejected: heavier to author, no extra signal for a first scenario).

## D6 — Deterministic failure path via a stub operator (FR-009, SC-007)

**Decision.** Add a `StubBrokenParserOperator` (Operator protocol) that installs a
deliberately broken parser into the sandbox. Run it through the **real**
sandbox→ingest→grade path in the default suite and assert a **completed, persisted,
failing** graded run record exists (session-log record present; verdict `passed=False`;
parser error captured) and that the harness does not raise.

**Rationale.** The session-log-substrate RCA was "failure path crashed before a
gradeable record existed." Proving the guarantee needs the real path, but must not need
the live model — a stub operator makes the most safety-critical edge case a default-suite
gate (stronger than a live-only check). The live cheap model hitting the same path in
layer 2 is the opt-in version of the same guarantee.

## D7 — Layer 2 (live cheap model) reuse (FR-007, NFR-001/002/003)

**Decision.** Reuse the existing `OllamaOperator` / driver factories and the
`live_trial` marker; the layer-2 entry selects the intake scenario. Inherits the
local-only `OLLAMA_URL` guard and synthetic-only retention unchanged. The run records
`run_kind="live_trial"`, `operator_model`, `driver_model`. No new model-backend
abstraction (C-002).

**Rationale.** Layer 2 is new *orchestration over* existing machinery, not a new
operator stack; the cheap model authors the intake parser from the shipped
parser-generator intake brief (skill unchanged here — gaps are a follow-up, not fixed).

## D8 — Captured intake provenance (FR-008)

**Decision.** Widen the harness's captured provenance so the runner envelope can carry
the intake surface (nutrition/supplement event counts + dedupe keys, `unmapped_metrics`,
`skipped_rows`, `source_descriptors`) alongside the observation surface, as transport
only (the grader still recomputes truth from the warehouse + manifest). The harness
remains the sole session-log writer.

**Rationale.** `_captured_provenance` is observation-shaped today; the intake strategy
needs the intake review-metadata to reconcile declared gaps, but provenance stays
*captured evidence to check*, never *trusted self-report* (FR-005).

## D9 — Generalize the in-sandbox self-reconciliation probe (FR-008, High-2 fix)

**Decision.** The in-sandbox probe (`_PROBE_TEMPLATE` in `live_trial_ollama.py:287-322`)
is the **observation-only self-reconciliation gate**: it `normalize_parse_output(...)`,
**discards `_intake`**, *requires* an observation batch, fails on zero `measurements`,
reads `MAPPED_SOURCE_COLUMNS`, and runs `self_reconcile(source, batch, mapped)`. This
mission **generalizes the probe to the scenario's target drawer**:

- keep the batch the scenario targets (for intake, do **not** discard the intake batch);
- require the scenario's batch type (intake → an `IntakeBatch`), not always observation;
- apply the drawer's non-empty check (intake → ≥1 nutrition/supplement event, not
  `measurements`);
- feed that batch + its `MAPPED_SOURCE_COLUMNS` to `self_reconcile`.

**`self_reconcile` itself is widened by TYPE only.** It is typed `IngestBatch`
(`self_reconcile.py:69-113`) but consults **only** `batch.unmapped_metrics` and
`batch.skipped_rows[*].raw_field` — both of which `IntakeBatch` also exposes. So it
becomes `IngestBatch | IntakeBatch` (or a small `HasDeclaredGaps` protocol); no logic
change. The observation-only coupling that must change is the **probe**, not the
reconciler.

**Parser convention.** The reference intake parser and the layer-2 cheap-model parser
both expose a module-level `MAPPED_SOURCE_COLUMNS` (the columns they consumed), exactly
as the observation parsers do; the gate never infers it from the batch (C-005 — it stays
manifest-blind).

**Rationale.** FR-008 requires the **same** structured self-reconciliation record shape
for intake runs. The reconciler already generalizes for free; the observation-only gate
is in the probe, and naming it here prevents the "minimal additive change" wording from
hiding a real generalization during implementation (the exact seam-capability drift the
audit method warns about).

## Open questions

None. The two product forks (scope; alien source) were resolved at specify; the
architecture forks were resolved in the Engineering Alignment and grounded above; the
two review High items (intake declared/emitted evidence seam — D3; intake self-reconcile
probe ownership — D9) are pinned to named primitives.
