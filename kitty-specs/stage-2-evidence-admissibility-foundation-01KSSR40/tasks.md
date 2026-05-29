# Tasks: Stage 2 Evidence Admissibility Foundation

**Input**: `kitty-specs/stage-2-evidence-admissibility-foundation-01KSSR40/spec.md`, `plan.md`, `data-model.md`, `research.md`, `contracts/evidence-policy-contract.md`, `quickstart.md`
**Branch contract**: Planning/base branch `master`; completed changes merge into `master`.

## Work Package Overview

| WP | Title | Priority | Dependencies | Prompt |
|---|---|---|---|---|
| WP01 | Policy Declaration Contract | High | None | `tasks/WP01-policy-declaration-contract.md` |
| WP02 | Deterministic Evidence Evaluator | High | WP01 | `tasks/WP02-deterministic-evidence-evaluator.md` |
| WP03 | Built-In Policy Registry | High | WP01, WP02 | `tasks/WP03-built-in-policy-registry.md` |
| WP04 | Public Surface And Contributor Contract | Medium | WP01, WP02, WP03 | `tasks/WP04-public-surface-and-contributor-contract.md` |
| WP05 | Resting HR Proof Integration | Medium | WP01, WP02, WP03, WP04 | `tasks/WP05-resting-hr-proof-integration.md` |

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Define closed policy enums for question type, outcome, rejection reason, freshness mode, temporal meaning, and policy shape. | WP01 | No | [D] |
| T002 | Add frozen dataclasses for freshness, sufficiency, question rules, examples, policy declarations, evidence candidates, outcomes, and evaluation results. | WP01 | No | [D] |
| T003 | Implement lightweight declaration validation that fails early for missing fields, invalid combinations, and non-parameter-like content. | WP01 | No | [D] |
| T004 | Expose the internal policy model through `premura.engine.policies` without touching the top-level engine surface yet. | WP01 | No | [D] |
| T005 | Add model-level tests for valid declarations, invalid declarations, caveat requirements, and result validation. | WP01 | No | [D] |
| T006 | Implement the deterministic evaluator entrypoint over question type, candidates, and metric-family policy declarations. | WP02 | No | [D] |
| T007 | Implement freshness, provenance, and question-type admissibility decisions with distinct rejection reasons. | WP02 | No | [D] |
| T008 | Implement sufficiency checks and no-admissible-evidence refusal aggregation. | WP02 | No | [D] |
| T009 | Add evaluator tests for stale, sparse, missing timestamp, wrong question type, and separated admissible/rejected evidence. | WP02 | No | [D] |
| T010 | Add tests proving evaluator output is deterministic for identical inputs. | WP02 | No | [D] |
| T011 | Add a lightweight policy registry for built-in family declarations with duplicate detection. | WP03 | No |
| T012 | Add representative built-in policy declarations covering at least 10 metric families through shared policy shapes. | WP03 | No |
| T013 | Add standing caveats, rationale text, and source notes to built-in declarations without claiming clinical authority. | WP03 | No |
| T014 | Add built-in registry tests for family coverage, policy shape reuse, duplicate rejection, and no exhaustive matrix drift. | WP03 | No |
| T015 | Add default-policy smoke tests that run representative candidates through the evaluator. | WP03 | No |
| T016 | Export the policy authoring/evaluation surface from `premura.engine` after the model, evaluator, and defaults exist. | WP04 | No |
| T017 | Update the Stage 2 engine contributor contract to explain the policy declaration pattern and PubMed review boundary. | WP04 | No |
| T018 | Add public-surface tests that import only through `premura.engine` and verify no runtime network/PubMed dependency is introduced. | WP04 | No |
| T019 | Add reviewer guidance for future agents adding or changing policy declarations. | WP04 | No |
| T020 | Add a failing proof-integration test for `resting_hr_status` showing stale current-status evidence is evaluated through the new policy layer. | WP05 | No |
| T021 | Wire `resting_hr_status` through the evidence evaluator while preserving its existing `StatusResult` output shape. | WP05 | No |
| T022 | Preserve existing resting-HR caveats and add policy-derived rejection context without adding diagnosis or population claims. | WP05 | No |
| T023 | Add regression checks proving trend signals and BMI behavior are not broadly refactored by this proof integration. | WP05 | No |

## WP01: Policy Declaration Contract

**Goal**: Establish the frozen dataclass/enumeration contract that future Stage 2 policy declarations must use.
**Priority**: High
**Independent test**: `uv run pytest tests/test_engine_policy_model.py -q`
**Dependencies**: None
**Prompt**: `tasks/WP01-policy-declaration-contract.md`
**Estimated prompt size**: ~204 lines

### Included Subtasks

- [x] T001 Define closed policy enums for question type, outcome, rejection reason, freshness mode, temporal meaning, and policy shape. (WP01)
- [x] T002 Add frozen dataclasses for freshness, sufficiency, question rules, examples, policy declarations, evidence candidates, outcomes, and evaluation results. (WP01)
- [x] T003 Implement lightweight declaration validation that fails early for missing fields, invalid combinations, and non-parameter-like content. (WP01)
- [x] T004 Expose the internal policy model through `premura.engine.policies` without touching the top-level engine surface yet. (WP01)
- [x] T005 Add model-level tests for valid declarations, invalid declarations, caveat requirements, and result validation. (WP01)

### Implementation Sketch

Create `src/premura/engine/policies/_model.py` and `src/premura/engine/policies/__init__.py`. Keep this WP focused on data shapes and validation only. Do not implement evaluator branching or built-in policy declarations here.

### Parallel Opportunities

None. This WP is the foundation for all later WPs.

### Risks

- Over-designing the model into a policy engine.
- Letting declarations accept arbitrary callables or expression strings.
- Forgetting that adding question types changes the Stage 2 authoring contract.

## WP02: Deterministic Evidence Evaluator

**Goal**: Evaluate candidates against declarations and return separated admissible, rejected, insufficient, and refusal outcomes.
**Priority**: High
**Independent test**: `uv run pytest tests/test_engine_policy_evaluator.py -q`
**Dependencies**: WP01
**Prompt**: `tasks/WP02-deterministic-evidence-evaluator.md`
**Estimated prompt size**: ~208 lines

### Included Subtasks

- [x] T006 Implement the deterministic evaluator entrypoint over question type, candidates, and metric-family policy declarations. (WP02)
- [x] T007 Implement freshness, provenance, and question-type admissibility decisions with distinct rejection reasons. (WP02)
- [x] T008 Implement sufficiency checks and no-admissible-evidence refusal aggregation. (WP02)
- [x] T009 Add evaluator tests for stale, sparse, missing timestamp, wrong question type, and separated admissible/rejected evidence. (WP02)
- [x] T010 Add tests proving evaluator output is deterministic for identical inputs. (WP02)

### Implementation Sketch

Create `src/premura/engine/policies/_evaluator.py`. Use only the model from WP01. The evaluator owns branching; declarations supply parameters only.

### Parallel Opportunities

None until WP01 lands. After WP02 lands, WP03 can proceed independently of WP04.

### Risks

- Collapsing rejection reasons into a generic quality score.
- Returning prose-only outcomes that downstream agents must parse.
- Using the current clock implicitly instead of accepting explicit reference times where needed.

## WP03: Built-In Policy Registry

**Goal**: Provide representative built-in family policies and registry helpers without exhaustive per-metric sprawl.
**Priority**: High
**Independent test**: `uv run pytest tests/test_engine_policy_defaults.py -q`
**Dependencies**: WP01, WP02
**Prompt**: `tasks/WP03-built-in-policy-registry.md`
**Estimated prompt size**: ~202 lines

### Included Subtasks

- [ ] T011 Add a lightweight policy registry for built-in family declarations with duplicate detection. (WP03)
- [ ] T012 Add representative built-in policy declarations covering at least 10 metric families through shared policy shapes. (WP03)
- [ ] T013 Add standing caveats, rationale text, and source notes to built-in declarations without claiming clinical authority. (WP03)
- [ ] T014 Add built-in registry tests for family coverage, policy shape reuse, duplicate rejection, and no exhaustive matrix drift. (WP03)
- [ ] T015 Add default-policy smoke tests that run representative candidates through the evaluator. (WP03)

### Implementation Sketch

Create `src/premura/engine/policies/_registry.py` and `_defaults.py`. Built-ins should cover at least 10 families by assigning them to a smaller number of reusable shapes.

### Parallel Opportunities

None until WP01 and WP02 land.

### Risks

- Accidentally creating a large bespoke clinical rule table.
- Treating source notes as runtime authority.
- Failing NFR-005 by under-covering metric families.

## WP04: Public Surface And Contributor Contract

**Goal**: Make the policy surface discoverable through public imports and document the contributor contract for future agents.
**Priority**: Medium
**Independent test**: `uv run pytest tests/test_engine_policy_public_surface.py -q`
**Dependencies**: WP01, WP02, WP03
**Prompt**: `tasks/WP04-public-surface-and-contributor-contract.md`
**Estimated prompt size**: ~202 lines

### Included Subtasks

- [ ] T016 Export the policy authoring/evaluation surface from `premura.engine` after the model, evaluator, and defaults exist. (WP04)
- [ ] T017 Update the Stage 2 engine contributor contract to explain the policy declaration pattern and PubMed review boundary. (WP04)
- [ ] T018 Add public-surface tests that import only through `premura.engine` and verify no runtime network/PubMed dependency is introduced. (WP04)
- [ ] T019 Add reviewer guidance for future agents adding or changing policy declarations. (WP04)

### Implementation Sketch

Update `src/premura/engine/__init__.py` and `src/premura/engine/CONTRACT.md`. Add a focused test file for public imports and documented constraints. Do not modify existing signal behavior in this WP.

### Parallel Opportunities

None until WP01-WP03 land.

### Risks

- Exporting private helpers that should remain implementation details.
- Reintroducing PubMed as a runtime dependency by wording or import choices.
- Making the contract too prose-only to guide agents.

## WP05: Resting HR Proof Integration

**Goal**: Prove one existing Stage 2 status signal can use the new evaluator without a broad refactor.
**Priority**: Medium
**Independent test**: `uv run pytest tests/test_engine_descriptive_policy_integration.py -q`
**Dependencies**: WP01, WP02, WP03, WP04
**Prompt**: `tasks/WP05-resting-hr-proof-integration.md`
**Estimated prompt size**: ~200 lines

### Included Subtasks

- [ ] T020 Add a failing proof-integration test for `resting_hr_status` showing stale current-status evidence is evaluated through the new policy layer. (WP05)
- [ ] T021 Wire `resting_hr_status` through the evidence evaluator while preserving its existing `StatusResult` output shape. (WP05)
- [ ] T022 Preserve existing resting-HR caveats and add policy-derived rejection context without adding diagnosis or population claims. (WP05)
- [ ] T023 Add regression checks proving trend signals and BMI behavior are not broadly refactored by this proof integration. (WP05)

### Implementation Sketch

Modify only `src/premura/engine/descriptive_signals.py` and add a new focused proof-integration test. The goal is to demonstrate the handoff, not to migrate every signal.

### Parallel Opportunities

None. This WP depends on the public policy surface.

### Risks

- Accidentally changing `TrendResult` or BMI behavior.
- Changing the `StatusResult` shape expected by MCP wrappers.
- Turning a proof integration into a broad refactor.

## Dependency Summary

- WP01 has no dependencies.
- WP02 depends on WP01.
- WP03 depends on WP01 and WP02.
- WP04 depends on WP01, WP02, and WP03.
- WP05 depends on WP01, WP02, WP03, and WP04.

## MVP Recommendation

The minimum viable implementation is WP01 plus WP02: a validated declaration model and deterministic evaluator. WP03 is needed to satisfy full spec coverage. WP04 and WP05 make the foundation usable by future agents and prove it against one existing signal.

## Validation Plan

Run focused tests per WP first, then the changed-scope quality gates:

```bash
uv run pytest tests/test_engine_policy_model.py tests/test_engine_policy_evaluator.py tests/test_engine_policy_defaults.py tests/test_engine_policy_public_surface.py tests/test_engine_descriptive_policy_integration.py -q
uv run ruff check src/premura/engine tests
uv run ruff format --check src/premura/engine tests
uv run mypy src
```
