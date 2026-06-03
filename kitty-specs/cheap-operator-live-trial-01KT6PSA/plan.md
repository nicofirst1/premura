# Implementation Plan: Cheap-operator live trial (parser path)

**Branch**: `master` | **Date**: 2026-06-03 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/cheap-operator-live-trial-01KT6PSA/spec.md`

## Summary

Slice two of issue #10. Wire a **real, deliberately cheap** operator into the
merged session-log substrate's live-trial seam on the parser-only path: a local
model authors a parser into a sandbox, a **runtime-faithful self-reconciliation**
retry loop drives recovery without ever seeing the grading manifest, the
slice-one grader judges independently, and each run records a **first-attempt and
final** verdict to a kept run record plus an append-only **capability-floor
scoreboard**. Local-only, never blocks CI. The existing seed
`src/premura/harness/live_trial_ollama.py` is non-authoritative inspiration; the
spec is the source of truth.

## Technical Context

**Language/Version**: Python (project standard; see `pyproject.toml`)
**Primary Dependencies**: existing slice-one machinery (`premura.harness.sandbox`,
`ingest_runner`, `live_trial`, `grader`; `premura.session_log.store`); a local
model server (Ollama HTTP at `localhost:11434`), reached via stdlib `urllib` (no
new third-party client).
**Storage**: append-only JSONL scoreboard + per-run kept session-log DuckDB +
`verdict.json`, all under a git-ignored `data/live_trials/`.
**Testing**: `pytest`; a `live_trial`-marked test deselected by default
(`addopts = -m "not regression and not live_trial"`); default-collected **unit**
tests for the self-reconciliation helper and scoreboard (no model server needed).
**Target Platform**: local developer/agent machine (macOS/Linux).
**Project Type**: single (library + harness under `src/premura/`).
**Performance Goals**: bounded — attempt cap (default ≤3) and per-call timeout
(default ≤300 s) per NFR-003; not throughput-sensitive.
**Constraints**: never blocks CI (NFR-001); no PHI/real-data persistence
(NFR-002); harness is sole log writer (NFR-004); reuse slice-one machinery
unchanged (NFR-006); manifest never shown to operator (C-005).
**Scale/Scope**: one model per run, one data category (heart_rate), one fixture.

## Charter Check

*GATE: software-dev-default charter, compact mode.*

- **DIRECTIVE_010 (named follow-ups, no silent waivers):** honored — this mission
  closes the named D4/R5 follow-up; remaining #10 scope (frontier driver, sweep
  orchestration, full path) is explicitly OUT in spec.md, not silently dropped.
- **DIRECTIVE_036 (outside-boundary substitutes):** the fixed-goal driver is a
  named substitute for #10's frontier driver, declared in FR-008.
- **Agent-first / design-a-level-above (AGENTS.md, DOCTRINE.md):** the trial is
  agent-launched; the self-reconciliation rule is stated as a *rule* (reconstruct
  `honest_about_gaps` from raw columns), not an enumerated column list.
- **Standards-first:** N/A to harness wiring (no new vendor-field resolution; the
  operator *model* applies the parser contract at runtime).
- No charter violations. Complexity Tracking: empty.

## Project Structure

### Documentation (this feature)

```
kitty-specs/cheap-operator-live-trial-01KT6PSA/
├── plan.md              # this file
├── research.md          # Phase 0 — decisions already settled by spec/review
├── data-model.md        # Phase 1 — run record, scoreboard entry, recon result
├── quickstart.md        # Phase 1 — how an agent runs a trial + reads the floor
├── contracts/           # Phase 1 — operator/driver, self-reconciliation, scoreboard
└── tasks.md             # Phase 2 — created by /spec-kitty.tasks (NOT here)
```

### Source Code (repository root)

```
src/premura/harness/
├── live_trial.py            # EXISTING seam — wire real_model_operator/driver
│                            #   to delegate (FR-013); otherwise unchanged (NFR-006)
├── live_trial_ollama.py     # operator/driver + retry loop + run entry (the deliverable)
├── self_reconcile.py        # NEW — raw-header honest_about_gaps twin (FR-003), shared helper
└── scoreboard.py            # NEW — append-only JSONL run record + scoreboard (FR-006/007/011)

tests/
├── test_self_reconcile.py   # default-collected unit test (no model server)
├── test_scoreboard.py       # default-collected unit test (append/read/integrity)
└── test_live_trial_ollama.py# live_trial-marked, model-server gated (end-to-end)

data/live_trials/            # git-ignored kept runs + scoreboard.jsonl (NFR-002)
```

**Structure Decision**: single-project layout under `src/premura/harness/`. New
seams are small, single-purpose modules so the self-reconciliation helper and the
scoreboard are unit-testable in the **default** suite without a model server,
while only the end-to-end operator run is gated behind `live_trial`.

## Phasing (build order)

1. **Self-reconciliation helper** (`self_reconcile.py`) — pure, manifest-blind,
   raw-header vs `declared ∪ loaded`; the answer-key-free `honest_about_gaps`
   twin. Default unit-tested. *(FR-003; the loophole-closed raw-columns version.)*
2. **Scoreboard + run record** (`scoreboard.py`) — append-only JSONL, kept
   session log + verdict, first-attempt & final fields, real-data → no-persist
   guard. Default unit-tested. *(FR-006/007/011/012, NFR-002/005.)*
3. **Operator/driver + loop + grading both attempts** (`live_trial_ollama.py`) —
   cheap operator with the step-1 helper in its retry loop; grade attempt-1 and
   final via the unchanged slice-one grader; persist via step 2. *(FR-001/002/
   005/008/009/010/014, C-005.)*
4. **Close the deferred seam** — wire `live_trial.real_model_operator/driver` to
   delegate to step 3; gated end-to-end test. *(FR-013; NFR-001/004/006.)*

## Complexity Tracking

*No charter violations; section intentionally empty.*
