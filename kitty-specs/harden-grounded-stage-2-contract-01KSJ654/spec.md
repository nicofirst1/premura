# Feature Specification: Harden Grounded Stage 2 Contract

**Mission**: harden-grounded-stage-2-contract-01KSJ654
**Created**: 2026-05-26
**Mission type**: software-dev
**Status**: Draft

## 1. Summary

A post-merge review of the `implement-grounded-stage-2-functions` mission found
that the six grounded Stage 2 answers and nine MCP tools ship and work, but four
contract surfaces were built-but-unwired or shape-dishonest. This follow-up
mission closes those gaps. It adds **no new answers and no new analysis** — it
makes the existing surfaces tell the truth and deliver what the prior spec
already promised.

The four gaps:

1. **Actionable missing-input guidance is authored but never surfaced.** Every
   signal carries a plain-language hint (e.g. "connect a wearable that records
   resting heart rate"), and a structured `MissingInputReport` type exists, but
   the Stage 3 surface never reads the hint or builds the report. A user with no
   data gets a generic "no value recorded" message instead of being told what to
   do. This is the unmet half of the prior mission's FR-008.
2. **The built-in signal loader has a suppression footgun.** Loading is gated on
   "is the registry non-empty?", so registering any custom signal first silently
   prevents all built-in signals from loading.
3. **The deep-sleep own-baseline result fabricates numbers.** When no
   trustworthy comparison exists, it reports `0.0` for the latest value and
   baseline mean instead of "no value", so a consumer that ignores the status
   field can render a false "0.0% vs 0.0%".
4. **One approved question lacks end-to-end coverage.** Five of the six approved
   questions have a Stage 3 call test; `weight_trend` does not, leaving the prior
   mission's "all six covered end to end" promise only partially met.

## 2. User Scenarios & Testing

### Primary actors

- **End user** asking an approved health question through the Stage 3 (MCP) tool
  surface.
- **Downstream caller / UI** that renders a tool response programmatically.
- **Future contributor / agent** extending the engine with a custom signal.

### Acceptance scenarios

1. **Missing data tells the user what to do.** Given a user with no recorded
   resting heart rate, when they ask for resting-HR status through Stage 3, then
   the response carries actionable guidance naming the data to connect (the
   signal's missing-input hint), not just a generic "no value" message.
2. **Missing data is machine-readable.** Given the same unavailable answer, when
   a downstream caller inspects the response, then it finds structured fields
   listing the required inputs and which are missing or stale, so it can branch
   without parsing prose.
3. **Each missing-input family is distinguishable.** Given missing vs.
   present-but-stale vs. present-but-too-sparse inputs, when Stage 3 responds,
   then the unavailable reason and the structured input detail differ
   accordingly (no collapse into one generic error).
4. **Custom signal does not hide built-ins.** Given a process that registers a
   custom signal before any built-in is loaded, when the system later needs
   built-in signals, then all built-in signals (lab ratios and the six grounded
   answers) are still present and callable.
5. **No fabricated baseline numbers.** Given a user with no deep-sleep value or
   too few prior nights to form a baseline, when they ask the deep-sleep
   own-baseline question, then the response presents no numeric latest value or
   baseline mean (the numbers are absent/empty) while the status and caveats
   explain why.
6. **Every approved question is covered through Stage 3.** Given the full set of
   six approved questions, when the test suite runs, then each — including
   `weight_trend` — is exercised by an end-to-end Stage 3 tool call, not only at
   the engine layer.

### Edge cases

- A signal that is unavailable for a reason other than missing input (e.g.
  present-but-stale) must still serialize honestly and not be forced into a
  missing-input shape.
- Hardening the loader must not break the existing lazy-load guarantee
  (importing the engine must not eagerly load signal modules).
- Making baseline numeric fields optional must not break callers of the other
  result families whose value fields legitimately stay required.

## 3. Functional Requirements

| ID | Requirement | Verification | Status |
|---|---|---|---|
| FR-001 | When an approved Stage 2 question cannot be answered because required data is absent, the Stage 3 response SHALL include the signal's plain-language missing-input guidance telling the user what data to connect or record. | Stage 3 test asserts the response for a data-absent case contains the signal's specific actionable guidance text, not only a generic message. | Draft |
| FR-002 | When an approved answer is unavailable, the Stage 3 response SHALL include a structured, machine-readable description of the inputs the answer needs, identifying required inputs and which are missing and/or stale. | Stage 3 test asserts the unavailable response carries structured required / missing / stale input fields a caller can branch on. | Draft |
| FR-003 | Stage 3 SHALL keep the distinct unavailable reasons (missing input, present-but-stale, insufficient data) separable in the response, and the new structured input detail SHALL appear only where it applies. | Stage 3 tests cover missing-input, stale-input, and insufficient-data cases and assert each stays structurally distinct. | Draft |
| FR-004 | Registering a custom signal before built-in signals have loaded SHALL NOT prevent built-in signals from loading; all built-in signals SHALL remain available afterward. | Regression test registers a custom signal first, then asserts all built-in signal names are present and callable. | Draft |
| FR-005 | When the deep-sleep own-baseline comparison is unavailable or its baseline is unknown, the result SHALL NOT present fabricated numeric values; the latest-value and baseline-mean fields SHALL be absent/empty so a consumer ignoring the status cannot render a false comparison. | Test asserts that in unavailable/unknown cases the numeric latest-value and baseline-mean fields are not present as fabricated numbers, while status and caveats still explain the outcome. | Draft |
| FR-006 | All six approved Stage 2 questions SHALL be exercised by an end-to-end Stage 3 tool-call test, including `weight_trend`. | Test suite contains a Stage 3 call test for each of the six approved questions. | Draft |

## 4. Non-Functional Requirements

| ID | Requirement | Threshold / Verification | Status |
|---|---|---|---|
| NFR-001 | The hardening SHALL preserve existing behavior of the six signals, the nine tools, and the lazy-load boundary. | Full existing test suite passes with no regressions, and importing the engine still does not eagerly load signal modules. | Draft |
| NFR-002 | The new guidance and structured fields SHALL remain non-diagnostic. | Review and tests confirm no clinical thresholds, statistical significance, or causal language is introduced; guidance only names data to connect/record. | Draft |
| NFR-003 | Unavailable answers SHALL never present a silent or misleading partial result. | In every missing/stale/sparse test case, the response carries an explicit unavailable/limited state plus honest (non-fabricated) fields. | Draft |

## 5. Constraints

| ID | Constraint | Status |
|---|---|---|
| C-001 | No new signals, no statistics/PubMed behavior, and no profile-dependent behavior; profile-dependent work stays deferred to issue `#6`. | Active |
| C-002 | The three raw warehouse tools (`query_warehouse`, `list_metrics`, `metric_summary`) keep their current contract and behavior unchanged. | Active |
| C-003 | Changes are confined to the engine result envelopes, the built-in loader, the deep-sleep own-baseline signal, the Stage 3 server surface, and their tests. No unrelated refactors. | Active |

## 6. Success Criteria

- SC-001: A user with no recorded data for an approved question receives a
  response that names the specific data to connect or record, in 100% of the
  approved data-absent cases.
- SC-002: A downstream caller can determine the required, missing, and stale
  inputs for an unavailable answer from structured fields alone, without parsing
  free text.
- SC-003: Registering a custom signal before built-ins never reduces the set of
  available built-in signals.
- SC-004: No approved-answer response ever shows a fabricated numeric value when
  the underlying comparison is unavailable or unknown.
- SC-005: All six approved questions are covered by end-to-end Stage 3 tests
  (six of six), with no regression in the existing suite.

## 7. Key Entities

- **Missing-input guidance**: per-signal plain-language text telling the user
  what data to connect or record to make an answer possible.
- **Structured missing-input report**: the machine-readable description of an
  unavailable answer's input needs (required / missing / stale inputs).
- **Own-baseline comparison result**: the deep-sleep result whose numeric latest
  value and baseline mean must be honestly absent when no trustworthy comparison
  exists.
- **Built-in signal loader**: the mechanism that loads built-in signals on first
  need, which must track load state explicitly rather than inferring it from
  registry contents.

## 8. Assumptions

- The missing-input guidance text already authored on each signal is acceptable
  copy; this mission surfaces it rather than rewriting it.
- "Honest absence" for numeric fields means an explicit empty/null value in the
  serialized response, consistent with how the status-family result already
  omits its value when unavailable.
- The structured missing-input detail reuses the already-defined report shape
  (required / missing / stale inputs) rather than inventing a new one.

## 9. Scope

**In scope**: surfacing authored missing-input guidance and a structured input
report through Stage 3; hardening the built-in loader against pre-registration
suppression; making the deep-sleep own-baseline result numerically honest when
unavailable/unknown; adding the missing `weight_trend` Stage 3 test; and
strengthening the related tests to constrain these behaviors.

**Out of scope**: new signals or question shapes; statistical tooling, external
references, or teaching behavior; profile-dependent answers (deferred to `#6`);
any change to the raw warehouse tools' contract; unrelated refactors.
