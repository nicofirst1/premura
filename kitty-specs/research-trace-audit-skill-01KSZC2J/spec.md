# Mission Specification: Research Trace Audit Skill

**Mission Type**: software-dev  
**Status**: Draft  
**Created**: 2026-05-31  
**Branch Contract**: Planning/base branch `master`; completed changes merge into `master`.

## Intent

Build a Premura-specific agent skill that audits an analytical answer against the session research trace that already ships. The skill should help an operating agent or reviewer decide whether the final answer was honest about search effort, refused calls, unavailable surfaced counts, and non-causal limits.

The mission starts with a research slice before implementation. That research should study how agent skills are written in general, how skills are installed or discovered across agent ecosystems, whether a write-once packaging approach can support multiple local installation homes, and how those findings should shape this Premura audit skill.

## User Need

Premura can now record what an agent examined during an analytical session, but the trace deliberately stops short of judging the final answer. The maintainer needs a skill that can read the structured trace disclosure and guide an agent through a reproducible review: did the answer disclose the number of hypotheses examined, mention refusals and unavailable surfaced marks when relevant, avoid hiding contradictory results, and avoid claims of cause, diagnosis, certainty, or statistical significance that the tools do not support?

## Actors

- **Premura operating agent**: Uses the skill while preparing or reviewing an answer based on analytical tool calls.
- **Maintainer**: Benefits from clearer, more reproducible agent behavior and approves the mission outputs.
- **Reviewer agent**: Checks whether the skill and its packaging guidance match the research trace contract and Premura doctrine.

## User Scenarios & Testing

### Scenario 1: Audit a Complete Trace

Given an analytical session with recorded calls, surfaced marks, and a final answer, when an operating agent invokes the audit skill, then the skill guides the agent to compare the final answer against the trace disclosure and produce a clear pass/fail/needs-revision judgment with cited reasons.

### Scenario 2: No Surfaced Marks Were Recorded

Given a trace disclosure where analytical calls exist but the surfaced summary is unavailable, when the skill audits the final answer, then it treats the missing surfaced marks as a review issue and does not infer a surfaced count from the prose or from effect size.

### Scenario 3: Refused Calls Were Omitted

Given a trace disclosure containing refused analytical calls, when the final answer only presents available findings, then the skill checks whether the answer appropriately discloses or contextualizes the refused calls instead of hiding the search effort.

### Scenario 4: Answer Overclaims the Tool Output

Given a final answer that turns an association, change, or smoothed pattern into causal, diagnostic, treatment, significance, or certainty language, when the skill audits it, then the skill flags the overclaim and recommends safer wording aligned with Premura's analytical boundaries.

### Scenario 5: Skill Portability Research

Given the mission's first work package, when the research slice is complete, then the maintainer has a concise recommendation for writing the audit skill once and installing or adapting it across the relevant local agent skill homes when feasible.

## Functional Requirements

| ID | Status | Requirement | Acceptance Criteria |
|---|---|---|---|
| FR-001 | Proposed | The mission MUST begin with a dedicated research slice before audit-skill implementation. | The plan contains a WP0 or equivalent first work package whose output is reviewed before later implementation work begins. |
| FR-002 | Proposed | The research slice MUST study how agent skills are generally written, using current external sources where useful. | The research output cites at least three relevant external sources or explains why fewer authoritative sources were available. |
| FR-003 | Proposed | The research slice MUST study how skills are installed and discovered across local agent environments. | The research output covers at least Claude-style and OpenCode-style local skill homes and identifies which installation patterns are directly relevant to this repo. |
| FR-004 | Proposed | The research slice MUST evaluate whether a write-once packaging or library approach can generate or install skill variants for multiple local homes. | The research output gives a recommendation of adopt, defer, or reject, with reasons and tradeoffs. |
| FR-005 | Proposed | The research slice MUST translate the general skill-writing findings into guidance for this Premura audit skill. | The research output includes Premura-specific authoring rules for inputs, review flow, output shape, and installation approach. |
| FR-006 | Proposed | The audit skill MUST consume the session disclosure shape documented by Premura's audit-consumer contract. | A reviewer can map each skill-required trace input to fields in the contract without relying on free-form trace prose. |
| FR-007 | Proposed | The audit skill MUST compare a final analytical answer against the trace disclosure. | The skill asks for or obtains both the structured trace disclosure and the final answer text before issuing an audit judgment. |
| FR-008 | Proposed | The audit skill MUST judge whether search effort was disclosed accurately. | The skill checks the raw analytical call count, unique hypothesis count, surfaced summary, and disclosure framing against the final answer. |
| FR-009 | Proposed | The audit skill MUST judge whether refused, errored, unavailable, or contradictory evidence was hidden or misrepresented. | The skill explicitly reviews refusal breakdown, terminal statuses, surfaced marks, and call records before marking an answer acceptable. |
| FR-010 | Proposed | The audit skill MUST flag overclaims beyond Premura's analytical boundaries. | The skill flags causal, diagnostic, treatment, p-value, statistical-significance, multiplicity-correction, and unsupported-certainty claims when the trace or tool outputs do not support them. |
| FR-011 | Proposed | The audit skill MUST produce an actionable audit result. | The result includes one of pass, needs revision, or blocked, plus specific reasons and suggested revisions or next steps. |
| FR-012 | Proposed | The audit skill MUST stay Premura-specific for its first shipped version. | The skill names Premura's research trace and audit-consumer contract as its target input and does not claim to audit arbitrary agent answers. |

## Non-Functional Requirements

| ID | Status | Requirement | Acceptance Criteria |
|---|---|---|---|
| NFR-001 | Proposed | A first-time skill user MUST be able to identify required inputs in under 2 minutes. | In review, a user can find the required trace disclosure and final-answer inputs from the skill instructions without reading source code. |
| NFR-002 | Proposed | The skill's audit decision MUST be reproducible for the same trace disclosure and final answer. | Two independent reviewer agents following the skill reach the same top-level judgment for at least 4 of 5 representative audit fixtures. |
| NFR-003 | Proposed | The skill MUST minimize false confidence. | Every non-pass result includes at least one concrete evidence reference from the trace disclosure or final-answer text. |
| NFR-004 | Proposed | The research output MUST be concise enough to guide planning. | The WP0 research summary is no more than 1,500 words, excluding citations and appendices. |
| NFR-005 | Proposed | The first shipped skill MUST preserve Premura's local-first runtime boundary. | Runtime use of the audit skill requires no background network call; any internet research belongs to WP0 or later authoring work, not ordinary audit execution. |
| NFR-006 | Proposed | Installation guidance MUST be verifiable by a reviewer. | The mission documents each supported installation target with a check a reviewer can run or inspect locally. |

## Constraints

| ID | Status | Constraint | Rationale |
|---|---|---|---|
| C-001 | Active | The mission MUST NOT change canonical trace counts or research-trace storage semantics. | The audit skill interprets the trace; it does not redefine the ledger. |
| C-002 | Active | The skill MUST NOT infer surfaced calls from effect size, final-answer prose, or available status as a canonical count. | Premura's trace contract makes surfaced marks explicit and reports unavailable rather than guessing. |
| C-003 | Active | The skill MUST NOT introduce p-values, statistical significance labels, or multiplicity-corrected statistics. | Premura's analytical layer deliberately avoids those semantics. |
| C-004 | Active | The skill MUST NOT present association, change, or smoothed pattern outputs as causation, diagnosis, treatment, or prediction. | The analytical tools are descriptive and bounded. |
| C-005 | Active | The first shipped version MUST target Premura's trace/audit contract rather than a generic answer-audit product. | The immediate product gap is the interpretation half of Premura's shipped trace. |
| C-006 | Active | The mission MUST keep skill packaging research separate from audit logic. | Installation strategy should not obscure the actual audit rubric. |

## Key Entities

- **Session Disclosure**: The structured audit-consumer object derived from a session research trace, including session identity, warehouse fingerprint, raw call count, unique hypothesis count, surfaced summary, refusal breakdown, and bounded call records.
- **Final Analytical Answer**: The text or response being audited against the session disclosure.
- **Audit Rubric**: The bounded set of review criteria the skill applies, covering search-effort disclosure, refused or unavailable calls, contradictory findings, and overclaiming.
- **Audit Result**: The skill's output judgment with reasons, evidence references, and recommended revisions or next steps.
- **Skill Packaging Recommendation**: The WP0 outcome describing how the skill should be authored and installed across relevant local agent environments.

## Assumptions

- The first useful version is a Premura-specific skill, not a general-purpose audit framework.
- The existing audit-consumer contract is stable enough to target directly.
- WP0 may use the internet for research, but normal audit execution should not depend on network access.
- Planning may refine exact supported installation targets after WP0, but the mission should at minimum consider Claude-style and OpenCode-style local skill homes.

## Edge Cases

- The trace has analytical calls but no surfaced marks.
- The trace contains refused or errored calls but the final answer only mentions available findings.
- The final answer includes cautious wording but omits the denominator of hypotheses examined.
- The final answer discloses search effort but still turns an association into causation.
- The trace disclosure has a bounded or truncated call list; the skill must respect summary counts rather than requiring every raw call.
- The available installation patterns differ enough that a write-once packaging approach is not worth adopting immediately.

## Success Criteria

| ID | Status | Criterion | Measurement |
|---|---|---|---|
| SC-001 | Proposed | The maintainer can decide how to author and install the audit skill before implementation begins. | WP0 produces an accepted recommendation covering general skill-writing patterns, installation targets, packaging options, and Premura-specific implications. |
| SC-002 | Proposed | The skill can audit representative Premura analytical answers. | At least 5 representative audit fixtures are reviewed, including pass, omitted search effort, hidden refusal, surfaced-unavailable, and overclaim cases. |
| SC-003 | Proposed | The skill gives actionable feedback instead of vague criticism. | Every failing fixture produces at least one concrete reason and one suggested correction. |
| SC-004 | Proposed | The skill preserves the trace contract's meaning. | Review confirms no requirement, test fixture, or skill instruction redefines unique hypothesis count, surfaced count, or forbidden semantics. |
| SC-005 | Proposed | Installation guidance is usable locally. | A reviewer can verify at least one supported local installation path and can see which additional paths are supported, deferred, or rejected. |

## Out of Scope

- Changing `premura.trace`, the trace schema, or the canonical audit-consumer contract unless WP0 or planning identifies a blocking mismatch that the maintainer explicitly approves.
- Building generic audit support for non-Premura agent answers.
- Adding new analytical tools, PubMed grounding, or intake resolvers.
- Creating a human dashboard for audit review.
- Making ordinary audit execution depend on live internet access.

## Open Questions

No open clarification markers remain. Planning may still refine the work-package breakdown and exact installation targets after WP0 research.
