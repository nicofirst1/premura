---
work_package_id: WP04
title: Shipped-State Documentation Sync
dependencies:
- WP03
requirement_refs:
- FR-007
- FR-010
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
history:
- timestamp: '2026-06-01T10:38:21Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/
execution_mode: code_change
owned_files:
- docs/operations/STATUS.md
- docs/product/ROADMAP.md
- docs/product/FULL_APP_DEVELOPMENT_PLAN.md
- docs/architecture/STAGES.md
tags: []
---

# Work Package Prompt: WP04 - Shipped-State Documentation Sync

## Implement Command

```bash
spec-kitty agent action implement WP04 --agent <name> --mission pubmed-grounding-tools-01KT1BPM
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Synchronize live product/architecture/status docs after the PubMed grounding tools ship. The documentation must make the actual shipped boundary clear: PubMed search/fetch are Stage 3 MCP grounding tools; fetched PMID records are citeable; search candidates are not citeable; the personal-data bridge and broader literature tooling remain deferred.

This WP should run only after WP03 confirms final tool names and default/operator tool counts.

## Authoritative Inputs

- `kitty-specs/pubmed-grounding-tools-01KT1BPM/spec.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/contracts/pubmed-grounding-contract.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/quickstart.md`
- Final code/tool names from WP03
- Existing docs listed under owned files
- `docs/product/DOCTRINE.md`
- `CONTEXT.md` language rules

## Owned Files

- `docs/operations/STATUS.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `docs/architecture/STAGES.md`

Do not edit source code, tests, mission-local planning artifacts, `README.md`, or `src/premura/engine/CONTRACT.md` in this WP unless the orchestrator explicitly expands ownership first.

## Required Subtasks

### T012: Update live status/roadmap/stage docs

Purpose: Reflect the shipped PubMed grounding slice in the live documentation set.

Guidance:
- In `docs/operations/STATUS.md`, add PubMed grounding to the current shipped Stage 3 surface only after verifying WP03's final tool names and counts.
- In `docs/product/ROADMAP.md`, move PubMed grounding from deferred next-depth item to shipped first slice, while naming remaining follow-ons.
- In `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`, update Phase 3 status and exit criteria to reflect that PubMed search/fetch grounding now exists.
- In `docs/architecture/STAGES.md`, update the Stage 3 MCP description and tool list.
- Preserve plain-English language from `CONTEXT.md`; avoid PM jargon and invented coinages.

Validation:
- Tool names and counts match WP03 tests.
- Docs do not claim the personal-data bridge exists.

### T013: Document deferred scope explicitly

Purpose: Prevent future agents from assuming broader literature capabilities shipped.

Guidance:
- State that search results are candidates only and fetched PMID records are citeable.
- State that full-text retrieval, deep paper analysis, Europe PMC/Unpaywall expansion, MeSH lookup, related-article discovery, and citation formatting are not part of this first slice.
- State that concept-to-metric mapping and literature-to-warehouse bridge remain future work.
- State that PubMed context does not diagnose, treat, name cause, or compute over the user's health data.

Validation:
- Grep/read the changed docs for false claims like “full text shipped,” “deep analysis shipped,” or “bridge shipped.”

### T014: Run changed-scope validation and record evidence

Purpose: Leave a clean handoff for review.

Guidance:
- Run the changed-scope validation commands appropriate to the code touched by prior WPs if they have not already been run in the merged lane context.
- At minimum, verify docs are internally consistent by reading changed sections and checking tool names/counts against WP03.
- If pre-existing lint/type/test failures appear outside this WP's changes, call them out explicitly in the handoff rather than hiding them.
- Do not commit new private data, PHI, or network-derived article contents into docs.

Suggested commands when in the final integrated lane:
```bash
uv run python -m pytest -q tests/test_mcp_pubmed.py tests/test_mcp_server.py -x --tb=short
uv run ruff check src/premura/mcp tests/test_mcp_pubmed.py tests/test_mcp_server.py
```

## Definition Of Done

- Live docs accurately state what shipped.
- Live docs accurately state what remains deferred.
- Tool names and counts match implementation.
- Changed-scope validation evidence is recorded in the WP handoff.
- No source code or tests were modified by this WP.

## Risks For Reviewer

- Watch for docs overstating PubMed grounding as a data bridge.
- Watch for docs implying search-only candidates are citeable.
- Watch for docs adding full-text/deep-analysis claims.
- Watch for stale default/operator tool counts.
