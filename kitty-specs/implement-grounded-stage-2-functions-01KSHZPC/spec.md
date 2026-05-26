# Implement Grounded Stage 2 Functions - Specification

> **Mission**: `implement-grounded-stage-2-functions-01KSHZPC`
> **Mission type**: `software-dev`
> **Target branch**: `master`
> **Created**: 2026-05-26
> **Status**: Draft

## 1. Purpose

Premura's research mission on grounded Stage 2 engine growth concluded that the next step is to build six specific, question-ready health answers and route Stage 3 through them instead of continuing to rely on direct warehouse reads for those same question shapes.

This mission turns that decision into shipped behavior. After it lands, Premura should answer six approved health questions through Stage 2 signals, surface when the answer is stale or unavailable, and let Stage 3 present those answers without bypassing the signal layer for those cases.

This mission also turns the research findings into a maintainer-ready contribution path. Future Stage 2 additions should have a clear written admission rule, a review checklist, and aligned product and architecture docs, while profile-dependent work remains explicitly deferred to issue `#6`.

## 2. Scope

### In scope

- Shipping the six research-approved Stage 2 answers:
  - current resting heart rate status
  - resting heart rate trend
  - daily steps trend
  - weight trend
  - deep-sleep percentage compared with the user's own recent baseline
  - overnight HRV change around a user-named date
- Routing Stage 3 through those Stage 2 answers for the matching question shapes so those flows no longer depend on direct raw warehouse reads.
- Showing explicit freshness, gap, caveat, and missing-input information when a grounded answer cannot be safely produced.
- Updating the Stage 2 contribution guidance and review gate so future grounded signal work follows a documented, repeatable path.
- Aligning the affected docs with what is now shipped, what remains deferred, and why.

### Out of scope

- Profile-dependent functions such as BMI or age-adjusted interpretation; these remain blocked on issue `#6`.
- Expanding Stage 3 statistics, significance testing, or external reference lookups.
- Solving every remaining direct-read path in Stage 3; this mission only replaces the flows covered by the six approved answers.
- New health directions or new question families beyond the ones already approved by the research mission.

## 3. User Scenarios & Testing

### Scenario A - A user asks for their current resting heart rate

1. The user enters through the cardiovascular direction.
2. Premura returns the user's current resting heart rate through the Stage 2 signal layer.
3. The answer clearly states whether the value is current enough to trust.
4. If the value is too old, Premura does not present it as current; it explains that the answer is stale or unavailable.

### Scenario B - A user asks whether a metric is trending up or down

1. The user asks about resting heart rate, steps, or weight.
2. Premura returns a trend answer based on the relevant Stage 2 signal.
3. The answer makes gaps or imputed periods visible enough that the user is not misled about continuity.
4. Stage 3 presents the Stage 2-backed answer rather than reading raw measurements directly for that question.

### Scenario C - A user asks whether last night's deep sleep was below their own normal

1. The user enters through sleep and recovery.
2. Premura compares the latest deep-sleep percentage with the user's own recent baseline.
3. The answer states that this is a comparison to the user's own normal, not a population or clinical reference range.
4. If the input is too sparse or unreliable, Premura explains why it cannot answer safely.

### Scenario D - A user asks whether overnight HRV changed after a chosen date

1. The user supplies a date tied to a personal change or event.
2. Premura returns a before-and-after HRV comparison around that date.
3. The answer reports the change without claiming causation or statistical significance.
4. If the needed data is missing around either side of the date, Premura reports that the question cannot be answered reliably.

### Scenario E - A maintainer wants to add a future grounded Stage 2 answer

1. The maintainer reads the Stage 2 contribution guidance.
2. They can see what evidence, caveats, review checks, and documentation updates are required.
3. They can tell which proposals belong in Stage 2, which should stay in Stage 3, and which must wait for issue `#6`.

### Edge cases

- The user has some relevant data, but it is outside the trusted freshness window.
- The user has intermittent gaps, so a trend can only be shown with explicit caveats.
- The user asks an approved question in a warehouse that does not contain the required metric at all.
- The user asks for an HRV change around a date that leaves too little data on one side of the comparison.
- Stage 3 receives a question that looks similar to the approved set but still requires statistics or reference data; that flow remains outside this mission.

## 4. Functional Requirements

| ID | Requirement | Verification | Status |
|---|---|---|---|
| FR-001 | Premura SHALL provide six grounded Stage 2 answers covering current resting heart rate status, resting heart rate trend, daily steps trend, weight trend, deep-sleep percentage versus the user's own recent baseline, and overnight HRV change around a user-named date. | Acceptance testing covers all six approved questions end to end. | Confirmed |
| FR-002 | For each approved question, Premura SHALL return the answer through the Stage 2 signal layer rather than relying on a direct raw warehouse read for that same question shape. | Acceptance testing and maintainer review confirm that the matching Stage 3 flows use Stage 2-backed answers. | Confirmed |
| FR-003 | Premura SHALL show when an approved answer is current, stale, unavailable, or limited by gaps, so users can tell whether the result is safe to trust. | Acceptance tests cover current, stale, and missing-data cases for the approved questions. | Confirmed |
| FR-004 | Premura SHALL refuse to present a misleading answer when required inputs are missing, too old, or too sparse for a grounded result. | Negative-path tests show an explicit unavailable or limited-result outcome instead of a silent fallback. | Confirmed |
| FR-005 | Premura SHALL keep the approved Stage 2 answers within the deterministic signal layer and keep statistical claims, external references, and teaching-only behavior outside those answers. | Maintainer review and acceptance tests confirm the shipped answers remain within the approved Stage 2 boundary. | Confirmed |
| FR-006 | Premura SHALL document a contributor path for future grounded Stage 2 answers that states the expected evidence, caveats, review checks, and same-change documentation obligations. | A maintainer can complete a dry-run review of a sample future proposal using only the written guidance. | Confirmed |
| FR-007 | Premura SHALL update the affected project docs so they reflect the six shipped answers, the reduced Stage 3 direct-read debt for those flows, and the continued deferral of profile-dependent work to issue `#6`. | Maintainer review confirms the named docs and issue reference match the shipped scope and remaining boundary. | Confirmed |
| FR-008 | Premura SHALL preserve a clear missing-input path for the approved questions so Stage 3 can tell the user what data is needed when an answer cannot yet be produced. | Acceptance tests show user-visible missing-input guidance for each approved question family where data is absent. | Confirmed |

## 5. Non-Functional Requirements

| ID | Requirement | Threshold / Verification | Status |
|---|---|---|---|
| NFR-001 | Approved answers must be reproducible. | For 100% of acceptance-test fixtures, repeated runs against unchanged warehouse contents produce the same result. | Confirmed |
| NFR-002 | Approved answers must be complete at the intended scope. | All 6 approved questions are covered by end-to-end acceptance tests, with no approved question left on a direct-read-only path. | Confirmed |
| NFR-003 | Trust signaling must be consistent. | In 100% of stale, sparse, or missing-data acceptance cases, Premura returns an explicit freshness or availability state rather than a silent partial answer. | Confirmed |
| NFR-004 | The new question flows must stay fast enough for interactive use. | On the maintainer's representative local datasets, at least 95% of approved-question responses complete in under 5 seconds. | Confirmed |
| NFR-005 | The mission must preserve Premura's local-first privacy posture. | Acceptance and regression testing show 0 background network calls and 0 silent data-sharing events in the approved flows. | Confirmed |
| NFR-006 | The contribution guidance must be usable by a non-specialist maintainer. | A maintainer can review one sample future proposal with no unwritten review steps and no unresolved placeholders in the guidance. | Confirmed |

## 6. Constraints

| ID | Constraint | Rationale | Status |
|---|---|---|---|
| C-001 | The mission is limited to the six Stage 2 answers approved by the research mission and the Stage 3 routing needed to use them. | Keeps scope aligned with the decision-ready shortlist the user asked to implement. | Confirmed |
| C-002 | Profile-dependent functions and interpretations remain out of scope until issue `#6` resolves how baseline personal attributes are represented. | Prevents this mission from silently taking on the unresolved profile-data dependency. | Confirmed |
| C-003 | This mission must not turn Stage 2 into a statistics, reference-lookup, or teaching layer. | Preserves the stage boundaries established in the research findings and architecture docs. | Confirmed |
| C-004 | The approved flows must remain local-first and must not add background network dependence or silent sharing of health data. | Preserves Premura's existing privacy posture. | Confirmed |
| C-005 | Direct-read debt outside the six approved question shapes may remain for now. | Bounds the mission so it stays implementable as one software-dev mission rather than an open-ended Stage 3 rewrite. | Confirmed |

## 7. Success Criteria

- SC-001: A user can ask each of the six approved questions and receive either a grounded answer or an explicit unavailable reason through the shipped product flow.
- SC-002: The matching Stage 3 flows for those six questions no longer depend on direct raw warehouse reads to produce the user-facing answer.
- SC-003: In stale or sparse-data cases, users are explicitly warned about freshness or data gaps in 100% of acceptance-test scenarios.
- SC-004: Maintainer acceptance testing confirms that all six approved questions remain inside Stage 2's deterministic boundary and do not introduce statistics, external reference lookup, or silent sharing.
- SC-005: The project docs and contributor guidance clearly describe what was shipped, what remains deferred to issue `#6`, and how future grounded Stage 2 answers should be reviewed.

## 8. Key Entities

- **Health direction**: The user-facing entry point used to route a question, such as cardiovascular or sleep and recovery.
- **Signal**: A validity-checked, question-ready value or series used to answer one of the approved questions.
- **Freshness verdict**: The user-visible statement that an answer is current enough, stale, or unavailable.
- **Own-baseline comparison**: A result that compares the user's latest value to their own recent normal rather than to a population reference.
- **Change-around-date result**: A before-and-after comparison around a user-provided date, reported without causation or significance claims.
- **Missing-input report**: The user-visible explanation of which data is needed when Premura cannot answer an approved question yet.
- **Contribution package**: The documented set of rationale, evidence, caveats, review checks, and doc updates required for a future Stage 2 addition.

## 9. Assumptions

- The user wants one combined implementation mission rather than two sequential missions, even though the research recommended Mission A first and Mission B second.
- The research findings in `kitty-specs/grounded-extensible-engine-research-01KSD0D1/findings.md` are the authoritative source for the approved question set, the stage boundary, and the deferred profile-data dependency.
- Existing direct-read behavior in Stage 3 may remain for question shapes that are not covered by the six approved answers.
- The affected product and architecture docs should be updated within this mission so the shipped behavior and the written guidance do not drift apart.
