# Feature Specification: Finish Analytical Tool Set

> Status: draft

**Mission Slug**: `finish-analytical-tool-set-01KT0Y95`

Created: 2026-06-01
Mission ID: `01KT0Y95X8XKZCQH3G1Y8QVPDJ`
Mission Type: `software-dev`

## Overview

Premura's analytical surface can already answer conservative single-series and
two-series questions through deterministic tools: `change_point`,
`smoothed_average`, and `correlate`. The current roadmap still names two
deferred tools, `rolling_mean` and `paired_t_test`, as the remaining work needed
to finish the first bounded analytical tool set before PubMed grounding,
nutrition/supplement source adaptation, or teaching UI work.

This mission completes that tool set. It gives the operating agent two more
reviewable ways to analyze the human beneficiary's own local data:

- a rolling mean tool that summarizes a metric's moving level over a declared
  window without hiding gaps or stale evidence;
- a paired comparison tool that compares matched before/after or condition-pair
  observations when the pairing rule is declared before the result exists.

Both tools must preserve Premura's existing honesty contract: the analytical
engine remains deterministic and local-first, weak evidence refuses with no
estimate, available results carry validity and confound metadata, and the MCP
surface narrates engine-owned envelopes rather than performing analytical work.

## Scope

### In Scope

- Add `rolling_mean` as a deterministic analytical tool for declared moving-window
  summaries over one admitted ordered series.
- Add `paired_t_test` as a deterministic analytical tool for declared paired
  comparisons over matched observations from the operator's own data.
- Expose both tools through the default agent-facing analytical surface.
- Record both tools in session research traces when a trace session is supplied.
- Ensure both tools return the shared analytical result envelope with complete
  validity metadata, confound checklist entries, or first-class refusals.
- Update live docs and review contracts so agents can discover, call, and review
  the completed analytical set.
- Preserve the current separation between engine computation, MCP wrapping, and
  trace recording.

### Out Of Scope

- PubMed search, PubMed fetch, literature grounding, or citation workflow.
- Nutrition or supplement parser adaptation and intake-domain resolvers.
- Teaching UI, health-direction interview flow, dashboard work, or charting.
- Automatic metric search, automatic condition discovery, automatic window search,
  or choosing the strongest result after scanning alternatives.
- Diagnostic, treatment, dosing, causation, or population-norm interpretation.
- Changes to the existing `change_point`, `smoothed_average`, or `correlate`
  statistical behavior except where shared docs/discovery lists need to mention
  the new completed set.

## User Scenarios & Testing

### Primary Scenario: Agent Summarizes A Metric With A Declared Rolling Window

An operating agent wants to describe how one metric's level has moved over time,
such as a seven-day rolling view of resting heart rate or steps. The agent names
the metric and window before requesting the result. Premura admits or refuses the
input evidence, then returns a moving-window summary with visible coverage,
missingness, and caveats.

Acceptance test: given an admitted ordered series with sufficient coverage for
the declared window, `rolling_mean` returns an available envelope with window
metadata, summary points, coverage metadata, imputation visibility, and no hidden
gap-filling language.

### Secondary Scenario: Agent Compares Declared Paired Observations

An operating agent wants to compare matched observations for the same person,
such as values before and after a declared date or values paired by a declared
condition. The agent supplies the pairing rule before the result exists. Premura
uses only matched pairs that satisfy the declared rule, refuses when support is
too weak, or returns a paired-difference estimate with uncertainty and validity
metadata.

Acceptance test: given admitted data with enough valid pairs, `paired_t_test`
returns an available envelope containing pair count, mean paired difference,
uncertainty metadata, direction metadata, and a confound checklist, with no cause
claim.

### Secondary Scenario: Evidence Is Too Weak Or The Request Is Too Broad

An agent asks for a rolling mean over a window that cannot be supported, or asks
for a paired comparison without a declared pairing rule. Premura refuses before
showing an estimate.

Acceptance test: unsupported windows, insufficient coverage, missing pairing
rules, too few valid pairs, stale inputs, missing inputs, and invalid parameters
return structured refusals with no estimate.

### Secondary Scenario: Session Trace Captures The Added Tools

An agent opens a research trace session, runs the new tools, marks surfaced
results, and requests disclosure. The disclosure includes `rolling_mean` and
`paired_t_test` calls in the same measured search-effort accounting used by the
existing analytical tools.

Acceptance test: traced calls to both new tools produce exactly one recorded call
each, exact retries collapse according to each tool's normalized hypothesis
identity, refusals still count as examined hypotheses, and surfaced marking works
without changing the engine result envelope.

### Edge Cases

- Empty series, missing metric, stale metric, or inadmissible evidence.
- Rolling window of zero, negative, one, larger than the available admitted span,
  or larger than the supported maximum.
- Rolling windows with partial coverage, long gaps, and upstream-accepted imputed
  points.
- Paired comparison with no valid pairs, too few pairs, identical pair
  differences, missing values on one side, or pair identities that collide.
- Requests that try to scan many windows, many dates, many conditions, or many
  metric pairs and keep the strongest result.
- Requests that ask the paired comparison to imply cause, diagnosis, treatment,
  or population standing.
- Trace sessions omitted, unknown, or supplied for a call that refuses.

## Functional Requirements

| ID | Status | Requirement | Acceptance Criteria |
|---|---|---|---|
| FR-001 | Proposed | The system SHALL provide `rolling_mean` as a first-class analytical tool for one admitted ordered series and one caller-declared rolling window. | Tool discovery lists `rolling_mean`; calls with a valid admitted series and supported window return an analytical envelope rather than an ad hoc payload. |
| FR-002 | Proposed | `rolling_mean` SHALL report window size, emitted summary points, coverage for each emitted point, imputation visibility, and the input span used. | Acceptance fixtures show those fields for 100% of available rolling-mean results. |
| FR-003 | Proposed | `rolling_mean` SHALL refuse unsupported windows, insufficient coverage, stale or inadmissible evidence, and empty inputs before returning any estimate. | Each refusal class has a test fixture that returns a no-estimate refusal with a distinct reason. |
| FR-004 | Proposed | The system SHALL provide `paired_t_test` as a first-class analytical tool for caller-declared paired comparisons over matched observations from the same operator. | Tool discovery lists `paired_t_test`; valid paired inputs return the shared analytical envelope. |
| FR-005 | Proposed | `paired_t_test` SHALL require the pairing rule and comparison direction to be declared before computation. | Calls missing the pairing rule or comparison direction return a no-estimate refusal. |
| FR-006 | Proposed | `paired_t_test` SHALL report pair count, paired-difference estimate, uncertainty metadata, direction metadata, and the admissible paired span. | Acceptance fixtures for available paired comparisons include all listed fields. |
| FR-007 | Proposed | `paired_t_test` SHALL refuse malformed or weak paired comparisons before returning any estimate. | Tests cover missing pairing rule, no pairs, too few pairs, stale evidence, inadmissible evidence, constant paired differences, and invalid parameters. |
| FR-008 | Proposed | Both new tools SHALL use the same available/refused analytical result envelope shape as the shipped analytical tools. | Serialized available results include estimate plus validity metadata; serialized refusals include refusal metadata and no estimate. |
| FR-009 | Proposed | Both new tools SHALL expose only closed-vocabulary analytical question types and confound keys. | Registration rejects any question type or confound key outside the committed vocabulary. |
| FR-010 | Proposed | Both new tools SHALL be available on the default agent-facing surface without analytical computation in that wrapper layer. | Wrapper tests show the agent-facing surface delegates to the analytical engine and only serializes the returned envelope. |
| FR-011 | Proposed | Both new tools SHALL support optional session trace recording without changing untraced result payloads. | For each tool, traced and untraced calls produce byte-equivalent engine envelopes aside from top-level trace metadata. |
| FR-012 | Proposed | Session disclosure SHALL include `rolling_mean` and `paired_t_test` in measured analytical-call counts and unique hypothesis counts. | Trace tests show each new tool records calls, collapses exact retries, includes refusals, and can be marked surfaced. |
| FR-013 | Proposed | The analytical tool catalog and live reference docs SHALL describe the completed tool set and the remaining deferred work accurately. | Docs list `change_point`, `smoothed_average`, `correlate`, `rolling_mean`, and `paired_t_test` as shipped when the mission closes, and keep PubMed grounding deferred. |
| FR-014 | Proposed | Both tools SHALL reject requests that scan alternatives to select the strongest-looking result. | Requests to auto-search windows, dates, conditions, metric pairs, or lags return refusals or require the caller to submit one declared hypothesis. |

## Non-Functional Requirements

| ID | Status | Requirement | Measurement |
|---|---|---|---|
| NFR-001 | Proposed | Both new tools SHALL be deterministic. | For identical inputs, declared parameters, and policies, repeated serialized outputs are byte-equivalent in 100% of acceptance fixtures. |
| NFR-002 | Proposed | Both new tools SHALL remain local-first and offline. | Runtime tests or static checks show 0 network, PubMed, remote API, or literature-fetch calls are reachable from either tool's runtime path. |
| NFR-003 | Proposed | Available results SHALL be complete enough for agent narration without guessing. | 100% of available results include inputs, declared parameters, estimate, validity status, sample/support counts, missingness or coverage metadata, and confound checklist. |
| NFR-004 | Proposed | Refusal behavior SHALL be specific and reviewable. | Each tool has at least 6 distinct refusal fixtures, and each fixture returns a machine-readable reason plus no estimate. |
| NFR-005 | Proposed | Generated caveat text SHALL be concise. | Every built-in caveat or refusal message intended for agent narration is 320 characters or fewer. |
| NFR-006 | Proposed | The new trace integration SHALL be reliable. | In end-to-end trace tests, 100% of dispatched traced calls to the new tools create exactly one recorded analytical-call row. |
| NFR-007 | Proposed | The completed analytical catalog SHALL remain discoverable quickly for agent startup. | Listing analytical tools returns the full built-in catalog in under 1 second on the reference local development environment. |
| NFR-008 | Proposed | The feature SHALL preserve existing analytical behavior. | 100% of existing tests for `change_point`, `smoothed_average`, `correlate`, and session trace pass unchanged except for expected catalog-size or documentation updates. |

## Constraints

| ID | Status | Constraint | Rationale |
|---|---|---|---|
| C-001 | Active | The analytical engine MUST remain stateless; session state belongs to the research trace boundary. | Trace accounting must not make deterministic tools depend on mutable session state. |
| C-002 | Active | Runtime analytical code MUST NOT call PubMed, external literature, network services, or remote APIs. | Literature grounding is a separate deferred mission. |
| C-003 | Active | The new tools MUST NOT produce diagnosis, treatment advice, dosing advice, emergency advice, population-norm ranking, or causal interpretation. | Premura's analytical surface is descriptive and comparative over one person's data. |
| C-004 | Active | The new tools MUST NOT auto-scan alternatives and keep the best-looking result. | Search effort must stay explicit and traceable, not hidden inside a tool. |
| C-005 | Active | Agent-facing wrappers MUST delegate analytical work to the engine-owned analytical path. | The MCP layer is a tool boundary, not a statistics implementation layer. |
| C-006 | Active | The mission MUST preserve the existing static, reviewable publication posture for built-in analytical tools. | Agents and reviewers need a predictable list of shipped built-in tools. |
| C-007 | Active | Any new analytical question type or confound key MUST be a reviewed closed-vocabulary addition. | Agents must branch on committed keys, not invented prose labels. |
| C-008 | Active | `rolling_mean` and `paired_t_test` MUST be specified as bounded abstractions, not as hardcoded metric-specific tools. | The doctrine requires rules agents can apply to future metrics, not enumerated metric pairs or cases. |

## Key Entities

- **Rolling mean**: A moving-window summary over one admitted ordered series,
  using a caller-declared window and visible coverage metadata.
- **Paired comparison**: A comparison over matched observations where each pair is
  defined by a caller-declared pairing rule before the result exists.
- **Pairing rule**: The declared rule that decides which observations form pairs,
  such as before/after around a named date or matched condition labels.
- **Analytical result envelope**: The shared result shape that carries either an
  available estimate with validity metadata or a refusal with no estimate.
- **Normalized hypothesis identity**: The per-tool identity used by the research
  trace to count unique examined hypotheses and collapse exact retries.
- **Confound checklist**: Closed-vocabulary validity and interpretation warnings
  that travel with available analytical results.

## Success Criteria

| ID | Criterion | Measurement |
|---|---|---|
| SC-001 | An agent can discover and call the completed analytical set from the default surface. | Tool discovery includes five analytical tools: `change_point`, `smoothed_average`, `correlate`, `rolling_mean`, and `paired_t_test`. |
| SC-002 | Rolling-window questions can be answered honestly when evidence supports them. | Supported rolling-mean fixtures return complete available envelopes with window, coverage, missingness, and caveat metadata. |
| SC-003 | Paired-comparison questions can be answered honestly when evidence supports them. | Supported paired-comparison fixtures return complete available envelopes with pair count, paired-difference estimate, uncertainty metadata, and caveats. |
| SC-004 | Weak or malformed requests cannot produce estimates. | 100% of required refusal fixtures for both tools return no-estimate refusals. |
| SC-005 | Search effort remains measurable for the new tools. | Trace disclosure includes new-tool calls in raw call counts, unique hypothesis counts, refusal breakdowns, and surfaced marks. |
| SC-006 | The completed tool set does not expand scope into literature or teaching. | No runtime PubMed/network calls or UI/interview behavior are added by this mission. |
| SC-007 | Existing analytical behavior is not regressed. | Existing analytical and trace regression tests pass, with only intentional catalog/documentation expectation changes. |

## Assumptions

- The mission includes both deferred tools: `rolling_mean` and `paired_t_test`.
- `rolling_mean` is distinct from the already shipped `smoothed_average`; it
  completes the explicitly named roadmap item rather than renaming existing
  behavior.
- `paired_t_test` may report a paired-difference estimate and uncertainty, but it
  must still preserve Premura's no-causation, no-diagnosis, and no-hidden-search
  boundaries.
- Exact numerical thresholds for minimum window coverage, minimum pair count, and
  supported parameter bounds are planning decisions, constrained by this spec's
  refusal and metadata requirements.
- PubMed grounding follows in a later mission after this tool set is complete.

## Dependencies

- The existing Stage 3 analytical contract and result envelope.
- The existing evidence-admissibility gate for analytical inputs.
- The existing session research trace service and disclosure tools.
- Current live docs that list `rolling_mean`, `paired_t_test`, and PubMed
  grounding as deferred analytical-depth work.
