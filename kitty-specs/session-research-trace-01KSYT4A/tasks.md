# Tasks: Session Research Trace and Multiplicity Disclosure

**Feature Dir**: `kitty-specs/session-research-trace-01KSYT4A`  
**Branch Strategy**: Current branch at workflow start: `master`. Planning/base branch for this feature: `master`. Completed changes must merge into `master`.  
**Generated**: 2026-05-31T10:54:25Z

## Subtask Index

| ID | Description | Work Package | Parallel |
|---|---|---|---|
| T001 | Add migration `005_trace_audit.sql` with `trace.*` tables and indexes | WP01 |  | [D] |
| T002 | Add migration tests proving `trace.*` exists outside `hp.*` and is idempotent | WP01 |  | [D] |
| T003 | Add schema-ownership tests proving trace writes cannot create health facts | WP01 |  | [D] |
| T004 | Add append-only enforcement tests for trace rows at the storage boundary | WP01 |  | [D] |
| T005 | Document migration assumptions in the WP handoff and keep schema compact | WP01 |  | [D] |
| T006 | Add `premura.trace` public dataclasses/result shapes for sessions, calls, marks, and disclosures | WP02 |  | [D] |
| T007 | Implement explicit session opening with warehouse fingerprint/schema-version capture | WP02 |  | [D] |
| T008 | Implement deterministic request/result hashing and normalized hypothesis identity declarations | WP02 |  | [D] |
| T009 | Implement call/result recording APIs with refusal and error terminal states | WP02 |  | [D] |
| T010 | Implement surfaced-mark APIs with same-session validation | WP02 |  | [D] |
| T011 | Implement disclosure computation and generated JSON/Markdown export shapes | WP02 |  | [D] |
| T012 | Add trace-service tests for deduplication, refusals, surfaced fallback, consistency, and 500-call performance | WP02 |  | [D] |
| T013 | Add MCP trace tools for opening sessions, marking surfaced calls, and reading disclosure | WP03 |  | [D] |
| T014 | Wire analytical wrappers to record calls before/after dispatch when a `session_id` is supplied | WP03 |  | [D] |
| T015 | Preserve existing analytical behavior when no trace session is supplied | WP03 |  | [D] |
| T016 | Return stable recorded-call references without changing engine result envelopes | WP03 |  | [D] |
| T017 | Add MCP tests for trace tools, analytical recording, refusals, retries, and non-analytical exclusions | WP03 |  | [D] |
| T018 | Add engine-purity regression tests proving traced and untraced envelopes are byte-identical | WP03 |  | [D] |
| T019 | Verify operator surface inherits trace behavior without exposing new raw-health semantics | WP03 |  | [D] |
| T020 | Sync live docs for shipped trace surface and deferred audit skill | WP04 | [P] |
| T021 | Update mission contracts/quickstart if implementation names or response fields differ from planning names | WP04 | [P] |
| T022 | Add final validation notes covering requirement coverage and quality gates | WP04 |  |
| T023 | Run and record final validation commands or explicit pre-existing failures | WP04 |  |

## Work Packages

### WP01 – Trace Schema Foundation

**Prompt**: `tasks/WP01-trace-schema-foundation.md`  
**Goal**: Establish the durable `trace.*` warehouse home and prove it stays separate from `hp.*`.  
**Priority**: P0 foundation.  
**Independent Test**: Migration/schema tests pass against a fresh temporary warehouse and prove idempotence plus schema separation.  
**Dependencies**: None.  
**Estimated Prompt Size**: ~330 lines.

Included subtasks:

- [x] T001 Add migration `005_trace_audit.sql` with `trace.*` tables and indexes (WP01)
- [x] T002 Add migration tests proving `trace.*` exists outside `hp.*` and is idempotent (WP01)
- [x] T003 Add schema-ownership tests proving trace writes cannot create health facts (WP01)
- [x] T004 Add append-only enforcement tests for trace rows at the storage boundary (WP01)
- [x] T005 Document migration assumptions in the WP handoff and keep schema compact (WP01)

Implementation sketch:

- Start with tests that initialize a temporary warehouse and assert the new schema/tables exist.
- Add the migration with only the minimum durable tables needed by the data model: session, tool call, result reference, surfaced mark.
- Keep indexes targeted at session disclosure queries and identity deduplication.
- Do not add trigger-heavy machinery unless the tests prove it is needed; append-only can be enforced by public APIs in WP02 plus schema tests here.

Parallel opportunities:

- This WP can run before all other WPs.

Risks:

- If table names use reserved words, implementation may need safe names such as `trace.research_session` instead of `trace.session`; preserve the contract meaning even if names change.
- Do not put provenance rows under `hp.*`.

### WP02 – Trace Service And Disclosure Logic

**Prompt**: `tasks/WP02-trace-service-and-disclosure.md`  
**Goal**: Implement the public trace service that opens sessions, records analytical calls/results, marks surfaced calls, and computes disclosure counts.  
**Priority**: P0 core behavior.  
**Independent Test**: Trace-service tests can create sessions/calls/marks directly and derive correct raw, `N`, `K`, refusal, and unavailable-surfaced outcomes.  
**Dependencies**: WP01.  
**Estimated Prompt Size**: ~470 lines.

Included subtasks:

- [x] T006 Add `premura.trace` public dataclasses/result shapes for sessions, calls, marks, and disclosures (WP02)
- [x] T007 Implement explicit session opening with warehouse fingerprint/schema-version capture (WP02)
- [x] T008 Implement deterministic request/result hashing and normalized hypothesis identity declarations (WP02)
- [x] T009 Implement call/result recording APIs with refusal and error terminal states (WP02)
- [x] T010 Implement surfaced-mark APIs with same-session validation (WP02)
- [x] T011 Implement disclosure computation and generated JSON/Markdown export shapes (WP02)
- [x] T012 Add trace-service tests for deduplication, refusals, surfaced fallback, consistency, and 500-call performance (WP02)

Implementation sketch:

- Keep `premura.trace` independent from MCP so it can be tested directly.
- Make normalized identity deterministic and stable across irrelevant request ordering/default differences.
- Count unique identities for `N`; expose raw call count separately.
- Treat surfaced marks as explicit records. If there are analytical calls but no surfaced marks, return surfaced `unavailable` rather than `0`.
- Bound disclosure reads and avoid returning unbounded row dumps.

Parallel opportunities:

- None until WP01 lands. After WP02, WP03 and WP04 can proceed in sequence/parallel depending on whether implementation names settle.

Risks:

- Avoid storing raw health fact dumps in result summaries.
- Do not infer surfaced status from effect sizes or result text.
- Do not make the trace service import from `premura.engine` in a way that mutates engine behavior.

### WP03 – MCP Boundary Integration

**Prompt**: `tasks/WP03-mcp-boundary-integration.md`  
**Goal**: Expose trace operations through the MCP surface and mechanically record analytical calls around dispatch without changing engine outputs.  
**Priority**: P0 user-facing behavior.  
**Independent Test**: MCP entrypoint tests show trace sessions, analytical recording, exact retry deduplication, surfaced marking, unknown-session handling, and byte-identical traced/untraced analytical envelopes.  
**Dependencies**: WP02.  
**Estimated Prompt Size**: ~500 lines.

Included subtasks:

- [x] T013 Add MCP trace tools for opening sessions, marking surfaced calls, and reading disclosure (WP03)
- [x] T014 Wire analytical wrappers to record calls before/after dispatch when a `session_id` is supplied (WP03)
- [x] T015 Preserve existing analytical behavior when no trace session is supplied (WP03)
- [x] T016 Return stable recorded-call references without changing engine result envelopes (WP03)
- [x] T017 Add MCP tests for trace tools, analytical recording, refusals, retries, and non-analytical exclusions (WP03)
- [x] T018 Add engine-purity regression tests proving traced and untraced envelopes are byte-identical (WP03)
- [x] T019 Verify operator surface inherits trace behavior without exposing new raw-health semantics (WP03)

Implementation sketch:

- Add trace tools to the default shared registration path so the operator surface gets them with the rest of the default tools.
- Extend analytical MCP wrapper signatures carefully, preserving untraced calls.
- Record only analytical tools, not catalog/metadata calls.
- Make the MCP response include stable trace references in a non-invasive way; do not alter the engine envelope itself.
- Cover both default and operator surfaces in tests.

Parallel opportunities:

- None until WP02 lands because MCP wrappers depend on the trace service API.

Risks:

- Tool-count docs/tests may need updates because adding trace tools changes the MCP surface.
- Adding `session_id` must not become required for normal analytical use.
- Wrapper code must avoid raw SQL or statistics work in the MCP layer.

### WP04 – Docs, Contracts, And Final Validation

**Prompt**: `tasks/WP04-docs-contracts-and-validation.md`  
**Goal**: Keep live docs and mission contracts synchronized with the final implemented trace surface, and record validation status.  
**Priority**: P1 release readiness.  
**Independent Test**: A reviewer can read STATUS/STAGES/ROADMAP/FULL_APP plus mission contracts and understand what shipped, what remains deferred, and how to validate it.  
**Dependencies**: WP03.  
**Estimated Prompt Size**: ~300 lines.

Included subtasks:

- [ ] T020 Sync live docs for shipped trace surface and deferred audit skill (WP04)
- [ ] T021 Update mission contracts/quickstart if implementation names or response fields differ from planning names (WP04)
- [ ] T022 Add final validation notes covering requirement coverage and quality gates (WP04)
- [ ] T023 Run and record final validation commands or explicit pre-existing failures (WP04)

Implementation sketch:

- Update the live reference docs only after code behavior is known.
- Preserve the distinction between trace shipped and audit skill deferred.
- Keep wording aligned with project vocabulary: design decision note, user-facing findings, unique hypotheses examined.
- Record validation outcomes in the WP handoff or relevant docs; do not hide pre-existing failures.

Parallel opportunities:

- T020 can begin from planned language, but final doc sync should wait for WP03 implementation details.

Risks:

- The repo has a recurring live-doc-sync drift pattern; this WP exists to prevent repeating it.
- Avoid implying the audit skill, PubMed grounding, `rolling_mean`, or `paired_t_test` shipped.

## Dependency Summary

- WP01 has no dependencies.
- WP02 depends on WP01.
- WP03 depends on WP02.
- WP04 depends on WP03.

## MVP Recommendation

The minimum viable implementation path is WP01 → WP02 → WP03. WP04 is required before release/review completion because FR-016 requires live-doc sync.
