# Tasks: Implement Grounded Stage 2 Functions

**Mission**: `implement-grounded-stage-2-functions-01KSHZPC`
**Mission ID**: `01KSHZPCHTFN326808SW6FRVFE`
**Generated**: `2026-05-26T11:32:28Z`
**Planning Branch**: `master`
**Merge Target**: `master`
**Feature Dir**: `/Users/nbrandizzi/repos/personal/premura/kitty-specs/implement-grounded-stage-2-functions-01KSHZPC`

## Branch Context

- Current branch at task generation: `master`
- Planning/base branch: `master`
- Final merge target: `master`
- Branches match expected planning context: `true`
- Branch strategy: planning artifacts were generated on `master`; execution worktrees are allocated later per computed lane from `lanes.json`, and all completed work merges back into `master`.

## Work Package Overview

| WP | Title | Priority | Dependencies | Prompt | Estimated Prompt Size |
|---|---|---|---|---|---|
| WP01 | Engine Seam And Contributor Contract | High | None | `tasks/WP01-engine-seam-and-contributor-contract.md` | ~320 lines |
| WP02 | Descriptive Stage 2 Signals | High | WP01 | `tasks/WP02-descriptive-stage2-signals.md` | ~360 lines |
| WP03 | Comparative Stage 2 Signals | High | WP01 | `tasks/WP03-comparative-stage2-signals.md` | ~320 lines |
| WP04 | Signal-Backed MCP Tools | High | WP01, WP02, WP03 | `tasks/WP04-signal-backed-mcp-tools.md` | ~340 lines |
| WP05 | Documentation Alignment | Medium | WP01, WP02, WP03, WP04 | `tasks/WP05-documentation-alignment.md` | ~280 lines |

## Subtask Index

| ID | Description | WP | Parallel |
|---|---|---|---|
| T001 | Add contributor-ready Stage 2 registry metadata without breaking the existing `SignalSpec` core or current lab-ratio behavior. | WP01 |  | [D] |
| T002 | Add shared Stage 2 result-envelope helpers for status, trend, own-baseline, and change-around-date answers. | WP01 |  | [D] |
| T003 | Update Stage 2 lazy built-in loading so current ratios and upcoming signal modules can register without breaking import safety. | WP01 |  | [D] |
| T004 | Add an engine-side contributor contract and route the parser-side contract toward it for future engine PRs. | WP01 | [D] |
| T005 | Add focused seam and contract tests that lock the Stage 2 extension surface before signal work starts. | WP01 |  | [D] |
| T006 | Add shared Stage 2 query helpers for freshness-aware latest-value lookup and trend-window extraction from the warehouse. | WP02 |  |
| T007 | Implement `resting_hr_status` with explicit current/stale/unavailable behavior. | WP02 |  |
| T008 | Implement `resting_hr_trend` with plain direction output and visible carried-forward points. | WP02 |  |
| T009 | Implement `steps_trend` without imputing missing days. | WP02 | [P] |
| T010 | Implement `weight_trend` with freshness and carried-forward caveats. | WP02 | [P] |
| T011 | Add descriptive-signal tests covering success, stale inputs, missing inputs, and gap handling. | WP02 |  |
| T012 | Implement the own-baseline comparison primitives needed for user-versus-own-normal answers. | WP03 |  |
| T013 | Implement `sleep_deep_pct_baseline` with own-baseline-only semantics and vendor-estimate caveats. | WP03 |  |
| T014 | Implement before/after comparison primitives around a user-supplied anchor date. | WP03 |  |
| T015 | Implement `hrv_change_around_date` with sufficiency checks and explicit non-causation/non-significance caveats. | WP03 |  |
| T016 | Add comparative-signal tests covering sparse windows, unavailable answers, and successful comparison output. | WP03 |  |
| T017 | Add six new signal-backed MCP server wrappers that delegate to Stage 2 instead of directly querying raw tables for those answers. | WP04 |  |
| T018 | Preserve the existing raw MCP tools unchanged alongside the new signal-backed tools. | WP04 |  |
| T019 | Standardize Stage 3 serialization of freshness, missing-input, and insufficient-data outcomes for the new tools. | WP04 |  |
| T020 | Update the FastMCP entrypoint so all nine tools are published with stable names and argument shapes. | WP04 |  |
| T021 | Add MCP tool tests covering registration plus representative success and failure responses for the six new tools. | WP04 |  |
| T022 | Update `docs/architecture/STAGES.md` to reflect the narrowed direct-read debt and the new grounded signal-backed path. | WP05 |  |
| T023 | Update `docs/operations/STATUS.md` with the new Stage 2 and Stage 3 capabilities after implementation. | WP05 | [P] |
| T024 | Update `docs/product/ROADMAP.md` so future analytical work starts from the new shipped baseline rather than the old stubbed state. | WP05 | [P] |
| T025 | Update `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` so phase-level planning no longer describes Stage 2 and Stage 3 as entirely missing. | WP05 | [P] |
| T026 | Update `docs/product/VISION.md` with a light reference to the first grounded question flows while preserving the privacy and non-diagnostic stance. | WP05 | [P] |

## Work Packages

### WP01 - Engine Seam And Contributor Contract

- Prompt: `tasks/WP01-engine-seam-and-contributor-contract.md`
- Goal: make the Stage 2 seam easier for agents and contributors to extend without redesigning the registry or taking on the deferred profile-data problem.
- Priority: High
- Independent validation: the Stage 2 registry exports still work, the new result envelopes are importable and documented, lazy loading remains safe, and the contributor contract is available inside the repo.
- Dependencies: None.
- Owned files: `src/premura/engine/_registry.py`, `src/premura/engine/__init__.py`, `src/premura/engine/_results.py`, `src/premura/engine/CONTRACT.md`, `src/premura/parsers/CONTRACT.md`, `tests/test_engine_contract.py`
- Estimated prompt size: ~320 lines

Included subtasks:
- [x] T001 Add contributor-ready Stage 2 registry metadata without breaking the existing `SignalSpec` core or current lab-ratio behavior. (WP01)
- [x] T002 Add shared Stage 2 result-envelope helpers for status, trend, own-baseline, and change-around-date answers. (WP01)
- [x] T003 Update Stage 2 lazy built-in loading so current ratios and upcoming signal modules can register without breaking import safety. (WP01)
- [x] T004 Add an engine-side contributor contract and route the parser-side contract toward it for future engine PRs. (WP01)
- [x] T005 Add focused seam and contract tests that lock the Stage 2 extension surface before signal work starts. (WP01)

Implementation sketch:
1. Extend the registry surface additively so future signal functions can declare the question they answer, the result family they belong to, and user-facing caveat hints without changing the existing execution contract.
2. Add one shared result-helper module so the six new functions can return consistent envelopes instead of ad-hoc dicts.
3. Make built-in signal loading resilient to more than one built-in module while preserving import safety and the current lab-ratio behavior.
4. Add a new engine-side contract doc and point the parser-side contract at it as the authoritative engine contributor guide.
5. Lock the seam with focused tests before any new Stage 2 signal implementation starts.

Parallel opportunities:
- T004 can proceed once the additive registry/result model is clear because it mostly touches documentation.

Risks:
- Over-expanding the seam could accidentally turn this into a plugin-system redesign.
- Under-specifying result envelopes would push ambiguity into Stage 3 wrappers and later contributor PRs.

Reviewer focus:
- Confirm the registry remains backwards-compatible for existing lab ratios.
- Confirm the result families are minimal, reusable, and non-diagnostic.
- Confirm no profile-precondition behavior is smuggled into this seam work.

### WP02 - Descriptive Stage 2 Signals

- Prompt: `tasks/WP02-descriptive-stage2-signals.md`
- Goal: implement the four descriptive first-wave Stage 2 answers on top of the hardened seam.
- Priority: High
- Independent validation: the four descriptive answers return grounded results or explicit unavailable states with correct freshness and gap behavior.
- Dependencies: WP01.
- Owned files: `src/premura/engine/_query.py`, `src/premura/engine/descriptive_signals.py`, `tests/test_engine_descriptive_signals.py`
- Estimated prompt size: ~360 lines

Included subtasks:
- [ ] T006 Add shared Stage 2 query helpers for freshness-aware latest-value lookup and trend-window extraction from the warehouse. (WP02)
- [ ] T007 Implement `resting_hr_status` with explicit current/stale/unavailable behavior. (WP02)
- [ ] T008 Implement `resting_hr_trend` with plain direction output and visible carried-forward points. (WP02)
- [ ] T009 Implement `steps_trend` without imputing missing days. (WP02)
- [ ] T010 Implement `weight_trend` with freshness and carried-forward caveats. (WP02)
- [ ] T011 Add descriptive-signal tests covering success, stale inputs, missing inputs, and gap handling. (WP02)

Implementation sketch:
1. Add shared warehouse-query helpers for latest usable observations and trend windows, keeping all logic deterministic and local.
2. Implement the status answer first, because it is the simplest freshness-correction example and exercises the new result envelope.
3. Implement the three descriptive trends next, paying close attention to each metric's existing `validity_window` and `missing_data_policy`.
4. Add focused tests that prove the difference between carried-forward values, genuine gaps, stale inputs, and unavailable answers.

Parallel opportunities:
- T009 and T010 are parallel-safe once the shared query helpers and common trend shape exist, because they touch separate metric logic in the same owned module.

Risks:
- `steps_trend` could accidentally inherit imputation behavior even though its policy is `none`.
- `weight_trend` could present stale values as current if freshness and trend logic are conflated.
- Trend-direction output could quietly imply statistical confidence if phrasing is not kept plain.

Reviewer focus:
- Confirm every descriptive result includes an explicit trust state.
- Confirm `resting_hr_status` is a true status answer, not a thin raw-row wrapper.
- Confirm `steps_trend` and `weight_trend` reflect their different missing-data policies.

### WP03 - Comparative Stage 2 Signals

- Prompt: `tasks/WP03-comparative-stage2-signals.md`
- Goal: implement the two heavier-caveat Stage 2 answers without crossing into reference-range or significance territory.
- Priority: High
- Independent validation: both comparative answers return meaningful structured output when data is sufficient and refuse to over-claim when it is not.
- Dependencies: WP01.
- Owned files: `src/premura/engine/comparative_signals.py`, `tests/test_engine_comparative_signals.py`
- Estimated prompt size: ~320 lines

Included subtasks:
- [ ] T012 Implement the own-baseline comparison primitives needed for user-versus-own-normal answers. (WP03)
- [ ] T013 Implement `sleep_deep_pct_baseline` with own-baseline-only semantics and vendor-estimate caveats. (WP03)
- [ ] T014 Implement before/after comparison primitives around a user-supplied anchor date. (WP03)
- [ ] T015 Implement `hrv_change_around_date` with sufficiency checks and explicit non-causation/non-significance caveats. (WP03)
- [ ] T016 Add comparative-signal tests covering sparse windows, unavailable answers, and successful comparison output. (WP03)

Implementation sketch:
1. Build the shared comparison helpers first so both functions use explicit window logic rather than ad-hoc slices.
2. Implement `sleep_deep_pct_baseline` as an own-baseline comparison only; do not introduce population interpretation.
3. Implement `hrv_change_around_date` as a before/after numeric summary only; do not add significance, confidence intervals, or causal language.
4. Add tests that make insufficiency and caveat behavior impossible to ignore during review.

Parallel opportunities:
- T013 and T015 can proceed in parallel once the baseline and before/after helper shapes are fixed.

Risks:
- `sleep_deep_pct_baseline` could drift into device-quality or clinical interpretation beyond the approved scope.
- `hrv_change_around_date` could get mistaken for a lightweight statistics tool rather than a deterministic comparison summary.

Reviewer focus:
- Confirm own-baseline semantics are explicit and consistent.
- Confirm `hrv_change_around_date` never returns significance or causal language.
- Confirm insufficient-data cases return structured refusal rather than partial, misleading output.

### WP04 - Signal-Backed MCP Tools

- Prompt: `tasks/WP04-signal-backed-mcp-tools.md`
- Goal: expose the six new grounded Stage 2 answers through Stage 3 while keeping the current raw tools intact.
- Priority: High
- Independent validation: the MCP server exposes nine total tools, and the six new ones delegate to Stage 2 and return consistent success or failure payloads.
- Dependencies: WP01, WP02, WP03.
- Owned files: `src/premura/mcp/server.py`, `src/premura/mcp/entrypoint.py`, `tests/test_mcp_signal_tools.py`
- Estimated prompt size: ~340 lines

Included subtasks:
- [ ] T017 Add six new signal-backed MCP server wrappers that delegate to Stage 2 instead of directly querying raw tables for those answers. (WP04)
- [ ] T018 Preserve the existing raw MCP tools unchanged alongside the new signal-backed tools. (WP04)
- [ ] T019 Standardize Stage 3 serialization of freshness, missing-input, and insufficient-data outcomes for the new tools. (WP04)
- [ ] T020 Update the FastMCP entrypoint so all nine tools are published with stable names and argument shapes. (WP04)
- [ ] T021 Add MCP tool tests covering registration plus representative success and failure responses for the six new tools. (WP04)

Implementation sketch:
1. Add Stage 3 wrapper functions that call the new engine helpers rather than issuing raw SQL for these question flows.
2. Preserve the existing raw tools as parallel utilities so this mission narrows direct-read debt instead of pretending to remove it everywhere.
3. Normalize how Stage 3 reports unavailable, stale, or insufficient-data states so the tool surface stays predictable.
4. Publish the new tools through the FastMCP entrypoint and add focused tests for registration and representative calls.

Parallel opportunities:
- T017 and T020 can overlap once the wrapper signatures are settled, but T021 should wait until the server and entrypoint surfaces are stable.

Risks:
- It is easy to accidentally break the current raw MCP tool surface while adding the new tools.
- Wrapper responses could leak engine-internal shapes instead of the contract defined in planning.
- Missing-input handling could silently collapse into generic errors instead of explicit user-facing states.

Reviewer focus:
- Confirm the raw tools still behave as before.
- Confirm the six new tools do not query raw tables for their answer logic.
- Confirm the tool names and request shapes match the planning contract exactly.

### WP05 - Documentation Alignment

- Prompt: `tasks/WP05-documentation-alignment.md`
- Goal: update the project docs so they describe the newly shipped Stage 2 and Stage 3 capabilities and the remaining deferred boundaries accurately.
- Priority: Medium
- Independent validation: the affected docs describe the new shipped baseline, future work starts from the right state, and the privacy plus non-diagnostic posture remains unchanged.
- Dependencies: WP01, WP02, WP03, WP04.
- Owned files: `docs/architecture/STAGES.md`, `docs/operations/STATUS.md`, `docs/product/ROADMAP.md`, `docs/product/FULL_APP_DEVELOPMENT_PLAN.md`, `docs/product/VISION.md`
- Estimated prompt size: ~280 lines

Included subtasks:
- [ ] T022 Update `docs/architecture/STAGES.md` to reflect the narrowed direct-read debt and the new grounded signal-backed path. (WP05)
- [ ] T023 Update `docs/operations/STATUS.md` with the new Stage 2 and Stage 3 capabilities after implementation. (WP05)
- [ ] T024 Update `docs/product/ROADMAP.md` so future analytical work starts from the new shipped baseline rather than the old stubbed state. (WP05)
- [ ] T025 Update `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` so phase-level planning no longer describes Stage 2 and Stage 3 as entirely missing. (WP05)
- [ ] T026 Update `docs/product/VISION.md` with a light reference to the first grounded question flows while preserving the privacy and non-diagnostic stance. (WP05)

Implementation sketch:
1. Update architecture truth first so the cross-stage boundary story is current.
2. Update status next so the live shipped snapshot matches the code.
3. Update roadmap and full-app planning after that so future work is sequenced from the new baseline rather than from the old stub language.
4. Keep the vision update intentionally light; it should acknowledge the first grounded flows without rewriting the long-term trajectory.

Parallel opportunities:
- T023, T024, T025, and T026 are parallel-safe once the Stage 2 and Stage 3 implementation details are final, because they touch different docs.

Risks:
- The docs could overstate how much of Stage 3 direct-read debt is gone.
- The vision update could accidentally sound diagnostic or weaken the privacy posture.
- The roadmap could reintroduce work already completed by this mission.

Reviewer focus:
- Confirm each doc now starts from the real shipped baseline.
- Confirm the remaining boundary around issue `#6` is still explicit.
- Confirm the wording stays plain-English and non-diagnostic.
