# Feature Specification: Session Research Trace and Multiplicity Disclosure

> Status: draft

**Mission Slug**: `session-research-trace-01KSYT4A`

Created: 2026-05-31
Mission ID: `01KSYT4AY2YPE4GZDS09VJ1327`

## Overview

Premura's analytical surface now offers three inference tools (`change_point`,
`correlate`, and the forthcoming `paired_t_test`). An agent can run many
hypotheses against one person's data and present only the one that fits. Each
tool is honest **per call**, but per-call honesty cannot see the search effort
across a whole investigative session — the classic n-of-1 danger of multiple
comparisons. The honest response is **disclosure of search effort** ("K
user-facing findings among N unique hypotheses examined"), not a fabricated
multiplicity-corrected statistic.

This feature adds a **session-scoped, append-only research trace at the MCP
boundary** that mechanically records every analytical tool call, derives a
**measured** multiplicity disclosure, and lets the agent mark which results it
actually surfaced to the user. The count is measured by the boundary, never
self-reported by the operating agent. The analytical engine stays pure
(stateless, deterministic, offline). This feature ships the trace and a stable
**audit-consumer contract**; the audit skill that interprets a trace and turns
findings into issues/PRs is an explicit follow-on.

Design background: design decision note
`docs/adr/0009-session-research-trace-and-multiplicity-disclosure.md` and the
planning brief `docs/planning/research-trace-multiplicity-audit.md`. This
feature is the trace/audit mission that design decision note `0008`
(`correlate`) explicitly deferred.

### Why a "level above" (doctrine)

- **Agent-first.** The trace is a ledger the agent reads and writes through the
  MCP surface; it is not a human dashboard. Human-readable exports are generated
  on demand, never the source of truth.
- **Guide, don't enumerate.** The feature defines the *rule* for what counts as
  an examined hypothesis (a normalized identity per tool) and how a surfaced
  finding is marked — not an enumerated catalog of "notable" findings or a fixed
  report format. Adding a future analytical tool means declaring its hypothesis
  identity, not editing a counting switch.
- **Local-first.** The trace lives in the same local warehouse file, under its
  own schema; nothing leaves the machine.

## User Scenarios & Testing

Actors: the **operating agent** (primary client, via the MCP surface), and the
**human beneficiary** (who receives the agent's answer and may later read an
exported trace).

### Primary scenario — measured multiplicity disclosure

1. The agent opens a research session at the MCP boundary.
2. The agent runs several analytical calls in that session — e.g. `correlate`
   on a few metric pairs and lags, a `change_point`, some repeats, and a couple
   of calls that refuse for weak support or no overlap.
3. As it composes its answer, the agent marks the one or two results it actually
   uses in the answer as **surfaced**, with a role and short rationale.
4. The agent (or the human, via export) requests the session disclosure and
   receives: **raw analytical call count**, **unique examined-hypothesis count
   (N)**, **surfaced count (K)**, **refusal count with reasons**, and **stable
   references** to each recorded call/result.
5. The disclosure reads "**K user-facing findings among N unique hypotheses
   examined**" (with the raw call count shown separately), never "K significant
   results among N tests".

### Acceptance scenarios

- **AS-1 (measured counts).** Given a session with multiple analytical calls
  including exact retries and refusals, the disclosure reports a raw call count
  greater than the unique-hypothesis count N, and N excludes exact retries.
- **AS-2 (refusals count toward N).** Given an analytical call that refuses for
  weak support / stale / inadmissible / no-overlap / out-of-bounds evidence, that
  call is recorded and **included** in N (a refusal is still a look at the data),
  and appears in the refusal breakdown.
- **AS-3 (excluded calls).** Given catalog/metadata calls (`list_metrics`,
  `metric_summary`), pre-question validation failures (empty metric id, invalid
  enum), re-exports of a prior result, and reads of the trace itself, none of
  them increments N or the raw analytical-call count.
- **AS-4 (surfaced marking).** Given the agent marks two results surfaced via the
  marking step, the disclosure reports K = 2 with their roles/rationales and
  stable references.
- **AS-5 (conservative fallback).** Given a session with analytical calls but no
  surfaced marks, the disclosure reports surfaced count as **unavailable** with
  an explicit message ("agent did not mark included results"), never a guessed or
  inferred number.
- **AS-6 (engine purity preserved).** The analytical engine performs no
  recording, holds no session state, and its tool outputs are byte-identical
  whether or not a trace session is active. Recording happens entirely at the MCP
  boundary, around dispatch.
- **AS-7 (provenance boundary).** Trace records persist under a dedicated
  non-`hp.*` schema; no trace write touches `hp.*`, and no health fact is written
  into the trace schema.
- **AS-8 (audit-consumer contract).** A consumer reading a session's trace can
  obtain, through documented stable fields/IDs: per-call tool name, normalized
  hypothesis identity, status/refusal reason, result reference (hash or compact
  envelope), surfaced markers, and the derived counts — without parsing prose.

### Edge cases

- Disclosure requested for an unknown / never-opened session → explicit
  "no such session" outcome, not an empty success.
- Two metric orders of the same pair with the same lag/direction → treated per
  the declared identity rule (whether order-sensitive is settled in the design
  note; the spec requires the rule be deterministic and documented).
- A call recorded "before" dispatch but the engine raises mid-dispatch → the
  trace records the attempt and its terminal status; the disclosure stays
  internally consistent (raw ≥ N ≥ surfaced unless surfaced is unavailable).
- Concurrent calls within one session → recording stays append-only and each
  call gets a stable, unique reference.
- Large session (hundreds of calls) → disclosure remains a single bounded query
  over the trace, not an unbounded scan returning every row.

## Requirements

### Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| FR-001 | The MCP boundary MUST open and identify a research session (stable session id, start time, client label, warehouse fingerprint/schema version) so calls can be grouped and a session reproduced. | Proposed |
| FR-002 | The MCP boundary MUST record every analytical tool invocation (the inference/estimate tools) in an append-only trace, capturing tool name, the call's normalized hypothesis identity, a request reference, timestamps, and terminal status (available or refused with reason). | Proposed |
| FR-003 | Recording MUST happen at the MCP boundary around dispatch (before/after), so counts are measured by the system, not self-reported by the operating agent. | Proposed |
| FR-004 | The trace MUST record a result reference for each non-refusal call (a compact result envelope or a stable result hash) and the machine-readable refusal reason for each refusal. | Proposed |
| FR-005 | Each analytical tool MUST contribute a deterministic **normalized hypothesis identity** used for dedup and the N count (correlate: left metric, right metric, lag, expected direction, declared params; change_point: metric, params; smoothed_average: metric, window, min coverage; future paired_t_test: outcome, grouping/event, windows, contrast, params). Adding a tool means declaring its identity, not editing a counting switch. | Proposed |
| FR-006 | The disclosure MUST compute **N = count of unique examined hypotheses** within a session (after normalizing and deduplicating identical requests) and MUST surface a separate **raw analytical-call count**. | Proposed |
| FR-007 | A refused analytical call (weak support, stale, inadmissible, no-overlap, out-of-bounds) MUST be recorded and MUST count toward N and the raw call count, and MUST appear in a refusal breakdown by reason. | Proposed |
| FR-008 | The following MUST NOT count toward N or the raw analytical-call count: exact retries of the same normalized request in-session; catalog/metadata calls (`list_metrics`, `metric_summary`); validation failures before a request becomes an analytical question; re-rendering/exporting a prior result; reading the trace. | Proposed |
| FR-009 | The agent MUST be able to mark a recorded call as **surfaced** (selected for presentation in the answer's claims/summary/recommendation/next-step), with a role and short rationale, through a session-layer marking step at the MCP boundary. | Proposed |
| FR-010 | The disclosure MUST compute **K = count of surfaced-marked calls** and present the framing "K user-facing findings among N unique hypotheses examined" — never "significant results" or "tests". | Proposed |
| FR-011 | When a session has analytical calls but no surfaced marks, the disclosure MUST report surfaced count as **unavailable** with an explicit message, and MUST NOT infer or guess K. (Audit-derived inference, if ever added, is a non-canonical follow-on, never produced here.) | Proposed |
| FR-012 | The MCP surface MUST expose a way to read/export a session disclosure returning raw call count, unique-hypothesis count N, surfaced count K (or unavailable), refusal breakdown, and stable per-call references. | Proposed |
| FR-013 | The feature MUST publish a stable **audit-consumer contract** (documented field names, IDs, normalized hypothesis identity, surfaced markers, refusal reasons, result references) that a later audit skill consumes, decoupled from the trace's internal storage. | Proposed |
| FR-014 | Human-readable trace exports (Markdown/JSON) MUST be generated from the structured trace on demand and MUST NOT be the canonical record. | Proposed |
| FR-015 | Requesting a disclosure/export for an unknown or never-opened session MUST return an explicit not-found outcome, distinct from an empty-but-valid session. | Proposed |
| FR-016 | Live reference docs (STATUS, STAGES, ROADMAP, FULL_APP_DEVELOPMENT_PLAN) MUST be updated to reflect the shipped trace surface and the deferred audit skill as part of this mission. | Proposed |

### Non-Functional Requirements

| ID | Requirement | Status |
|---|---|---|
| NFR-001 | The analytical engine MUST remain pure: no clock, no session state, no filesystem, no network introduced by this feature. Analytical tool outputs MUST be byte-identical whether or not a trace session is active (verified by a regression comparing envelopes with tracing on vs off). | Proposed |
| NFR-002 | The trace MUST persist under a dedicated schema separate from `hp.*` (health facts). 0 trace writes may target `hp.*`, and 0 health-fact writes may target the trace schema (verified by schema-ownership tests). | Proposed |
| NFR-003 | The trace MUST be append-only: no update or delete of a recorded call/result/mark in normal operation (verified by tests asserting recorded rows are immutable through the public surface). | Proposed |
| NFR-004 | Counts MUST be measured at the boundary: a test in which the agent self-reports a false count MUST NOT change the disclosure's N/K/raw values. | Proposed |
| NFR-005 | A session disclosure MUST be produced by a single bounded query over the trace and MUST return in under 1 second for a session of up to 500 recorded calls on the reference local warehouse. | Proposed |
| NFR-006 | Disclosure counts MUST be internally consistent for any session: raw_calls ≥ N ≥ K, except when K is reported unavailable (verified by a property/invariant test over recorded sessions). | Proposed |
| NFR-007 | Recording MUST be reliable for the analytical surface: every dispatched analytical call in an open session yields exactly one recorded call row (no double-count, no silent drop), verified end-to-end through the MCP surface. | Proposed |

### Constraints

| ID | Constraint | Status |
|---|---|---|
| C-001 | The trace store MUST live in the existing local DuckDB warehouse file (no new datastore, no network service). | Active |
| C-002 | The feature MUST NOT introduce p-values, significance tests, or any "significant" labeling; "surfaced" means selected-for-presentation, never statistically significant. | Active |
| C-003 | The audit skill (interpreting a trace; generating issues/PRs/suggestions; critiquing the final answer against the trace) is OUT of scope; this mission ships only the trace and the audit-consumer contract. | Active |
| C-004 | PubMed/literature grounding and any change to existing analytical tool math are OUT of scope. | Active |
| C-005 | A design decision note (`0009`) locking the trace home, the non-`hp.*` schema boundary, the public types, and the audit-consumer contract MUST exist before implementation (per repo convention: a note precedes a mission that introduces a new stage interface or public type). | Active |
| C-006 | Tool-use provenance recorded in the trace MUST NOT be treated as health data; it is excluded from the encrypted health export / backup semantics that apply to `hp.*`. | Active |

## Success Criteria

- **SC-001** For any analytical session, an agent or human can obtain a single
  disclosure stating "K user-facing findings among N unique hypotheses examined"
  plus the raw call count and a refusal breakdown.
- **SC-002** The disclosure's N and raw counts are unchanged by an agent that
  reports false counts — the numbers reflect what the boundary observed, 100% of
  the time.
- **SC-003** Exact retries and non-analytical calls (catalog/metadata, pre-question
  validation failures, re-exports, trace reads) contribute 0 to N.
- **SC-004** Refused analytical calls are included in N and itemized by reason.
- **SC-005** When no results are marked surfaced, the disclosure reports surfaced
  as unavailable with an explicit message in 100% of such sessions — it never
  shows a guessed number.
- **SC-006** Analytical tool outputs are byte-identical with tracing on vs off
  (engine purity preserved).
- **SC-007** No trace write touches health-fact storage and no health fact is
  written into the trace schema.
- **SC-008** A documented audit-consumer contract exists such that a follow-on
  reader can derive every disclosure number from stable fields without parsing
  prose.
- **SC-009** A session of up to 500 recorded calls produces its disclosure in
  under 1 second on the reference local warehouse.

## Key Entities

- **Research session** — a grouping of analytical calls with a stable id, start
  time, client label, and warehouse fingerprint/schema version; the unit a
  disclosure is computed over and a session can be reproduced from.
- **Recorded analytical call** — one analytical invocation: tool name, normalized
  hypothesis identity, request reference, timestamps, terminal status
  (available/refused) and refusal reason when applicable.
- **Recorded result reference** — a compact result envelope or stable result hash
  attached to a non-refusal call.
- **Surfaced mark** — an agent-declared marker that a recorded call was used in
  the user-facing answer, with role and rationale.
- **Disclosure** — the derived view over a session: raw call count, unique
  examined-hypothesis count N, surfaced count K (or unavailable), refusal
  breakdown, and stable references.
- **Normalized hypothesis identity** — the per-tool key that determines whether
  two calls are the "same" examined hypothesis (drives dedup and N).

## Assumptions

- Sessions are opened explicitly through the MCP surface (favored over implicit
  per-connection sessions) to guarantee a reproducible session id; the exact
  lifecycle is finalized in design decision note `0009` / planning.
- "Analytical tools" subject to recording are the inference/estimate tools on the
  analytical surface; `smoothed_average` is recorded as an examined hypothesis
  when used to explore patterns. The precise inclusion list is confirmed against
  the analytical registry during plan.
- Exact `request hash` / `result hash` normalization and the order-sensitivity of
  the correlate identity are implementation details settled in plan, constrained
  by the determinism requirement (NFR-001, NFR-006).
- The reference local warehouse for NFR-005/SC-009 is a developer machine
  comparable to the operator's; numbers are a sanity bound, not a benchmark.

## Out of Scope

- The audit skill (trace interpretation, issue/PR/suggestion generation,
  automated critique of the final answer) — follow-on mission (C-003).
- PubMed/literature grounding (C-004).
- Any change to engine purity or existing analytical tool math (C-004, NFR-001).
- New analytical tools (`rolling_mean`, `paired_t_test`) — this mission only
  requires the trace to accommodate them via the declared-identity rule.

## Dependencies

- The shipped analytical contract and tools (`change_point`, `smoothed_average`,
  `correlate`) and their dispatch path (`premura.engine.analytical_contract`,
  the MCP analytical wrappers).
- The local DuckDB warehouse and its migration mechanism.
- Design decision note `0009` (must precede implementation, C-005).
