# Data Model: Tool-loop live-trial tier (Phase 1)

No new persistent stores. The model extends two existing record types
(back-compatibly) and introduces in-memory orchestration types in the new
module. The session-log DuckDB schema is **unchanged** — tool calls land as
the existing `tool_call` step rows written by the harness (sole log writer).

## Extended entities

### `LiveTrialRunRecord` (`premura.harness.scoreboard`)

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `operator_model` | str | unchanged | |
| `driver_model` | str | unchanged | |
| `attempts_used` | int | unchanged | for the tool loop: **turns used** |
| `first_attempt_verdict` | Verdict | unchanged | tool loop: verdict of first `write_parser` content |
| `final_verdict` | Verdict | unchanged | tool loop: verdict of parser at loop end |
| `run_kind` | str | unchanged (`"live_trial"`) | both tiers are live trials |
| `tier` | str | **NEW**, default `"one_shot"` | `"tool_loop"` for this tier; the tier axis FR-007 compares on |

### `ScoreboardEntry` (`premura.harness.scoreboard`)

| Field | Type | Change | Notes |
|-------|------|--------|-------|
| `ts` | str | unchanged | |
| `operator_model` | str | unchanged | |
| `driver_model` | str | unchanged | |
| `attempts_used` | int | unchanged | turns used for tool-loop rows |
| `first_attempt_pass` | bool | unchanged | |
| `final_pass` | bool | unchanged | |
| `tier` | str | **NEW**, default `"one_shot"` | serialized in `to_json_line`; `from_json` defaults missing key to `"one_shot"` (legacy lines parse unchanged) |

**Validation rules**: `tier` is a non-empty string; the scoreboard file stays
append-only (no rewrite of prior lines — "alongside, never overwriting").

**Derived view**: `current_floor` groups by `(operator_model, tier)`; the CLI
floor table gains a `tier` column. Legacy rows appear under
`(model, "one_shot")`.

## New in-memory types (`premura.harness.live_trial_tool_loop`)

### `ToolRegistration` — the bounded tool contract instance (FR-003/FR-004)

| Field | Type | Notes |
|-------|------|-------|
| `name` | str | tool name exposed to the model |
| `description` | str | what the model is told it does |
| `parameters` | dict | JSON schema for the chat `tools` param |
| `handler` | callable | bounded capability; receives validated args + the trial context |

The registry is a `dict[str, ToolRegistration]`. **Capability bounds are
physical**: `read_context`'s handler resolves only against an explicit
allowlist (the scenario's source artifact + the contract files inside the
sandbox tree); there is no handler with access to the fixture manifest or any
ground-truth mapping, so C-005/FR-004 hold by construction at every turn.
Adding a tool = adding a registration (NFR-005).

First registered instances:

| Tool | May read/do | Guarantees |
|------|-------------|-----------|
| `read_context` | source artifact; allowlisted contract files (`CONTRACT.md`, `base.py`) inside the sandbox | served **whole** (FR-002); allowlist-only; manifest unreachable |
| `write_parser` | writes the module to the sandbox parser destination | sandbox-tree-only edit; first call's content snapshotted as the first-complete-parser |
| `run_ingest` | runs the real WP03 ingest subprocess over the scenario source against the sandbox warehouse | returns the runner envelope verbatim; never the manifest, never a grader verdict |

### `ToolLoopOperator` — implements the existing `Operator` protocol

| Field | Type | Notes |
|-------|------|-------|
| `source` | Path | scenario source (synthetic by default) |
| `model_id` | str | recorded as session `operator_model` |
| `max_turns` | int | from `LIVE_TRIAL_MAX_TURNS`, default 8 |
| `num_ctx` | int | from `LIVE_TRIAL_NUM_CTX`, default 16384 |
| `probe` | `_DrawerProbe` | reused rubric entry (scenario-parametric, FR-008) |
| `turns_used` | int | telemetry |
| `first_parser_code` | str | snapshot of first `write_parser` content |
| `transcript` | list | turn telemetry for session-log steps (harness writes) |

State transitions (loop protocol, FR-001/FR-005):

```
BRIEFED → (assistant turn) → TOOL_CALLS? → execute + append results → next turn
                            └ no tool calls → GATE (self-reconcile, manifest-blind)
GATE pass → DONE
GATE fail + turns remain → feedback message → next turn
turns exhausted → DONE (best-effort parser graded as-is)
```

### `ToolLoopOutcome` — returnable result (mirrors `LiveTrialOutcome`)

| Field | Type | Notes |
|-------|------|-------|
| `model_unavailable` | bool | endpoint unreachable (NFR-006) |
| `tool_calls_unsupported` | bool | **NEW state**: model template lacks tool support — explicit returnable outcome, never a crash |
| `record` | `LiveTrialRunRecord \| None` | with `tier="tool_loop"` |
| `turns` | list | per-turn telemetry |
| `final_result` / `first_attempt_result` | `LiveTrialResult \| None` | kept only for synthetic + `keep_sandboxes` |
| `persisted_run_dir` | `Path \| None` | None for any non-synthetic source (NFR-002) |

**Outcome invariant (NFR-006)**: every started trial ends in exactly one of
{complete graded record, `model_unavailable`, `tool_calls_unsupported`}.

## Relationships

```
run_live_trial_tool_loop()
  ├─ ToolLoopOperator ──implements──▶ live_trial.Operator (protocol, unchanged)
  ├─ OllamaDriver (reused, scenario goal)
  ├─ live_trial.run_live_trial_with_log (reused grading/run path, unchanged)
  ├─ _gate_parser / _DRAWER_PROBES (reused from live_trial_ollama)
  ├─ is_synthetic_source → persist_run / append_scoreboard (tier="tool_loop")
  └─ session_log.store (harness-written steps; schema unchanged)
```
