# Work Packages: Close the Stage 3 Direct-Read Exception

**Mission**: `close-stage-3-direct-read-exception-01KSJVFG`  
**Feature Dir**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/close-stage-3-direct-read-exception-01KSJVFG`  
**Branch Contract**: Current branch at workflow start: `master`. Planning/base branch for this feature: `master`. Completed changes must merge into `master`.  
**Generated**: `2026-05-27T07:06:15Z`

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Add typed Stage 2 result envelopes for metric catalog and metric summary | WP01 | No | [D] |
| T002 | Implement engine helper for validity-gated metric catalog entries | WP01 | No | [D] |
| T003 | Implement engine helper for per-metric validity summaries over a fixed 30-day window | WP01 | No | [D] |
| T004 | Add engine tests for current/stale/unavailable catalog and summary semantics | WP01 | No | [D] |
| T005 | Extend lazy-load contract coverage for the new engine helpers | WP01 | No | [D] |
| T006 | Rewire `list_metrics` in `src/premura/mcp/server.py` to consume Stage 2 catalog helpers | WP02 | No | [D] |
| T007 | Rewire `metric_summary` in `src/premura/mcp/server.py` to consume Stage 2 summary helpers | WP02 | No | [D] |
| T008 | Serialize machine-branchable validity/imputation fields with honest absence semantics | WP02 | No | [D] |
| T009 | Add MCP payload tests for fresh/stale/empty/unknown catalog and summary responses | WP02 | No | [D] |
| T010 | Re-run and tighten signal-tool regression coverage so six existing signal-backed tools do not regress | WP02 | No | [D] |
| T011 | Refactor MCP registration into shared core plus explicit default/operator entrypoint builders | WP03 | No | [D] |
| T012 | Add a separate operator entrypoint that registers `query_warehouse` on top of the default tool set | WP03 | No | [D] |
| T013 | Wire packaging / command entrypoints so the operator surface is invokable explicitly | WP03 | No | [D] |
| T014 | Add tool-list tests confirming default vs operator surfaces differ only by `query_warehouse` | WP03 | No | [D] |
| T015 | Encode lower-guarantee operator mode language in entrypoint or tool descriptions without implying validity guarantees | WP03 | No | [D] |
| T016 | Remove the Stage 2 -> Stage 3 exception language from boundary documentation and restate the clean contract | WP04 | No |
| T017 | Add a new ADR documenting the separate operator entrypoint decision and lower-guarantee mode | WP04 | No |
| T018 | Update top-level product/ops docs to show the default agent-facing path and the operator fallback path | WP04 | No |
| T019 | Align `src/premura/mcp/__init__.py` package documentation with the cleaned boundary | WP04 | No |
| T020 | Update `tests/test_skeleton.py` and any doc-facing assertions to match the new architectural truth | WP04 | No |

## Work Package 1 - Stage 2 Catalog and Summary Primitives

**Prompt**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/close-stage-3-direct-read-exception-01KSJVFG/tasks/WP01-stage2-catalog-and-summary-primitives.md`  
**Priority**: High  
**Dependencies**: None  
**Independent test**: Engine helpers can compute validity-gated catalog and summary envelopes for fresh, stale, empty, and unknown metrics without changing MCP yet.  
**Estimated prompt size**: ~360 lines

### Included subtasks

- [x] T001 Add typed Stage 2 result envelopes for metric catalog and metric summary (WP01)
- [x] T002 Implement engine helper for validity-gated metric catalog entries (WP01)
- [x] T003 Implement engine helper for per-metric validity summaries over a fixed 30-day window (WP01)
- [x] T004 Add engine tests for current/stale/unavailable catalog and summary semantics (WP01)
- [x] T005 Extend lazy-load contract coverage for the new engine helpers (WP01)

### Implementation sketch

1. Extend `src/premura/engine/_results.py` with dedicated catalog/summary envelopes that reuse the current `FreshnessState` vocabulary.
2. Add Stage 2 helper functions behind the public engine surface in `src/premura/engine/__init__.py` (or a tightly scoped supporting module it owns).
3. Use existing query/window helpers; do not invent a second freshness model.
4. Calculate `sample_size`, `imputed_proportion`, and `gap_count` over the fixed 30-day recent window agreed in planning.
5. Add engine-level tests, then tighten lazy-load tests so importing `premura.engine` still does not eagerly load signal modules.

### Parallel opportunities

- None inside this WP; the engine contract should land as one coherent foundation.

### Risks

- Accidentally introducing eager built-in loading while wiring new helpers.
- Returning ad-hoc dicts instead of typed envelopes, which would weaken the engine contract.
- Leaking all-time aggregates back into the new summary shape.

## Work Package 2 - Re-back Default MCP Catalog and Summary Tools

**Prompt**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/close-stage-3-direct-read-exception-01KSJVFG/tasks/WP02-reback-default-mcp-catalog-and-summary.md`  
**Priority**: High  
**Dependencies**: WP01  
**Independent test**: The default server surface still exposes catalog and summary tools, but they now return validity/imputation envelopes and never raw row counts or all-time extrema.  
**Estimated prompt size**: ~380 lines

### Included subtasks

- [x] T006 Rewire `list_metrics` in `src/premura/mcp/server.py` to consume Stage 2 catalog helpers (WP02)
- [x] T007 Rewire `metric_summary` in `src/premura/mcp/server.py` to consume Stage 2 summary helpers (WP02)
- [x] T008 Serialize machine-branchable validity/imputation fields with honest absence semantics (WP02)
- [x] T009 Add MCP payload tests for fresh/stale/empty/unknown catalog and summary responses (WP02)
- [x] T010 Re-run and tighten signal-tool regression coverage so six existing signal-backed tools do not regress (WP02)

### Implementation sketch

1. Leave `query_warehouse` alone in this WP; focus only on the default catalog/summary behavior.
2. Replace direct SQL result shaping in `src/premura/mcp/server.py` with calls into the new engine helpers from WP01.
3. Ensure the serialized MCP payloads expose explicit fields for validity/imputation rather than forcing downstream parsing of prose.
4. Keep outputs non-diagnostic and preserve the existing six signal-backed tools unchanged.
5. Add tests that exercise the public MCP tool functions rather than importing internal helper logic.

### Parallel opportunities

- Can run in parallel with WP03 after WP01 lands, because WP02 owns `src/premura/mcp/server.py` while WP03 owns entrypoint registration.

### Risks

- Regressing `_serialize_signal_result()` behavior or the six already-shipped signal tools.
- Incomplete "honest absence" handling for unknown or empty metrics.
- Payload drift that leaves downstream callers unable to branch on discrete fields.

## Work Package 3 - Separate Operator Entrypoint and Raw SQL Escape Hatch

**Prompt**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/close-stage-3-direct-read-exception-01KSJVFG/tasks/WP03-separate-operator-entrypoint-and-raw-sql.md`  
**Priority**: High  
**Dependencies**: WP01  
**Independent test**: `premura-mcp` omits `query_warehouse`, while the explicit operator entrypoint exposes exactly one additional raw-SQL tool on top of the default surface.  
**Estimated prompt size**: ~340 lines

### Included subtasks

- [x] T011 Refactor MCP registration into shared core plus explicit default/operator entrypoint builders (WP03)
- [x] T012 Add a separate operator entrypoint that registers `query_warehouse` on top of the default tool set (WP03)
- [x] T013 Wire packaging / command entrypoints so the operator surface is invokable explicitly (WP03)
- [x] T014 Add tool-list tests confirming default vs operator surfaces differ only by `query_warehouse` (WP03)
- [x] T015 Encode lower-guarantee operator mode language in entrypoint or tool descriptions without implying validity guarantees (WP03)

### Implementation sketch

1. Split entrypoint registration in `src/premura/mcp/entrypoint.py` into shared builder helpers.
2. Keep one shared server core; do not fork Stage 2 or warehouse access logic.
3. Add a second explicit operator command/entrypoint for the raw SQL escape hatch.
4. Ensure the default agent-facing surface remains the clean doctrinal default.
5. Add registration tests around public tool listings and command wiring.

### Parallel opportunities

- Can run in parallel with WP02 after WP01 lands because file ownership is non-overlapping.

### Risks

- Accidentally exposing `query_warehouse` on the default surface.
- Introducing a second behavior fork that is larger than intended for this mission.
- Failing to communicate the lower-guarantee nature of operator mode clearly enough in the exposed surface.

## Work Package 4 - Boundary Docs, ADR, and Public Surface Cleanup

**Prompt**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/close-stage-3-direct-read-exception-01KSJVFG/tasks/WP04-boundary-docs-adr-and-surface-cleanup.md`  
**Priority**: Medium  
**Dependencies**: WP02, WP03  
**Independent test**: The architecture and public package docs no longer describe a temporary exception, and the new ADR records the separate operator entrypoint / explicit-approval rule.  
**Estimated prompt size**: ~320 lines

### Included subtasks

- [ ] T016 Remove the Stage 2 -> Stage 3 exception language from boundary documentation and restate the clean contract (WP04)
- [ ] T017 Add a new ADR documenting the separate operator entrypoint decision and lower-guarantee mode (WP04)
- [ ] T018 Update top-level product/ops docs to show the default agent-facing path and the operator fallback path (WP04)
- [ ] T019 Align `src/premura/mcp/__init__.py` package documentation with the cleaned boundary (WP04)
- [ ] T020 Update `tests/test_skeleton.py` and any doc-facing assertions to match the new architectural truth (WP04)

### Implementation sketch

1. Update `docs/architecture/STAGES.md` first so the boundary contract reads clean.
2. Add an ADR that records why raw SQL remains available only behind an explicit operator entrypoint and why agent use requires explicit user approval.
3. Update the most user-visible docs (`README.md`, `docs/operations/STATUS.md`) only where needed to keep the public story honest.
4. Align package docstrings and skeleton tests with the new reality.

### Parallel opportunities

- None recommended; this WP should follow the settled implementation shape from WP02 and WP03.

### Risks

- Docs drifting from the actual entrypoint names or final tool registration shape.
- Leaving one stale “known exception” reference behind.
- Under-documenting the lower-guarantee operator mode and explicit user approval requirement.

## MVP Recommendation

Start with **WP01**. It creates the Stage 2 contract that both the default MCP rewiring and the operator-entrypoint split depend on.
