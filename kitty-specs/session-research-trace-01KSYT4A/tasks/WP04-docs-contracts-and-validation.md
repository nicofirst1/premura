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
branch_strategy: Planning artifacts were generated on master; completed changes must merge back into master. Execution worktrees are allocated per computed lane from lanes.json after finalize-tasks.
subtasks:
- T020
- T021
- T022
- T023
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
