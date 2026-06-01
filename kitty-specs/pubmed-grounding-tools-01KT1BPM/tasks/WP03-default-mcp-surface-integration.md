---
work_package_id: WP03
title: Default MCP Surface Integration
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-003
- FR-007
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T008
- T009
- T010
- T011
agent: "claude:opus:reviewer:reviewer"
shell_pid: "28485"
history:
- timestamp: '2026-06-01T10:38:21Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/mcp/
execution_mode: code_change
owned_files:
- src/premura/mcp/server.py
- src/premura/mcp/entrypoint.py
- tests/test_mcp_server.py
tags: []
---

# Work Package Prompt: WP03 - Default MCP Surface Integration

## Implement Command

```bash
spec-kitty agent action implement WP03 --agent <name> --mission pubmed-grounding-tools-01KT1BPM
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Expose the PubMed grounding behavior from WP02 as exactly two tools on Premura's default MCP surface: `pubmed_search` and `pubmed_fetch`. Preserve the default/operator surface discipline: the default surface gets the supported agent-safe tools, while the operator surface is default plus `query_warehouse`.

This WP should not change the PubMed provider implementation. It consumes WP02's public helper surface.

## Authoritative Inputs

- `src/premura/mcp/pubmed.py` from WP02
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/contracts/pubmed-grounding-contract.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/quickstart.md`
- `tests/test_mcp_server.py`
- `src/premura/mcp/entrypoint.py`
- `src/premura/mcp/server.py`

## Owned Files

- `src/premura/mcp/server.py`
- `src/premura/mcp/entrypoint.py`
- `tests/test_mcp_server.py`

Do not edit `src/premura/mcp/pubmed.py` or `tests/test_mcp_pubmed.py`; WP02 owns those. Do not edit live docs; WP04 owns documentation sync.

## Required Subtasks

### T008: Add MCP server wrapper functions

Purpose: Put the PubMed core behavior behind the same Stage 3 server helper style as existing tools.

Guidance:
- In `src/premura/mcp/server.py`, add wrapper functions for PubMed search and fetch.
- Delegate to WP02's `premura.mcp.pubmed` public surface.
- Keep wrappers thin: no health warehouse access, no analytical computation, no diagnosis language.
- Ordinary PubMed no-results/unavailable outcomes should pass through as structured dictionaries.
- Validate trivial boundary inputs if the existing MCP helper style does so for similar wrappers.

Expected function shape:
- A search wrapper accepting a query plus optional limit/sort if supported by WP02.
- A fetch wrapper accepting a PMID.
- Both return JSON-safe dictionaries.

### T009: Register default MCP tools with citation-safe descriptions

Purpose: Make PubMed grounding available to agents through the default MCP server.

Guidance:
- In `src/premura/mcp/entrypoint.py`, register `pubmed_search` and `pubmed_fetch` inside `_register_default_tools`.
- Tool docstrings must explain:
  - Search returns candidates only.
  - Fetch-by-PMID returns citeable records.
  - Final answers may cite only fetched records.
  - PubMed context does not compute claims about the user's warehouse data.
- Do not register broad third-party tools directly.
- Do not add any raw SQL or warehouse reads.

### T010: Update default/operator tool catalog tests and counts

Purpose: Keep the MCP surface exact and reviewable.

Guidance:
- Update `_DEFAULT_TOOLS` in `tests/test_mcp_server.py` to include exactly `pubmed_search` and `pubmed_fetch` in addition to existing default tools.
- Update comments/count expectations where necessary.
- Keep `_OPERATOR_TOOLS` as `_DEFAULT_TOOLS + ["query_warehouse"]`.
- Ensure the default server still excludes `query_warehouse`.

Validation:
- `test_build_server_registers_expected_tools` passes.
- `test_operator_server_registers_expected_tools` passes.

### T011: Add narrow-surface integration tests

Purpose: Prevent accidental exposure of a broad third-party PubMed server.

Guidance:
- Add assertions in `tests/test_mcp_server.py` that out-of-scope PubMed tool names are absent from the default surface.
- Examples to guard against: full-text fetch, deep paper analysis, MeSH lookup, Europe PMC search, Unpaywall, related-article discovery.
- The test should not assume the internal provider choice; it should inspect the MCP tool catalog only.

Validation:
- The default surface contains the two intended PubMed tools.
- The default surface does not contain broad third-party PubMed tools.

## Definition Of Done

- Default MCP surface exposes `pubmed_search` and `pubmed_fetch`.
- Operator surface remains default plus `query_warehouse`.
- Tool descriptions preserve the candidate-vs-fetched citation rule.
- MCP catalog tests pass.
- No broad third-party PubMed tools are exposed.

## Risks For Reviewer

- Watch for direct third-party MCP server registration.
- Watch for tool descriptions that imply search results are citeable.
- Watch for accidental health warehouse reads in PubMed wrappers.
- Watch for mismatched tool counts between docs/comments/tests.

## Activity Log

- 2026-06-01T10:56:50Z – claude:opus:implementer:implementer – shell_pid=23402 – Started implementation via action command
- 2026-06-01T11:00:02Z – claude:opus:implementer:implementer – shell_pid=23402 – Ready for review: two PubMed tools registered on default surface, citation-safe docstrings, narrow-surface tests, operator surface unchanged
- 2026-06-01T11:00:26Z – claude:opus:reviewer:reviewer – shell_pid=28485 – Started review via action command
- 2026-06-01T11:02:01Z – claude:opus:reviewer:reviewer – shell_pid=28485 – Review passed: LIVE wiring verified end-to-end (build_server().list_tools() returns pubmed_search+pubmed_fetch; entrypoint @mcp.tool fns call warehouse_server wrappers which delegate to premura.mcp.pubmed). Default surface=20 tools (18->20), operator=21 (default + query_warehouse only), query_warehouse absent from default. Counts internally consistent across module docstring/comments/tests. Wrappers are thin pure delegations: no hp.*/SQL/warehouse access, no analytical compute, no diagnosis/causal language. Docstrings preserve candidate-vs-fetched citation rule (search=candidate_only, fetch=citeable_fetched_record, final answers cite only fetched, PubMed computes no warehouse claims). Narrow-surface tests guard full-text/MeSH/Europe-PMC/Unpaywall/related/deep-analysis. WP03 changed only its 3 owned files; pubmed.py/test_mcp_pubmed.py NOT in commit. 35/35 pytest pass; ruff check/format clean; mypy clean on owned files.
