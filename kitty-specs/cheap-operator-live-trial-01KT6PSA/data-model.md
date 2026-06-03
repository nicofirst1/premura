# Data Model (Phase 1)

No warehouse schema changes. These are in-process structures and one on-disk
record format. All persisted artifacts live under git-ignored `data/live_trials/`.

## SelfReconciliationResult (in-process; FR-003)

The manifest-blind, raw-header honesty gate's output.

| Field | Type | Meaning |
| --- | --- | --- |
| `passed` | bool | true iff every raw source column is accounted for |
| `source_columns` | list[str] | columns read from the source file header/structure (ground set) |
| `accounted` | set[str] | columns that are a declared metric's source OR in `unmapped`/`skipped` |
| `unaccounted` | list[str] | `source_columns − accounted` (sorted); fed back to the operator on failure |

Rule: `passed == (unaccounted == [])`. Never references the fixture manifest.

## AttemptRecord (in-process; FR-010/FR-014)

One operator attempt within the retry loop.

| Field | Type | Meaning |
| --- | --- | --- |
| `index` | int | 1-based attempt number |
| `self_reconciliation` | SelfReconciliationResult | the in-loop gate outcome |
| `parser_error` | str \| null | import/parse/validate error, if any |

## LiveTrialRunRecord (persisted per run; FR-006/FR-014)

Written to `data/live_trials/<ts>-<model_slug>/` for a **synthetic-fixture** run
only (a real-data run writes nothing — FR-012/NFR-002).

| Field | Type | Meaning |
| --- | --- | --- |
| `operator_model` | str | operator model identity (FR-005) |
| `driver_model` | str | driver model identity (FR-005/FR-008) |
| `attempts_used` | int | number of operator attempts (≤ cap, NFR-003) |
| `first_attempt_verdict` | Verdict | grader verdict of attempt 1, un-nagged (FR-014) |
| `final_verdict` | Verdict | grader verdict of the final attempt (FR-004) |
| `run_kind` | str | `"live_trial"` (slice-one schema) |

Plus the kept files in the run dir: `session_log.duckdb` (the harness-written
log) and `verdict.json` (the final verdict, no ids/timestamps — slice-one
determinism). `Verdict` is the existing slice-one three-rule object
(`loaded` / `runtime_valid` / `honest_about_gaps`), unchanged.

## ScoreboardEntry (persisted append-only; FR-007/FR-011, NFR-005)

One JSON object per line in `data/live_trials/scoreboard.jsonl`.

| Field | Type | Meaning |
| --- | --- | --- |
| `ts` | str | ISO timestamp of the run (append time) |
| `operator_model` | str | capability tier identity |
| `driver_model` | str | driver identity |
| `attempts_used` | int | attempts to reach the final verdict |
| `first_attempt_pass` | bool | did attempt 1 pass all three grader rules (un-nagged) |
| `final_pass` | bool | did the final attempt pass all three rules |

Integrity (NFR-005): append-only; each line is independently parseable; N
sequential runs ⇒ N readable, ordered lines. A read groups by `operator_model` to
answer "current floor": which tiers reach `final_pass`, and how `first_attempt_pass`
vs `final_pass` trends over time (FR-011).

## State / lifecycle

`build sandbox → open session (operator/driver identities, run_kind) → operator
loop (attempt → self-reconcile → feedback) → grade attempt 1 → … → grade final →
(synthetic only) persist run record + append scoreboard → tear sandbox down`.
The harness is the sole session-log writer throughout (NFR-004).
