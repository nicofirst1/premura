-- schema.sql — the session log's OWN local DuckDB tables.
--
-- Mission: session-log-substrate-01KT45S1 (WP01). ADR 0011, spec C-001/C-002,
-- FR-070.
--
-- Why a standalone file (NOT a warehouse migration, NOT the trace.* schema):
-- the session log records what an *operating* agent did during a run and the
-- Premura-internal facts of each ingest, so the deterministic grader can
-- recompute a verdict. It is deliberately a SEPARATE DuckDB file from both the
-- health warehouse (`health.duckdb`, `hp.*`) and the analytical research trace
-- (`trace.*` in the warehouse). Keeping it in its own file removes the
-- single-file write contention the trace schema would otherwise reintroduce
-- (the harness is the sole writer, FR-021/NFR-008), and makes the boundary
-- structural: a session-log write can never land in a health-fact or research-
-- trace table. This DDL is applied by the session-log package's own
-- `init_schema()` (idempotent CREATE IF NOT EXISTS), never by
-- `premura.store.duck.run_migrations`.
--
-- It adopts the OpenTelemetry GenAI vocabulary / tree shape BY HAND (hardcoded
-- strings, no OTel library, no server) — the same idiom as `premura.trace`.
--
-- A bare/default schema is used on purpose: this is a standalone file, so the
-- tables do not need (and must not carry) a `trace`/`hp` schema prefix.

-- ----------------------------------------------------------------------------
-- log_session — one row per operating run. Carries the run identity the grader
-- and a maintainer need to reproduce / situate a run (FR-031/FR-032). The
-- timestamps are nondeterministic wall-clock and are deliberately NOT consumed
-- by the grader (data-model D5).
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_session (
    session_id       VARCHAR PRIMARY KEY,  -- ULID string (python-ulid)
    started_at       TIMESTAMP NOT NULL,   -- nondeterministic; not used by grader
    finished_at      TIMESTAMP,            -- nullable until teardown
    operator_model   VARCHAR NOT NULL,     -- operating AI model id (or fake sentinel)
    driver_model     VARCHAR NOT NULL,     -- driver AI model id (or fake sentinel)
    premura_version  VARCHAR NOT NULL,     -- sandbox run identity
    isolation_tag    VARCHAR NOT NULL,     -- unique per-sandbox tag
    run_kind         VARCHAR NOT NULL      -- 'repeatable_check' | 'live_trial'
);

-- ----------------------------------------------------------------------------
-- log_step — one row per captured unit of work; a tree via parent_step_id
-- (turn -> model_call / tool_call). The verdict-bearing step is the one with
-- tool_name='ingest_run'; its detail lands in log_ingest_provenance.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_step (
    step_id          VARCHAR PRIMARY KEY,
    session_id       VARCHAR NOT NULL REFERENCES log_session(session_id),
    parent_step_id   VARCHAR REFERENCES log_step(step_id),  -- nullable; the tree
    kind             VARCHAR NOT NULL,     -- 'agent_turn' | 'model_call' | 'tool_call'
    name             VARCHAR,              -- e.g. the gen_ai tool name
    tool_name        VARCHAR,              -- named-tool convention (FR-004)
    request_summary  VARCHAR,              -- PHI-safe envelope summary
    request_hash     VARCHAR,
    result_status    VARCHAR NOT NULL,     -- fixed six-value vocabulary (FR-003)
    result_summary   VARCHAR,
    result_hash      VARCHAR,
    started_at       TIMESTAMP NOT NULL,   -- not used by grader
    finished_at      TIMESTAMP             -- not used by grader
);
-- Walk a session's steps / reconstruct its tree.
CREATE INDEX IF NOT EXISTS ix_step_session ON log_step(session_id);
CREATE INDEX IF NOT EXISTS ix_step_parent  ON log_step(parent_step_id);

-- ----------------------------------------------------------------------------
-- log_ingest_provenance — Premura-internal facts per ingest run, with a MIXED
-- source-of-truth that is explicitly distinguished:
--
--   * loader-MEASURED facts (authoritative): rows_inserted / rows_skipped_dup /
--     rows_skipped_priority, plus the dim_metric-existence enforcement result
--     captured downstream via the declared/emitted sets the grader recomputes.
--   * parser-DECLARED CLAIMS (NOT authoritative): unmapped_metrics_json,
--     skipped_rows_json — persisted as the parser's claim so the grader can
--     reconcile them, never discarded.
--   * declared_metrics_json and emitted_metric_ids_json are captured as SEPARATE
--     sets so the grader can recompute "declared == emitted".
--
-- contract_pass is the grader's RECOMPUTED runtime-subset result, written back
-- here; it is NEVER a parser/runner self-report (FR-061/FR-065). This WP only
-- persists whatever the caller (the grader) supplies.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_ingest_provenance (
    -- One provenance row per ingest_run step: step_id is the PRIMARY KEY so this
    -- core audit table cannot silently hold duplicate rows for one ingest_run.
    step_id                  VARCHAR PRIMARY KEY REFERENCES log_step(step_id),
    batch_id                 VARCHAR,   -- from LoadStats.batch_id
    parser_kind              VARCHAR,   -- which parser ran
    rows_inserted            INTEGER,   -- loader-measured (authoritative)
    rows_skipped_dup         INTEGER,   -- loader-measured (authoritative)
    rows_skipped_priority    INTEGER,   -- loader-measured (authoritative)
    declared_metrics_json    VARCHAR,   -- captured set: parser-declared metrics
    emitted_metric_ids_json  VARCHAR,   -- captured set: batch's emitted metric_ids
    unmapped_metrics_json    VARCHAR,   -- parser CLAIM (not authoritative)
    skipped_rows_json        VARCHAR,   -- parser CLAIM (not authoritative)
    contract_pass            BOOLEAN    -- grader's recomputed result, written back
);
-- (step_id is the PRIMARY KEY, so it is already indexed for the
-- fetch-provenance-by-step lookup; no separate index is needed.)

-- ----------------------------------------------------------------------------
-- log_live_trial_attempt — per-attempt cheap-model telemetry owned by the harness.
--
-- Persists the operator's self-reconciliation result and parser import/parse
-- failure detail for each attempt under a live-trial session. This keeps the
-- attempt log durable in the session-log file rather than only on the returned
-- in-memory object (FR-008), while preserving the harness as the sole writer.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_live_trial_attempt (
    attempt_id                   VARCHAR PRIMARY KEY,
    session_id                   VARCHAR NOT NULL REFERENCES log_session(session_id),
    attempt_index                INTEGER NOT NULL,
    self_reconciliation_passed   BOOLEAN NOT NULL,
    source_columns_json          VARCHAR NOT NULL,
    accounted_json               VARCHAR NOT NULL,
    unaccounted_json             VARCHAR NOT NULL,
    parser_error                 VARCHAR,
    UNIQUE(session_id, attempt_index)
);
CREATE INDEX IF NOT EXISTS ix_live_trial_attempt_session
    ON log_live_trial_attempt(session_id, attempt_index);
