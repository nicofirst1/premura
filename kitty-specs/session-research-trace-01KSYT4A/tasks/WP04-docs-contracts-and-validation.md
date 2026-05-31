---
work_package_id: WP04
title: Docs Contracts And Validation
dependencies:
- WP03
requirement_refs:
- FR-013
- FR-014
- FR-016
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T020
- T021
- T022
- T023
agent: "claude:opus:docs-reviewer:reviewer"
shell_pid: "37548"
history:
- timestamp: '2026-05-31T10:54:25Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/
execution_mode: code_change
owned_files:
- docs/operations/STATUS.md
- docs/architecture/STAGES.md
- docs/product/ROADMAP.md
- docs/product/FULL_APP_DEVELOPMENT_PLAN.md
- kitty-specs/session-research-trace-01KSYT4A/contracts/mcp-trace-tools.md
- kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md
- kitty-specs/session-research-trace-01KSYT4A/quickstart.md
tags: []
---

# Work Package Prompt: WP04 – Docs, Contracts, And Validation

## Implement Command

```bash
spec-kitty agent action implement WP04 --agent <name> --mission session-research-trace-01KSYT4A
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Synchronize live reference docs and mission contracts with the implemented trace surface. This WP exists because recent analytical missions drifted by updating STATUS while leaving STAGES or counts stale. Do not skip live-doc sync.

## Dependencies

Depends on WP03 because final tool names, response fields, and tool counts must be known before docs are authoritative.

## Authoritative Inputs

- Implemented behavior from WP01-WP03.
- `docs/adr/0009-session-research-trace-and-multiplicity-disclosure.md`.
- `kitty-specs/session-research-trace-01KSYT4A/spec.md`.
- `kitty-specs/session-research-trace-01KSYT4A/contracts/`.

## Owned Files

- `docs/operations/STATUS.md`
- `docs/architecture/STAGES.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `kitty-specs/session-research-trace-01KSYT4A/contracts/mcp-trace-tools.md`
- `kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md`
- `kitty-specs/session-research-trace-01KSYT4A/quickstart.md`

Do not edit source code or tests in this WP.

## Subtasks

### T020: Sync live docs for shipped trace surface and deferred audit skill

Update live docs to reflect the final behavior:

- `docs/operations/STATUS.md`: add the shipped trace surface, measured disclosure, explicit session lifecycle, and audit skill deferred status. Update MCP tool counts if trace tools changed the default/operator surface counts.
- `docs/architecture/STAGES.md`: update Stage 3 MCP boundary description so it includes trace provenance at the MCP boundary, not in the engine.
- `docs/product/ROADMAP.md`: mark reproducible trace/multiplicity disclosure as shipped once implementation is done; keep PubMed, `rolling_mean`, `paired_t_test`, and audit skill deferred if still true.
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`: sync Phase 3 current state and exit criteria language.

Use project vocabulary: design decision note, user-facing findings, unique hypotheses examined, explicit refusal, local-first.

### T021: Update mission contracts/quickstart if implementation names or response fields differ from planning names

Compare implementation against:

- `kitty-specs/session-research-trace-01KSYT4A/contracts/mcp-trace-tools.md`.
- `kitty-specs/session-research-trace-01KSYT4A/contracts/audit-consumer-contract.md`.
- `kitty-specs/session-research-trace-01KSYT4A/quickstart.md`.

If tool names or response fields changed during implementation, update these planning artifacts so they describe reality. Preserve the semantics from the spec; do not weaken them to hide missing behavior.

### T022: Add final validation notes covering requirement coverage and quality gates

Record validation coverage in the WP handoff or appropriate doc section:

- Which tests cover raw count vs `N`.
- Which tests cover surfaced unavailable fallback.
- Which tests prove engine purity.
- Which tests prove `trace.*`/`hp.*` separation.
- Which tests cover MCP default/operator surfaces.

Do not create a new process doc unless necessary; concise handoff notes are enough.

### T023: Run and record final validation commands or explicit pre-existing failures

Run the relevant quality gates from the quickstart where feasible:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/premura
uv run pytest -q
```

If any failure is pre-existing or unrelated, call it out explicitly. Do not silently skip a gate. If a gate is too slow or unavailable in the environment, explain that in the handoff.

## Live Doc Sync Checklist

Use this checklist while editing docs:

- `STATUS.md` should say what is true today after the mission, including exact MCP surface counts if trace tools changed them.
- `STAGES.md` should describe the trace as MCP-boundary provenance and should not imply the engine became stateful.
- `ROADMAP.md` should move reproducible trace/multiplicity disclosure out of the deferred bucket only if WP03 actually shipped it.
- `FULL_APP_DEVELOPMENT_PLAN.md` should keep Phase 3 coherent: trace shipped, audit skill deferred, PubMed and remaining deterministic tools still separate unless other missions changed them.
- Mission contracts should match implementation names and fields.
- Quickstart should be runnable in spirit by an implementer/reviewer, even if MCP test harness details differ.

## Required Wording Rules

Use these terms consistently:

- `research trace` or `session research trace` for the ledger.
- `user-facing findings` for surfaced results.
- `unique hypotheses examined` for `N`.
- `raw analytical calls` for the separate raw count.
- `surfaced unavailable` when no marks exist.
- `audit skill deferred` for the follow-on interpretation work.

Avoid these claims:

- Do not say `significant results`.
- Do not say Premura computes multiplicity-corrected statistics.
- Do not say the audit skill shipped.
- Do not imply trace data is health facts.
- Do not imply Markdown is the canonical record.

## Known Drift Risks

This repo recently had stale spots where one live doc updated and another did not. Explicitly check:

- STAGES §3 tool enumeration and future-work wording.
- STATUS MCP surface counts and test/metric counts if touched by implementation.
- ROADMAP Phase 3 deferred/open list.
- FULL_APP current-starting-point language, not only the Phase 3 block.

If code adds three trace tools to both default and operator surfaces, docs and tests should reflect the new counts. If implementation uses fewer or differently named tools, docs should reflect the actual surface, not the planning examples.

## Validation Notes Format

At handoff, include a concise validation block. Example:

```text
Validation:
- uv run ruff check .: passed
- uv run ruff format --check .: passed
- uv run mypy src/premura: passed
- uv run pytest -q: passed
```

If something fails:

```text
Validation:
- uv run pytest -q: failed in unrelated pre-existing test X; trace-specific tests passed with ...
```

Do not hide failures. The charter allows calling out pre-existing failures; it does not allow silent skips.

## Acceptance Coverage

This WP contributes to:

- FR-013 by keeping the audit-consumer contract synchronized.
- FR-014 by keeping generated export semantics clear.
- FR-016 by updating live reference docs.

It also protects review quality by making sure the shipped state can be understood without spelunking through code.

## Test Strategy

This WP is documentation/validation focused. It should not add new tests unless documentation reveals a missing acceptance check that belongs to the code WPs. Prefer reporting that gap to the responsible WP rather than editing code here.

## Definition Of Done

- Live docs describe the shipped trace surface accurately.
- Docs clearly state the audit skill is still deferred.
- Mission contracts and quickstart match implemented tool names/fields.
- Final validation commands are run or explicitly accounted for.
- No code changes are included.

## Reviewer Guidance

Reviewers should compare docs against actual code behavior. The main failure mode is stale or overclaiming docs, especially implying that the audit skill, PubMed grounding, `rolling_mean`, or `paired_t_test` shipped.

## Activity Log

- 2026-05-31T11:48:00Z – claude:opus:python-implementer:implementer – shell_pid=21664 – Started implementation via action command
- 2026-05-31T12:06:20Z – claude:opus:python-implementer:implementer – shell_pid=21664 – Ready for review: live docs + contracts synced to shipped trace surface; ruff-format gap on mission code files fixed; gates recorded
- 2026-05-31T12:06:34Z – claude:opus:docs-reviewer:reviewer – shell_pid=37548 – Started review via action command
- 2026-05-31T12:14:14Z – claude:opus:docs-reviewer:reviewer – shell_pid=37548 – Review passed: verified from code default=16 / operator=17 (16 + query_warehouse); 3 trace tools research_trace_open/_mark_surfaced/_disclosure; disclosure fields (calls, calls_truncated, schema_version, warehouse_fingerprint, started_at_utc, surfaced/marks, refusal_breakdown, disclosure_text) + open client_label + mark rationale + top-level trace wrapper (session_id/call_id/terminal_status/result_id) + error_kind all match trace.py/entrypoint.py. STATUS/STAGES/ROADMAP/FULL_APP accurate (trace=MCP-boundary provenance not engine state; audit skill/PubMed/rolling_mean/paired_t_test deferred). All 29 cited validation tests exist. Wording grep clean (every 'significant'/'canonical' is a negation or pre-existing-unrelated). Gates: pytest 631 passed; ruff format --check on 4 mission files clean; mypy 14 pre-existing errors none in trace.py/entrypoint.py (identical on master). Hygiene commit 05644b5 confirmed format+rename-only (no semantic change). No code in WP04's own commits.
