# Feature Specification: Intake Parser Acceptance Scenario

**Mission**: intake-parser-acceptance-scenario-01KTBT72
**Mission type**: software-dev
**Target branch**: master
**Created**: 2026-06-05
**Status**: Draft

## Why this mission exists

Premura's central bet (GitHub issue #10, now written down in `CONTEXT.md`
§"Acceptance evaluation") is that an AI agent can be handed a fresh clone, teach
Premura to read a health-data file it has never seen, and answer honestly. The
project grades that in two layers: cheap **deterministic checks** (the floor) and
a **live, two-agent, judge-graded** end-to-end run (the destination). Only the
deterministic floor exists today, and it exercises **one kind of data only —
observations** (a device measurement, e.g. heart rate). When a parser returns
*intake* data (what the operator ate, drank, or supplemented), the live-trial
harness literally **discards it** (`live_trial_ollama.py`:
`observation, _intake = normalize_parse_output(...)` — `_intake` is dropped) and
grades only the observation batch.

Intake is now a first-class, shipped domain (the `usable-intake-dimensions`
mission: a runtime intake parser path, `persist_intake_batch`, two intake
signals). But nothing yet **tests whether an agent can build an intake parser for
an unfamiliar meals/supplements file** the way the acceptance evaluation tests it
for observations.

This mission closes that gap by adding a **reusable acceptance scenario** for
intake. It does **not** invent a parallel harness: it lifts the harness's
implicit "one hardcoded observation source" into an explicit **scenario**
abstraction (a source + its ground-truth manifest + which warehouse drawer it
targets + a reference parser), then proves that abstraction generalizes by running
**both** the existing observation source and a new, deliberately-alien intake
source through it. Per DOCTRINE ("design a level above"), it defines *what a
scenario is and how intake is graded as a rule*, rather than hardcoding "intake"
as a second special case.

## Scope at a glance (the three layers)

This mission builds **layers 1 and 2**, designed so **layer 3** attaches later
without reshaping anything:

- **Layer 1 — deterministic floor (default suite).** A committed reference intake
  parser reads an alien synthetic meals/supplements source; fixed-rule checks
  confirm the data landed in the intake drawer, the parser is contract-valid, and
  it was honest about unmapped fields. Never flaky, never networked.
- **Layer 2 — live cheap operator (opt-in).** The local cheap model authors the
  intake parser itself for that source and is graded by the same rules. Behind the
  `live_trial` marker; never blocks CI; local-only.
- **Layer 3 — answer + judge (NOT in this mission).** The operator answers an
  intake question and a judge grades honesty. Named follow-up (the judge agent
  does not exist yet — DIRECTIVE_010: named, not silently waived).

## User Scenarios & Testing

> "User" here is **agent-first**: the primary actor is the operating agent under
> test and the maintainer who reads the resulting score. There is no human form
> or dashboard in this mission.

### Primary flows

1. **Read an unfamiliar meals/supplements file (deterministic).** The harness is
   handed the intake scenario — an alien synthetic source plus its ground-truth
   manifest. The reference intake parser runs as the operator. The harness loads
   the parser's intake output through the intake load path and grades it by
   reconciliation: the expected meals/supplement rows are present in the intake
   tables, the parser is contract-valid, and every source field that has no
   canonical home was declared as a gap. The verdict is a full pass, every run,
   with no network.

2. **One harness, two kinds of source.** The same scenario abstraction scores the
   pre-existing observation source (a measurements file) and the new intake source
   (a meals/supplements file). No source-specific branch lives in the shared grade
   path; adding the intake source was registering a scenario, not editing harness
   logic.

3. **A live cheap agent builds the intake parser (opt-in).** With the local model
   server available, the cheap model is the operator: it writes an intake parser
   for the alien source from the parser-generator brief and is graded by the same
   three rules. The run records its `run_kind`, `operator_model`, and
   `driver_model` and prints its score for inspection. It is never asserted to
   pass and can never block a code change.

### Edge cases

- **A meal row mis-filed as a measurement.** If a parser writes a nutrition/
  supplement row into the observation tables instead of the intake tables, the
  "loaded" rule **fails** by reconciliation — no cross-drawer coercion is ever
  scored as success.
- **An unmappable source field.** A field in the alien source with no canonical
  home must be surfaced as a declared gap (the intake batch's unmapped/skipped
  channel), never silently dropped; a parser that drops it is graded **not honest
  about gaps**.
- **A renamed-but-consumed field.** A source column the parser consumes under a
  different name (e.g. the source calls it `when`, the parser maps it to the event
  timestamp) is reconciled as **accounted**, not reported as an unaccounted column.
- **Intake-only vs both.** A parser that returns only intake (no observation) is
  graded fully on the intake drawer; a parser that returns both is graded on each
  drawer in its scenario's target set — the harness no longer assumes observation.
- **Malformed parser (failure path).** A parser that fails to import or parse
  still produces and **persists a completed, failing graded record** with a
  structured per-attempt self-reconciliation and the parser error — the harness
  never crashes before a gradeable record exists (FR-009). This failure path is
  proved **deterministically in the default suite** via a stub operator that emits
  a broken parser; it does **not** require the live model. (The live cheap model
  hitting the same path in layer 2 is the opt-in version of the same guarantee.)

## Requirements

### Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| FR-001 | The harness exposes a **scenario** abstraction: a named bundle of (source artifact, ground-truth field manifest, target warehouse drawer(s), reference parser). A new acceptance source is added by **registering a scenario**, not by branching harness code. **Failure clause (testable):** adding a new scenario must require **no change to the shared grading logic** — registering the scenario is the only edit. In particular, *which warehouse tables count as boundary truth for `loaded`* and *which `runtime_valid` clause set applies* are carried **by the scenario**, never hardwired in the shared grader. | Draft |
| FR-002 | A new **structurally-alien synthetic intake source** ships as a scenario: a made-up meals/supplements file whose container, field names, units, and time encoding differ from every built-in source **and** from the existing intake fixtures. It covers at least one nutrition shape and one supplement shape. It contains **no real data**. | Draft |
| FR-003 | The harness **keeps and grades the intake half** of a parse: when a parser returns intake (a parse output carrying an intake batch), the harness loads it through the shipped intake load path and reconciles it. Intake is no longer discarded. | Draft |
| FR-004 | **Layer 1:** a committed **reference intake parser**, run as the operator in the default suite, produces a well-formed three-rule verdict — `loaded` (the expected intake rows landed in the intake tables), `runtime_valid` (the bounded runtime-checkable subset of FR-010, **not** the full parser-review contract), `honest_about_gaps` (per FR-005: every unmapped/skipped source field declared, none silently dropped). | Draft |
| FR-005 | Every rule for an intake scenario is computed **by reconciliation against ground truth** (the intake-drawer tables + the scenario manifest), **never** from the parser's or runner's self-report. The parser's **declared** unmapped/skipped metadata is reconciled against the **manifest-derived** gap set: a source field that is **neither truly loaded (warehouse truth) nor declared** is a silent-drop **failure** of `honest_about_gaps`. Declared gaps are **evidence to verify, never proof to accept**. The persisted contract-pass is the grader's recomputed `runtime_valid`. | Draft |
| FR-006 | For an intake scenario, the `loaded` rule reconciles rows in the **intake drawer** (the nutrition/supplement homes), per the boundary-truth tables the scenario carries (FR-001). A row that lands in the **observation drawer** instead is a `loaded` **failure** (no cross-drawer coercion is scored as success). | Draft |
| FR-007 | **Layer 2:** the local cheap model can drive the intake scenario as the operator — it authors the intake parser for the alien source and is graded by the same three rules. The run records `run_kind`, `operator_model`, and `driver_model` so capability tiers stay comparable. | Draft |
| FR-008 | Each intake-scenario run records, for the graded attempt(s), a structured per-attempt **self-reconciliation** (source columns / accounted / unaccounted) plus any parser import/parse error, written to the session log by the harness as the sole log writer — the same record shape the observation scenario produces. | Draft |
| FR-009 | **Failure path produces a completed record.** A **completed, persisted graded run record** exists even when the operator's parser fails to import or parse: the failure path produces and persists a *failing* graded record (with the structured self-reconciliation + parser error of FR-008) and **never crashes before a gradeable record exists**. | Draft |
| FR-010 | `runtime_valid` is a **bounded runtime-checkable subset**, explicitly **not** the full parser-review contract (`src/premura/parsers/CONTRACT.md`). For an **observation** scenario it is exactly the clauses the shipped `check_runtime_contract` enforces: (1) no reserved `derived:` namespace emitted, (2) declared set equals emitted set, (3) every declared metric exists in `dim_metric`, (4) the ingest produced a batch without raising. For an **intake** scenario it is the **analogous** bounded check over the intake batch's declared/emitted surface (produced-a-batch-without-raising; declared-equals-emitted over the intake batch's declared keys; no reserved/forbidden namespace) — defined for the intake batch shape, because the observation clauses are `metric_id`/`dim_metric`-shaped and do not transfer verbatim. The spec's clause list and the implementation's runtime checker **must agree** (verified in plan). | Draft |
| FR-011 | The intake scenario is built so the later **answer + judge** step (layer 3) can attach without reshaping it: the scenario record carries the source, manifest, and graded-run references a future answer-and-judge pass would consume. Layer 3 itself is **not** built here. | Draft |

### Non-Functional Requirements

| ID | Requirement | Measurable threshold | Status |
|---|---|---|---|
| NFR-001 | **Deterministic floor.** Layer 1 runs in the default pytest suite, offline. | 0 network calls and 0 model-server dependency in the default suite; the full default suite stays green. | Draft |
| NFR-002 | **Never blocks CI.** Layer 2 is collected only under the `live_trial` marker. | 0 default-collected tests invoke a real model; a failing/absent layer-2 run cannot fail a code change. | Draft |
| NFR-003 | **Local-only backend.** Layer 2 inherits the local-only model-URL guard. | 100% of non-local backend configurations are rejected before any network request. | Draft |
| NFR-004 | **No PHI / synthetic-only.** The intake source and all fixtures are synthetic and obviously fake. | 0 real meals/supplement records enter the repo or a commit; real-data no-persist and synthetic-only sandbox-retention rules are unchanged. | Draft |
| NFR-005 | **No fork.** The intake scenario reuses the existing sandbox / ingest runner / session-log store / grader layers. | 0 second copies of those layers; 0 per-source `if observation / elif intake` branches in the shared grade path (asserted structurally by a test). | Draft |
| NFR-006 | **Reusability proven, not asserted.** Both the observation source and the intake source run through the one scenario abstraction. | ≥ 2 scenarios run over 1 abstraction with 0 scenario-specific code in the shared harness path. | Draft |

### Constraints

| ID | Constraint | Source | Status |
|---|---|---|---|
| C-001 | **No judge agent and no answer step** are built in this mission (layer 3 is a named follow-up, DIRECTIVE_010). | Agreed scope | Active |
| C-002 | **No new model-backend abstraction** beyond the existing local model server. | Agreed scope | Active |
| C-003 | The grader **recomputes every rule from ground truth** and never trusts a parser self-report (inherited harness invariant, restated for the intake drawer). | Existing harness contract | Active |
| C-004 | Turning on intake grading **must not change** any existing observation-scenario verdict (observation path behavior preserved). | Regression safety | Active |
| C-005 | **No ground-truth leakage:** no operator-visible path (prompt or sandbox) ever exposes the scenario manifest or any expected-mapping; the cheap model gets the source + the parser contract only. | Inherited C-005 | Active |

## Success Criteria

| ID | Criterion |
|---|---|
| SC-001 | An **end-to-end** default-suite run (drop → parse → load → grade) proves Premura can be taught to read an unfamiliar meals/supplements file: the reference intake parser scores a full pass on all three rules, every run, with no network. |
| SC-002 | A meals/supplement row that lands in the measurements drawer never counts as success — proven by an **end-to-end harness run** where a mis-filed row fails the `loaded` rule (not a component-level assertion). |
| SC-003 | The same harness scores at least two different kinds of source (a measurements file and a meals/supplements file) with **no source-specific code in the shared scoring path**, proven by both scenarios running through the one abstraction. |
| SC-004 | A source field with no canonical home is reported as a declared gap, never silently dropped — proven by an **end-to-end harness run** over a fixture containing an unmappable field; a parser that drops it is graded not honest. |
| SC-005 | The local cheap model drives the meals/supplements scenario end-to-end at least once (opt-in run), producing a well-formed verdict whose score is recorded for inspection and **never asserted as a pass**. |
| SC-006 | Enabling intake scoring leaves every existing measurements-scenario result **unchanged** (regression-proven). |
| SC-007 | The **failure path** is proved by an **end-to-end default-suite run** using a stub operator that emits a broken parser: a completed, persisted, **failing** graded record exists and the harness does not crash (FR-009). |
| SC-008 | `runtime_valid` for both scenarios checks **exactly the bounded runtime subset** (FR-010) and **never** the full parser-review contract — asserted against the shipped runtime checker's clause set. |

## Key Entities

- **Scenario** — the bounded abstraction this mission introduces: a source
  artifact + its ground-truth manifest + the target warehouse drawer(s) +
  a reference parser. The observation source and the intake source are two
  instances of it.
- **Alien intake source + manifest** — a synthetic meals/supplements file
  (nutrition + supplement shapes) deliberately unlike all built-in sources, plus
  the ground-truth field mapping the grader reconciles against (manifest is
  grader-only; never operator-visible).
- **Reference intake parser** — the committed known-good parser that turns the
  alien source into an intake batch; the layer-1 operator.
- **Intake batch + load path** — the shipped `IntakeBatch` → `persist_intake_batch`
  path the harness now drives and reconciles.
- **Three-rule verdict** — `loaded` / `runtime_valid` / `honest_about_gaps`,
  recomputed from ground truth. `runtime_valid` is the **bounded runtime subset**
  (FR-010), not the full parser-review contract; `loaded` boundary truth and the
  `runtime_valid` clause set are **carried by the scenario**, not hardwired.
- **Bounded runtime check** — the closed clause set `runtime_valid` recomputes
  (FR-010): the observation form is the shipped `check_runtime_contract`; the
  intake form is its analogue over the intake batch's declared/emitted surface.
- **Run record** — the session-log entry carrying `run_kind`, `operator_model`,
  `driver_model`, and per-attempt self-reconciliation.

## Assumptions

- The mission **reuses** the existing three-rule grader, sandbox, ingest runner,
  and session-log store, extending them with the scenario knob — it does not
  rewrite them.
- The alien intake source bundles **both** a nutrition shape and a supplement
  shape so both intake homes are exercised by layer 1.
- The cheap operator is a local-model-served code model (the existing live trial's
  qwen-class model); the exact model stays configuration, not a hardcoded value.
- The shipped **parser-generator skill's intake path** is the brief the layer-2
  cheap model follows; this mission does not rewrite that skill, though it may
  surface gaps as a named follow-up if the cheap model cannot follow it.
- "Drawer" in this spec means the warehouse domain homes: observation tables
  (`fact_*`) vs intake tables (`hp.nutrition_intake_*` / `hp.supplement_intake_*`).

## Dependencies

- **Shipped:** `usable-intake-dimensions` (the runtime intake parser path,
  `persist_intake_batch`, the parse-output normalization that already separates
  observation from intake).
- **Shipped:** the live-trial seam + grader + sandbox + ingest runner +
  session-log store (the `session-log-substrate` and `cheap-operator-live-trial`
  missions).
- **Context:** GitHub issue #10 (parent acceptance-evaluation vision) and
  `CONTEXT.md` §"Acceptance evaluation" (the vocabulary this mission instantiates).

## Out of scope (named so it is not assumed shipped)

- The **judge agent** and the **answer step** (layer 3) — named follow-up.
- A **human-playing driver** beyond what the seam already provides for the
  parser-building loop.
- Adapting a **real vendor export** — the source here is synthetic and alien, not
  a real file.
- Any **CI gating** of the live cheap-model run.
- **Multi-tier model-sweep orchestration** — the run records model identity so
  tiers stay comparable, but this mission does not orchestrate a sweep.
- Changes to the **parser-generator skill** itself (gaps may be recorded as a
  follow-up, not fixed here).
