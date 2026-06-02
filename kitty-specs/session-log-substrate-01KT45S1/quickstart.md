# Quickstart: Session Log Substrate (Slice One)

Audience: a contributor or CI verifying the slice from a clean clone.

## Run the repeatable check (always-on, deterministic, offline)

```bash
uv run pytest -q tests/test_repeatable_check.py
```

What it proves end-to-end, from the repo alone (no private data, no network):

1. Builds a **sandbox** (full temp copy of the tracked tree; warehouse + session
   log at temp files).
2. Installs the committed **`good_fitbit_hr`** reference parser into the sandbox
   and runs the ingest via the in-sandbox subprocess runner.
3. The **harness** (sole writer) records the session log: `tool_call` steps
   (`edit_file`, `parser_contract_check`, `ingest_run`) + `log_ingest_provenance`.
4. The **grader** recomputes the three rules from the sandbox warehouse + the
   committed fixture + captured evidence → **PASS**.
5. Repeats with **`dishonest_fitbit_hr`** (silently drops `altitude_m`) → grader
   returns **FAIL** with `silent_drops: ["altitude_m"]`.
6. Re-running yields a **byte-identical verdict** (NFR-001).

Inspect a verdict shape: see `contracts/grader-verdict.schema.json`.

## Run the full suite + gates (before review handoff)

```bash
uv run ruff check src/premura tests
uv run ruff format --check src/premura tests
uv run mypy src/premura            # changed scope
uv run pytest -q
```

## Live trial (local-only, occasional, never blocks)

The seam is built; the cheap-model operator is a follow-up (D4). To exercise the
seam with the fake operator today:

```bash
uv run pytest -q tests/test_live_trial_seam.py
```

When the real operator lands, it will target the local Fitbit dump (heart-rate
category) — real data stays local and is never committed:

```
~/Downloads/MyFitbitData    # live trial only; not in the repo
```

## Key paths

- Session log file (per run): a temp DuckDB file in the sandbox; in real runs
  later, `settings.session_log_path` (default `data/session_log.duckdb`).
- Fixture: `tests/fixtures/session_log/fitbit_heart_rate_synthetic.csv`
  + ground-truth `tests/fixtures/session_log/fixture_fields.yaml`.
- Reference parsers: `tests/fixtures/session_log/parsers/{good,dishonest}_fitbit_hr.py`.
