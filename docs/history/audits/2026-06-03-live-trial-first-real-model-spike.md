# Live-trial first real-model spike (R5) — 2026-06-03

> **Where this sits:** a first data point inside **issue #10** (end-to-end agent
> acceptance sandbox / capability-tier sweep), on the **parser-only path**. The
> merged session-log substrate is slice one of the design note
> [`docs/building/planning/agent-interaction-audit-substrate.md`](../../building/planning/agent-interaction-audit-substrate.md);
> this exercises its live-trial seam with a real cheap operator. It is NOT #10
> itself — see "How thin a slice" below.

First time a **real model** was driven end-to-end through the session-log
substrate's live-trial seam (`src/premura/harness/live_trial.py`), exercising the
explicitly-deferred `real_model_operator` / `real_model_driver` follow-up
(D4 / R5 / SC-005, plan.md Risks R5). Started as a throwaway local spike; the
harness now lives in the repo (see below). Ran over the **synthetic fixture**
(no PHI, C-003/NFR-004 respected).

## How thin a slice (vs. issue #10's full design)

- **Driver:** #10 wants a *capable frontier* model improvising as a naive user;
  this used a **canned** `OllamaDriver` (fixed goal, "proceed").
- **Path:** #10's operator runs the *full* path (install from docs → ingest a
  *novel* dump → answer health questions); this ran the **parser-only** path over
  the *committed synthetic* fixture.
- **Sweep:** #10 wants a **capability-tier sweep** (many models, find the floor);
  this was **one** model (qwen2.5-coder:7b), one category (heart_rate).

## Setup

- **Operator model:** local Ollama `qwen2.5-coder:7b` (a deliberately cheap,
  low-capability AI, per the §"Why a deliberately weak agent" intent).
- **Seam entry:** `run_live_trial_with_log(...)` with a real `OllamaOperator`
  (drives the model to author a parser into the sandbox) and a fixed-goal
  `OllamaDriver`.
- **Source:** `tests/fixtures/session_log/fitbit_heart_rate_synthetic.csv` — same
  data the committed `ReferenceParserOperator` uses, so the grader verdict is
  directly comparable to the known-good baseline.
- **Prompt:** the parser contract surface (CONTRACT.md essentials + `base.py`
  API) + the data sample + the goal. The reference parser was **not** shown
  (no teaching-to-the-test).

## Result: seam works, one-shot cheap model fails

The harness drove the model, logged the `edit_file` / `ingest_run` steps as the
sole writer, and the deterministic grader recomputed a **FAIL** on all three rules:

| Rule | Result | Cause |
| --- | --- | --- |
| `loaded` | FAIL | 0 warehouse rows — `parse()` raised |
| `runtime_valid` | FAIL | `ingest_run failed` (batch never built) |
| `honest_about_gaps` | FAIL | whole raw CSV lines pushed into `unmapped_metrics` |

**qwen-7b one-shot hallucinated the `IngestBatch` API:**

1. Invented a `methods={...}` constructor kwarg (passing lambdas for
   `validate` / `attach_source_artifact`) — that field does not exist → `TypeError`.
2. Re-defined `validate` / `attach_source_artifact` as no-op methods on its own
   parser class (they live on `IngestBatch`, not the parser).
3. Misread the honesty contract — dumped whole raw CSV **lines** into
   `unmapped_metrics` instead of the unmapped **column names**.

## Finding (R5, evidenced)

A naive single-shot prompt to a cheap 7b model is **not sufficient** to author a
contract-valid parser. The real-operator follow-up needs scaffolding, not just a
prompt:

- the `parser-generator` skill + `base.py` available in-context, and
- a **contract-check → re-prompt feedback loop** (feed
  `src/premura/parsers/contract_check.py` errors back to the model and retry),
  which the seam does **not** currently exercise.

Whether such a loop gets qwen to green is the next planned data point (retry-loop
spike) before scoping the real-operator mission.

## Retry-loop follow-up (same day): the feedback loop works — for what it checks

Added a **contract-check → re-prompt** loop (write parser → import + `parse()` +
`validate()` + assert ≥1 measurement → feed any error back → retry, ≤3 tries) and
reran. Two illustrative runs:

- **Run A (3 attempts):** attempt 1 → `TypeError: ... unexpected keyword 'methods'`;
  attempt 2 → `ValueError: IngestBatch missing source descriptors for: ['fitbit_heart_rate']`;
  attempt 3 → contract-check PASS. Final grader: `loaded` PASS, `runtime_valid` PASS,
  `honest_about_gaps` **FAIL**.
- **Run B (1 attempt):** passed contract-check first try; same grader shape —
  `loaded`/`runtime_valid` PASS, `honest_about_gaps` **FAIL** (put a row *value*,
  `timestamp_str`, into `unmapped_metrics` and omitted `confidence`/`altitude_m`).

**Sharpened finding — the loop only fixes what it checks.** The feedback loop
reliably drives the cheap model past the *structural* failures (bad kwargs,
missing descriptors) because those are what the check tests. But the check did
**not** test honesty, so the model converged on "it loads" and stopped — and
`honest_about_gaps` stayed the consistent failure.

**Refinement (added after spec design, 2026-06-03).** The first-pass wording above
("feed back the *grader's* honesty verdict") was too strong and is superseded.
`grader.honest_about_gaps` (`grader.py:153-184`) is just: *every raw source column
is loaded-or-declared, else a silent drop* — it uses the committed manifest only
to **enumerate column names**. Those names are readable straight from the source
file header, so the loop can reconstruct that exact check **answer-key-free**
("every raw source column from the header is declared metric or declared
unmapped"). That self-reconciliation is the runtime-faithful signal a real
operator actually has (at real runtime there is no manifest or grader), and it
catches the silent-drop failure seen here. The grader still judges all three rules
**independently** at the end and is the recorded authority. The loop must check
**all raw columns from the file**, not "columns the parser chose to read" (that
would be gameable). See the mission spec `cheap-operator-live-trial-01KT6PSA`
FR-003/FR-004/FR-014.

## Process note → fixed: this harness now lives in the repo

The first spike ran from `/tmp` and tore its session log down with the sandbox —
wrong for a substrate whose whole point is a **repeatable, often-run, loggable**
local trial. Corrected the same day: the harness is now in the repo as
`src/premura/harness/live_trial_ollama.py` (`OllamaOperator` / `OllamaDriver` /
`run_ollama_live_trial`), with an opt-in test `tests/test_live_trial_ollama.py`
under a new `live_trial` pytest marker that the default suite excludes
(`addopts = -m "not regression and not live_trial"`) — runnable on demand
(`uv run python -m premura.harness.live_trial_ollama`), never blocking CI (NFR-005).

Still open for the mission: the substrate tears the session-log DuckDB down with
the sandbox (NFR-004), so the trial's own audit artifact is lost. The mission
should offer a **keep-the-log / export** path for live trials; the
synthetic-fixture trial carries no PHI, so keeping its log is safe (the PHI guard
is specific to the real-dump path).
