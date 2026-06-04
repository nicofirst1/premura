# Feature Specification: Usable Intake Dimensions

**Mission**: usable-intake-dimensions-01KT950A
**Mission type**: software-dev
**Target branch**: master
**Created**: 2026-06-04
**Status**: Draft

## Why this mission exists

Premura already stores nutrition and supplement intake: the
`nutrition_intake` and `supplement_intake` domains are valid declaration targets,
the storage tables exist, and a normalized load path (`IntakeBatch` →
`persist_intake_batch`) is shipped. But these dimensions are **second-class**:

- A runtime agent **cannot build-and-use an intake parser**: the parser protocol
  itself is observation-only (`parse(path) -> IngestBatch`), with no wired path
  from a parser to `IntakeBatch` / `persist_intake_batch` — so even though the
  storage seam exists, there is no intake parser path to follow. The
  parser-generator skill correspondingly documents only the observation path
  (it emits `IngestBatch` + `dim_metric.yaml` rows and says nothing about intake).
- Even when intake rows land, **nothing in Premura can read them** — both
  domains resolve to an explicit `unsupported_domain` outcome, so no signal can
  use them.

The result is a half-built domain: intake can be *stored* but never *built by
runtime* and never *used by analysis*.

This mission closes that gap and — because we do **both** domains at once —
**proves the existing input-resolution seam generalizes**, so adding the next
intake dimension is fill-in-the-blank rather than a fresh design pass. It does
**not** invent a new abstraction layer; it proves the seam we have already
generalizes and writes down the rule. Whether a dedicated intake-dimension
contract is ever worth building is left as a reasoned recommendation, not built.

## User Scenarios & Testing

### Primary flows

1. **Supplement adherence (descriptive).** An operator has logged supplement
   intake. Through an agent, they ask "how consistently have I taken
   *<a supplement I name>* recently?" Premura answers with an honest coverage
   read ("logged on K of the last N days"), or an explicit "not enough data" —
   never a recommendation and never a fabricated count.

2. **Nutrition intake trend (descriptive).** An operator has logged meals.
   Through an agent, they ask "is my recent logged *<nutrient/energy I name>*
   trending up, down, or flat?" Premura answers descriptively, the way the
   existing steps trend does, and **never imputes missing days**.

3. **Honest refusal when there is no data.** An operator who has logged no intake
   asks either question. Premura returns an explicit, honest outcome (no usable
   data / not yet supported until a source is added) — never a guessed value and
   never a fallback into another domain's data.

4. **Build-and-use a new intake source at runtime.** An operator drops an
   unfamiliar nutrition or supplement export. A runtime agent follows one written
   rule (the parser-generator skill's intake path) to build a parser, loads the
   operator's own data, and uses it immediately — **with no human review**, per
   the settled runtime build-and-use boundary. Review applies only if the
   operator later chooses to contribute the parser back as a public PR.

### Edge cases

- **Stale intake.** The most recent logged intake is older than the signal's
  freshness window → an explicit `stale_input` outcome, not a confident answer.
- **Partial logging.** Some days in the window have no logged intake → the
  nutrition trend reports over the days that exist and never fills gaps; coverage
  is visible.
- **Unmapped source field.** A reference-parser source column that has no
  canonical home is **declared as a gap** (surfaced for review), never silently
  dropped.
- **Text-only supplement dose.** A supplement logged with a descriptive dose and
  no numeric amount is still a valid, resolvable intake record.
- **Event-level vs item-level nutrition quantity.** A nutrition quantity attached
  to the whole event resolves correctly without being double-counted against
  item-level quantities.
- **Declared-but-empty domain.** The domain is declarable but the operator has no
  rows yet → resolves to an honest non-usable outcome, distinct from "domain not
  supported."

## Requirements

### Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| FR-001 | Both `nutrition_intake` and `supplement_intake` resolve to a **usable resolved value** through the existing input-resolution seam when matching rows exist, replacing today's `unsupported_domain` outcome. | Draft |
| FR-002 | A declared intake dependency with **no matching, fresh row** resolves to an explicit non-usable outcome (**missing / stale**) and **never** substitutes a value from another domain (no hidden fallback). *(Answer-sufficiency — `insufficient_data` — is decided at the signal layer; see FR-005.)* | Draft |
| FR-003 | A descriptive **supplement-intake signal** answers a coverage/cadence question over a caller-declared supplement and window ("logged on K of the last N days"), declaring its `supplement_intake` dependency and reading **only** through the resolver. | Draft |
| FR-004 | A descriptive **nutrition-intake signal** answers an intake-trend question over a caller-declared nutrient/energy field ("up / down / flat recently"), declaring its `nutrition_intake` dependency and **never imputing missing days**. | Draft |
| FR-005 | Each new signal returns the **standard signal envelope** with explicit `available` / `missing_input` / `stale_input` / `insufficient_data` states and authored missing-input guidance, consistent with the existing six signals. | Draft |
| FR-006 | Both new signals are reachable on the **default agent surface** as tools, following the same validity-gated pattern as the existing signal-backed tools (they make intake genuinely usable by an agent, not just resolvable internally). | Draft |
| FR-007 | The **authoritative intake parser contract and the parser-generator skill** are updated together so runtime intake parser authoring is implementable, not merely described: the contract must name the supported parser shape for nutrition/supplement sources, the runtime load path for `IntakeBatch`, and any required protocol/surface change beyond today's observation-only `parse(...) -> IngestBatch` shape; the skill then documents that settled intake path generically so a runtime agent can build-and-use an intake parser with no review. | Draft |
| FR-008 | A **minimal reference intake parser + synthetic fixture** exists for at least one nutrition shape and one supplement shape, proving `parse → IntakeBatch → persist` end-to-end with made-up values only. | Draft |
| FR-009 | The repo documents the **generalized "add a new intake dimension" rule** — the domain-agnostic steps to make a declared intake dimension resolvable and signal-backed — exercised and validated by **both** shipped domains. | Draft |
| FR-010 | A **final recommendation note** summarizes the generalization as proven across both domains and gives a go/no-go, a sketch, and an explicit **trigger condition** for a future dedicated intake-dimension contract (the deferred abstraction). | Draft |

### Non-Functional Requirements

| ID | Requirement | Measurable threshold | Status |
|---|---|---|---|
| NFR-001 | New signals stay **descriptive, non-diagnostic**. | Zero diagnosis / causation / statistical-significance claims: no reference ranges, no "you should", no p-value or "significant"; asserted by tests over the signal envelopes. | Draft |
| NFR-002 | **Local-first / privacy** preserved. | Zero new outbound network calls introduced by this mission; intake data stays in its existing PHI-bearing local tables and is never added to any export path. | Draft |
| NFR-003 | **No silent fallback.** | In 100% of "no matching row" cases across both domains, resolution returns an explicit non-usable outcome; a regression test proves a same-named observation row never satisfies an intake dependency. | Draft |
| NFR-004 | **Deterministic, offline test coverage.** | Every new resolver, signal, tool wrapper, and reference-parser path is covered by deterministic offline tests; the full `pytest` suite remains green with no network dependency. | Draft |
| NFR-005 | **Generalization is structural, not asserted.** | Both domains register through the same `@resolver(domain=...)` seam with **no per-domain special-casing** in the shared resolution path; a test asserts the shared seam contains no domain-specific branch for the two intake domains. | Draft |
| NFR-006 | **Temporal basis is explicit and test-locked.** | Every day/window/count the new intake resolvers and signals report is derived from the same declared basis they compute on: local calendar day from the intake event timestamp + `local_tz` when present (else the warehouse's existing naive-UTC convention). At least one acceptance fixture crosses local midnight so local day != UTC date, and asserts both computation and reported metadata use the local-day basis. | Draft |

### Constraints

| ID | Constraint | Source | Status |
|---|---|---|---|
| C-001 | No real operator exports or PHI committed; all fixtures are synthetic (real structure, made-up values). | AGENTS.md | Active |
| C-002 | Intake stays a **separate seam** from `IngestBatch` / observations; intake meanings are never written into `fact_measurement` / `fact_interval` / note storage. | PROFILE_AND_INTAKE_CONTRACT | Active |
| C-003 | **No new abstraction layer** for intake dimensions is built in this mission (approach A); a dedicated contract is only *recommended* (FR-010), never implemented here. | This mission's agreed scope | Active |
| C-004 | Use the existing `@resolver(domain=...)` seam and the already-declared `SEMANTIC_DOMAINS`; do not re-pick the storage shape or add domains beyond the two already declared. | engine input-resolution seam | Active |
| C-005 | The reference parser is a **proof/test anchor**, not an officially-supported vendor; runtime build-and-use remains the path for real operator sources (no review for own-data use). | Runtime build-and-use boundary (session-log-substrate FR‑130 clarification; ADR 0010; DOCTRINE) | Active |
| C-006 | The profile/intake meaning-contract invariants hold (e.g. a meal's energy is never merged with a wearable's total kcal); the contract test harness must still pass. | PROFILE_AND_INTAKE_CONTRACT | Active |
| C-007 | Design a level above: the deliverable is the **rule** for adding an intake dimension, not a hardcoded list of nutrients/supplements; signals take caller-declared fields rather than enumerating specific ones. | DOCTRINE (guide, don't enumerate) | Active |

## Success Criteria

| ID | Outcome | Status |
|---|---|---|
| SC-001 | A user who has logged supplement intake can ask how consistently they have taken a named supplement recently and get an honest coverage answer (or an explicit "not enough data"), with no diagnosis or recommendation. | Draft |
| SC-002 | A user who has logged meals can ask whether a named nutrient/energy intake is trending and get a descriptive up/down/flat answer that never invents missing days. | Draft |
| SC-003 | When no intake has been logged, both questions return an explicit, honest "no usable data / not yet supported" outcome — never a fabricated number and never another domain's value. | Draft |
| SC-004 | An agent handed an unfamiliar nutrition or supplement export can follow one written rule to build a parser that loads it and use it immediately, with no human review for the operator's own data; that rule is backed by the shipped parser contract / protocol surface, not only by skill prose. | Draft |
| SC-005 | Adding the *next* intake dimension after this mission requires following the documented rule only, with **no change to the shared resolution seam** — verifiable because both shipped domains followed exactly those steps. | Draft |
| SC-006 | The mission leaves a clear, reasoned recommendation on whether and when to build a dedicated intake-dimension contract, including an explicit trigger condition. | Draft |

## Key Entities

- **Intake dimension** — a declarable semantic domain whose data is intake, not
  observation (`nutrition_intake`, `supplement_intake`).
- **IntakeBatch** — the parser-to-store seam for intake (events → items →
  quantities/doses), distinct from the observation `IngestBatch`.
- **Resolver** — a domain-aware reader that turns a declared dependency into
  either a resolved value or an explicit non-usable outcome, with no cross-domain
  fallback.
- **Intake-aware signal** — a descriptive, non-diagnostic signal that declares an
  intake dependency and reads through its resolver.
- **Reference parser + synthetic fixture** — the minimal, made-up proof that the
  intake build-and-load path works end-to-end; a contract-test anchor, not a
  supported vendor.
- **Add-a-dimension rule** — the written, domain-agnostic generalization the two
  domains exercise.
- **Recommendation note** — the signpost for the deferred dedicated
  intake-dimension contract (go/no-go + sketch + trigger).

## Assumptions

- The two intake domains already exist as declarable `SEMANTIC_DOMAINS` with
  concrete storage tables and a working `persist_intake_batch` load path
  (confirmed in the current codebase) — this mission builds *over* that seam, not
  another modeling pass.
- New signals follow the existing four-family descriptive/comparative envelope
  and reach the agent surface the same way the existing six do.
- "Logged supplement / meals" presupposes intake rows were loaded by *some*
  parser; this mission ships only a **reference** parser + fixture as proof, not a
  production vendor parser (real vendor parsers are built at runtime per C-005).
- Caller-declared signal inputs (which supplement, which nutrient/energy field,
  which window) keep the signals general and avoid enumerating specific
  nutrients/supplements (C-007).

## Dependencies

- The shipped **input-resolution seam** (`@resolver(domain=...)`,
  `resolve_dependency`, `SEMANTIC_DOMAINS`) and its `unsupported_domain` outcome.
- The shipped **intake storage + load path** (`IntakeBatch`,
  `NutritionIntakeInput` / `SupplementIntakeInput`, `persist_intake_batch`) and
  the intake domain tables.
- The **profile/intake meaning contract** and its test harness.
- The **parser-generator skill** (currently observation-only).
- The **authoritative parser contract / protocol surface** in `src/premura/parsers/CONTRACT.md` and `src/premura/parsers/base.py`, which currently describe two seams but still type parser plugins as `parse(path) -> IngestBatch`.
- The **default agent (MCP) surface** that exposes signal-backed tools.

## Out of scope (named so it is not assumed shipped)

- Any **production vendor** nutrition/supplement parser (e.g. a specific app's
  export) — that is runtime build-and-use work, not a mission deliverable.
- A **dedicated intake-dimension contract / registry** (approach B) — only
  recommended here (FR-010), never built.
- **Age-adjusted or any diagnostic interpretation** of intake.
- New intake **domains beyond the two** already declared.
- Cross-linking intake to literature or to observation analytics (e.g.
  "supplement X vs my HRV") — a later, separately-scoped concern.
