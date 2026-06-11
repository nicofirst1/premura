---
work_package_id: WP05
title: Spec edge-case fixtures and gated real-model test
dependencies:
- WP04
requirement_refs:
- C-004
- C-005
- NFR-002
- NFR-003
- NFR-006
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planned on master; implemented in the lane worktree allocated from lanes.json (after WP04 in the same dependency chain); merged back to master via the spec-kitty merge workflow.
subtasks:
- T016
- T017
- T018
history:
- date: '2026-06-11T14:19:42Z'
  action: created
  by: /spec-kitty.tasks
authoritative_surface: tests/
execution_mode: code_change
owned_files:
- tests/test_live_trial_tool_loop_edges.py
- tests/test_live_trial_tool_loop_real.py
tags: []
---

# WP05 — Spec edge-case fixtures and gated real-model test

## Objective

Every edge case the spec **names** gets an end-to-end fixture through the real
public path (`run_live_trial_tool_loop`), per the charter's whole-story
fidelity gate (drift dimension D7: "an edge case the spec names but no
end-to-end fixture exercises is a coverage defect"). Plus the
`live_trial`-marked real-model test module that exercises the tier against an
actual local model — never collected by default (NFR-003, SC-004). This WP is
tests-only: it owns NO production files; if a fixture exposes a production
bug, reject/flag back to WP04 rather than patching out of scope.

## Context you need

- Read first: mission `spec.md` §"Edge cases" + acceptance scenarios 3–6 —
  that list IS your checklist; `contracts/tool-loop-tier.md` §4 (outcome
  table); the charter's Fidelity Gates section (D7 rationale).
- WP04's deliverables you build on: the injectable fake chat backend seam and
  the test patterns in `tests/test_live_trial_tool_loop.py` (read it first;
  reuse its backend helper by importing from it if exported, otherwise build
  the same shape — do NOT edit that file, WP04 owns it).
- The existing edge-case suite style: `tests/test_live_trial_edge_cases.py`
  (the one-shot equivalents — your structural reference).
- Marker config: `pyproject.toml` already excludes `live_trial` via `addopts`
  (`-m "not regression and not live_trial"`); the marker is registered. You
  add NO config — just mark the module.
- Precedent for the gated test: the `ollama_available()` skip pattern in the
  existing gated one-shot test (find it: `grep -rn "live_trial" tests/`).

## Subtasks

### T016 — E2E edge fixtures: loop-behavior edges

**Purpose**: spec edge cases "regression across turns", "malformed tool
call", "tool misuse", "no parser ever produced" — each end-to-end through
`run_live_trial_tool_loop` with a scripted fake backend, default suite, no
model server.

**Steps**: create `tests/test_live_trial_tool_loop_edges.py`:
1. **Regression across turns** (spec edge case 1; FR-006): script first
   write_parser = the KNOWN-GOOD reference parser body, then a SECOND
   write_parser = a broken body, then done. Assert
   `first_attempt_verdict["passed"] is True` and
   `final_verdict["passed"] is False` and both are visible on the persisted
   record + scoreboard line (temp paths) — regression is *reported*, neither
   hidden nor best-of'd.
2. **Tool misuse / manifest refusal e2e** (spec edge case 2; FR-004): script a
   `read_context` call for `fixture_fields.yaml` (and one absolute-path
   escape). Assert the refusal string came back as that call's tool message in
   the captured next-request history, the manifest content appears NOWHERE in
   any captured request (assert a known manifest substring is absent across
   the whole transcript), and the trial still completes graded.
3. **Malformed tool call** (spec edge case 3): script a tool call with an
   unknown name and one with unparseable arguments. Assert each consumed a
   turn (turns_used reflects them), a corrective message was fed back, no
   exception escaped.
4. **No parser ever produced** (spec edge case 4 / scenario 6; SC-005):
   script only read_context calls then done — no write_parser. Assert the
   outcome is a COMPLETE record (not an exception, not a half-record), both
   verdicts are deterministic FAILs, and (synthetic source) the record
   persisted + scoreboard appended.

**Validation**: all green in the default suite; total runtime stays in the
existing suite's interactive range (these spawn real sandboxes + subprocess
ingest runs — reuse the committed synthetic fixture, keep scripts short; if a
case doesn't need an ingest, script no run_ingest call).

### T017 — E2E outcome edges: unavailable, unsupported, real-source no-persist

**Purpose**: contract §4's outcome table (NFR-002, NFR-006; SC-003) and spec
acceptance scenarios 3–4.

**Steps** (same file):
1. **Model unavailable**: backend raises `OllamaUnavailableError` on first
   call → outcome `model_unavailable=True`, `record is None`, nothing
   persisted (assert empty temp runs_dir + absent scoreboard file).
2. **Tool calls unsupported — mid-conversation**: backend returns one valid
   reply then raises `ToolCallsUnsupportedError` → outcome
   `tool_calls_unsupported=True`, nothing persisted, no kept sandbox dirs left
   (assert the sandbox parent temp area is clean — mirror how existing seam
   tests locate sandbox roots).
3. **Real-source no-persist** (SC-003; spec scenario 3): copy the synthetic
   CSV to a temp path (a non-registered path is treated as REAL by
   `is_synthetic_source` — that is the point), run a happy-path script, pass
   `keep_sandboxes=True`. Assert: outcome HAS a record (the trial ran),
   `persisted_run_dir is None`, scoreboard file never created, AND both kept
   results are `None` / sandboxes torn down despite the flag (the
   keep-sandboxes-synthetic-only rule).
4. **Default-collection assertion** (SC-004 evidence): one test asserting the
   real-model module (T018) is excluded by default — run
   `pytest --collect-only -q tests/test_live_trial_tool_loop_real.py` via
   `subprocess` with default addopts and assert zero collected, OR assert the
   marker exclusion config directly (`-m "not ... live_trial"` in
   `pyproject.toml`). Choose the boundary-crossing form (subprocess) — it
   pins the actual behavior, not the config text.

**Validation**: green by default; zero artifacts leak into `data/` (use temp
dirs everywhere; assert post-conditions).

### T018 — Gated real-model test module

**Purpose**: the tier's real-model proof, runnable locally, never in CI
(NFR-003).

**Steps**: create `tests/test_live_trial_tool_loop_real.py`:
1. `pytestmark = pytest.mark.live_trial` at module level.
2. Skip guard: `ollama_available()` false → `pytest.skip` (import from
   `live_trial_ollama` — same guard the existing gated test uses).
3. One test: `run_live_trial_tool_loop()` over the default synthetic
   observation scenario with the real default model. Assert ONLY harness
   honesty, never model capability (a cheap model may legitimately FAIL —
   that's a floor finding, not a test failure):
   - outcome is exactly one of the three contract states;
   - if a record exists: both verdicts present, `tier == "tool_loop"`,
     `attempts_used >= 1`, scoreboard line appended (temp path), kept-run
     teardown respected;
   - if `tool_calls_unsupported`: that is a legitimate outcome for a
     tool-incapable model — assert nothing persisted and pass with an
     explanatory message.
4. A second test for the intake scenario (FR-008 symmetry), same posture.
5. Run locally once if Ollama is available and note the observed outcome in
   the WP report (model, turns, verdicts) — this is plan risk R1's evidence.
   If Ollama is not available on the implementing machine, say so explicitly
   in the report (the default suite must be green regardless).

**Validation**: `uv run pytest -q` collects NOTHING from this module;
`uv run pytest -q -m live_trial tests/test_live_trial_tool_loop_real.py`
runs or skips cleanly. Gates: ruff + format + mypy on owned files.

## Definition of Done

- [ ] Every spec-named edge case has an e2e fixture through
      `run_live_trial_tool_loop` (D7): regression, misuse/manifest, malformed,
      no-parser, unavailable, unsupported, real-source no-persist.
- [ ] Manifest-absence asserted across the full captured transcript (C-005
      witnessed end-to-end, not just at the WP03 unit level).
- [ ] SC-003 and SC-004 each have a committed evidence test (the ownership
      table in tasks.md names this WP).
- [ ] Real-model module excluded by default, runnable via `-m live_trial`,
      asserts harness honesty not model capability.
- [ ] Tests-only diff: zero production files touched; default suite green.

## Risks / notes for the reviewer

- Reviewer: the no-parser-ever case is the class of defect that crashed a
  prior mission's integrated run (a spec-named edge nobody drove e2e) — walk
  that test's path personally: it must reach a persisted FAIL record, not an
  exception.
- Reviewer: in the real-source test, verify the temp copy genuinely classifies
  as non-synthetic (resolve-path semantics) — a test accidentally using the
  registered fixture path would silently test the wrong branch (presence vs
  absence, charter fidelity gate).
- If any fixture exposes a WP04 bug: REJECT WP04 / flag it with the failing
  fixture attached; do not patch production from this WP (ownership).
