# Implementation Plan: Tool-loop live-trial tier

**Branch**: `master` (planning base and merge target; `branch_matches_target: true`)
**Date**: 2026-06-11 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/tool-loop-live-trial-tier-01KTVG26/spec.md`

## Summary

Add a multiturn, tool-using live-trial **tier** as new orchestration over the
shipped harness machinery (sandbox, ingest runner, grader, session-log store,
scoreboard). A distinct `ToolLoopOperator` drives a local Ollama model through
the **chat endpoint with native tool-calling**: the model works from one
coherent brief (the proven curated contract surface inlined; full contract
files servable whole via a READ tool), interacts only through a registered tool
contract (`read_context`, `write_parser`, `run_ingest` — the fixture manifest
physically unreachable), and stops at an env-overridable turn cap. Each trial
records two independent grader verdicts (first written parser, final parser)
as a **tier-tagged** result (`tier: "tool_loop"`) alongside the one-shot floor
(`tier: "one_shot"`), comparable per operator model. The one-shot path, its
scoring, and all containment guarantees (local-only endpoint, synthetic-only
persistence, `live_trial` marker) are unchanged.

## Technical Context

**Language/Version**: Python 3.11+ (charter-pinned; no new language)
**Primary Dependencies**: stdlib `urllib` against local Ollama `/api/chat`
(no third-party HTTP client — same posture as the one-shot path); existing
harness modules (`live_trial`, `live_trial_ollama`, `sandbox`, `grader`,
`session_log.store`, `scoreboard`, `self_reconcile`, `scenario_registry`)
**Storage**: existing per-sandbox session-log DuckDB + append-only
`data/live_trials/scoreboard.jsonl` (extended with a back-compatible `tier`
field); no new stores
**Testing**: pytest; default-suite tests drive the loop through a deterministic
fake chat backend (outside-boundary substitute, DIRECTIVE_036); the real-model
test is `@pytest.mark.live_trial`-gated and never collected by default
**Target Platform**: macOS local-first (charter); pure-local execution
**Project Type**: single project (existing `src/premura` layout)
**Performance Goals**: a synthetic tool-loop trial completes within the turn
cap (default 8) with bounded per-call timeouts (same 300 s call timeout as the
one-shot path); no default-suite test invokes a model
**Constraints**: local-only model endpoint (inherits `_validated_ollama_url`);
real-source runs persist nothing; manifest unreachable through any tool;
no CI/default-gate change
**Scale/Scope**: one new harness module + one back-compatible scoreboard
extension + tests; ~3–5 files touched

### Decisions carried from spec discovery + plan interrogation (confirmed)

1. **Transport**: Ollama `/api/chat` with **native tool-calling** (`tools`
   param; parse `message.tool_calls`). History lives in the `messages` array;
   `options.num_ctx` pinned via `LIVE_TRIAL_NUM_CTX` (default 16384). A model
   whose template lacks tool support yields an explicit returnable
   `tool_calls_unsupported` outcome — a rule ("the tier requires a
   tool-capable model"), not a model list.
2. **Brief serving (FR-002)**: the brief inlines the same curated contract
   surface the one-shot tier uses (proven to carry a capable local model to a
   pass); `read_context` additionally serves `CONTRACT.md` / `base.py` whole —
   never truncated. Budget is accounted: brief + tool schemas + history fit
   the pinned `num_ctx`.
3. **Operator placement**: new module `src/premura/harness/live_trial_tool_loop.py`
   with `ToolLoopOperator` (implements the existing `Operator` protocol) and
   `run_live_trial_tool_loop(...)` mirroring `run_live_trial_ollama(...)`.
   One-shot `OllamaOperator` untouched. Shared pieces (`_DrawerProbe` rubric,
   `_gate_parser`, `is_synthetic_source`, persist/scoreboard) are **imported**,
   never copied (NFR-004; smallest-viable-diff).
4. **Loop protocol**: standard agent loop — each assistant response is one
   turn; tool calls are executed and results appended; a response with **no
   tool calls** ends the working phase. The harness then runs the manifest-blind
   self-reconcile gate; on failure with turns remaining, the gate feedback goes
   back as a message and the loop continues; on pass or cap exhaustion the
   trial ends. Cap: `LIVE_TRIAL_MAX_TURNS`, default 8.
5. **Verdict shape (FR-006)**: "first complete parser" = the content of the
   **first `write_parser` call**; snapshotted and graded independently through
   the same machinery (fixed-code operator), exactly as one-shot grades
   attempt 1. If no `write_parser` ever occurs, the first verdict is the
   deterministic FAIL the machinery already produces for an absent parser
   (empty-warehouse FAIL path), so every trial stays gradeable (NFR-006).
6. **Tier tagging (FR-007)**: `LiveTrialRunRecord` and `ScoreboardEntry` gain a
   `tier` field, default `"one_shot"`; `from_json` defaults a missing key to
   `"one_shot"` so existing scoreboard lines parse unchanged (append-only —
   nothing rewritten). `current_floor` groups by `(operator_model, tier)`.
7. **FR-009 (renamed-field rule)**: the existing `self_reconcile` gate already
   fails a consumed-but-undeclared column; this mission (a) sharpens the
   brief's contract line to state the renamed-field case explicitly and
   (b) lands the committed deterministic fixture test proving the gate fails
   it (SC-007). If the test exposes a gate hole, the gate is fixed — the test
   defines the contract first (DIRECTIVE_034).

## Charter Check

*GATE: evaluated pre-Phase-0 and re-checked post-Phase-1 — PASS (no violations).*

- **Design altitude (Directive 9 / DOCTRINE.md)**: the tool contract is a
  registry rule (name → bounded handler + schema); a new tool or drawer is a
  registration, not a loop-body branch. The drawer-probe rubric is reused, not
  forked. No enumerated model list — tool capability is probed, and
  incapability is a returnable outcome. ✅
- **Risk boundaries (Directive 8)**: local-first/offline — the only network
  touch is the already-guarded localhost Ollama endpoint; no live API scraping;
  PHI hygiene — real sources persist nothing, sandboxes torn down, no PHI in
  tests/commits (synthetic fixtures only). ✅
- **Test-first (DIRECTIVE_034) + black-box (DIRECTIVE_036)**: default-suite
  tests drive `run_live_trial_tool_loop` through its public interface with a
  fake chat backend (outside-boundary substitute for the local model server,
  same pattern WP05 used for the one-shot path); assertions target observable
  outputs (outcome states, scoreboard lines, session-log rows, verdicts). ✅
- **Quality gates**: ruff + mypy + `pytest -q` green before handoff; the
  `live_trial` marker keeps real-model tests out of the default suite. ✅
- **Fidelity gates**: every spec-enumerated edge case (regression-across-turns,
  tool misuse, malformed tool call, no-parser-ever, unavailable backend,
  tool-incapable model) gets an end-to-end fixture through the public entry
  point (drift dimension D7); measurable NFR/SC ownership is assigned at
  `/spec-kitty.tasks`. Post-merge live-doc reconciliation (D6) is the
  orchestrator's close-out, not a pre-merge WP writing the future. ✅

## Project Structure

### Documentation (this feature)

```
kitty-specs/tool-loop-live-trial-tier-01KTVG26/
├── plan.md              # This file
├── research.md          # Phase 0 output
├── data-model.md        # Phase 1 output
├── quickstart.md        # Phase 1 output
├── contracts/
│   └── tool-loop-tier.md  # Tool contract + loop protocol + record shapes
└── tasks.md             # Phase 2 output (/spec-kitty.tasks — NOT created here)
```

### Source Code (repository root)

```
src/premura/harness/
├── live_trial.py             # UNCHANGED seam (Operator/Driver protocols, run path)
├── live_trial_ollama.py      # one-shot tier — behavior unchanged except the
│                             #   sharpened renamed-field prompt line (FR-009);
│                             #   shared helpers imported by new modules (no copies)
├── tool_loop_contract.py     # NEW: chat client (+ToolCallsUnsupportedError),
│                             #   ToolRegistration + registry + 3 bounded handlers,
│                             #   brief assembler with loud budget check
├── live_trial_tool_loop.py   # NEW: ToolLoopOperator (agent loop),
│                             #   run_live_trial_tool_loop, ToolLoopOutcome, CLI
├── scoreboard.py             # tier field on LiveTrialRunRecord/ScoreboardEntry
│                             #   (back-compatible default "one_shot");
│                             #   current_floor groups by (model, tier)
└── self_reconcile.py         # unchanged unless SC-007's test exposes a hole

tests/
├── test_scoreboard.py                    # extended: tier round-trip + legacy parse
├── test_self_reconcile_renamed_field.py  # NEW: SC-007 fixture (FR-009)
├── test_tool_loop_contract.py            # NEW: registry bounds, brief invariants
├── test_live_trial_tool_loop.py          # NEW: fake-backend loop e2e
├── test_live_trial_tool_loop_edges.py    # NEW: spec edge-case fixtures (D7)
└── test_live_trial_tool_loop_real.py     # NEW: live_trial-marked, default-excluded
```

**Structure Decision**: single-project layout. Refined at `/spec-kitty.tasks`
(recorded in tasks.md, DIRECTIVE_010): the new code splits into **two**
modules — `tool_loop_contract.py` (pure, deterministic contract surface:
client, tool registry, brief) and `live_trial_tool_loop.py` (orchestration:
loop, outcomes, entry point) — for modularity and disjoint WP ownership. No
new packages, stores, or CLI surfaces beyond the module `_main`.

## Complexity Tracking

No charter violations to justify. The only structural addition is one new
module; the scoreboard change is an additive, back-compatible field.

## Open risks (each resolves to a WP task, non-goal, or acceptance check at /spec-kitty.tasks)

| # | Risk | Planned resolution |
|---|------|--------------------|
| R1 | Native tool-call quality varies per local model (malformed/absent calls) | Malformed-call feedback path is a spec edge case → owned end-to-end fixture; gated real-model test observes actual behavior. |
| R2 | `num_ctx` default too small for brief + history at cap | Budget accounting check in the brief assembler (fails loudly, never truncates) → WP task + test. |
| R3 | `current_floor` grouping change could mis-render existing one-shot rows | Legacy-line parse test (missing `tier` → `one_shot`) → WP task. |
| R4 | SC-007 test may expose a `self_reconcile` gate hole | Test-first: fixture lands first; gate fixed only if red (DIRECTIVE_034). |

## Phase status

- Phase 0 (research): complete — [research.md](research.md)
- Phase 1 (design & contracts): complete — [data-model.md](data-model.md),
  [contracts/tool-loop-tier.md](contracts/tool-loop-tier.md),
  [quickstart.md](quickstart.md)
- Phase 2 (tasks): NOT started — run `/spec-kitty.tasks`
