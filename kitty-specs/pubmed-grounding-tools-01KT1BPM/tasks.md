# Tasks: PubMed Grounding Tools

**Input**: `kitty-specs/pubmed-grounding-tools-01KT1BPM/spec.md`, `plan.md`, `research.md`, `data-model.md`, `contracts/pubmed-grounding-contract.md`, `quickstart.md`
**Mission**: `pubmed-grounding-tools-01KT1BPM`
**Branch contract**: planning/base `master`; final merge target `master`

## Work Package Overview

| WP | Title | Priority | Dependencies | Subtasks | Prompt |
| --- | --- | --- | --- | ---: | --- |
| WP01 | Research Gate And Contract Finalization | High | None | 3 | `tasks/WP01-research-gate-and-contract-finalization.md` |
| WP02 | PubMed Core Provider Contract | High | WP01 | 4 | `tasks/WP02-pubmed-core-provider-contract.md` |
| WP03 | Default MCP Surface Integration | High | WP02 | 4 | `tasks/WP03-default-mcp-surface-integration.md` |
| WP04 | Shipped-State Documentation Sync | Medium | WP03 | 3 | `tasks/WP04-shipped-state-documentation-sync.md` |

## Subtask Index

| ID | Description | WP | Parallel |
| --- | --- | --- | --- |
| T001 | Broaden the prior-art survey beyond the three seed PubMed MCP servers and record the evaluated candidate set. | WP01 |  |
| T002 | Make the adopt-vs-wrap-vs-build decision explicit with rationale and rejected alternatives. | WP01 |  |
| T003 | Finalize the mission-local contract/data-model/quickstart if the research decision changes provider assumptions. | WP01 |  |
| T004 | Add acceptance-first tests for PubMed candidate, fetched, no-results, invalid, and provider-error outcomes. | WP02 |  |
| T005 | Create the Premura-owned PubMed provider/data contract in Stage 3 MCP code. | WP02 |  |
| T006 | Implement the chosen provider path behind an injectable adapter seam. | WP02 |  |
| T007 | Ensure serialization preserves missingness, provenance, bounded result size, and citation status. | WP02 |  |
| T008 | Add MCP server wrapper functions for PubMed search and fetch. | WP03 |  |
| T009 | Register PubMed tools on the default MCP surface with citation-safe descriptions. | WP03 |  |
| T010 | Update default/operator MCP tool catalog tests and counts. | WP03 |  |
| T011 | Add integration tests that default surface exposure remains narrow and excludes broad third-party tools. | WP03 |  |
| T012 | Update live status/roadmap/stage docs to reflect shipped PubMed grounding. | WP04 | [P] |
| T013 | Document the deferred scope: personal-data bridge, concept mapping, full-text, deep analysis, and broader literature expansion. | WP04 | [P] |
| T014 | Run changed-scope validation and record any known pre-existing failures or deferrals in the docs/review notes. | WP04 |  |

## WP01: Research Gate And Contract Finalization

**Goal**: Complete the prior-art gate before code chooses a provider path.
**Priority**: High
**Independent test**: A reviewer can read `research.md` and see which PubMed MCP servers/options were evaluated, why direct adoption/wrapping/native build was chosen, and how the chosen path satisfies Premura's citation and stage-boundary contract.
**Dependencies**: None
**Estimated prompt size**: ~330 lines

### Included Subtasks

- [ ] T001 Broaden the prior-art survey beyond the three seed PubMed MCP servers and record the evaluated candidate set. (WP01)
- [ ] T002 Make the adopt-vs-wrap-vs-build decision explicit with rationale and rejected alternatives. (WP01)
- [ ] T003 Finalize the mission-local contract/data-model/quickstart if the research decision changes provider assumptions. (WP01)

### Implementation Sketch

1. Re-read `research.md`, `plan.md`, and `contracts/pubmed-grounding-contract.md`.
2. Search for additional PubMed MCP servers or integration libraries using low-noise methods available in the implementation environment.
3. Compare all candidates against Premura's contract rather than feature richness.
4. Record the final provider decision in `research.md`.
5. If the final decision changes accepted response/status vocabulary, update only the mission-local contract/data model/quickstart.

### Parallel Opportunities

This WP should run first. Later implementation WPs depend on its final decision.

### Dependencies And Risks

- Blocks WP02 because provider choice affects core adapter shape.
- Risk: choosing the most feature-rich external server rather than the smallest contract-preserving path.
- Risk: evaluating only the three seed links and missing a simpler maintained option.

## WP02: PubMed Core Provider Contract

**Goal**: Build the Stage 3 core PubMed grounding contract behind a provider seam, with tests before production behavior.
**Priority**: High
**Independent test**: `tests/test_mcp_pubmed.py` proves search candidates are not citeable, fetched records are citeable, ordinary PubMed failures are structured, and no live network is needed for the default test loop.
**Dependencies**: WP01
**Estimated prompt size**: ~460 lines

### Included Subtasks

- [ ] T004 Add acceptance-first tests for PubMed candidate, fetched, no-results, invalid, and provider-error outcomes. (WP02)
- [ ] T005 Create the Premura-owned PubMed provider/data contract in Stage 3 MCP code. (WP02)
- [ ] T006 Implement the chosen provider path behind an injectable adapter seam. (WP02)
- [ ] T007 Ensure serialization preserves missingness, provenance, bounded result size, and citation status. (WP02)

### Implementation Sketch

1. Start with failing public tests for `pubmed_search` and `pubmed_fetch` behavior at the Stage 3 helper boundary.
2. Add a small `src/premura/mcp/pubmed.py` module with provider protocol/dataclasses or equivalent typed records.
3. Implement the WP01 provider choice behind an injectable seam so tests can use deterministic fixtures.
4. Preserve missing fields explicitly and never fabricate article metadata.
5. Keep this WP below the MCP tool-registration layer; WP03 owns default-surface registration.

### Parallel Opportunities

None before WP01. After WP02 lands, WP03 and WP04 can proceed in sequence with clear code/doc boundaries.

### Dependencies And Risks

- Depends on WP01 provider decision.
- Risk: accidentally introducing live network into the default test suite.
- Risk: adding broad PubMed features from a third-party server instead of the narrow search/fetch contract.
- Risk: adding a dependency without recording why it is justified for this first slice.

## WP03: Default MCP Surface Integration

**Goal**: Expose the narrow PubMed grounding tools on Premura's default MCP surface and keep the operator/default surface contract exact.
**Priority**: High
**Independent test**: MCP tool catalog tests show `pubmed_search` and `pubmed_fetch` on the default surface, operator surface remains default plus `query_warehouse`, and broad out-of-scope PubMed tools are absent.
**Dependencies**: WP02
**Estimated prompt size**: ~430 lines

### Included Subtasks

- [ ] T008 Add MCP server wrapper functions for PubMed search and fetch. (WP03)
- [ ] T009 Register PubMed tools on the default MCP surface with citation-safe descriptions. (WP03)
- [ ] T010 Update default/operator MCP tool catalog tests and counts. (WP03)
- [ ] T011 Add integration tests that default surface exposure remains narrow and excludes broad third-party tools. (WP03)

### Implementation Sketch

1. Add wrapper functions in `src/premura/mcp/server.py` that delegate to WP02's PubMed core module.
2. Register exactly two tools in `src/premura/mcp/entrypoint.py`: search and fetch.
3. Tool docstrings must state the candidate-vs-fetched citation rule.
4. Update `_DEFAULT_TOOLS` and `_OPERATOR_TOOLS` tests in `tests/test_mcp_server.py`.
5. Add assertions that out-of-scope broad tools are not present on the default surface.

### Parallel Opportunities

WP03 depends on WP02. It should not run in parallel with WP02 because it consumes the core helper names and response shapes.

### Dependencies And Risks

- Depends on WP02's helper API.
- Risk: tool registration exposes a third-party server's full tool list rather than Premura's narrow two-tool surface.
- Risk: operator/default tool count drift if tests are not updated exactly.

## WP04: Shipped-State Documentation Sync

**Goal**: Bring live docs into alignment with the shipped PubMed grounding behavior and preserve deferred boundaries.
**Priority**: Medium
**Independent test**: A reviewer can read the live docs and tell that PubMed search/fetch shipped, citation requires fetched PMIDs, and the personal-data bridge/concept mapping/full-text/deep-analysis work remains deferred.
**Dependencies**: WP03
**Estimated prompt size**: ~340 lines

### Included Subtasks

- [ ] T012 Update live status/roadmap/stage docs to reflect shipped PubMed grounding. (WP04)
- [ ] T013 Document the deferred scope: personal-data bridge, concept mapping, full-text, deep analysis, and broader literature expansion. (WP04)
- [ ] T014 Run changed-scope validation and record any known pre-existing failures or deferrals in the docs/review notes. (WP04)

### Implementation Sketch

1. Update `docs/operations/STATUS.md`, `docs/product/ROADMAP.md`, `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`, and `docs/architecture/STAGES.md` only after WP03 confirms shipped tool names and counts.
2. Keep language plain and agent-first: PubMed is a Stage 3 grounding tool, not a diagnosis engine or data bridge.
3. State deferred scope explicitly so future agents do not infer that full-text, concept mapping, or literature-to-warehouse querying shipped.
4. Run changed-scope docs/tests validation and record any relevant evidence in the WP handoff.

### Parallel Opportunities

T012 and T013 can be drafted in parallel after WP03 is approved, but final wording must reconcile with actual tool names/counts.

### Dependencies And Risks

- Depends on WP03 because docs must name actual shipped tools and counts.
- Risk: docs overstate PubMed grounding as a personal-data bridge.
- Risk: docs imply full-text/deep-analysis support shipped when it did not.
