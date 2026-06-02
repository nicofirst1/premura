# Phase 0 Research: Session Log Substrate (Slice One)

This consolidates the decisions that resolve every open unknown before design.
Most storage/scope questions were already settled in the spec and ADR 0011; the
three architecture forks below were resolved with the maintainer during planning.

## D1 — Session-log storage: separate local DuckDB file, hand-written OTel shape

- **Decision**: The session log is its **own local DuckDB file**, separate from
  the warehouse (`health.duckdb`) and from the `trace.*` tables. It is **not** a
  new `006_*.sql` warehouse migration. It adopts the OpenTelemetry GenAI
  *vocabulary and tree shape* but takes **no OTel library and runs no server**;
  rows are written by hand in the idiom `premura.trace` already uses.
- **Rationale**: ADR 0011 (locked). A separate file makes "never sync, never
  export" one physical rule (PHI-bearing), is trivial to point at a temp file and
  discard, and removes the warehouse-vs-log connection contention that
  `mcp/entrypoint.py` currently brackets around (DuckDB refuses concurrent
  handles to one file).
- **Code grounding**: `trace.py` is connection-agnostic (caller owns the conn);
  `store/duck.py:run_migrations` applies `CREATE ... IF NOT EXISTS` SQL in lexical
  order. The session log reuses the *idiom* (idempotent DDL applied on connect)
  but against its **own** file via its **own** `connect()` + `init_schema()`,
  not the warehouse migration runner.
- **Alternatives rejected**: (a) OTel SDK + exporter — only auto-captures
  OpenAI/Anthropic client SDKs, blind to Premura's MCP tools / file edits /
  ingest provenance, and the GenAI attribute names are still churning
  "Development" status. (b) A new schema inside the warehouse — reintroduces the
  contention the separate file exists to remove and entangles PHI with the
  warehouse's sync/export surface.

## D2 — Sandbox isolation: full temp copy of the tracked tree + subprocess runner

- **Decision**: A sandbox is a **full throwaway copy of the tracked repo tree**
  in a temp folder (excluding `.git`, `.venv`, `kitty-specs/`, `data/`,
  `.worktrees/`), with the warehouse path and the session-log path pointed at
  temp files. The ingest is executed **inside the sandbox as a subprocess** that
  emits a structured JSON **outcome envelope** on stdout; the parent harness reads
  it back. Sandbox is torn down after the run.
- **Rationale**: The parser-build flow has an agent **write parser modules** into
  `src/premura/parsers/` and append to `dim_metric.yaml` — isolation must cover
  source edits, not just data files. A real copy faithfully models that and is
  what the live trial needs (a real agent edits the sandbox tree). The subprocess
  gives the run its own DuckDB handles (no concurrency dance with the parent) and
  is an **outside-boundary substitute** (config params + subprocess wrapper),
  which DIRECTIVE_036 explicitly permits.
- **Single-writer**: The subprocess **does not write the session log**. It
  *returns* its outcome; the **parent harness is the sole writer** of the
  session-log file (FR-021). Concurrent log connections never occur.
- **Alternatives rejected**: in-process path redirection — fast, but cannot
  faithfully model a second copy of the package being imported/edited (the
  module is already imported in the parent), and would force the live trial onto
  a different mechanism. We chose one mechanism that serves both modes.
- **Reproducibility note**: The copy is built from `git ls-files`-tracked paths
  so the input tree is deterministic from a clean checkout (NFR-002).

## D3 — Repeatable check determinism: scripted fake agent + committed reference parsers

- **Decision**: The repeatable check's "agent" is the harness **scripting fixed
  steps** (no model): it installs a **committed reference parser** into the
  sandbox tree and invokes the runner. We commit **two** reference parsers:
  - `good_fitbit_hr` — maps the mappable field(s), declares the rest as
    `unmapped_metrics`, loads cleanly → must be graded **PASS**.
  - `dishonest_fitbit_hr` — silently **drops** a fixture field (neither loads it
    nor declares it) → must be graded **FAIL** by reconciliation.
- **Rationale**: A real model can't run in CI deterministically. Committed
  reference parsers exercise both the happy path and the silent-drop detection
  end-to-end and byte-identically every run (NFR-001, NFR-007, SC-002). They live
  under `tests/fixtures/` and are installed **only into the sandbox** — they are
  **not** shipped production parsers, preserving Fitbit as a genuinely unsupported
  target for the live trial.
- **Alternatives rejected**: testing the fail path with an in-test stub only —
  weaker end-to-end proof; the committed dishonest parser proves the rail across
  the same boundary production crosses (fidelity gate).

## D4 — Live trial: build the harness seam now, defer model wiring

- **Decision**: Build the full repeatable check + sandbox + log + grader
  end-to-end now, and lay down the **live-trial seam** — `Driver` / `Operator`
  protocols and the Fitbit-pointing config + `run_kind=live_trial` plumbing — but
  **defer actually invoking a cheap model** to a follow-up. Tests drive the seam
  with a fake `Operator` (an outside-boundary substitute).
- **Rationale**: Smaller, lower-risk foundational slice; the machinery is proven
  deterministically; the live trial never blocks anything (NFR-005), so deferring
  its model wiring costs nothing in CI. The seam keeps `operator_model` /
  `driver_model` capture so the later capability-tier sweep is unfored.
- **Spec reconciliation**: SC-005 is refined to *"the live-trial harness can
  target the Fitbit dump (heart-rate) and the seam is exercised by a fake
  operator; model-driven execution is a named follow-up"* — not silently dropped
  (DIRECTIVE_010). Recorded in plan.md Risks.

## D5 — Determinism boundary: verdict is independent of ids/timestamps

- **Decision**: The session log's row ids and timestamps are nondeterministic
  run-to-run; the **grader verdict** is computed **only** from content (warehouse
  row counts, captured declared/emitted metric sets, unmapped/skipped claims,
  fixture field set) with all lists sorted, and its serialization **excludes** ids
  and timestamps. NFR-001 ("byte-identical verdict") binds the **verdict**, not
  the raw log.
- **Rationale**: Keeps the always-on check byte-stable without forcing an
  injectable clock/id-generator into slice one. A fully-reproducible log (via an
  injected clock) is noted as an optional later nicety, not required here.

## D6 — Honesty reconciliation needs an authored fixture manifest, not a per-field resolution map

- **Decision**: We commit a `fixture_fields.yaml` manifest listing the
  **complete** source-field set we authored, each tagged with its honest
  disposition: `canonical_metric: <metric_id>` for mappable fields, or
  `canonical_metric: null` for inherently-unmappable fields. The grader
  reconciles each source field F:
  - `canonical_metric` set → handled iff (that metric is present in the sandbox
    warehouse) **or** (F appears in `unmapped_metrics`/`skipped_rows`);
  - `canonical_metric: null` → handled iff (F appears in
    `unmapped_metrics`/`skipped_rows`);
  - otherwise → **silent drop → fail**.
- **Rationale**: FR-064 reconciliation needs to know, per field, what "honestly
  handled" means — and **we** know it because we authored the fixture. This is
  ground truth, not parser self-report. The deeper **per-field resolution map**
  (which `suggest_metric` rule matched) is explicitly **out of scope** (spec), so
  we do not require it.
- **Fixture-authoring constraint**: each mappable source field maps to a
  **distinct** `metric_id` in the fixture, so "metric present" unambiguously
  witnesses that field (avoids two fields sharing a metric masking a drop).
  Documented in data-model.md.

## D7 — Runtime contract checker: a pure function the grader calls on captured evidence

- **Decision**: Build a minimal `check_runtime_contract(...)` (none exists today)
  that recomputes the runtime-valid subset: no `derived:` emitted;
  `declared_metrics == emitted metric_ids`; declared metrics exist in
  `dim_metric`; parser produced a batch without raising. The **grader** calls it
  on **captured** declared/emitted sets + the sandbox warehouse — it does **not**
  trust any precomputed `contract_pass` (FR-061). The grader writes its recomputed
  result back as `contract_pass` for the record (FR-065).
- **Code grounding**: `base.py:387` already raises on emitted `derived:` metrics;
  `loader.validate_batch_against_warehouse` already raises on missing
  `dim_metric` entries. The checker recomputes these from captured evidence so a
  green verdict never rests on the loader/parser having been trusted.
