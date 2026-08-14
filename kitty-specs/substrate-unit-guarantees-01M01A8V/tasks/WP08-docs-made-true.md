---
work_package_id: WP08
title: Docs made true + doctrine substrate test + live-doc sync
dependencies:
- WP03
- WP05
- WP06
- WP07
requirement_refs:
- FR-010
planning_base_branch: mission/substrate-unit-guarantees
merge_target_branch: mission/substrate-unit-guarantees
branch_strategy: Planning artifacts for this mission were generated on mission/substrate-unit-guarantees. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into mission/substrate-unit-guarantees unless the human explicitly redirects the landing branch.
subtasks:
- T022
- T023
- T024
phase: Phase 4 - Truth
history:
- timestamp: '2026-08-15T00:00:00Z'
  agent: system
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/
create_intent: []
execution_mode: code_change
owned_files:
- src/premura/parsers/CONTRACT.md
- src/premura/parsers/PARSER_CONTRIBUTING.md
- docs/building/STAGES.md
- docs/shared/SPEC.md
- src/premura/store/UPDATE_STRATEGY.md
- docs/shared/DOCTRINE.md
- docs/shared/CHANGELOG.md
- src/premura/mcp/entrypoint.py
tags: []
tracker_refs: []
---

# Work Package Prompt: WP08 – Docs made true

## Objective

Every guarantee claim names its mechanical enforcement home; doctrine gains the substrate test; live docs stop drifting. Docs trail the code — this WP runs last.

## Read first

The merged WP02/03/05/06/07 diffs; `docs/shared/DOCTRINE.md` (structure + tone of the two existing rules); each target doc's current claim (listed in plan.md IC-07).

## Subtasks

- **T022**: contract truth — `parsers/CONTRACT.md` failure-claim rewritten to the real split (batch-level violations fail the batch; row-level unit/parse issues skip-and-record to `hp.ingest_skip`); `PARSER_CONTRIBUTING.md` states parsers emit unit-as-observed and never convert; `STAGES.md` "canonical units" claim points at the loader as the enforcement home; `SPEC.md` unit table marked display-vs-storage with `units.normalize_unit` as the mapping home; `UPDATE_STRATEGY.md` names delete-and-re-enter as the manually-entered-data variant.
- **T023**: `DOCTRINE.md` — new short section (parallel to "guide, don't enumerate"): the substrate test — "for each guarantee ask: what happens if an agent simply doesn't follow the process? If bad data lands silently, the guarantee is fiction — move it to the chokepoint that cannot be bypassed" — with the labsheet incident as the worked example (cite issue #113, not mission tokens).
- **T024**: live-doc sync — CHANGELOG carries the mission narrative (the repo's live-doc home); `mcp/entrypoint.py` module-docstring tool count/prose updated (prefer pointing at the inventory test over restating a number).

## Done criteria

`bash ops/lint_docs.sh` and `bash ops/check_no_mission_citations.sh` pass (no FR/WP tokens in tracked docs — cite issues/ADRs instead); each rewritten claim spot-checked against shipped code; full suite green.

## Constraints

Minimal words (agent-docs bar). No provenance-dating in living prose. Post-merge live-doc reconciliation happens at mission review (a pre-merge WP cannot describe its own merge).
