# Feature Specification: Tool-loop live-trial tier

**Mission**: `tool-loop-live-trial-tier-01KTVG26` (mission_id `01KTVG26W1FWKR738ZA7VY39K8`)
**Created**: 2026-06-11
**Status**: Draft
**Target branch**: `master`
**Input**: Promotion of the parked draft
[`docs/building/planning/tool-loop-live-trial-tier.md`](../../docs/building/planning/tool-loop-live-trial-tier.md),
motivated and bounded by the
[2026-06-04 tool-loop follow-up audit](../../docs/history/audits/2026-06-04-live-trial-tool-loop-14b-followup.md).
The queue gate (intake source-adaptation, ROADMAP §"Profile and intake" item 1)
shipped 2026-06-11 (first real vendor parser merged), so this draft is promoted.

> **Doctrine note (read before reviewing):** per
> [`DOCTRINE.md`](../../docs/shared/DOCTRINE.md), this spec defines **rules and
> bounded contracts** (what counts as a tool, how a tier is scored, how a drawer
> registers), not enumerated lists of tools, drawers, or models. The named
> tools/drawers below are the *first registered instances* of those rules, not
> their bounds.

## Premise (corrected — carried from the audit)

The earlier framing — "a separate tier is needed because cheap models hit a
capability floor when given tools" — was **reversed** by the 2026-06-04 clean
re-test: the original spike measured **harness context quality**, not operator
capability. A capable local model passes when given a coherent brief. This
mission is therefore **not** a capability remedy. It is:

1. **Context-plumbing hardening** of the multiturn/tool harness so a capable
   local operator receives a fair, coherent brief, and
2. a **separately-scored tier** exercising the full path (read context → author
   a parser over multiple turns using tools → run a real sandbox ingest →
   final answer) as **headroom above** the constrained one-shot floor signal —
   never a replacement for it.

## User Scenarios & Testing *(mandatory)*

### Primary user story

Premura is operated by agents for a human beneficiary. The "user" of this
feature is the **maintainer agent** assessing which operator models are capable
enough to run live trials, and at what tier. Today it has one signal: the
constrained one-shot floor probe. It needs a second, separately-scored signal —
the same trial run through a multiturn, tool-using loop — so it can compare,
per operator model, "what the model can do in one constrained shot" against
"what the model can do with tools and turns", and make tiering decisions from
honest, comparable evidence.

### Acceptance scenarios

1. **Given** a registered acceptance scenario (e.g. observation heart-rate) and
   a reachable local model backend, **when** the maintainer agent runs the
   tool-loop trial over the committed synthetic source, **then** the operator
   works from one coherent brief, interacts only through the bounded tool
   contract, and the run ends with a **tier-tagged scored result** carrying two
   independent grader verdicts (first complete parser, final parser) recorded
   alongside — not overwriting — any one-shot floor results for the same
   operator model.
2. **Given** the intake acceptance scenario (or any other registered drawer),
   **when** the same tool-loop trial is run, **then** the identical loop
   handles it via the drawer's registered probe entry — no drawer-specific
   loop variant exists.
3. **Given** a real (non-synthetic) local source, **when** a tool-loop trial is
   run over it, **then** the run persists **nothing** (no scoreboard entry, no
   kept run artifacts, no retained sandbox) regardless of inspection flags.
4. **Given** an unreachable local model backend, **when** a tool-loop trial is
   requested, **then** the harness returns an explicit "model unavailable"
   outcome (no crash, no partial record).
5. **Given** an operator that consumes a source column to populate a renamed
   output field (e.g. a `timestamp` column consumed as the UTC timestamp
   field) without declaring that column accounted, **when** its parser is
   gated, **then** the gate fails it as a silent absorption — not a pass.
6. **Given** an operator that exhausts the turn cap without producing a working
   parser, **when** the trial ends, **then** the result is a complete, graded,
   deterministic FAIL record — never an aborted half-record or an exception
   that escapes before a record exists.

### Edge cases

- **Regression across turns** (first complete parser passes, final fails): both
  verdicts are recorded, so regression is visible as first-pass/final-fail —
  the loop must not reward it by reporting only the final verdict, nor hide it
  by reporting only the best.
- **Tool misuse**: an operator turn that requests something outside the tool
  contract (including any path that could reach the fixture manifest or
  ground-truth mapping) is refused by construction — the material is not
  reachable by any tool — and the refusal is fed back as that turn's result.
- **Malformed tool call**: a turn the harness cannot parse as a valid tool call
  consumes a turn and feeds a corrective error back; it never crashes the trial.
- **No parser ever produced**: if the operator never writes a complete parser
  within the cap, the "first complete parser" verdict is recorded as absent and
  the final verdict is a graded FAIL over whatever state exists (consistent
  with scenario 6).
- **Context overflow**: the brief plus accumulated turn history must fit the
  explicitly-pinned model context budget; the harness accounts for this budget
  rather than silently truncating (truncation that can drop required API
  surface is the defect this mission exists to prevent).

## Requirements *(mandatory)*

### Functional requirements

| ID | Requirement | Status |
|----|-------------|--------|
| FR-001 | The tool loop runs from **one coherent brief**: a single assembled instruction set in which no instruction contradicts another (the spike's "output only a module, no fences" vs. "iterate using tools" self-contradiction class cannot recur). A committed check verifies the brief is assembled from one canonical source. | Proposed |
| FR-002 | The context served to the operator **always includes, un-truncated, the complete parser API surface it must implement against** (every class/field/method the contract requires), plus the data sample in the same form the production one-shot operator is shown. No serving step may truncate in a way that can drop required API surface; the context budget is explicitly accounted for (the harness pins the model's context size to fit the full brief). | Proposed |
| FR-003 | The operator interacts only through a **bounded tool contract**, defined as a rule (what a tool may read or do, and what it guarantees) rather than a fixed enumerated list. The first registered instances are READ (source and permitted context files) and RUN (a real sandbox ingest). Registering a new tool is adding an entry under the rule, not editing loop branches. | Proposed |
| FR-004 | **Ground-truth exclusion holds by construction at every turn**: no tool, at any turn, can reach the fixture manifest or any ground-truth mapping (the one-shot tier's answer-key exclusion, C-005 there, inherited here as physical unreachability rather than prompt discipline). | Proposed |
| FR-005 | The loop terminates at a **bounded, environment-overridable turn cap** with a documented default; a trial always terminates and always yields a gradeable record. | Proposed |
| FR-006 | Each trial records **two independent grader verdicts**: the **first complete parser** the operator produces (un-coached by later feedback) and the **final parser** at loop end — mirroring the one-shot tier's first/final shape so capability and feedback-driven improvement stay separable and regression across turns is visible. | Proposed |
| FR-007 | A completed tool-loop trial records a **tier-tagged result distinct from the one-shot floor result**, never overwriting it, comparable by operator model (the result schema already carries operator/driver model identities). | Proposed |
| FR-008 | The loop is **scenario-parametric over every registered acceptance drawer** (observation and intake at promotion time) via the existing drawer-probe registration rule; no per-drawer loop variant or branch exists. | Proposed |
| FR-009 | **Sharpened declared-gap rule**: a source column the operator consumes to populate any output field — including under a renamed field (e.g. `timestamp` consumed as the UTC timestamp) — must be declared accounted (in its declared mapped set) or be an explicit gap. A consumed-but-undeclared column is a self-reconcile **failure**, and the brief's contract states this rule explicitly. | Proposed |

### Non-functional requirements

| ID | Requirement | Status |
|----|-------------|--------|
| NFR-001 | **Local-only model backend**: the tier inherits the existing local-endpoint guard; a non-local model endpoint is refused 100% of the time, and zero bytes of prompt, brief, or source sample leave the machine. | Proposed |
| NFR-002 | **Persistence rules unchanged**: a trial over any non-synthetic source persists zero artifacts (no result record, no scoreboard entry, no retained sandbox — inspection flags included); only committed synthetic scenario sources persist. | Proposed |
| NFR-003 | **Never blocks CI**: the tool-loop path is gated behind the existing live-trial marker; zero default-suite tests invoke a real model, and a failing or absent tool-loop trial blocks zero CI gates. | Proposed |
| NFR-004 | **Reuse, not fork**: the loop is new orchestration over the existing sandbox, runner, grader, session-log store, and scoreboard layers — zero duplicated copies of those layers; the existing one-shot path's behavior and its default-suite tests are unchanged. | Proposed |
| NFR-005 | **Defined by rule, not enumeration**: the tier is specified by what counts as a tool, how a drawer registers, and how a tier is scored — adding a tool, drawer, or operator model is a registration, not a code-branch edit (measured at review: a new drawer or tool requires zero edits to the loop body). | Proposed |
| NFR-006 | **Honest record on every path**: 100% of started trials end in exactly one of {complete graded record, explicit model-unavailable outcome}; no path ends in an exception that escapes before a record or outcome exists. | Proposed |

### Constraints

| ID | Constraint | Status |
|----|-----------|--------|
| C-001 | No real operator data, extracted PHI, or generated private artifacts are ever copied into the repo or a git commit (project-level rule; applies to all fixtures, briefs, and recorded results). | Proposed |
| C-002 | The constrained one-shot floor probe is neither replaced nor weakened: its behavior, scoring, and persisted record shapes are unchanged by this mission. | Proposed |
| C-003 | No new model-backend abstraction beyond the existing local backend; no requirement for a frontier or cloud model anywhere in the tier. | Proposed |
| C-004 | No CI or default-gate changes: the tier ships entirely behind the existing live-trial opt-in surface. | Proposed |
| C-005 | The fixture manifest and all ground-truth mappings remain grader-only: unreachable by the operator through any tool, prompt, or context path, at every turn. | Proposed |

## Success criteria

| ID | Criterion |
|----|-----------|
| SC-001 | A maintainer agent can run a complete tool-loop trial over each registered acceptance scenario with a single invocation, ending in a tier-tagged scored result. |
| SC-002 | For one operator model, the one-shot floor result and the tool-loop tier result are simultaneously visible and distinguishable on the recorded scoreboard — neither overwrote the other. |
| SC-003 | 100% of trials over non-synthetic sources leave zero persisted artifacts on disk after the run. |
| SC-004 | The default test suite passes unchanged with zero tests invoking a real model; removing the model backend entirely breaks zero CI gates. |
| SC-005 | A trial whose operator never produces a working parser still ends with a complete graded FAIL record (synthetic source) or explicit outcome — zero aborted half-records across all trials. |
| SC-006 | The served brief verifiably contains the complete required API surface: every class the operator must implement against appears in full in the brief (checkable without running a model). |
| SC-007 | A consumed-but-undeclared source column (the renamed-field case) is failed by the gate in a committed deterministic test. |

## Key entities

- **Tier**: a named, separately-scored way of running the live trial (the
  existing constrained one-shot floor; this mission's tool loop). Defined by a
  scoring rule, not a model list.
- **Brief**: the single coherent instruction set the operator works from —
  contract surface, goal, data sample, tool protocol — assembled from one
  canonical source.
- **Tool contract**: the bounded rule stating what a tool may read or do and
  what it guarantees; READ and RUN are its first registered instances.
- **Turn**: one operator interaction (a tool call or a parser submission) plus
  the harness's fed-back result; turns are bounded by the cap.
- **Tier result**: the persisted, tier-tagged record of one trial — operator
  and driver model identities, turns used, first-complete-parser verdict, final
  verdict.
- **Drawer probe**: the existing per-scenario registration (contract surface,
  batch selection, non-empty check, goal) the loop resolves scenarios through.

## Assumptions

- The complete parser API contract surface (~30 KB ≈ 8–9k tokens measured at
  promotion) plus the loop brief fits a capable local model's context window
  when the harness pins the context budget explicitly; "focused summary vs.
  full contract" is a plan-time serving decision **within** FR-002's
  no-truncation rule, with full-contract the default given the measurements.
- The existing drawer-probe registry, scenario registry, grader, session-log
  store, and scoreboard are stable seams this mission orchestrates over
  (shipped by the session-log-substrate and usable-intake-dimensions missions).
- The one-shot tier's two-verdict (first/final) shape is the right comparison
  shape for the loop tier (confirmed at discovery).

## Dependencies

- Shipped live-trial seam and one-shot cheap-model operator (session-log
  substrate slice one + its closed real-model follow-up).
- Shipped intake acceptance drawer and drawer-probe registration rule
  (usable-intake-dimensions mission) — the queue gate, cleared 2026-06-11.
- The 2026-06-04 follow-up audit as the factual record bounding this scope.

## Out of scope

- Any requirement for a frontier or cloud model; any new model-backend
  abstraction beyond the existing local one.
- Replacing, weakening, or re-scoring the constrained one-shot floor probe.
- Any CI or default-gate change.
- A human-facing UI or human-operated flow for running trials (agent-first:
  the maintainer agent is the operator of this machinery).
- Multi-model tournaments, tier auto-selection policies, or capability routing
  decisions built on top of the recorded tiers (future work that reads these
  results).

## Review & acceptance checklist

See [`checklists/requirements.md`](checklists/requirements.md).
