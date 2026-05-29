# Tasks: Stage 3 Analytical Tools

**Feature Dir**: `kitty-specs/stage-3-analytical-tools-01KST48C/`  
**Planning Branch**: `master`  
**Merge Target**: `master`  
**Branch Strategy**: Current branch at workflow start: `master`. Planning/base branch for this feature: `master`. Completed changes must merge into `master`.

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Write the durable Stage 3 analytical-depth research note | WP01 |  | [D] |
| T002 | Capture method decisions for `change_point` and smoothed average | WP01 |  | [D] |
| T003 | Capture analytical `QuestionType` and confound vocabulary decisions | WP01 |  | [D] |
| T004 | Cross-check research note against doctrine, roadmap, and plan | WP01 |  | [D] |
| T005 | Add analytical registry and tool descriptor contract | WP02 |  | [D] |
| T006 | Add analytical result/refusal/confound model types | WP02 |  | [D] |
| T007 | Add contract validation for unknown confound keys and malformed results | WP02 |  | [D] |
| T008 | Add contract tests through the new analytical contract module | WP02 |  | [D] |
| T009 | Add admissible input-series model and overlap metadata handling | WP03 |  | [D] |
| T010 | Add input-preparation refusal behavior before computation | WP03 |  | [D] |
| T011 | Add analytical question-type policy wiring for prepared inputs | WP03 |  | [D] |
| T012 | Add input-preparation tests with fixture-backed evidence | WP03 |  | [D] |
| T013 | Implement conservative `change_point` computation | WP04 |  | [D] |
| T014 | Implement smoothed-average computation | WP04 |  | [D] |
| T015 | Add proof-tool tests for supported and refused inputs | WP04 |  | [D] |
| T016 | Verify proof tools do not claim causation, prediction, or significance | WP04 |  | [D] |
| T017 | Add engine public analytical dispatch/load surface | WP05 |  | [D] |
| T018 | Re-export stable analytical symbols from `premura.engine` | WP05 |  | [D] |
| T019 | Add public-surface tests for registration, dispatch, determinism, and serialization | WP05 |  | [D] |
| T020 | Preserve static built-in loading and no dispatch ladder behavior | WP05 |  | [D] |
| T021 | Add MCP server wrappers for `change_point` and `smoothed_average` | WP06 |  | [D] |
| T022 | Register analytical tools on the default MCP surface | WP06 |  | [D] |
| T023 | Add MCP analytical-tool tests for success and refusal payloads | WP06 |  | [D] |
| T024 | Run final quality gates and document any unrelated pre-existing failures | WP06 |  | [D] |

## Work Packages

### WP01: Analytical Research Note

**Prompt**: `tasks/WP01-analytical-research-note.md`  
**Priority**: High  
**Dependencies**: None  
**Goal**: Create the durable research note that justifies the method and vocabulary decisions implementation will follow.  
**Independent Test**: A reviewer can read the research note and verify it resolves the four planning questions without reading implementation code.  
**Estimated Prompt Size**: ~260 lines

Included subtasks:

- [x] T001 Write the durable Stage 3 analytical-depth research note (WP01)
- [x] T002 Capture method decisions for `change_point` and smoothed average (WP01)
- [x] T003 Capture analytical `QuestionType` and confound vocabulary decisions (WP01)
- [x] T004 Cross-check research note against doctrine, roadmap, and plan (WP01)

Implementation sketch:

- Create a project-history research note under `docs/history/research/`.
- Base the decisions on `plan.md`, `research.md`, and the product doctrine.
- Keep the note plain-English, agent-facing, and explicit about what is a runtime contract versus rationale.

Parallel opportunities:

- None. This WP gates the code work.

Risks:

- If this note leaves choices open, later WPs will implement incompatible contract shapes.

### WP02: Analytical Contract Model

**Prompt**: `tasks/WP02-analytical-contract-model.md`  
**Priority**: High  
**Dependencies**: WP01  
**Goal**: Add the typed analytical contract, registry, result envelope, refusal, and confound validation model.  
**Independent Test**: Contract tests can register a trivial tool, serialize valid results, reject malformed results, and reject unknown confound keys.  
**Estimated Prompt Size**: ~430 lines

Included subtasks:

- [x] T005 Add analytical registry and tool descriptor contract (WP02)
- [x] T006 Add analytical result/refusal/confound model types (WP02)
- [x] T007 Add contract validation for unknown confound keys and malformed results (WP02)
- [x] T008 Add contract tests through the new analytical contract module (WP02)

Implementation sketch:

- Introduce the analytical contract in a dedicated engine module.
- Keep it independent from MCP and warehouse access.
- Drive implementation from tests that assert observable contract behavior.

Parallel opportunities:

- After WP01, WP02 can proceed independently of MCP work, but WP03-WP06 depend on it.

Risks:

- Over-broad registries or arbitrary vocabularies would violate the doctrine and make future agent-authored tools unreviewable.

### WP03: Admissible Input Preparation

**Prompt**: `tasks/WP03-admissible-input-preparation.md`  
**Priority**: High  
**Dependencies**: WP02  
**Goal**: Add the engine-owned input-series preparation path that gates analytical computation with evidence admissibility and overlap metadata.  
**Independent Test**: Fixture-backed tests prove stale, insufficient, inadmissible, and out-of-bounds inputs refuse before statistical computation.  
**Estimated Prompt Size**: ~440 lines

Included subtasks:

- [x] T009 Add admissible input-series model and overlap metadata handling (WP03)
- [x] T010 Add input-preparation refusal behavior before computation (WP03)
- [x] T011 Add analytical question-type policy wiring for prepared inputs (WP03)
- [x] T012 Add input-preparation tests with fixture-backed evidence (WP03)

Implementation sketch:

- Build prepared input shapes separately from proof methods.
- Wire the reviewed analytical question types to the evidence-admissibility evaluator.
- Refuse before computation whenever evidence or parameters are unsupported.

Parallel opportunities:

- None before WP02. Once WP03 is complete, WP04 and WP05 can proceed in sequence.

Risks:

- Letting proof tools query data directly would bypass the safety layer this mission exists to prove.

### WP04: Proof Analytical Tools

**Prompt**: `tasks/WP04-proof-analytical-tools.md`  
**Priority**: High  
**Dependencies**: WP03  
**Goal**: Implement `change_point` and smoothed average behind the analytical contract.  
**Independent Test**: Proof-tool tests show deterministic success envelopes for representative inputs and structured refusals for unsupported inputs.  
**Estimated Prompt Size**: ~500 lines

Included subtasks:

- [x] T013 Implement conservative `change_point` computation (WP04)
- [x] T014 Implement smoothed-average computation (WP04)
- [x] T015 Add proof-tool tests for supported and refused inputs (WP04)
- [x] T016 Verify proof tools do not claim causation, prediction, or significance (WP04)

Implementation sketch:

- Implement the methods chosen in the research note.
- Return analytical envelopes through the contract model.
- Keep uncertainty honest: state when a method has no natural confidence interval.

Parallel opportunities:

- `change_point` and smoothed-average tests can be developed in parallel within this WP, but one agent owns the files.

Risks:

- Method output that looks like significance or causation would violate the charter.

### WP05: Public Engine Analytical Surface

**Prompt**: `tasks/WP05-public-engine-analytical-surface.md`  
**Priority**: Medium  
**Dependencies**: WP04  
**Goal**: Expose analytical tools through a stable public engine surface while preserving static built-in loading and no dispatch ladder behavior.  
**Independent Test**: Public-surface tests can list/invoke built-in analytical tools and prove repeated runs serialize identically.  
**Estimated Prompt Size**: ~390 lines

Included subtasks:

- [x] T017 Add engine public analytical dispatch/load surface (WP05)
- [x] T018 Re-export stable analytical symbols from `premura.engine` (WP05)
- [x] T019 Add public-surface tests for registration, dispatch, determinism, and serialization (WP05)
- [x] T020 Preserve static built-in loading and no dispatch ladder behavior (WP05)

Implementation sketch:

- Add public engine helpers only after contract and proof methods exist.
- Re-export stable symbols intentionally; do not expose private helper internals.
- Keep built-in loading static and explicit.

Parallel opportunities:

- None before WP04. This WP enables WP06.

Risks:

- Public exports can accidentally freeze too much internal surface. Keep exports minimal and contract-owned.

### WP06: MCP Analytical Exposure

**Prompt**: `tasks/WP06-mcp-analytical-exposure.md`  
**Priority**: Medium  
**Dependencies**: WP05  
**Goal**: Publish the two proof tools on the default MCP surface through thin wrappers and complete validation gates.  
**Independent Test**: MCP tests prove the default surface exposes `change_point` and `smoothed_average`, delegates to the engine, and returns serialized success/refusal payloads.  
**Estimated Prompt Size**: ~470 lines

Included subtasks:

- [x] T021 Add MCP server wrappers for `change_point` and `smoothed_average` (WP06)
- [x] T022 Register analytical tools on the default MCP surface (WP06)
- [x] T023 Add MCP analytical-tool tests for success and refusal payloads (WP06)
- [x] T024 Run final quality gates and document any unrelated pre-existing failures (WP06)

Implementation sketch:

- Keep MCP wrappers thin: validate caller-facing parameters, call engine, serialize outcome.
- Do not add raw SQL or statistical logic to MCP code.
- Run full quality gates at the end of the mission.

Parallel opportunities:

- None before WP05. This is the final integration WP.

Risks:

- Accidentally exposing lower-guarantee raw SQL behavior on the default surface would violate the Stage 3 boundary.

## Dependency Summary

- WP01 has no dependencies.
- WP02 depends on WP01.
- WP03 depends on WP02.
- WP04 depends on WP03.
- WP05 depends on WP04.
- WP06 depends on WP05.

## Parallelization Highlights

The mission is intentionally mostly sequential because each layer depends on a stable contract from the prior layer. Parallelism is safest inside WPs after the owning agent has the worktree, not across WPs that share conceptual contracts.

## MVP Scope Recommendation

The MVP is WP01 through WP04: research note, analytical contract, admissible input preparation, and proof methods. WP05 and WP06 are required for full Stage 3 default-surface delivery.
