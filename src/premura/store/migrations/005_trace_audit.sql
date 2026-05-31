-- 005_trace_audit.sql — durable home for session research traces.
--
-- Mission: session-research-trace-01KSYT4A (WP01).
--
-- Why a dedicated `trace.*` schema instead of reusing `hp.*`: tool-use
-- provenance is NOT a health fact. `hp.*` holds health observations, notes,
-- profile, and intake; `trace.*` holds the record of which analytical tools an
-- agent invoked during a research session, what they returned, and which
-- results the agent marked as surfaced in a user-facing answer. Keeping the two
-- in separate schemas makes the boundary structural: a trace write can never
-- accidentally land in a health-fact table, and the multiplicity disclosure
-- (N unique hypotheses, K surfaced) is derived from these rows rather than
-- duplicated into health storage. See ADR 0009.
--
-- Append-only shaping: in normal operation rows are inserted and never updated
-- or deleted. A call row may be written before dispatch and finalized with its
-- terminal status after dispatch (WP02 owns that transaction); results and
-- surfaced marks are separate append-only rows that reference an immutable
-- call_id rather than mutating the call. There is deliberately NO mutable
-- aggregate / disclosure-cache table here: disclosure is a derived query so it
-- cannot drift from the canonical call/result/mark rows.
--
-- Idempotency: every statement uses CREATE ... IF NOT EXISTS so the normal
-- migration loader (premura.store.duck.run_migrations) can re-run it safely on
-- an already-initialized warehouse. No `hp.*` object is touched here.
--
-- Identity / payload notes (handoff to WP02):
--   * Identifiers (session_id, call_id, result_id, mark_id) are VARCHAR stable
--     generated ids produced by the Python boundary, not DB sequences, so calls
--     can be addressed before insert and across processes.
--   * hypothesis_identity is stored as canonical JSON text (a deterministic
--     normalized key). Counting distinct hypothesis_identity within a session
--     yields N after exact retries collapse.
--   * tool_result stores a result_hash plus an optional compact result_summary
--     (JSON text) — a safe envelope subset, never raw health rows / paired
--     series. raw_payload is NOT present; the trace references results
--     compactly, it does not duplicate personal data.

CREATE SCHEMA IF NOT EXISTS trace;

-- ----------------------------------------------------------------------------
-- Research session: groups analytical calls and carries warehouse context so a
-- disclosure can be reproduced against the warehouse state it was computed on.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trace.research_session (
    session_id             VARCHAR PRIMARY KEY,
    started_at_utc         TIMESTAMP NOT NULL,
    client_label           VARCHAR,        -- optional caller/agent label
    warehouse_fingerprint  VARCHAR,        -- stable reference to warehouse state
    schema_version         VARCHAR,        -- trace/warehouse schema version
    created_by             VARCHAR         -- optional boundary/client identifier
);

-- ----------------------------------------------------------------------------
-- Recorded analytical call: one row per analytical invocation observed at the
-- MCP boundary. The normalized hypothesis_identity is what dedupes exact
-- retries when counting N. Terminal status / refusal_reason / error_kind are
-- nullable so WP02 may insert before dispatch and finalize after.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trace.tool_call (
    call_id              VARCHAR PRIMARY KEY,
    session_id           VARCHAR NOT NULL REFERENCES trace.research_session(session_id),
    tool_name            VARCHAR NOT NULL,   -- e.g. change_point, smoothed_average, correlate
    request_hash         VARCHAR,            -- deterministic hash of normalized request
    hypothesis_identity  VARCHAR,            -- canonical JSON text; distinct count = N
    started_at_utc       TIMESTAMP NOT NULL,
    finished_at_utc      TIMESTAMP,
    terminal_status      VARCHAR,            -- 'available' | 'refused' | 'error'
    refusal_reason       VARCHAR,            -- machine-readable, only when refused
    error_kind           VARCHAR             -- machine-readable, only on dispatch error
);
-- Bounded session disclosure: walk every call in a session.
CREATE INDEX IF NOT EXISTS ix_tc_session ON trace.tool_call(session_id);
-- Count unique hypotheses (N) per session by collapsing exact retries.
CREATE INDEX IF NOT EXISTS ix_tc_session_hypothesis
    ON trace.tool_call(session_id, hypothesis_identity);

-- ----------------------------------------------------------------------------
-- Recorded result reference: compact, immutable reference to a non-refusal
-- result. Links to an immutable call_id; stores a hash plus an optional compact
-- summary envelope, never raw health data.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trace.tool_result (
    result_id       VARCHAR PRIMARY KEY,
    call_id         VARCHAR NOT NULL REFERENCES trace.tool_call(call_id),
    result_hash     VARCHAR,        -- deterministic hash of serialized result envelope
    result_summary  VARCHAR,        -- optional compact JSON-text envelope subset
    created_at_utc  TIMESTAMP NOT NULL
);
-- Fetch the result reference(s) for a recorded call.
CREATE INDEX IF NOT EXISTS ix_tr_call ON trace.tool_result(call_id);

-- ----------------------------------------------------------------------------
-- Surfaced mark: an explicit agent declaration that a recorded call was used in
-- a user-facing answer. Appended as its own row (surfaced status never
-- overwrites the call), referencing an immutable call_id. Surfaced means
-- "selected for presentation", never "statistically significant".
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS trace.surfaced_mark (
    mark_id        VARCHAR PRIMARY KEY,
    session_id     VARCHAR NOT NULL REFERENCES trace.research_session(session_id),
    call_id        VARCHAR NOT NULL REFERENCES trace.tool_call(call_id),
    role           VARCHAR,         -- validated label, e.g. claim/summary/recommendation
    rationale      VARCHAR,         -- short agent explanation
    marked_at_utc  TIMESTAMP NOT NULL
);
-- Fetch marks for a recorded call (K, surfaced subset).
CREATE INDEX IF NOT EXISTS ix_sm_call    ON trace.surfaced_mark(call_id);
CREATE INDEX IF NOT EXISTS ix_sm_session ON trace.surfaced_mark(session_id);
