---
work_package_id: WP03
title: Documentation and Handoff Routing
dependencies:
- WP02
requirement_refs:
- FR-001
- FR-004
- FR-005
- FR-007
- FR-008
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T013
- T014
- T015
- T016
- T017
history:
- timestamp: '2026-06-01T15:11:47Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: README.md
execution_mode: code_change
owned_files:
- README.md
- CONTRIBUTING.md
- docs/operations/STATUS.md
- tests/test_bootstrap_docs.py
- kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/quickstart.md
tags: []
---

# Work Package Prompt: WP03 - Documentation and Handoff Routing

## Implement Command

```bash
spec-kitty agent action implement WP03 --agent <name> --mission fresh-clone-bootstrap-agent-01KT1VFR
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after `spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned by the runtime for this WP.

## Objective

Make the shipped `hpipe bootstrap` path discoverable without turning root docs into long duplicated setup manuals. This WP updates root/contributor/operations docs after the command exists and records final validation evidence in the mission quickstart.

## Authoritative Inputs

- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/spec.md`
- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/plan.md`
- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/quickstart.md`
- WP02 shipped CLI behavior
- `docs/product/DOCTRINE.md`
- `CONTEXT.md` maintainer mental model and planning language
- `.kittify/charter/charter.md`

## Owned Files

- `README.md`
- `CONTRIBUTING.md`
- `docs/operations/STATUS.md`
- `tests/test_bootstrap_docs.py`
- `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/quickstart.md`

Do not edit `src/premura/cli.py` or `src/premura/bootstrap.py`; code behavior belongs to WP01/WP02.

## Required Subtasks

### T013: Update the root README fresh-clone path

Purpose: Let humans and agents find the new command quickly.

Guidance:
- Add or adjust the Quick start section so a fresh clone points to `hpipe bootstrap` before normal operation.
- Keep README welcoming and concise; do not paste the full command contract.
- State plainly that bootstrap prepares/verifies the local checkout and reports reload guidance.
- Preserve the existing distinction between setup, ingest, encrypt, and opt-in upload.

Validation:
- README contains `hpipe bootstrap` and does not imply bootstrap ingests data or uploads.

### T014: Update contributor setup guidance

Purpose: Keep contributor docs aligned with the new bootstrap path.

Guidance:
- Update `CONTRIBUTING.md` setup guidance to mention `hpipe bootstrap` as the agent-friendly fresh-clone path.
- Preserve development validation commands such as pytest/ruff/mypy.
- Keep setup instructions readable for both humans and agents.
- Do not duplicate every implementation detail from the contract.

Validation:
- CONTRIBUTING names the bootstrap path and still points to the relevant development checks.

### T015: Update operations shipped-state docs

Purpose: Record that the setup surface exists once WP02 has shipped it.

Guidance:
- Update `docs/operations/STATUS.md` with a short setup/ops note.
- Make clear this is setup-only, not runtime health-data operation.
- Do not overstate platform support beyond the charter and implementation.

Validation:
- STATUS mentions `hpipe bootstrap` only as shipped setup behavior.

### T016: Add documentation checks or lightweight assertions

Purpose: Prevent docs from drifting away from the new command.

Guidance:
- Add `tests/test_bootstrap_docs.py` or extend an appropriate docs test if one exists.
- Keep the test lightweight: verify key docs mention `hpipe bootstrap` and preserve boundary phrases such as no ingest/upload, if practical.
- Do not make brittle assertions on entire paragraphs.

Validation:
- Docs test fails if the bootstrap command disappears from root setup docs.

### T017: Record final validation evidence in mission quickstart/docs

Purpose: Leave the planning artifact aligned with what actually shipped.

Guidance:
- Update `kitty-specs/fresh-clone-bootstrap-agent-01KT1VFR/quickstart.md` with actual validation commands and any final invocation nuance discovered during implementation.
- Record the setup-only boundary checks reviewers should run.
- If a planned behavior changed, document the deviation and point to the code/docs that explain why.

Validation:
- Quickstart matches the shipped command behavior.
- No real health data is required by the validation path.

## Definition of Done

- README routes fresh-clone setup to `hpipe bootstrap`.
- CONTRIBUTING keeps contributor setup aligned with bootstrap.
- STATUS records the shipped setup command without making runtime claims.
- A lightweight docs test protects the command reference.
- Mission quickstart reflects actual validation evidence.

## Reviewer Guidance

- Reject if docs imply bootstrap ingests health data, uploads artifacts, or answers health questions.
- Reject if root docs become a long duplicate of the implementation contract.
- Verify documentation follows the repo language preference: plain English, agent-first execution, human-first purpose.
