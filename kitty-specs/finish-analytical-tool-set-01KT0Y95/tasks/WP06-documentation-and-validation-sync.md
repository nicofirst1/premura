---
work_package_id: WP06
title: Documentation And Validation Sync
dependencies:
- WP05
requirement_refs:
- FR-013
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T026
- T027
- T028
- T029
- T030
- T031
agent: "claude:opus:python-reviewer:reviewer"
shell_pid: "76386"
history:
- timestamp: '2026-06-01T06:44:16Z'
  agent: opencode
  action: Prompt generated via /spec-kitty.tasks
authoritative_surface: docs/
execution_mode: code_change
owned_files:
- docs/operations/STATUS.md
- docs/architecture/STAGES.md
- docs/product/ROADMAP.md
- docs/product/FULL_APP_DEVELOPMENT_PLAN.md
- README.md
- pyproject.toml
- src/premura/engine/CONTRACT.md
tags: []
---

# Work Package Prompt: WP06 - Documentation And Validation Sync

## Implement Command

```bash
spec-kitty agent action implement WP06 --agent <name> --mission finish-analytical-tool-set-01KT0Y95
```

## Branch Strategy

Planning/base branch: `master`.

Final merge target: `master`.

Execution worktrees are allocated per computed lane from `lanes.json` after
`spec-kitty agent mission finalize-tasks`. Work only in the workspace assigned
by the runtime for this WP.

## Objective

Synchronize live docs, contributor guidance, and release metadata after the
completed analytical tool set is publicly available. This WP also records
validation results for the mission handoff. It should not change source
behavior.

## Authoritative Inputs

- `kitty-specs/finish-analytical-tool-set-01KT0Y95/spec.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/plan.md`
- `kitty-specs/finish-analytical-tool-set-01KT0Y95/quickstart.md`
- Final public names and behavior from WP05

## Owned Files

- `docs/operations/STATUS.md`
- `docs/architecture/STAGES.md`
- `docs/product/ROADMAP.md`
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`
- `README.md`
- `pyproject.toml`
- `src/premura/engine/CONTRACT.md`

Do not edit implementation code, MCP wrappers, trace logic, or tests in this WP.

## Subtasks

### T026: Sync live roadmap/status/stage docs to name the completed analytical tool set

Update live docs to reflect final behavior:

- `docs/operations/STATUS.md`: list `rolling_mean` and `paired_t_test` as shipped
  alongside the existing analytical tools once implementation is complete.
- `docs/architecture/STAGES.md`: update the default MCP surface and long-term
  surface language so these tools are no longer deferred.
- `docs/product/ROADMAP.md`: remove `rolling_mean` and `paired_t_test` from the
  open analytical-tool list and keep PubMed grounding deferred.
- `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`: summarize the completed tool set
  and keep later phases correctly sequenced.

Keep prose concise. Do not duplicate the full contracts in live docs.

### T027: Update the Stage 2/3 contributor contract with the new bounded tool shapes

Update `src/premura/engine/CONTRACT.md` so future agents understand how to add or
review these shapes.

The contract should state:

- `rolling_mean` is a declared-window moving summary and must not scan windows.
- `paired_t_test` in this mission means simple anchor-date before/after pairing.
- Broader condition-label pairing requires a future contract extension.
- Both tools keep the same no-diagnosis/no-causation/no-hidden-search boundary.

### T028: Add documentation checks for deferred PubMed and condition-pairing scope

Read the changed docs for accidental scope drift.

Confirm docs do not imply:

- PubMed grounding shipped in this mission.
- A teaching UI shipped in this mission.
- Nutrition/supplement intake shipped in this mission.
- `paired_t_test` supports arbitrary condition labels or pair maps.
- The tools diagnose, treat, or establish cause.

If a doc needs a brief future-work sentence, keep it short and point to the
mission contracts rather than reopening design.

### T029: Run focused validation commands and record any pre-existing unrelated failures

Run the quickstart validation commands appropriate to the final changed scope:

```bash
uv run python -m pytest tests/test_engine_analytical_tools.py -q
uv run python -m pytest tests/test_engine_analytical_inputs.py -q
uv run python -m pytest tests/test_engine_analytical_public_surface.py -q
uv run python -m pytest tests/test_mcp_analytical_tools.py tests/test_mcp_trace_recording.py tests/test_trace_store.py -q
uv run ruff check .
uv run ruff format --check .
uv run mypy src/premura/engine src/premura/mcp src/premura/trace.py
```

If command names differ after implementation, use the nearest focused test files
created by earlier WPs and explain the substitution in the handoff.

### T030: Prepare final mission handoff notes for review and downstream task execution

Add a concise handoff note in the WP completion result, not a new repository doc,
covering:

- Which tools now ship.
- Which validation commands passed.
- Any pre-existing unrelated failures.
- The explicit deferred work: PubMed grounding and broader condition-pairing.
- The exact pre-`v1` release tag expected after merge.

### T031: Prepare the pre-v1 release gate

Make the smallest metadata changes needed so the mission can close with a real
restore point instead of only implementation commits.

Required checks:

- Confirm this mission remains on the pre-`v1` line. `v1.0.0` is reserved for a
  coherent user-facing path across all four stages.
- Update `pyproject.toml` to the intended `v0.x.0` package version for the
  analytical-tool-set release, if it has not already been updated by a release
  task.
- Keep README and live docs aligned with the current default MCP surface.
- In the handoff, include the exact post-merge tag command, for example
  `git tag v0.x.0 && git status`, using the final chosen version.
- Do not create the git tag from the implementation worktree. The tag is cut on
  `master` after the mission merge and validation evidence are accepted.

Definition of done:

- Live docs accurately reflect shipped behavior.
- Contributor contract names the bounded extension rules.
- Focused validation results are recorded in the WP handoff.
- Release metadata and the post-merge tag command are ready.

## Test Strategy

This is docs/validation work. Run the commands in T029 and report results.

## Risks

- Docs can overstate what shipped. Keep PubMed and condition-label pairing
  clearly deferred.
- Rewriting large roadmap sections creates review noise. Make the smallest
  accurate updates.

## Reviewer Guidance

Review for factual synchronization, not prose preference. The key question is
whether a future agent can tell what shipped and what remains deferred.

## Activity Log

- 2026-06-01T08:46:32Z – claude:opus:python-implementer:implementer – shell_pid=60882 – Started implementation via action command
- 2026-06-01T08:58:40Z – claude:opus:python-implementer:implementer – shell_pid=60882 – Ready for review: synced live docs (STATUS/STAGES/ROADMAP/FULL_APP_DEVELOPMENT_PLAN/README) and engine CONTRACT.md to the completed 5-tool analytical set (change_point, smoothed_average, correlate, rolling_mean, paired_t_test); default surface 18 tools / operator 19; PubMed grounding + nutrition/supplement + teaching kept deferred; paired_t_test documented as a paired-difference + descriptive uncertainty band (NOT a significance test, no p-value, no causation), anchor-date pairing only with condition-label pairing as deferred extension; rolling_mean as a declared moving-window summary distinct from smoothed_average; pyproject bumped to v0.3.0 (pre-v1 line); full pytest 785/785 green; ruff/format/mypy issues are pre-existing on lane base (test/parser files), none introduced by WP06.
- 2026-06-01T08:59:37Z – claude:opus:python-reviewer:reviewer – shell_pid=76386 – Started review via action command
- 2026-06-01T09:07:15Z – claude:opus:python-reviewer:reviewer – shell_pid=76386 – Review PASSED. Live engine.list_analytical_tools() (uv run, lane env) returns exactly the 5 tools: change_point, correlate, paired_t_test, rolling_mean, smoothed_average; live default MCP surface = 18 tools (incl. rolling_mean + paired_t_test), operator = 19 — docs' counts match reality. FR-013: STATUS/STAGES/ROADMAP/README/FULL_APP_PLAN all list the 5 as SHIPPED; rolling_mean + paired_t_test no longer deferred (only paired_t_test's condition-label pairing extension stays deferred). SC-006: PubMed grounding, nutrition/supplement parsing, and teaching UI all correctly remain deferred (grep-confirmed; only diagram/storage-seam mentions, no false shipped-claims). paired_t_test documented honestly as a paired difference + descriptive uncertainty band, NOT a significance test / no p-value / names no cause — matches WP04 impl (paired_difference_estimate, unsupported_parameter refusal for p-value/scan/condition-label). rolling_mean documented as declared moving-window with visible coverage, distinct from smoothed_average (not a rename). CONTRACT.md documents both tools' envelope fields, refusal classes, no-significance/no-causation boundary, anchor-date-only scope with condition-label pairing named as the deferred extension, plus trace identities and the rule for a 6th tool. No source behavior change: git show --stat = only 5 docs + README + pyproject + CONTRACT.md + uv.lock (version-bump byproduct); zero .py source touched. Full pytest 785/785 passed (regression incl.). ruff(12 errors/5 files), format(38 files), mypy(2) are ALL pre-existing on lane base — none in WP06's diff. RISK A ruling (version bump): NOT a blocker. The pyproject 0.1.1->0.3.0 bump WAS mandated by T031 (v0.x release for the analytical-tool-set / v0.3 phase) — in-scope, correct. src/premura/__init__.py __version__='0.1.0' is stale (was already stale vs 0.1.1 pre-WP), is NOT in WP06 owned_files, and is consumed/asserted NOWHERE (grep: zero readers; importlib.metadata refs are entry-point wiring only) — so the mismatch is cosmetic, not a release-correctness defect. RISK B ruling (git checkout master -- on owned docs): correct approach, dropped NO tool-set content and pulled in NO unrelated master changes; pre-v1 blocks now byte-identical to master. MERGE-OWNER ACTION ITEMS: (1) trivial add/add conflict in README.md when merging to current master (both master commit 12531f1 and the lane added an identical pre-v1 block at the same anchor; resolve by keeping one copy — STATUS/ROADMAP/PLAN/pyproject auto-merge clean; master's 2cb9398 test-loop README edit auto-merges); (2) after merge, reconcile src/premura/__init__.py __version__ to 0.3.0 (or wire to importlib.metadata.version) and cut the post-merge tag v0.3.0 on master per T031.
- 2026-06-01T09:14:56Z – claude:opus:python-reviewer:reviewer – shell_pid=76386 – Done override: Mission squash-merged to master (984cc48)
