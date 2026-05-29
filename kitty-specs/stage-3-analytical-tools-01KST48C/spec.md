# Stage 3 Analytical Tools Specification

## Mission Type

software-dev

## Background

Premura can already answer grounded, freshness-aware descriptive and comparative
questions through Stage 2 result families (`status`, `trend`, `baseline`, and
`change`). Those answers are exposed through Stage 3 MCP tools that delegate to
the engine and avoid direct fact-table access from the default agent surface.

The next analytical-depth step is a deterministic statistical layer over the
operator's own admissible evidence. This mission defines the contract for that
layer and proves it with a narrow first tool set: `change_point` plus a smoothed
average tool. The goal is not broad statistics coverage. The goal is to make the
safe extension shape real, so later analytical tools can be added by following a
bounded contract rather than inventing one-off conventions.

This mission addresses the narration-honesty half of R7: an agent should narrate
computed estimates, uncertainty, and validity metadata returned by tools instead
of fabricating magnitudes from priors. It does not eliminate the underlying
weakness of n-of-1 self-tracked time series. That weakness is handled by carrying
validity and confound metadata beside every estimate, and by refusing when the
data cannot honestly support the requested analysis.

## Scope

### In Scope

- Define a deterministic analytical-tool contract with a registry, declared tool
  descriptor, engine-owned input-series contract, and mandatory result envelope.
- Preserve the repo's static built-in loading and explicit MCP wrapper posture
  unless the mission explicitly changes it.
- Require default-surface MCP wrappers for analytical tools to delegate to the
  engine-owned analytical path and avoid raw fact-table access in the wrapper.
- Route analytical inputs through evidence-admissibility evaluation before any
  statistical computation runs.
- Define how analytical tools receive prepared input series after admissibility:
  aligned values plus overlap, sample size, freshness, imputation, source, and
  refusal metadata.
- Define a result envelope that includes estimate, uncertainty when applicable,
  `validity_status`, `is_imputed_pct`, sample size, and a closed-vocabulary
  confound checklist.
- Implement `change_point` and smoothed average as the first conservative proof
  tools.
- Publish both proof tools on the default MCP surface as agent-callable tools
  that delegate to the engine and return the serialized analytical envelope.
- Decide, through the preceding analytical-depth research note, whether
  analytical admissibility maps to existing evidence-policy `QuestionType`
  values or requires reviewed analytical question types.
- Keep all output descriptive, non-diagnostic, local-first, and non-causal.

### Out Of Scope

- PubMed search/fetch and the literature-to-warehouse bridge.
- Reproducible research traces or notebook output.
- Network access from the analytical layer.
- New Stage 2 answer families or changes to the closed `RESULT_FAMILIES` set.
- Broad significance-testing coverage or a general hypothesis-testing suite.
- Diagnosis, treatment, medication, dosing, emergency guidance, or
  population-norm comparison.
- User interface or teaching-layer work.

## User Scenarios & Testing

### Primary Scenario: Agent Finds a Level Shift

An agent acting for the operator asks whether and when a metric's baseline level
shifted, such as whether resting heart rate stepped to a new level after a known
life or training change. The `change_point` tool evaluates the input evidence,
detects a level shift conservatively, and returns the estimated change-point date,
old level, new level, uncertainty, validity status, imputation percentage, sample
size, and confound checklist. The result names no cause.

Acceptance test: given an admissible series with a representative level shift,
`change_point` returns an estimate and uncertainty metadata, and test validation
rejects the result unless the full analytical envelope is present.

### Secondary Scenario: Agent Requests a Smoothed Average

An agent asks for a smoothed recent average of one admissible metric so the
operator can see a conservative pattern rather than a noisy point value. The
smoothed average tool evaluates the input evidence, applies the declared smoothing
rules, and returns the smoothed value or series with window metadata, sample size,
imputation percentage, validity status, uncertainty behavior where defined, and a
confound checklist.

Acceptance test: given an admissible noisy series, the smoothed average tool
returns a deterministic smoothed output with declared window and metadata; given
insufficient or stale evidence, it returns a structured refusal and no estimate.

### Secondary Scenario: Agent Requests an Unsupported Change Point

An agent asks where a metric's level shifted, but the available evidence is too
sparse, too stale, or outside supported parameters. The tool refuses with a
distinct machine-readable reason rather than returning a spurious change point.

Acceptance test: stale input, insufficient overlap/sample size, and out-of-bounds
parameters each produce a distinct refusal outcome with no estimate.

### Secondary Scenario: Agent Adds a New Analytical Tool

An agent or contributor adds a new deterministic analytical tool by registering it
against the analytical contract, declaring its inputs, result shape, and confound
checklist. The new tool is invoked through the shared analytical dispatch path
without adding a per-tool branch to the dispatcher.

Acceptance test: a test registers a trivial analytical tool through the public
contract and invokes it through the same analytical dispatch path as the built-in
proof tools, without adding a per-tool dispatcher branch.

### Edge Cases

- One input series is admissible and another required input is not.
- Inputs are admissible but their usable window is below the minimum sample size.
- A method has no natural confidence interval and must say so explicitly.
- Input is heavily imputed but otherwise admissible.
- Requested smoothing, window, lag, or change-point parameters are outside
  supported bounds.
- An implementer tries to treat `change_point` as a Stage 2 `change` answer
  family instead of a Stage 3 analytical tool.

## Functional Requirements

| ID | Status | Requirement | Acceptance Criteria |
|---|---|---|---|
| FR-001 | Draft | The system SHALL define a deterministic analytical-tool contract consisting of a registry plus declared tool descriptor, so a new analytical tool is added through registration rather than a per-tool dispatch branch. | A trivial analytical tool can be registered and invoked through the shared analytical dispatch path without adding a per-tool dispatcher branch. |
| FR-002 | Draft | Each default-surface analytical MCP wrapper SHALL delegate to the engine-owned analytical path. | Analytical MCP wrappers do not query raw fact tables directly and return only serialized engine analytical results or structured refusals. |
| FR-003 | Draft | The engine-owned analytical path SHALL evaluate input evidence for admissibility before statistical computation. | Inputs that fail admissibility never reach the statistical computation and instead return a structured refusal reason. |
| FR-004 | Draft | The system SHALL define the analytical input-series contract consumed after admissibility evaluation. | Analytical inputs include aligned timestamps and values plus overlap, sample size, freshness, imputation, source, and refusal metadata. |
| FR-005 | Draft | The system SHALL define a mandatory analytical result envelope. | Non-refusal analytical results cannot be serialized unless they include estimate, uncertainty behavior, `validity_status`, `is_imputed_pct`, sample size, and confound checklist. |
| FR-006 | Draft | The system SHALL enforce a closed confound-checklist vocabulary for analytical results. | Confound keys outside the committed vocabulary are rejected by validation tests. |
| FR-007 | Draft | The system SHALL implement `change_point` as a conservative proof analytical tool. | Given an admissible representative level-shift series, `change_point` returns a deterministic change-point estimate with complete analytical metadata; unsupported inputs return no estimate. |
| FR-008 | Draft | The system SHALL implement smoothed average as a conservative proof analytical tool. | Given an admissible noisy series, the tool returns a deterministic smoothed average output with declared smoothing/window metadata and complete analytical metadata; unsupported inputs return no estimate. |
| FR-009 | Draft | The proof tools SHALL be available on the default MCP surface as agent-callable tools. | Both proof tools appear on the default surface, delegate to the engine, and return serialized analytical envelopes or structured refusals. |
| FR-010 | Draft | Analytical tools SHALL NOT assert causation, diagnosis, treatment advice, medication guidance, dosing guidance, emergency guidance, or population-norm comparison. | Tool outputs and caveats contain no causal, diagnostic, treatment, dosing, emergency, or population-norm claims. |
| FR-011 | Draft | The mission SHALL resolve the analytical evidence-policy question-shape strategy before implementation planning. | The spec or linked research note states whether analytical admissibility reuses existing `QuestionType` values or introduces reviewed analytical question types; no ad-hoc string question types are used. |
| FR-012 | Draft | The system SHALL keep `change_point` separate from the Stage 2 `change` result family. | `change_point` is registered and exposed as a Stage 3 analytical tool, not as a new or extended Stage 2 `change` answer family. |

## Non-Functional Requirements

| ID | Status | Requirement | Measurement |
|---|---|---|---|
| NFR-001 | Draft | Analytical computations SHALL be deterministic. | For identical warehouse evidence, tool name, policy version, and parameters, repeated runs produce byte-equivalent serialized outputs in 100% of test cases. |
| NFR-002 | Draft | Analytical results SHALL always carry validity and confound metadata. | 100% of non-refusal analytical results expose `validity_status`, `is_imputed_pct`, sample size, and closed-vocabulary confound checklist fields. |
| NFR-003 | Draft | Analytical outputs SHALL be inspectable. | 100% of analytical outcomes serialize to JSON-safe payloads that record inputs, parameters, estimate or refusal, uncertainty behavior, and metadata sufficient to rerun the call. |
| NFR-004 | Draft | Refusal states SHALL be testable and distinct. | Tests cover stale input, inadmissible input, insufficient data, and out-of-bounds parameters, and each maps to a distinct machine-readable reason. |
| NFR-005 | Draft | The analytical layer SHALL remain local-first. | Static checks and tests show no network-access modules or PubMed/literature calls are reachable from analytical runtime code. |
| NFR-006 | Draft | User-facing caveats SHALL be concise. | Each plain-English caveat is 280 characters or fewer unless a reviewer explicitly approves a longer caveat in the mission review record. |

## Constraints

| ID | Status | Constraint | Rationale |
|---|---|---|---|
| C-001 | Draft | Analytical MCP wrappers MUST delegate to engine-owned analytical preparation/evaluation and MUST NOT read raw fact tables directly. | The default agent surface must keep the same boundary as existing signal-backed tools. |
| C-002 | Draft | Analytical tools MUST use the operator's own warehouse evidence only. | The mission is local-first n-of-1 analysis, not literature-grounded or population inference. |
| C-003 | Draft | Analytical runtime MUST NOT make network calls. | PubMed and literature grounding are later missions. |
| C-004 | Draft | The mission MUST define a contract for adding analytical tools rather than enumerate the full intended statistical surface. | Premura's doctrine requires guided abstractions agents can extend, not exhaustive lists. |
| C-005 | Draft | The mission MUST NOT add or change a Stage 2 result family. | Stage 2 answer families remain closed unless a dedicated mission approves that contract change. |
| C-006 | Draft | Built-in tools MUST preserve static built-in loading unless this mission explicitly changes the publication contract. | Current engine and MCP conventions avoid filesystem scanning, entry-point loading, and accidental publication. |
| C-007 | Draft | Analytical results MUST surface uncertainty, validity, and confound metadata rather than bare point estimates. | Bare estimates would overstate certainty in confounded n-of-1 data. |
| C-008 | Draft | The proof set MUST remain conservative and narrow: `change_point` plus smoothed average. | The mission proves the contract, not broad statistical coverage. |

## Key Entities

- **Analytical tool**: A deterministic Stage 3 computation over admissible Stage 2
  evidence, such as `change_point` or smoothed average.
- **Analytical tool contract / registry**: The bounded extension point an agent
  fills in to add a tool without adding per-tool dispatcher branches.
- **Analytical input series**: The engine-owned, post-admissibility input shape a
  statistical method receives, including aligned values and validity metadata.
- **Analytical result envelope**: The required output shape carrying estimate or
  refusal, uncertainty behavior, validity, imputation, sample-size, and confound
  metadata.
- **Confound checklist**: A closed-vocabulary set of validity warnings attached to
  an analytical result.
- **Refusal outcome**: A structured result explaining why an analysis cannot
  honestly run, with a distinct machine-readable reason and no estimate.

## Success Criteria

| ID | Criterion | Measurement |
|---|---|---|
| SC-001 | An agent can run `change_point` over admissible operator evidence and receive a deterministic estimate with uncertainty and confound metadata. | Acceptance fixtures show `change_point` returning complete metadata-bearing envelopes for supported inputs and refusals for unsupported inputs. |
| SC-002 | An agent can run smoothed average over admissible operator evidence and receive a deterministic smoothed result with validity metadata. | Acceptance fixtures show smoothed average returning complete metadata-bearing envelopes for supported inputs and refusals for unsupported inputs. |
| SC-003 | Bad evidence cannot silently produce an analytical estimate. | 100% of stale, inadmissible, insufficient, and out-of-bounds cases return a distinct-reason refusal with no estimate. |
| SC-004 | A new analytical tool can be added through the contract without a per-tool dispatch branch. | A public-contract test registers and invokes a trivial analytical tool without adding a dispatcher branch. |
| SC-005 | The LLM narration-honesty half of R7 is retired for the proof tools. | Proof tool outputs include computed estimates, uncertainty behavior, and validity/confound metadata that an agent can narrate directly. |

## Assumptions

- The evidence-admissibility foundation and the existing grounded signals are the
  substrate this layer reads; this mission does not reopen them.
- A preceding analytical-depth research note will justify the conservative
  change-point method, smoothed-average shape, analytical question-type strategy,
  and proposed confound vocabulary.
- The research note may propose confound keys, but this mission owns the
  committed runtime vocabulary and validation tests.
- The current engine and MCP surfaces use static built-in loading and explicit
  wrapper registration. This mission preserves that posture unless it explicitly
  scopes a separate publication-contract change.
- The evidence-policy `QuestionType` vocabulary is closed today; this mission
  must either map analytical admissibility to existing values or explicitly
  extend that vocabulary as part of the reviewed contract before implementation
  planning.

## Dependencies

- Preceding Stage 3 analytical-depth research note for the conservative
  change-point method, smoothed-average method shape, analytical question-type
  strategy, and confound vocabulary proposal.
- `docs/product/DOCTRINE.md` for the agent-first and guide-don't-enumerate rules.
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` and `docs/product/ROADMAP.md` for
  Phase 3 analytical-depth sequencing.
- `docs/architecture/STAGES.md` for the Stage 2 / Stage 3 boundary.
- `src/premura/engine/CONTRACT.md` for Stage 2 result-family and evidence-policy
  constraints.
- `src/premura/engine/policies/` for the evidence-admissibility evaluator.
- `src/premura/mcp/server.py` and `src/premura/mcp/entrypoint.py` for the current
  explicit MCP wrapper pattern.
