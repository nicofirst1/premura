# Tasks: Finish Analytical Tool Set

**Mission**: `finish-analytical-tool-set-01KT0Y95`  
**Mission ID**: `01KT0Y95X8XKZCQH3G1Y8QVPDJ`  
**Planning/base branch**: `master`  
**Final merge target**: `master`

## Overview

This task breakdown completes Premura's first bounded analytical tool set by
adding `rolling_mean` and the simple anchor-date version of `paired_t_test`.
The implementation is deliberately split by reviewable seams: vocabulary/policy,
rolling mean, before/after pairing, paired comparison, publication/trace, and
docs/validation. Tests are included because the charter requires test-first work
for new behavior touching health data and analytical claims.

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Add reviewed analytical question vocabulary for moving-window and paired-comparison shapes | WP01 |  | [D] |
| T002 | Add evidence-admissibility policy defaults for the new analytical question shapes | WP01 |  | [D] |
| T003 | Add contract tests for vocabulary closure and forbidden ad hoc labels | WP01 |  | [D] |
| T004 | Add policy tests proving the new question shapes are admissibility-gated independently | WP01 |  | [D] |
| T005 | Document the contract/policy decisions in code comments without widening scope | WP01 |  | [D] |
| T006 | Add failing rolling-mean acceptance tests for available envelopes | WP02 | [P] |
| T007 | Add failing rolling-mean refusal tests for invalid windows, weak coverage, and refused input | WP02 | [P] |
| T008 | Implement the deterministic `rolling_mean` tool registration and estimate payload | WP02 | [P] |
| T009 | Add rolling-mean caveats/confounds and forbidden-language assertions | WP02 | [P] |
| T010 | Keep rolling-mean runtime local, deterministic, and independent of MCP/trace | WP02 | [P] |
| T011 | Add failing before/after paired-input tests for anchor-date pairing | WP03 | [P] |
| T012 | Add failing before/after paired-input refusal tests for malformed requests and weak pairs | WP03 | [P] |
| T013 | Implement simple before/after request, pair, and paired-input shapes | WP03 | [P] |
| T014 | Implement deterministic anchor-date pairing semantics with visible imputation metadata | WP03 | [P] |
| T015 | Guard against condition-label pairing, arbitrary pair maps, and anchor/window scanning | WP03 | [P] |
| T016 | Add failing paired-t-test acceptance tests for available paired-difference envelopes | WP04 |  |
| T017 | Add failing paired-t-test refusal tests for weak, malformed, and constant-difference inputs | WP04 |  |
| T018 | Implement the deterministic `paired_t_test` tool registration and estimate payload | WP04 |  |
| T019 | Add paired-t-test uncertainty, direction, caveat, and confound metadata | WP04 |  |
| T020 | Add no-causation, no-diagnosis, and no-hidden-search assertions for paired_t_test | WP04 |  |
| T021 | Publish both tools through the analytical built-in loader and public engine surface | WP05 |  |
| T022 | Add thin default MCP wrappers for `rolling_mean` and simple `paired_t_test` | WP05 |  |
| T023 | Add trace normalized hypothesis identities for both new tools | WP05 |  |
| T024 | Add MCP and trace tests for publication, recording, exact retries, refusals, and surfaced marks | WP05 |  |
| T025 | Verify traced and untraced engine envelopes remain byte-equivalent aside from trace metadata | WP05 |  |
| T026 | Sync live roadmap/status/stage docs to name the completed analytical tool set | WP06 | [P] |
| T027 | Update the Stage 2/3 contributor contract with the new bounded tool shapes | WP06 | [P] |
| T028 | Add documentation checks for deferred PubMed and condition-pairing scope | WP06 | [P] |
| T029 | Run focused validation commands and record any pre-existing unrelated failures | WP06 |  |
| T030 | Prepare final mission handoff notes for review and downstream task execution | WP06 |  |

## Work Packages

### WP01: Contract And Policy Vocabulary

**Prompt**: `tasks/WP01-contract-and-policy-vocabulary.md`  
**Priority**: High  
**Dependencies**: None  
**Estimated prompt size**: ~330 lines

**Summary**: Establish the closed analytical question vocabulary and evidence
policy rules the two new tools need. This WP does not implement either tool; it
only makes their question shapes reviewable and admissibility-gated.

**Independent test**: policy/contract tests fail before the vocabulary and policy
defaults exist, then pass without importing MCP, trace, or runtime network code.

**Included subtasks**:

- [x] T001 Add reviewed analytical question vocabulary for moving-window and paired-comparison shapes (WP01)
- [x] T002 Add evidence-admissibility policy defaults for the new analytical question shapes (WP01)
- [x] T003 Add contract tests for vocabulary closure and forbidden ad hoc labels (WP01)
- [x] T004 Add policy tests proving the new question shapes are admissibility-gated independently (WP01)
- [x] T005 Document the contract/policy decisions in code comments without widening scope (WP01)

**Implementation sketch**: Add the smallest closed-vocabulary extension that lets
`rolling_mean` and anchor-date `paired_t_test` be gated independently. Prefer
reusing `SMOOTHED_PATTERN` for `rolling_mean` only if tests prove the question
shape is honestly identical; otherwise add a narrow moving-window type. Add a
paired-comparison question type for `paired_t_test`.

**Parallel opportunities**: After WP01 lands, WP02 and WP03 can proceed in
parallel because they own separate files and use the vocabulary/policy seam.

**Risks**: Over-broad question types would make later tools unreviewable. Avoid a
generic `comparison` type unless it is narrowed by rules strong enough for the
paired before/after shape.

### WP02: Rolling Mean Engine Tool

**Prompt**: `tasks/WP02-rolling-mean-engine-tool.md`  
**Priority**: High  
**Dependencies**: WP01  
**Estimated prompt size**: ~360 lines

**Summary**: Implement `rolling_mean` as a deterministic engine-owned analytical
tool over one admitted ordered series. The tool emits moving-window summary
points with visible coverage and missingness.

**Independent test**: synthetic engine-level fixtures can import/register the
tool directly and verify available/refused envelopes without default MCP surface
publication.

**Included subtasks**:

- [ ] T006 Add failing rolling-mean acceptance tests for available envelopes (WP02)
- [ ] T007 Add failing rolling-mean refusal tests for invalid windows, weak coverage, and refused input (WP02)
- [ ] T008 Implement the deterministic `rolling_mean` tool registration and estimate payload (WP02)
- [ ] T009 Add rolling-mean caveats/confounds and forbidden-language assertions (WP02)
- [ ] T010 Keep rolling-mean runtime local, deterministic, and independent of MCP/trace (WP02)

**Implementation sketch**: Create a focused built-in tool module for rolling mean,
with tests proving descriptor registration, available envelope shape, refusal
classes, caveats, deterministic serialization, and no network/PubMed imports.
Do not edit MCP or trace surfaces in this WP.

**Parallel opportunities**: Can run in parallel with WP03 after WP01 because it
touches a distinct tool module and test file.

**Risks**: Do not silently duplicate `smoothed_average` and call it done. This WP
must expose the moving-window series shape from the contract.

### WP03: Simple Before/After Pairing Input

**Prompt**: `tasks/WP03-simple-before-after-pairing-input.md`  
**Priority**: High  
**Dependencies**: WP01  
**Estimated prompt size**: ~360 lines

**Summary**: Add the engine-owned preparation shape for simple before/after
pairing around a declared anchor date. This is only input preparation; it does
not compute the paired comparison estimate.

**Independent test**: synthetic prepared series fixtures produce deterministic
before/after pairs or structured refusals, and condition-label pairing is refused
as out of scope.

**Included subtasks**:

- [ ] T011 Add failing before/after paired-input tests for anchor-date pairing (WP03)
- [ ] T012 Add failing before/after paired-input refusal tests for malformed requests and weak pairs (WP03)
- [ ] T013 Implement simple before/after request, pair, and paired-input shapes (WP03)
- [ ] T014 Implement deterministic anchor-date pairing semantics with visible imputation metadata (WP03)
- [ ] T015 Guard against condition-label pairing, arbitrary pair maps, and anchor/window scanning (WP03)

**Implementation sketch**: Build a narrow helper module for anchor-date pairing
that consumes admitted ordered series and produces immutable paired input or a
refusal. Keep the pair construction rule fixed and documented. Do not implement
`paired_t_test` math in this WP.

**Parallel opportunities**: Can run in parallel with WP02 after WP01. WP04 waits
for this WP.

**Risks**: Pairing can easily become an arbitrary matching system. Keep it to one
anchor date plus before/after windows and refuse every broader shape.

### WP04: Paired T-Test Engine Tool

**Prompt**: `tasks/WP04-paired-t-test-engine-tool.md`  
**Priority**: High  
**Dependencies**: WP03  
**Estimated prompt size**: ~360 lines

**Summary**: Implement `paired_t_test` as a deterministic engine-owned analytical
tool over the simple before/after paired input from WP03. It reports paired
difference, uncertainty, direction metadata, caveats, or refusal.

**Independent test**: synthetic paired-input fixtures verify available and
refused envelopes without MCP or trace integration.

**Included subtasks**:

- [ ] T016 Add failing paired-t-test acceptance tests for available paired-difference envelopes (WP04)
- [ ] T017 Add failing paired-t-test refusal tests for weak, malformed, and constant-difference inputs (WP04)
- [ ] T018 Implement the deterministic `paired_t_test` tool registration and estimate payload (WP04)
- [ ] T019 Add paired-t-test uncertainty, direction, caveat, and confound metadata (WP04)
- [ ] T020 Add no-causation, no-diagnosis, and no-hidden-search assertions for paired_t_test (WP04)

**Implementation sketch**: Add a focused paired-test tool module that consumes
only the WP03 paired input shape. Treat output as paired-difference analysis and
do not introduce population diagnosis, cause claims, or condition-label pairing.

**Parallel opportunities**: None until WP03 exists. After WP04 lands, WP05 and
WP06 can proceed.

**Risks**: Conventional t-test language can smuggle significance claims. Keep the
payload and caveats aligned with Premura's descriptive honesty boundary.

### WP05: Default Surface And Trace Integration

**Prompt**: `tasks/WP05-default-surface-and-trace-integration.md`  
**Priority**: High  
**Dependencies**: WP02, WP04  
**Estimated prompt size**: ~420 lines

**Summary**: Publish both tools through the default analytical surface and session
research trace accounting. This WP wires discovery, MCP wrappers, and normalized
hypothesis identities, but does not change tool math.

**Independent test**: public engine discovery, MCP wrappers, and trace disclosure
tests show both new tools are callable, recorded, deduplicated, and surfaced.

**Included subtasks**:

- [ ] T021 Publish both tools through the analytical built-in loader and public engine surface (WP05)
- [ ] T022 Add thin default MCP wrappers for `rolling_mean` and simple `paired_t_test` (WP05)
- [ ] T023 Add trace normalized hypothesis identities for both new tools (WP05)
- [ ] T024 Add MCP and trace tests for publication, recording, exact retries, refusals, and surfaced marks (WP05)
- [ ] T025 Verify traced and untraced engine envelopes remain byte-equivalent aside from trace metadata (WP05)

**Implementation sketch**: Update the static built-in analytical publication
list, public exports, MCP entrypoint/server wrappers, and trace identity registry.
Wrappers must validate only caller-facing shape, delegate preparation/dispatch to
the engine, and serialize returned envelopes.

**Parallel opportunities**: Must wait for WP02 and WP04 because it publishes both
tools. Can run in parallel with WP06 after those dependencies land.

**Risks**: This WP touches the public surface. Do not compute statistics in MCP,
do not write trace state in the engine, and do not broaden operator/raw SQL
surfaces.

### WP06: Documentation And Validation Sync

**Prompt**: `tasks/WP06-documentation-and-validation-sync.md`  
**Priority**: Medium  
**Dependencies**: WP05  
**Estimated prompt size**: ~330 lines

**Summary**: Synchronize live docs and contributor guidance after the tools are
published, then run and record the focused validation gates. This WP closes the
mission's planning-to-status loop.

**Independent test**: docs accurately say the analytical set is complete, PubMed
grounding remains deferred, and broader condition-pairing remains out of scope.

**Included subtasks**:

- [ ] T026 Sync live roadmap/status/stage docs to name the completed analytical tool set (WP06)
- [ ] T027 Update the Stage 2/3 contributor contract with the new bounded tool shapes (WP06)
- [ ] T028 Add documentation checks for deferred PubMed and condition-pairing scope (WP06)
- [ ] T029 Run focused validation commands and record any pre-existing unrelated failures (WP06)
- [ ] T030 Prepare final mission handoff notes for review and downstream task execution (WP06)

**Implementation sketch**: Update only docs and contributor-contract text needed
to keep live references aligned with shipped behavior. Run the focused validation
commands from quickstart and document results in the WP handoff.

**Parallel opportunities**: Can run after WP05 and may overlap with review of
code WPs if docs are rebased on final public names.

**Risks**: Avoid turning docs into a new design document. The implementation
contracts already exist; live docs should summarize and point to them.

## Dependency Summary

- WP01 has no dependencies.
- WP02 depends on WP01.
- WP03 depends on WP01.
- WP04 depends on WP03.
- WP05 depends on WP02 and WP04.
- WP06 depends on WP05.

## Parallelization Summary

- After WP01, WP02 and WP03 can run in parallel.
- After WP03, WP04 can begin while WP02 finishes if lanes permit.
- WP05 is the integration gate and should wait for both tool implementations.
- WP06 should wait for WP05 so docs reflect final public names and surfaces.

## MVP Recommendation

The smallest useful implementation slice is WP01 + WP02: it proves a new
roadmap-named analytical tool can be added through the bounded contract without
MCP publication. The mission is not complete until all six WPs land.
