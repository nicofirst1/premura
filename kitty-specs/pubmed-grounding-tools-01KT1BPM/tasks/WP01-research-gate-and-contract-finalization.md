---
work_package_id: WP01
title: Research Gate And Contract Finalization
dependencies: []
requirement_refs:
- FR-007
- FR-010
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T001
- T002
- T003
agent: "claude:opus:implementer:implementer"
shell_pid: "5909"
history:
- timestamp: '2026-06-01T10:38:21Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: kitty-specs/pubmed-grounding-tools-01KT1BPM/
execution_mode: planning_artifact
owned_files:
- kitty-specs/pubmed-grounding-tools-01KT1BPM/research.md
- kitty-specs/pubmed-grounding-tools-01KT1BPM/data-model.md
- kitty-specs/pubmed-grounding-tools-01KT1BPM/contracts/pubmed-grounding-contract.md
- kitty-specs/pubmed-grounding-tools-01KT1BPM/quickstart.md
tags: []
---

# Work Package Prompt: WP01 - Research Gate And Contract Finalization

## Implement Command

```bash
spec-kitty agent action implement WP01 --agent <name> --mission pubmed-grounding-tools-01KT1BPM
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Complete the provider research gate before implementation code chooses a path. The mission already has seed research, but the maintainer explicitly asked that Phase 0 look beyond the three named PubMed MCP servers. This WP must make the final adopt-vs-wrap-vs-build decision concrete and leave the mission-local contract aligned with that decision.

This WP does not implement runtime PubMed tooling. It owns planning artifacts only.

## Authoritative Inputs

- `kitty-specs/pubmed-grounding-tools-01KT1BPM/spec.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/plan.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/research.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/data-model.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/contracts/pubmed-grounding-contract.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/quickstart.md`
- `docs/product/DOCTRINE.md`
- `.kittify/charter/charter.md`

## Owned Files

- `kitty-specs/pubmed-grounding-tools-01KT1BPM/research.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/data-model.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/contracts/pubmed-grounding-contract.md`
- `kitty-specs/pubmed-grounding-tools-01KT1BPM/quickstart.md`

Do not edit source code, tests, or live docs in this WP.

## Required Subtasks

### T001: Broaden the prior-art survey

Purpose: Ensure the mission does not build custom PubMed support without checking existing MCP servers and adjacent libraries.

Guidance:
- Start from the three seed candidates already recorded in `research.md`.
- Search for additional PubMed MCP servers, biomedical literature MCP servers, and PubMed client libraries that could satisfy the first slice.
- Record each candidate with enough detail for a reviewer to understand why it was accepted, wrapped, or rejected.
- Compare candidates against Premura's contract, not against feature richness.
- If search is rate-limited or unavailable, record the attempted route and a lower-noise follow-up path rather than pretending the search was complete.

Candidate evaluation dimensions:
- Does it support search returning PMIDs?
- Does it support exact PMID fetch?
- Does it distinguish candidate search results from citeable fetched records?
- Can it be constrained to only two tools on Premura's default surface?
- Does it require a new runtime or package manager?
- Can tests run deterministically without live network?
- Does it expose out-of-scope full text, deep analysis, Europe PMC, Unpaywall, MeSH, or related-article tools by default?

Validation:
- `research.md` includes a candidate table or equivalent structured comparison.
- The three seed candidates remain covered.
- At least one broader search attempt is documented.

### T002: Make the adopt-vs-wrap-vs-build decision explicit

Purpose: Give WP02 a clear implementation path.

Guidance:
- Choose exactly one path: direct adoption, wrapping/adapting, or minimal native build.
- Direct adoption is allowed only if the selected candidate already satisfies the mission contract without exposing broader tools.
- Wrapping/adapting is appropriate when a candidate has useful provider code but the default MCP surface must stay Premura-owned.
- Native build is appropriate if the needed search/fetch behavior is smaller than integrating a broader server.
- State rejected alternatives and the reason each lost.

Expected output:
- A clear `Decision` section in `research.md` naming the path WP02 must implement.
- A `Rationale` paragraph tied to citation safety and stage boundaries.
- An `Alternatives considered` list that includes direct third-party exposure and native E-utilities.

Validation:
- A reviewer can answer: “What should WP02 build?” without re-opening the whole research question.

### T003: Finalize mission-local contract/data model/quickstart if needed

Purpose: Keep the planning artifacts consistent with the selected path.

Guidance:
- If the selected path changes response status names, provider fields, or validation examples, update `data-model.md`, `contracts/pubmed-grounding-contract.md`, and `quickstart.md`.
- Preserve the core citation rule: search candidates are not citeable; fetched-by-PMID records are citeable.
- Preserve the Stage 3 boundary: no runtime PubMed dependency in `premura.engine`, parsers, or store code.
- Do not add the personal-data bridge, concept-to-metric mapping, full-text retrieval, or deep paper analysis to scope.

Validation:
- Mission-local contract names the final accepted tool behavior.
- Quickstart validation examples still match the contract.
- No `[NEEDS CLARIFICATION]` markers are introduced.

## Definition Of Done

- `research.md` contains the broader prior-art survey and final adopt-vs-wrap-vs-build decision.
- Mission-local contract/data-model/quickstart remain internally consistent.
- No source code or live docs were modified.
- No unresolved clarification markers remain.

## Risks For Reviewer

- The WP may overvalue rich third-party feature sets. Review against Premura's two-tool first slice.
- The WP may leave the decision ambiguous. Require one chosen path.
- The WP may accidentally expand scope into full text or concept mapping. Reject that drift.

## Activity Log

- 2026-06-01T10:43:10Z – claude:opus:implementer:implementer – shell_pid=5909 – Started implementation via action command
