# Research (Phase 0)

No open `NEEDS CLARIFICATION` markers remain in the spec; the contested design
questions were resolved during specify + a spec review. This records the
decisions so downstream phases don't relitigate them.

## D1 — In-loop honesty = self-reconciliation, NOT manifest feedback

- **Decision**: the retry loop's honesty gate checks **all raw source columns
  from the file header**: each must be a declared metric or declared unmapped.
  The committed manifest is never shown to the operator.
- **Rationale**: `grader.honest_about_gaps` (`grader.py:153-184`) is purely "every
  source field is loaded OR declared, else a silent drop"; it uses the manifest
  *only* to enumerate field names — which are readable straight from the file
  header. So self-reconciliation is the **answer-key-free reconstruction** of that
  rule, and it is the only honesty signal that exists at real runtime (no manifest
  or grader there).
- **Loophole closed**: check the file's columns, not "columns the parser chose to
  read" — otherwise a lazy parser passes by not reading a column.
- **Alternatives rejected**: feeding the grader verdict (or manifest) back —
  contaminates the independent judge and measures a signal absent in production.

## D2 — Record first-attempt AND final verdict

- **Decision**: grade attempt 1 (before any feedback) and the final attempt; record
  both.
- **Rationale**: an honesty-enforcing loop makes the *final* honesty result always
  pass, so it stops discriminating between model tiers. Un-nagged honesty is the
  real capability-floor signal (planning note §"Why a deliberately weak agent").

## D3 — Scoreboard: minimal append-only JSONL (new specify-time decision)

- **Decision**: one git-ignored `data/live_trials/scoreboard.jsonl`, one line per
  run. Per-run kept artifacts in `data/live_trials/<run>/`.
- **Rationale**: smallest durable store that answers "current capability floor,
  first-attempt vs final, over time" (FR-011). Explicitly new scope vs the prior
  plan (which committed only to recording model identities); kept minimal so it
  isn't gold-plating.
- **Alternatives rejected**: a DB/table (overkill, one writer, append-only); no
  scoreboard (loses the cross-run floor trend the mission set out to measure).

## D4 — Model backend: local Ollama via stdlib urllib

- **Decision**: reach the local Ollama HTTP API with stdlib `urllib`; model
  configurable via env (default the locally available cheap coder model).
- **Rationale**: zero new dependency; already exercised by the seed. C-003 fixes
  the local-server choice for this slice; a multi-backend abstraction is OUT.

## D5 — Reuse slice-one machinery unchanged (NFR-006)

- **Decision**: call `sandbox` / `ingest_runner` / `store` / `grader` and the
  `run_live_trial_with_log` seam directly; add no second copy. `live_trial.py`
  changes only to make the deferred `real_model_operator`/`real_model_driver`
  delegate to the new module (FR-013).
