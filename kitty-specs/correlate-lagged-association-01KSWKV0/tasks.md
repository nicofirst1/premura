# Tasks: Correlate Lagged Association

**Input**: `kitty-specs/correlate-lagged-association-01KSWKV0/spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/correlate-contract.md`, `quickstart.md`
**Mission**: `correlate-lagged-association-01KSWKV0`
**Branch contract**: planning/base `master`; final merge target `master`; tasks generated on `master`.

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Add failing contract tests for lagged-association vocabulary and `common_cause_plausible`. | WP01 | No | [D] |
| T002 | Extend the closed analytical question and confound vocabularies for correlate. | WP01 | No | [D] |
| T003 | Add evidence-policy question mapping and default sufficiency/freshness declarations for lagged association. | WP01 | No | [D] |
| T004 | Add contract validation tests for paired input shape metadata and forbidden confound keys. | WP01 | No | [D] |
| T005 | Verify no runtime network or PubMed dependency is introduced by the contract changes. | WP01 | No | [D] |
| T006 | Add failing paired-preparation tests for same-day pairing after caller-declared lag. | WP02 | No |
| T007 | Define paired hypothesis/input data shapes and validation in the analytical input layer. | WP02 | No |
| T008 | Implement paired input preparation over two usable series with narrowed overlap metadata. | WP02 | No |
| T009 | Implement paired-preparation refusal behavior for invalid lag, missing hypothesis, inadmissible input, no overlap, and weak paired support. | WP02 | No |
| T010 | Add imputed-pair percentage and paired-source provenance to the paired input output. | WP02 | No |
| T011 | Add failing engine tool tests for available correlate output and core refusal classes. | WP03 | No |
| T012 | Implement deterministic Spearman rho and rank handling for paired observations. | WP03 | No |
| T013 | Implement effective sample size and association-band calculation with deterministic truncation. | WP03 | No |
| T014 | Implement correlate result envelope, direction alignment, confounds, caveats, and refusal outcomes. | WP03 | No |
| T015 | Register `correlate` as a built-in analytical tool and export the public engine surface. | WP03 | No |
| T016 | Add forbidden-output tests for p-values, significance, causal language, diagnosis, and lag scanning. | WP03 | No |
| T017 | Add failing default-surface tests for the agent-facing `correlate` wrapper. | WP04 | No |
| T018 | Implement the thin MCP wrapper that delegates all behavior to the engine analytical path. | WP04 | No |
| T019 | Validate wrapper serialization for available and refused outcomes. | WP04 | No |
| T020 | Verify the MCP layer performs no statistical computation, no raw fact-table analysis, and no network/PubMed work. | WP04 | No |
| T021 | Update engine and analytical contributor docs for lag, association, paired inputs, and confound rules. | WP05 | No |
| T022 | Update product/status roadmap docs to show `correlate` shipped and ledger/PubMed still deferred. | WP05 | No |
| T023 | Add the ADR-0008 back-pointer that `common_cause_plausible` was resolved by the research note. | WP05 | No |
| T024 | Run changed-scope documentation and quality-gate checks, recording any pre-existing unrelated failures. | WP05 | No |

## Work Packages

### WP01: Contract And Policy Vocabulary

**Prompt**: `tasks/WP01-contract-and-policy-vocabulary.md`
**Priority**: High
**Goal**: Make lagged association and common-cause risk first-class reviewed vocabulary before any paired computation exists.
**Independent test**: Policy/contract tests fail first, then pass with the new closed vocabulary and no runtime network dependency.
**Dependencies**: None.
**Estimated prompt size**: ~430 lines.

Included subtasks:

- [x] T001 Add failing contract tests for lagged-association vocabulary and `common_cause_plausible`. (WP01)
- [x] T002 Extend the closed analytical question and confound vocabularies for correlate. (WP01)
- [x] T003 Add evidence-policy question mapping and default sufficiency/freshness declarations for lagged association. (WP01)
- [x] T004 Add contract validation tests for paired input shape metadata and forbidden confound keys. (WP01)
- [x] T005 Verify no runtime network or PubMed dependency is introduced by the contract changes. (WP01)

Implementation sketch:

1. Start with tests that describe the closed vocabulary expected by the spec.
2. Add only the reviewed vocabulary needed by `correlate`: lagged association and `common_cause_plausible`.
3. Wire the new question type through existing evidence-policy defaults without inventing a new policy mini-language.
4. Keep the analytical dispatch/registration pattern branch-free.
5. Confirm imports stay local/offline and no PubMed/network modules are reachable.

Parallel opportunities: None. This WP is the foundation for all others.

Risks:

- Accidentally widening the policy layer into behavior instead of parameters.
- Reusing a single-series question type and hiding correlation-specific sufficiency.
- Adding vocabulary strings without closed-enum validation.

### WP02: Paired Input Preparation

**Prompt**: `tasks/WP02-paired-input-preparation.md`
**Priority**: High
**Goal**: Create the two-series preparation seam that aligns by declared lag, narrows overlap metadata, and refuses before computation.
**Independent test**: Input-preparation tests prove same-day post-lag pairing, overlap narrowing, imputation metadata, and no-estimate refusals.
**Dependencies**: WP01.
**Estimated prompt size**: ~470 lines.

Included subtasks:

- [ ] T006 Add failing paired-preparation tests for same-day pairing after caller-declared lag. (WP02)
- [ ] T007 Define paired hypothesis/input data shapes and validation in the analytical input layer. (WP02)
- [ ] T008 Implement paired input preparation over two usable series with narrowed overlap metadata. (WP02)
- [ ] T009 Implement paired-preparation refusal behavior for invalid lag, missing hypothesis, inadmissible input, no overlap, and weak paired support. (WP02)
- [ ] T010 Add imputed-pair percentage and paired-source provenance to the paired input output. (WP02)

Implementation sketch:

1. Add tests that fail against the current single-series-only preparation seam.
2. Introduce paired shapes in the input layer, not in the statistical method.
3. Pair on same local calendar day after applying one integer lag.
4. Refuse early for malformed hypotheses or unusable inputs.
5. Preserve the existing single-series `AnalyticalInputSeries` contract.

Parallel opportunities: Can begin after WP01. It is independent of MCP and docs work but blocks the engine method.

Risks:

- Treating lag like a tolerance window.
- Letting refused single-series inputs reach paired computation.
- Mutating the single-series shape instead of adding a bounded paired seam.

### WP03: Correlate Engine Method

**Prompt**: `tasks/WP03-correlate-engine-method.md`
**Priority**: High
**Goal**: Implement the deterministic `correlate` tool over paired inputs, including Spearman rho, effective sample size, association band, confounds, and all no-estimate refusals.
**Independent test**: Engine analytical tool tests cover available output plus mandatory refusal and forbidden-output cases.
**Dependencies**: WP01, WP02.
**Estimated prompt size**: ~560 lines.

Included subtasks:

- [ ] T011 Add failing engine tool tests for available correlate output and core refusal classes. (WP03)
- [ ] T012 Implement deterministic Spearman rho and rank handling for paired observations. (WP03)
- [ ] T013 Implement effective sample size and association-band calculation with deterministic truncation. (WP03)
- [ ] T014 Implement correlate result envelope, direction alignment, confounds, caveats, and refusal outcomes. (WP03)
- [ ] T015 Register `correlate` as a built-in analytical tool and export the public engine surface. (WP03)
- [ ] T016 Add forbidden-output tests for p-values, significance, causal language, diagnosis, and lag scanning. (WP03)

Implementation sketch:

1. Write acceptance-style engine tests that assert serialized observable outcomes.
2. Implement rank correlation with deterministic tie handling.
3. Compute effective support using the mission's fixed truncation and imputation rules.
4. Build the result through the existing analytical envelope conventions.
5. Register the tool and ensure public engine imports expose it consistently.

Parallel opportunities: None. This is the core computation and should be sequential after WP02.

Risks:

- Accidentally returning a p-value, confidence/significance language, or a causal phrase.
- Overfitting the method to one fixture rather than implementing the declared rule.
- Failing to make constant/rank-deficient series a refusal.

### WP04: Default Agent-Facing Surface

**Prompt**: `tasks/WP04-default-agent-facing-surface.md`
**Priority**: Medium
**Goal**: Publish `correlate` on the default MCP surface as a thin wrapper over the engine-owned analytical path.
**Independent test**: Agent-facing tests show available and refused serialized envelopes with no statistical work in the wrapper.
**Dependencies**: WP03.
**Estimated prompt size**: ~360 lines.

Included subtasks:

- [ ] T017 Add failing default-surface tests for the agent-facing `correlate` wrapper. (WP04)
- [ ] T018 Implement the thin MCP wrapper that delegates all behavior to the engine analytical path. (WP04)
- [ ] T019 Validate wrapper serialization for available and refused outcomes. (WP04)
- [ ] T020 Verify the MCP layer performs no statistical computation, no raw fact-table analysis, and no network/PubMed work. (WP04)

Implementation sketch:

1. Follow the current proof-tool MCP wrapper pattern.
2. Keep warehouse reads/preparation aligned with existing analytical wrapper conventions.
3. Delegate computation and refusals to the engine.
4. Assert serialized outputs preserve the analytical envelope without adding MCP-only interpretation.

Parallel opportunities: Can proceed after WP03. Docs in WP05 can start after this or in parallel if implementation decisions are settled.

Risks:

- Moving statistical behavior into the MCP layer.
- Making the wrapper a raw fact-table analysis path.
- Adding runtime literature or network behavior.

### WP05: Documentation And Review Gates

**Prompt**: `tasks/WP05-documentation-and-review-gates.md`
**Priority**: Medium
**Goal**: Synchronize docs and run changed-scope quality checks so agents can review `correlate` without re-deciding the method.
**Independent test**: Documentation states the shipped behavior and deferred work; quality-gate commands are run or any pre-existing unrelated failures are named.
**Dependencies**: WP04.
**Estimated prompt size**: ~330 lines.

Included subtasks:

- [ ] T021 Update engine and analytical contributor docs for lag, association, paired inputs, and confound rules. (WP05)
- [ ] T022 Update product/status roadmap docs to show `correlate` shipped and ledger/PubMed still deferred. (WP05)
- [ ] T023 Add the ADR-0008 back-pointer that `common_cause_plausible` was resolved by the research note. (WP05)
- [ ] T024 Run changed-scope documentation and quality-gate checks, recording any pre-existing unrelated failures. (WP05)

Implementation sketch:

1. Update only docs whose source-of-truth status changes after the tool lands.
2. Preserve the distinction between per-call `correlate` honesty and the later session ledger.
3. Keep docs at doctrine altitude: rules and extension seams, not metric-pair catalogs.
4. Run changed-scope checks and record failures honestly in the WP handoff.

Parallel opportunities: Some prose drafting can happen once WP03 behavior is stable, but final status updates should wait for WP04.

Risks:

- Claiming ledger, PubMed grounding, Kendall, or broader significance testing shipped.
- Reintroducing causal vocabulary in docs.
- Hiding unrelated pre-existing ruff/mypy failures.

## Dependency Graph

- WP01 has no dependencies.
- WP02 depends on WP01.
- WP03 depends on WP01 and WP02.
- WP04 depends on WP03.
- WP05 depends on WP04.

## Parallelization Summary

The critical path is WP01 -> WP02 -> WP03 -> WP04 -> WP05 because the contract,
paired seam, engine method, and publication layer build on one another. Within
each WP, tests should be written before production changes and can often be
reviewed independently from implementation. Broad parallel implementation is not
recommended until the paired seam and engine method are stable.

## MVP Recommendation

The MVP is WP01 through WP03: a closed-vocabulary, engine-only `correlate` tool
that can compute/refuse honestly through public engine tests. WP04 and WP05 make
it default-surface usable and review-ready.
