# Stage 2 Evidence Admissibility Foundation

## Mission Type

software-dev

## Background

Premura is a local-first personal health-data warehouse used mainly by AI agents
on behalf of a human operator. Because the domain is health, the system must not
let an agent turn stale, sparse, or poorly grounded data into confident-sounding
advice.

The research note at
`docs/history/research/STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md` records the
input to this mission. Its central finding is that the dangerous failure is not
only generic hallucination. A more specific failure is using the wrong evidence
for the question, especially old evidence presented as if it described the
present.

This mission turns that research into the first implementable Stage 2 foundation:
a deterministic policy layer that decides which evidence is admissible before
later analytical tools use it.

## Scope

### In Scope

- Define a small set of question types that Stage 2 can classify before evidence
  selection.
- Define metric-family policy classes that describe what each family can
  honestly support.
- Decide whether candidate evidence is admissible, rejected, or insufficient for
  the question.
- Preserve provenance, timestamps, caveats, and rejection reasons in the result.
- Refuse clearly when no admissible evidence remains.
- Keep the behavior descriptive and non-diagnostic.

### Out Of Scope

- New Stage 3 MCP analytical tools.
- PubMed or external literature integration.
- Diagnosis, treatment advice, medication advice, or emergency guidance.
- A user interface or teaching layer.
- New parser support or new source artifacts.
- Clinically authoritative per-analyte rules for every lab marker.

## User Scenarios & Testing

### Primary Scenario: Agent asks for current status

An agent acting for the operator asks whether a health measure describes the
operator's current state. Stage 2 checks whether the available evidence is recent
and semantically appropriate for a current-status question. If the evidence is
old or only suitable for historical context, the result refuses to treat it as
current and explains why.

Acceptance test:
Given only evidence outside the accepted freshness policy for current status,
the result identifies the evidence as rejected for current-status use and does
not return a current-state answer.

### Secondary Scenario: Agent asks for a recent trend

An agent asks whether a metric has been moving up, down, or staying similar over
a recent period. Stage 2 checks whether there are enough observations across the
relevant period and whether missingness makes the trend unsafe to summarize. If
the evidence is too sparse, the result refuses with a clear insufficiency reason.

Acceptance test:
Given fewer observations than the policy requires for a recent trend, the result
returns an insufficient-evidence outcome rather than a trend direction.

### Secondary Scenario: Agent asks about long-term control

An agent asks about a marker whose meaning is long-horizon rather than immediate.
Stage 2 treats that evidence as potentially useful for long-term control while
still refusing to use it for a present-tense claim.

Acceptance test:
Given a long-horizon marker, the result can mark it admissible for long-term
control and inadmissible for current status in the same policy vocabulary.

### Edge Cases

- Evidence exists but has no usable timestamp.
- Evidence is recent but belongs to the wrong semantic class for the question.
- Evidence is present but too sparse to support a trend.
- Evidence is method-sensitive and needs caveats rather than a hard verdict.
- Multiple evidence items disagree because they come from different times or
  source artifacts.

## Functional Requirements

| ID | Status | Requirement | Acceptance Criteria |
|---|---|---|---|
| FR-001 | Accepted | The system SHALL classify analytical requests into the question types `current_status`, `recent_trend`, `long_term_control`, and `historical_baseline` before evidence is admitted for use. | Each supported request shape is assigned exactly one question type, and unsupported shapes return a clear unsupported-question outcome. |
| FR-002 | Accepted | The system SHALL define metric-family policy classes that state which question types each family can honestly support. | At least the families in the saved research note are represented or deliberately deferred with a documented reason. |
| FR-003 | Accepted | The system SHALL evaluate candidate evidence against the selected question type before that evidence is eligible for later analytical use. | Evidence valid for one question type can be marked inadmissible for another without losing its provenance. |
| FR-004 | Accepted | The system SHALL return explicit rejection reasons for evidence that is stale, too sparse, missing required context, or semantically wrong for the question. | Every rejected evidence item has one or more machine-readable rejection reasons and a plain-English explanation. |
| FR-005 | Accepted | The system SHALL keep admissible evidence separate from rejected evidence in its result. | Consumers can inspect which evidence was used and which evidence was rejected without parsing prose. |
| FR-006 | Accepted | The system SHALL preserve provenance for every admissible and rejected evidence item. | Each evidence item includes source identity when known, timestamp or effective date, metric identity, and policy outcome. |
| FR-007 | Accepted | The system SHALL refuse to answer when no admissible evidence remains after policy evaluation. | A no-admissible-evidence case returns a refusal outcome with the reason, not an empty or guessed analytical answer. |
| FR-008 | Accepted | The system SHALL attach standing caveats for method-sensitive families rather than presenting them as definitive. | Families marked method-sensitive always produce caveat text when admitted or rejected. |
| FR-009 | Accepted | The system SHALL keep this foundation descriptive and non-diagnostic. | Results do not contain diagnosis, treatment advice, medication advice, emergency guidance, or population-norm claims. |

## Non-Functional Requirements

| ID | Status | Requirement | Measurement |
|---|---|---|---|
| NFR-001 | Accepted | The policy evaluation SHALL be deterministic. | For the same warehouse state, request, and policy version, repeated evaluations produce identical outcomes in 100% of test cases. |
| NFR-002 | Accepted | The result shape SHALL be traceable. | 100% of admissible and rejected evidence entries expose provenance and policy outcome fields. |
| NFR-003 | Accepted | The foundation SHALL avoid diagnostic or prescriptive language. | Automated text checks and reviewer inspection find zero diagnosis, treatment, dosing, or emergency-advice claims in policy-produced messages. |
| NFR-004 | Accepted | The foundation SHALL make refusal states testable. | Tests cover stale evidence, sparse evidence, missing timestamp, wrong question type, and no admissible evidence. |
| NFR-005 | Accepted | The foundation SHALL cover the initial policy taxonomy. | At least 10 metric families or explicit family groups from the research note have policy-class coverage before mission acceptance. |
| NFR-006 | Accepted | The foundation SHALL keep policy caveats concise for downstream surfaces. | Plain-English explanations are no longer than 280 characters per evidence-level caveat unless reviewer-approved. |

## Constraints

| ID | Status | Constraint | Rationale |
|---|---|---|---|
| C-001 | Accepted | The foundation MUST sit in Stage 2 and not introduce Stage 3 tool behavior. | The mission prepares evidence for later tools but does not expand the agent-facing tool surface. |
| C-002 | Accepted | The foundation MUST use the user's own warehouse evidence only. | Premura's current analytical layer is grounded in local personal data, not external clinical authority. |
| C-003 | Accepted | The foundation MUST NOT create a new answer family unless a later mission approves that contract change. | Existing Stage 2 contracts keep answer families closed unless explicitly expanded. |
| C-004 | Accepted | Stable profile facts MUST be treated as effective-dated assertions rather than expiring observations. | Profile context is semantically distinct from observation history. |
| C-005 | Accepted | Intake and profile dependencies MUST remain explicit if a future consumer needs them. | Hidden fallback to whatever row happens to exist would violate the profile/intake contract. |
| C-006 | Accepted | The policy MUST be framed as a safety and admissibility default, not as clinical authority. | Premura should not pretend to provide universal medical rules. |

## Key Entities

- **Question type**: The kind of analytical question being asked, such as current
  status or recent trend.
- **Metric family**: A group of metrics with similar temporal meaning, such as
  acute spot measures, long-horizon control markers, or method-sensitive
  wearable estimates.
- **Policy class**: The admissibility behavior assigned to a metric family, such
  as strict-window, baseline-relative, caveat-only, or valid-until-superseded.
- **Candidate evidence**: A warehouse value or series being considered for use.
- **Admissible evidence**: Candidate evidence that passes the policy for the
  selected question type.
- **Rejected evidence**: Candidate evidence that exists but is unsafe or wrong to
  use for the selected question type.
- **Refusal outcome**: A result that explains why the system cannot answer rather
  than guessing.

## Success Criteria

| ID | Criterion | Measurement |
|---|---|---|
| SC-001 | Agents can distinguish current-status evidence from historical or long-term-control evidence. | In acceptance fixtures, 100% of old long-horizon markers are blocked from current-status answers while remaining available for their appropriate question type. |
| SC-002 | Stale, sparse, and wrong-kind evidence cannot silently influence later analysis. | In acceptance fixtures, 100% of rejected evidence is excluded from the admissible evidence set and carries a rejection reason. |
| SC-003 | The operator can understand why Premura refused to answer. | In review, every refusal outcome has a plain-English explanation understandable without technical knowledge. |
| SC-004 | The foundation is ready for a later deterministic-tools mission. | The next mission can reference the policy classes and result shape without reopening the basic freshness/admissibility decision. |

## Assumptions

- The saved research note is sufficient background for this mission and does not
  need to become a runtime contract.
- The first implementation should prefer conservative refusal over broad
  coverage.
- Policy classes can start as general defaults and become more specific in later
  missions when real metric families require it.
- Stage 3 tools will be specified separately after this foundation is accepted.

## Dependencies

- `docs/architecture/STAGES.md` for the Stage 2 / Stage 3 boundary.
- `src/premura/engine/CONTRACT.md` for Stage 2 evidence and caveat rules.
- `docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md` for profile and intake
  meaning boundaries.
- `docs/history/research/STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md` for the
  research summary that motivates the policy taxonomy.
