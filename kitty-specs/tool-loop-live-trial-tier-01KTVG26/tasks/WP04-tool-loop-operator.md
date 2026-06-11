---
work_package_id: WP04
title: ToolLoopOperator and tier entry point
dependencies:
- WP01
- WP03
requirement_refs:
- C-001
- FR-005
- FR-006
- FR-007
- FR-008
- NFR-002
- NFR-004
- NFR-006
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T012
- T013
- T014
- T015
agent: "claude:fable:reviewer:reviewer"
shell_pid: "57356"
history:
- date: '2026-06-11T14:19:42Z'
  action: created
  by: /spec-kitty.tasks
authoritative_surface: src/premura/harness/live_trial_tool_loop.py
execution_mode: code_change
owned_files:
- src/premura/harness/live_trial_tool_loop.py
- tests/test_live_trial_tool_loop.py
tags: []
---

# WP04 — ToolLoopOperator and tier entry point

## Objective

Create `src/premura/harness/live_trial_tool_loop.py` — the mission's core: the
multiturn agent loop (`ToolLoopOperator`, implementing the existing
`live_trial.Operator` protocol) and the tier entry point
`run_live_trial_tool_loop(...)` that records **two independent grader
verdicts** (first written parser, final parser) as a **tier-tagged**
(`tier="tool_loop"`) result alongside the one-shot floor. Spec FR-005/006/
007/008, NFR-002/004/006; SC-001/SC-005. Binding behavior:
`contracts/tool-loop-tier.md` §§3–5.

**Reuse, don't fork (NFR-004)**: this module is new orchestration over
existing machinery. Grading goes through `live_trial.run_live_trial_with_log`
(unchanged); the gate is `live_trial_ollama._gate_parser` (unchanged); tools/
brief/client come from WP03's `tool_loop_contract`; persistence goes through
`scoreboard.persist_run`/`append_scoreboard` with WP01's `tier` field.

## Context you need

- Read first: mission `spec.md` (FR-005..008, acceptance scenarios 1–3, 6),
  `research.md` §R-3/§R-4/§R-5, `data-model.md` (ToolLoopOperator /
  ToolLoopOutcome tables + state machine), `contracts/tool-loop-tier.md`.
- Study `src/premura/harness/live_trial_ollama.py::run_live_trial_ollama`
  end-to-end — your entry point mirrors its flow exactly (final run →
  attempt records into the kept log → independent first-parser grade via a
  fixed-code operator → record assembly → synthetic-only persist → conditional
  sandbox teardown). Reuse `_FixedCodeOperator` (import it) for the
  first-parser grade; reuse `OllamaDriver`, `is_synthetic_source`,
  `_teardown_kept_sandbox`, `_print_verdict` where they fit.
- From WP03 (`premura.harness.tool_loop_contract`): `ollama_chat`,
  `ToolCallsUnsupportedError`, `TrialContext` factory, `default_tool_registry`,
  `registry_as_chat_tools`, `assemble_brief`, `LIVE_TRIAL_NUM_CTX` parsing.
- From WP01: `LiveTrialRunRecord(..., tier="tool_loop")`,
  `ScoreboardEntry(..., tier="tool_loop")`.
- Key protocol fact: `Operator.operate(sandbox, goal)` is called by
  `live_trial._drive_live_trial` AFTER the sandbox is built and BEFORE the
  ingest/grade steps. Your loop therefore runs **inside** `operate()` — the
  whole chat conversation happens there, editing only the sandbox tree. The
  harness remains the sole session-log writer; like the one-shot module, you
  may append per-turn telemetry to the kept log AFTER the run via
  `store.record_live_trial_attempt` (post-run, same pattern
  `run_live_trial_ollama` uses — see its `record_live_trial_attempt` block).
- Env knobs (contract §6): `LIVE_TRIAL_MAX_TURNS` default 8 (this module's
  single home); `LIVE_TRIAL_NUM_CTX` imported from WP03's module.

## Loop protocol (implement exactly — contract §3, data-model state machine)

```
operate(sandbox, goal):
  context  = TrialContext(sandbox, source, allowlist)
  registry = default_tool_registry()
  messages = [system/brief]            # assemble_brief(probe, goal, source)
  for turn in 1..max_turns:
      reply = chat(messages, tools=registry_as_chat_tools(registry))
      if reply has tool_calls:
          for call in tool_calls (in order):
              result = dispatch via registry        # unknown name / bad args →
              append role:"tool" message            #   corrective string, turn
          continue                                   #   still consumed
      # no tool calls → working phase over for this round:
      gate = _gate_parser(sandbox_src, source, probe) # manifest-blind
      if gate.passed: break
      if turns remain: append gate feedback as user message; continue
  # loop ends: parser-on-disk (or none) is what gets graded
```

- One assistant response = one turn, ALWAYS — malformed/unknown calls consume
  their turn with a corrective tool message (spec edge case "malformed tool
  call").
- Snapshot the FIRST `write_parser` call's `code` argument into
  `self.first_parser_code` (FR-006) — the loop intercepts the dispatch result
  for that one tool name to capture it (keep the WP03 handler stateless).
- Record per-turn telemetry in `self.attempts` reusing the one-shot
  `AttemptRecord` shape (index, self_reconciliation, parser_error, code) so
  the post-run `record_live_trial_attempt` call works unchanged: gate rounds
  produce full records; you may attach the gate's `SelfReconciliationResult`
  to the turn that triggered it.

## Subtasks

### T012 — Failing loop tests via injectable fake chat backend

**Purpose**: the contract pinned before code (DIRECTIVE_034); the fake backend
is the outside-boundary substitute (DIRECTIVE_036) standing in for the local
model server, exactly as WP05 of the substrate mission faked the operator.

**Steps**: create `tests/test_live_trial_tool_loop.py`:
1. Build a `FakeChatBackend`: a callable scripted with a list of canned
   replies (each either `{"tool_calls": [...]}` or `{"content": "done"}`),
   injected through the module's chat seam (constructor/parameter — design the
   seam in T013; the test defines it). It must capture every request
   (messages, tools) for assertions.
2. Failing tests, all driving the PUBLIC `run_live_trial_tool_loop(...)` over
   the committed synthetic observation fixture with a temp `runs_dir` and
   scoreboard `path` (never `data/`):
   - **Happy path** (SC-001): script read_context(source) → write_parser(a
     KNOWN-GOOD parser body — lift the committed reference parser the seam
     test installs, see `tests/test_live_trial_seam.py` for its source path) →
     run_ingest → no-tool-call reply. Assert: outcome has a record with
     `tier == "tool_loop"`; both verdicts present; final verdict PASSES;
     scoreboard line written with `tier: "tool_loop"`; turns_used ≤ cap.
   - **First-snapshot** (FR-006): script TWO write_parser calls (bad code
     then good); assert `first_attempt_verdict` grades the FIRST body (FAIL)
     while `final_verdict` grades the second (PASS) — regression direction
     covered in WP05.
   - **Gate feedback loop**: script a parser that fails self-reconcile
     (silently drops a column), then a no-tool-call reply, then (after the
     fed-back gate failure) a corrected write_parser + done. Assert the gate
     feedback message reached the conversation (inspect captured requests) and
     the trial still ends graded.
   - **Cap exhaustion** (FR-005): script replies that never stop calling
     tools; assert the loop stops at `LIVE_TRIAL_MAX_TURNS` (monkeypatch env
     to a small cap), the trial ends with a complete graded record (SC-005),
     and never raises.
   - **Turn accounting**: a scripted unknown-tool call consumes a turn and
     produces a corrective tool message in the next request's history.
3. Run: all red (module absent).

### T013 — `ToolLoopOperator`

**Purpose**: the loop itself (FR-005, FR-008).

**Steps**:
1. Class fields per `data-model.md`: `source`, `model_id`, `max_turns`,
   `num_ctx`, `probe` (default observation via `_resolve_drawer_probe` /
   passed in — scenario-parametric, NO drawer branch in the loop body),
   `turns_used`, `first_parser_code`, `attempts`, plus the injectable chat
   backend seam (default: real `ollama_chat`).
2. Implement `operate(sandbox, goal)` per the protocol block above. Mind:
   - tool-call arguments arrive as dict or JSON-string depending on backend —
     normalize defensively; an unparseable argument set is a malformed call
     (corrective message, turn consumed);
   - `ToolCallsUnsupportedError`/`OllamaUnavailableError` must propagate OUT
     of `operate` — the entry point maps them to outcome states (T014); never
     swallow them into a half-graded trial;
   - the loop edits ONLY the sandbox tree (tools are sandbox-bounded by WP03);
     it never opens the session log (FR-021 inheritance).
3. Docstring: state the boundaries (sole-log-writer inheritance, C-005 via the
   registry, cap semantics, what propagates).

**Validation**: T012 loop-mechanics tests green (happy path may still need T014).

### T014 — `run_live_trial_tool_loop` + `ToolLoopOutcome` + tier persistence

**Purpose**: the tier's scored, persisted result (FR-006, FR-007, NFR-002,
NFR-006).

**Steps**:
1. `ToolLoopOutcome` dataclass per `data-model.md` (note the NEW
   `tool_calls_unsupported: bool` beside `model_unavailable`).
2. `run_live_trial_tool_loop(*, model=DEFAULT_MODEL, source=None,
   max_turns=None, repo_root=_REPO_ROOT, operator=None, keep_sandboxes=False,
   scenario=None) -> ToolLoopOutcome`, mirroring `run_live_trial_ollama`:
   - resolve scenario → probe → source (defaults: observation, scenario
     source);
   - default-construct the operator (availability probe like the one-shot:
     unreachable → `ToolLoopOutcome(model_unavailable=True)`);
   - final run via `live_trial.run_live_trial_with_log` (the operator's whole
     loop runs inside it); catch `OllamaUnavailableError` →
     `model_unavailable`, `ToolCallsUnsupportedError` →
     `tool_calls_unsupported` (both: nothing persisted, sandboxes already
     torn down by the run path or never built);
   - post-run: append per-turn `record_live_trial_attempt` rows to the kept
     log (same block shape as the one-shot module);
   - first-parser grade: `_FixedCodeOperator(first_parser_code, model=...)`
     through the same path. Empty `first_parser_code` (no write_parser ever)
     still grades — the machinery's absent-parser path yields the
     deterministic FAIL (SC-005; spec scenario 6); do not special-case it
     beyond passing the empty string through;
   - assemble `LiveTrialRunRecord(..., attempts_used=turns_used,
     tier="tool_loop")`; persist via `persist_run(..., is_synthetic=
     is_synthetic_source(source))`; append `ScoreboardEntry(...,
     tier="tool_loop")` ONLY when synthetic (NFR-002);
   - `keep_sandboxes` honored only for synthetic sources (same guard +
     comment rationale as the one-shot module: a kept sandbox holds parsed
     real data).
3. The outcome invariant (NFR-006): structure the function so every exit is
   one of {record, model_unavailable, tool_calls_unsupported} — no bare
   raise paths after the trial starts.

**Validation**: T012 fully green, including persistence assertions.

### T015 — CLI + module surface

**Purpose**: runnable per quickstart.md; bounded public API.

**Steps**:
1. `_main()`: print model/source/cap header, run, then per-verdict lines via
   the imported `_print_verdict`; exit codes: `0` ran, `2` model unavailable,
   `3` tool calls unsupported (quickstart.md documents these). Mirror the
   one-shot `_main`'s teardown-in-finally discipline.
2. `__all__`: the public names (`ToolLoopOutcome`, `ToolLoopOperator`,
   `run_live_trial_tool_loop`, `LIVE_TRIAL_MAX_TURNS`...).
3. Module docstring: tier purpose (headroom above the one-shot floor, never a
   replacement — spec premise), boundaries (local-only, synthetic-only
   persistence, never-blocks-CI), run instructions (the two quickstart
   commands).
4. Full gates: `uv run pytest -q` (entire default suite — prove NFR-004's
   "one-shot untouched" by zero failures elsewhere), `ruff check` +
   `ruff format --check`, `mypy` on owned files.

**Validation**: `uv run python -m premura.harness.live_trial_tool_loop`
exits 2 cleanly with no Ollama running (manual check, not a committed test).

## Definition of Done

- [ ] Loop implements contract §3 exactly: one response = one turn; malformed
      calls consume turns; gate-fail feedback continues; cap always
      terminates into a graded record.
- [ ] Two independent verdicts per trial; first = first `write_parser`
      content; absent parser → deterministic FAIL for both (SC-005).
- [ ] Record + scoreboard line carry `tier="tool_loop"`; non-synthetic
      sources persist nothing and tear down always (NFR-002).
- [ ] All three outcome states reachable and returned, never raised (NFR-006).
- [ ] No copied machinery — grading/persistence/gate all imported (NFR-004);
      full default suite green with zero edits outside `owned_files`.

## Risks / notes for the reviewer

- Reviewer: trace FR-006 from snapshot to scoreboard — the first-parser grade
  must run through the SAME `run_live_trial_with_log` path as the final (not
  a shortcut gate call), or the two verdicts aren't comparable.
- Reviewer: verify `ToolCallsUnsupportedError` propagates from inside
  `operate()` (mid-conversation, not just turn 1) to the
  `tool_calls_unsupported` outcome with sandboxes torn down.
- Reviewer: confirm the loop body contains no `if scenario.name == ...` /
  `if tool_name == ...` ladders beyond registry dispatch (DOCTRINE altitude;
  NFR-005).
- The chat-seam design (injectable backend) is this WP's API decision — keep
  it the same seam WP03's client exposes so WP05's edge tests reuse it.

## Activity Log

- 2026-06-11T18:12:47Z – claude:fable:implementer:implementer – shell_pid=40987 – Started implementation via action command
- 2026-06-11T18:29:25Z – claude:fable:implementer:implementer – shell_pid=40987 – Ready for review: ToolLoopOperator + run_live_trial_tool_loop landed on lane-a (23df59f); 8 default-suite fake-backend tests; full suite 1100 passed; CLI exit-2 manually verified
- 2026-06-11T18:30:04Z – claude:fable:reviewer:reviewer – shell_pid=57356 – Started review via action command
- 2026-06-11T18:38:10Z – claude:fable:reviewer:reviewer – shell_pid=57356 – Review passed: ToolLoopOperator implements contract §3 exactly (one response = one turn incl. malformed/unknown calls, gate-fail feedback re-enters, cap always terminates into a graded record); FR-006 first-parser snapshot grades through the same run path; tier=tool_loop on record + scoreboard line; all three NFR-006 outcome states returnable with sandbox teardown verified; warehouse-clear in operate() finally is correct and necessary (loader dedupe would falsely FAIL the graded ingest); CLI exit 2 verified live; full suite 1100 passed; ruff/format/mypy clean; commit 23df59f touches only owned files.
