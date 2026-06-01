---
work_package_id: WP02
title: PubMed Core Provider Contract
dependencies:
- WP01
requirement_refs:
- FR-001
- FR-002
- FR-003
- FR-004
- FR-005
- FR-006
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-pubmed-grounding-tools-01KT1BPM
base_commit: 0823dc2bd37afac64d1d42532b02215e745e78f5
created_at: '2026-06-01T10:50:07.459713+00:00'
subtasks:
- T004
- T005
- T006
- T007
shell_pid: "15687"
agent: "claude:opus:implementer:implementer"
history:
- timestamp: '2026-06-01T10:38:21Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: src/premura/mcp/
execution_mode: code_change
owned_files:
- src/premura/mcp/pubmed.py
- tests/test_mcp_pubmed.py
- pyproject.toml
- uv.lock
tags: []
---

# Work Package Prompt: WP02 - PubMed Core Provider Contract

## Implement Command

```bash
spec-kitty agent action implement WP02 --agent <name> --mission pubmed-grounding-tools-01KT1BPM
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Build the core Stage 3 PubMed grounding service behind a Premura-owned provider contract. This WP creates the behavior that later MCP wrappers expose, but it does not register MCP tools on the default surface. That registration is WP03's responsibility.

Use the provider path chosen by WP01. If WP01 selected a third-party candidate, wrap it behind the contract in `src/premura/mcp/pubmed.py` rather than exposing the third-party MCP server directly.

## Authoritative Inputs

- `kitty-specs/pubmed-grounding-tools-01KT1BPM/research.md` after WP01
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/contracts/pubmed-grounding-contract.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/data-model.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/spec.md`
- `src/premura/mcp/server.py` for local style and structured helper behavior
- `.kittify/charter/charter.md`

## Owned Files

- `src/premura/mcp/pubmed.py`
- `tests/test_mcp_pubmed.py`
- `pyproject.toml`
- `uv.lock`

Do not edit `src/premura/mcp/server.py`, `src/premura/mcp/entrypoint.py`, or `tests/test_mcp_server.py`; WP03 owns those. Do not edit `premura.engine`, parser, or store code.

## Required Subtasks

### T004: Add acceptance-first core tests

Purpose: Define the PubMed grounding behavior before implementation.

Guidance:
- Create `tests/test_mcp_pubmed.py` first.
- Drive behavior through public functions/classes from `premura.mcp.pubmed`, not through private internals.
- Use deterministic fake provider/transport responses. The default test suite must not call live PubMed.
- Cover at least these cases:
  - Search success returns candidates with PMIDs and `citation_status = candidate_only`.
  - Search no-results returns `status = no_results` and an empty candidate list.
  - Fetch success returns a record with `citation_status = citeable_fetched_record`, PMID, and PubMed URL/provenance.
  - Fetch with missing optional metadata keeps fields absent/null rather than fabricated.
  - Invalid/unavailable PMID returns a structured outcome, not an uncaught exception for ordinary lookup failure.
  - Search limit defaults to no more than 20 candidates.

Validation:
- Tests fail before production code exists.
- Tests assert output fields from the contract, especially `citation_status`.

### T005: Create the Premura-owned PubMed provider/data contract

Purpose: Give the rest of the MCP layer a stable local API independent of external provider details.

Guidance:
- Add `src/premura/mcp/pubmed.py`.
- Define a small public surface such as `pubmed_search(...)` and `pubmed_fetch(...)`, or a service object plus wrapper functions.
- Keep names aligned with the contract unless there is a strong reason to choose clearer code names.
- Use typed records/dataclasses or typed dictionaries with clear serialization helpers.
- Keep ordinary no-results/unavailable/provider-error outcomes as data, not unhandled exceptions.
- Reserve exceptions for programming errors or truly unexpected failures.

Required behavior:
- Candidate records are never citeable.
- Fetched records are citeable only after exact PMID fetch.
- Missing article fields are explicit.
- Provider provenance is preserved.

### T006: Implement the chosen provider path behind an injectable adapter seam

Purpose: Make real PubMed lookup possible while keeping tests deterministic and provider choice isolated.

Guidance:
- Follow WP01's decision.
- If building native support, use NCBI E-utilities as the baseline provider and keep the client minimal: search and exact fetch only.
- If wrapping a third-party package/server, expose only the Premura contract and hide third-party tool names/extra capabilities.
- Use dependency injection for the HTTP/provider layer so tests can provide fake responses.
- Do not add a live PubMed call to import-time behavior.
- Do not add background network activity.

Dependency guidance:
- Prefer existing project dependencies or Python standard library if the native path is small enough.
- If adding a dependency, update only `pyproject.toml` and `uv.lock` in this WP and document the reason in the handoff.

### T007: Ensure serialization preserves missingness, provenance, bounded size, and citation status

Purpose: Make the output safe for an agent to narrate.

Guidance:
- Enforce or clamp default search result size to at most 20 candidates.
- Include a citation-rule message or field on search output.
- Include PubMed provenance on fetched records.
- Preserve missing optional fields as `None`, empty lists, or explicit unavailable markers.
- Do not synthesize abstracts, authors, journal names, or dates.
- Do not include any computed claims about the user's own data.

Validation:
- `tests/test_mcp_pubmed.py` covers bounded search, missing metadata, candidate/fetched distinction, and structured failures.

## Definition Of Done

- `tests/test_mcp_pubmed.py` passes without live network.
- `src/premura/mcp/pubmed.py` provides the core search/fetch behavior.
- No default MCP tool registration was added in this WP.
- No code outside owned files was modified.
- If a dependency was added, `pyproject.toml` and `uv.lock` are both updated and the rationale is documented.

## Risks For Reviewer

- Watch for hidden live network in tests.
- Watch for third-party API response shapes leaking into the Premura contract.
- Watch for broad features such as full text, MeSH, related articles, or deep analysis creeping in.
- Watch for PubMed logic imported into `premura.engine` or other non-MCP stages.

## Activity Log

- 2026-06-01T10:50:08Z – claude:opus:implementer:implementer – shell_pid=15687 – Assigned agent via action command
- 2026-06-01T10:54:26Z – claude:opus:implementer:implementer – shell_pid=15687 – Ready for review: native E-utilities provider, injectable seam, offline deterministic tests, citation-status rule enforced
