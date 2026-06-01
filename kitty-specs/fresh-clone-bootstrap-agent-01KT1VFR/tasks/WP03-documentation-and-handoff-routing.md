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

## Documentation Notes

This WP is about routing and shipped-state clarity. The root README should help a human or agent know what to run first; it should not become a full implementation plan. CONTRIBUTING should keep the development setup path clear. STATUS should record what now works without overselling runtime behavior.

Use the repo's chosen language:

- Say "agent" for the setup actor, not "orchestrator".
- Say "fresh clone" or "local checkout" when describing setup.
- Keep "bootstrap agent" separate from runtime operating roles.
- Avoid implying that bootstrap handles health-data goals.
- Avoid claiming broad platform support beyond the implementation and charter.

The docs should make one thing easy: a new agent in the repo can find the setup command and understand that a reload may be required after skill installation.

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

## Test Strategy

Add lightweight docs coverage only where it protects real drift:

- `test_readme_mentions_hpipe_bootstrap`: root README contains the command in the setup/quick-start area.
- `test_contributing_mentions_bootstrap_without_dropping_dev_checks`: CONTRIBUTING names bootstrap and still includes changed-scope validation guidance.
- `test_status_records_setup_only_boundary`: STATUS mentions the command as setup and does not describe it as ingest/upload/analysis.

Do not assert entire paragraphs. Assert stable command names and boundary words. The goal is to catch accidental deletion or overclaiming, not freeze prose style.

## Validation Commands

Run docs tests:

```bash
uv run python -m pytest -q tests/test_bootstrap_docs.py --tb=short
```

Run markdown-aware review manually by reading the changed docs and checking these questions:

- Can a fresh-clone agent find `hpipe bootstrap` quickly?
- Does the README still distinguish setup from ingest/export/upload?
- Does CONTRIBUTING still tell contributors how to validate code changes?
- Does STATUS avoid claiming bootstrap runs health analysis?

Run formatting/lint only if the docs test file or Python test support needs it:

```bash
uv run ruff check tests/test_bootstrap_docs.py
uv run ruff format --check tests/test_bootstrap_docs.py
```

## Risk Checklist

- Do not duplicate long setup policy in multiple docs.
- Do not tell users bootstrap is enough to ingest or analyze their data.
- Do not remove the existing opt-in upload warning.
- Do not imply no reload is needed after skill installation unless the shipped command can honestly know that.
- Do not add private health examples or real operator data to docs or tests.

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
