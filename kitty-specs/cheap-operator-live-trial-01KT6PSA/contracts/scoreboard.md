# Contract: kept run record + capability-floor scoreboard (FR-006/007/011/012, NFR-002/005)

## Surface

```
persist_run(run_record, *, kept_session_log, verdict, is_synthetic) -> Path | None
append_scoreboard(entry) -> None
read_scoreboard() -> list[ScoreboardEntry]
current_floor(entries) -> mapping[model -> {first_attempt_pass, final_pass, runs, last_ts}]
```

## Rules

- **Location**: everything under git-ignored `data/live_trials/`. `persist_run`
  writes `data/live_trials/<ts>-<model_slug>/{session_log.duckdb, verdict.json}`;
  the scoreboard is `data/live_trials/scoreboard.jsonl`.
- **Real-data guard (FR-012/NFR-002)**: when `is_synthetic` is false, `persist_run`
  writes **nothing** and `append_scoreboard` is not called — no kept log, no
  scoreboard line, no extracted data anywhere. A real-data run leaves zero new
  files under the repo.
- **Append-only integrity (NFR-005)**: `append_scoreboard` only appends one
  parseable JSON line; never rewrites prior lines. N sequential appends ⇒ N
  ordered, independently-parseable lines. A malformed line is skipped on read with
  a warning, never silently dropping the rest.
- **Floor query (FR-011)**: `current_floor` groups by `operator_model` and reports,
  per tier, whether it reaches `final_pass` and how `first_attempt_pass` vs
  `final_pass` has trended — the capability floor at any time.
- **No off-machine path (NFR-002)**: no function syncs/uploads/exports any of
  these artifacts. Local files only.

## Git-ignore

`.gitignore` MUST exclude `data/live_trials/` so kept logs, verdicts, and the
scoreboard are never committed (C-001).
