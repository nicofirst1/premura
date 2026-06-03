# Contract: cheap operator + driver (FR-001/002/005/008/010/014)

Implements the slice-one `live_trial.Operator` / `Driver` protocols
(`model_id`; `Operator.operate(sandbox, goal)`; `Driver.goal()` / `respond()`),
so it runs through `run_live_trial_with_log` unchanged (NFR-006).

## Operator (cheap model)

```
class <Backend>Operator:
    model_id: str
    def operate(self, sandbox, goal) -> None   # edits ONLY the sandbox tree
```

Retry loop (each attempt):
1. Prompt the local model with the parser-contract surface + a sample of the
   source + the goal (and, on retries, the prior failure to fix). The
   ground-truth manifest is NEVER included (C-005).
2. Write the parser into the sandbox tree at the runner-resolved path.
3. Gate with `self_reconcile` (raw-header check) **and** import/parse/validate.
4. On failure within the attempt cap (NFR-003): feed back `unaccounted` columns
   and/or the parse error; retry. On success or cap exhaustion: stop.

Loop telemetry exposed for recording: `attempts_used`, the per-attempt
`AttemptRecord`s, and a handle to grade **attempt 1** independently (FR-014). The
operator never opens the session log (NFR-004).

## Driver (fixed-goal stand-in, FR-008)

```
class <Backend>Driver:
    model_id: str
    def goal(self) -> str        # fixed goal for the heart_rate parser path
    def respond(self, q) -> str   # canned
```

Records a driver `model_id` for tier comparison; does NOT invoke a frontier model
(that is #10's later slice — DIRECTIVE_036 named substitute).

## Run entry (FR-009)

```
run_live_trial_<backend>(*, model, source=<synthetic fixture>, max_tries, repo_root)
    -> (LiveTrialRunRecord, AttemptRecord[])
```

- Default source is the committed synthetic fixture (no private data, C-001).
- Grades attempt 1 and the final via the unchanged slice-one grader (the recorded
  authority, FR-004); persists per data-model.md for synthetic runs only.
- Surfaces a clear "model server unavailable" outcome without raising into the
  default suite (NFR-001).
