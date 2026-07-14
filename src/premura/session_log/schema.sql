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

-- ----------------------------------------------------------------------------
-- log_turn — the per-turn transcript of a live-trial run: the operator's actual
-- conversation history (system prompt + every user/assistant/tool turn), one row
-- per turn. The session log already records the *shape* of a run (the step tree
-- in log_step); log_turn records the *conversation* the judge-AI follow-on needs
-- to read. The harness (the sole writer, FR-021) flushes the transcript post-run.
--
--   * turn_index is the 0-based position within the session's transcript; the
--     (session_id, turn_index) pair is UNIQUE so the ordered transcript cannot
--     hold a duplicate slot.
--   * step_id is nullable and, when set, links the turn to the log_step node it
--     occurred under (typically the run's root agent_turn). It is an enforced
--     FK; the harness flushes the step row before the transcript turns.
--   * role is a fixed vocabulary {system, user, assistant, tool}, validated at
--     the store boundary (TURN_ROLES), mirroring the chat-API role standard.
--   * tool_name / model / token_count are optional per-turn telemetry; nullable.
--
-- content stores the full turn content (tool results may quote operator data);
-- the session log is the local, PHI-bearing store per ADR 0011 and NFR-002 — no
-- code path syncs or exports it.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_turn (
    turn_id      VARCHAR PRIMARY KEY,  -- ULID string (python-ulid)
    session_id   VARCHAR NOT NULL REFERENCES log_session(session_id),
    step_id      VARCHAR REFERENCES log_step(step_id),  -- nullable link to the step
    turn_index   INTEGER NOT NULL,     -- 0-based position in the transcript
    role         VARCHAR NOT NULL,     -- {system, user, assistant, tool} (TURN_ROLES)
    content      VARCHAR NOT NULL,     -- full turn content (PHI-bearing, local-only)
    tool_name    VARCHAR,              -- nullable; set on tool-result turns
    model        VARCHAR,              -- nullable; the model that produced the turn
    token_count  INTEGER,              -- nullable; optional per-turn telemetry
    UNIQUE(session_id, turn_index)
);
-- Walk a session's transcript in order.
CREATE INDEX IF NOT EXISTS ix_turn_session ON log_turn(session_id, turn_index);

-- ----------------------------------------------------------------------------
-- log_judgment — one row per AI-judge invocation over a recorded session
-- (judge-ai mission m3). The mechanical grader judges a run with `contract_pass`
-- (in log_ingest_provenance) and the scoreboard records pass/fail; the AI judge
-- evaluates the run's *process* against a versioned rubric and persists a
-- structured, DESCRIPTIVE verdict here. It can NEVER alter `contract_pass`, the
-- scoreboard, or the trial verdict — this is a separate, additive table the judge
-- only writes into through the sole-writer harness surface (store.record_judgment).
--
--   * status is a fixed vocabulary {complete, unparseable, model_unavailable}
--     (JUDGMENT_STATUSES), validated at the store boundary. A judgment attempt is
--     always recorded honestly: on unparseable / model_unavailable, criteria_json
--     is an empty object, overall_band is NULL, and raw_output preserves what the
--     model actually said (if anything).
--   * criteria_json is a JSON object mapping rubric criterion id -> {band,
--     rationale, evidence_quote}. The criterion IDS are rubric-owned data, NEVER
--     enumerated in code; each band is validated against CRITERION_BANDS at the
--     store boundary. evidence_quote (issue #52) is a verbatim span of the dossier
--     text the judge verified in code before recording — an ungrounded quote is
--     rejected and retried, never persisted.
--   * overall_band / each criterion band ∈ {strong, adequate, weak,
--     not_applicable} (CRITERION_BANDS) — DESCRIPTIVE bands only: no numeric
--     scores, no pass/fail language confusable with the mechanical grader verdict
--     (NFR-6).
--   * rubric_version pins which rubric produced the judgment (FR-3: a new
--     criterion bumps the rubric version; no schema or store change is needed).
--
-- raw_output / rationale carry full model text; the session log is the local,
-- PHI-bearing store per ADR 0011 / NFR-002 — no code path syncs or exports it.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_judgment (
    judgment_id    VARCHAR PRIMARY KEY,  -- ULID string (python-ulid)
    session_id     VARCHAR NOT NULL REFERENCES log_session(session_id),
    judged_at      TIMESTAMP NOT NULL,   -- nondeterministic wall-clock; not graded
    judge_model    VARCHAR NOT NULL,     -- the local model that produced the judgment
    rubric_version VARCHAR NOT NULL,     -- which rubric version produced it (FR-3)
    status         VARCHAR NOT NULL,     -- {complete, unparseable, model_unavailable}
    criteria_json  VARCHAR NOT NULL,     -- {criterion_id: {band, rationale}} (JSON)
    overall_band   VARCHAR,              -- nullable; {strong, adequate, weak, not_applicable}
    rationale      VARCHAR,              -- nullable; the judge's overall rationale
    raw_output     VARCHAR,              -- nullable; verbatim model output (honest record)
    -- issue #52: how many verdicts this invocation rejected because a criterion's
    -- evidence_quote was not a verbatim span of the dossier text shown to the judge
    -- (confabulated evidence). A standing measure of the judge's own confabulation
    -- rate; 0 for a clean or non-complete judgment.
    ungrounded_rejections INTEGER NOT NULL DEFAULT 0
);
-- Fetch a session's judgments.
CREATE INDEX IF NOT EXISTS ix_judgment_session ON log_judgment(session_id);

-- ----------------------------------------------------------------------------
-- log_improvement — one row per durable improvement PROPOSAL the improvement
-- hook (mission m4) derives from a judgment. The judge (m3) writes a structured
-- verdict into log_judgment but nothing consumes it; the improvement hook reads
-- those verdicts (plus the rubric for criterion→category lookup) and persists
-- agent-readable proposals here — "the operator keeps failing this criterion;
-- look at the prompt's guidance" — so a maintainer agent or the human can decide
-- what to change. The hook PROPOSES; it never acts, never edits prompts/harness/
-- rubrics/skills, and NEVER changes a run's verdict. This is a separate, additive
-- table written only through the sole-writer harness surface
-- (store.record_improvement), exactly like log_judgment.
--
--   * criterion_id is NULLABLE — opaque, rubric-owned data (never enumerated in
--     code). It is NULL for judgment-level proposals (e.g. a non-complete judgment
--     status) and the rubric criterion id for criterion-level proposals.
--   * area is a playbook-owned id (IMPROVEMENT_PLAYBOOK.md). Code never hardcodes
--     area semantics; it parses the playbook and records whatever area the playbook
--     maps the judgment evidence to (the same altitude as the rubric's criterion ids).
--   * status is a fixed vocabulary {open, dismissed, addressed} (PROPOSAL_STATUSES),
--     validated at the store boundary. This mission only ever writes 'open'; the
--     other statuses exist now so a later lifecycle mission needs no schema
--     migration.
--   * playbook_version pins which playbook produced the proposal — the same
--     versioning idiom as log_judgment.rubric_version (a new area bumps the
--     playbook version; no schema or store change is needed).
--
-- summary / evidence carry agent-readable prose; the session log is the local,
-- PHI-bearing store per ADR 0011 / NFR-002 — no code path syncs or exports it.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_improvement (
    improvement_id   VARCHAR PRIMARY KEY,  -- ULID string (python-ulid)
    session_id       VARCHAR NOT NULL REFERENCES log_session(session_id),
    judgment_id      VARCHAR NOT NULL REFERENCES log_judgment(judgment_id),
    created_at       TIMESTAMP NOT NULL,   -- nondeterministic wall-clock; not graded
    criterion_id     VARCHAR,              -- nullable; opaque rubric-owned id (NULL = judgment-level)
    area             VARCHAR NOT NULL,     -- playbook-owned area id (IMPROVEMENT_PLAYBOOK.md)
    summary          VARCHAR NOT NULL,     -- agent-readable proposal summary
    evidence         VARCHAR NOT NULL,     -- the grounding the proposal carries
    playbook_version VARCHAR NOT NULL,     -- which playbook version produced it
    status           VARCHAR NOT NULL      -- {open, dismissed, addressed} (PROPOSAL_STATUSES)
);
-- Fetch a session's improvement proposals.
CREATE INDEX IF NOT EXISTS ix_improvement_session ON log_improvement(session_id);

-- ----------------------------------------------------------------------------
-- log_handoff — the runtime orchestrator's dispatch/handoff trace
-- (docs/building/architecture/OPERATING_ROLES.md). One row per cross-role
-- handoff; compact PHI-safe references, never raw health data. Deliberately
-- NOT FK-bound to log_session: runtime operating sessions are identified by
-- the caller's stable id (typically the research-trace session id) and exist
-- outside the harness-run lifecycle log_session models. Kept out of the
-- warehouse research trace so multiplicity counts stay uncontaminated.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_handoff (
    handoff_id          VARCHAR PRIMARY KEY,
    runtime_session_id  VARCHAR NOT NULL,
    from_id             VARCHAR NOT NULL,  -- 'orchestrator' or a role_id
    to_id               VARCHAR NOT NULL,  -- a role_id, 'orchestrator', or 'human'
    task_summary        VARCHAR NOT NULL,  -- PHI-safe one-liner
    inputs_ref          VARCHAR,           -- compact reference, never raw data
    outputs_ref         VARCHAR,
    surface_touched     VARCHAR,
    status              VARCHAR NOT NULL,  -- 'dispatched' | 'returned' | 'refused' | 'failed'
    reason              VARCHAR,
    recorded_at         TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_lh_session ON log_handoff(runtime_session_id);

-- ----------------------------------------------------------------------------
-- log_answer_audit — answer-audit verdicts keyed by the draft's sha256. The
-- blocking present_answer gate refuses a health-interpreting draft without a
-- passing row for exactly that hash (OPERATING_ROLES.md v1 checks). The
-- verdict rows are append-only; a revised draft is a new hash, never an edit.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_answer_audit (
    audit_id            VARCHAR PRIMARY KEY,
    runtime_session_id  VARCHAR,           -- research-trace session id when given
    draft_sha256        VARCHAR NOT NULL,
    passed              BOOLEAN NOT NULL,
    trace_verified      BOOLEAN NOT NULL,
    disclosure          VARCHAR,           -- measured disclosure the gate attaches
    refusal_count       INTEGER,
    failures            VARCHAR,           -- JSON list of failed-check descriptions
    recorded_at         TIMESTAMP NOT NULL
);
CREATE INDEX IF NOT EXISTS ix_laa_draft ON log_answer_audit(draft_sha256);

-- ----------------------------------------------------------------------------
-- log_improvement_item — the runtime `improvement_scan` role's PRIVATE, LOCAL
-- queue (docs/building/architecture/OPERATING_ROLES.md "Improvement scan,
-- queue, sharing", operating-roles slice 3). One row per improvement
-- candidate the role turns runtime friction (refusals, unmapped metrics,
-- audit failures, repeated handoff loops) into. The item shape is exactly
-- the one the promoted spec adopts from the draft
-- (docs/building/planning/operating-agent-roles.md §"Improvement scan and
-- queue"): id, created_at, status, kind, summary, suggested_action,
-- privacy_level, trace_refs, github_refs.
--
-- NOT the same table as `log_improvement` above. `log_improvement` is a
-- HARNESS-ONLY, dev-time table: the improvement hook (mission m4) derives
-- proposals from an AI judge's `log_judgment` verdict over one recorded
-- repeatable-check/live-trial RUN, keyed to a `judgment_id`, written only by
-- the harness. `log_improvement_item` is the RUNTIME `improvement_scan`
-- role's queue: any operating agent may record an item during a live
-- session through the sole-writer surface below
-- (`store.record_improvement_item`), keyed to no judgment at all. The two
-- tables never share rows or code paths.
--
--   * `kind` is a BOUNDED, OPEN registry id (`premura.ui.improvement_kinds`),
--     never a fixed enum: the seeded kinds are the draft's six
--     (parser_gap / analysis_gap / teaching_gap / workflow_gap / docs_gap /
--     other) and a new kind registers with a short description at write
--     time (DOCTRINE rule 2 — guide, don't enumerate). Validated against the
--     LIVE registry contents at the store boundary, never a frozenset baked
--     into this schema or the store module.
--   * `status` is a FIXED lifecycle vocabulary
--     (`store.IMPROVEMENT_ITEM_STATUSES`), the seven values the draft
--     names; validated at the store boundary.
--   * `privacy_level` is a FIXED vocabulary
--     (`store.IMPROVEMENT_PRIVACY_LEVELS`) naming which of the draft's three
--     sharing levels (minimal / structural / synthetic_example) this
--     candidate would need IF it were ever shared. Sharing itself (share
--     packets, GitHub writes) is out of scope for this slice (later slice
--     4) — the field exists now so slice 4 needs no schema change, and no
--     code path in this slice reads it to make a network call.
--   * `trace_refs_json` / `github_refs_json` are JSON lists of COMPACT
--     references, never raw health data — the same discipline as
--     `log_handoff`'s `*_ref` columns. `github_refs_json` is always
--     caller-supplied and inert here: nothing in this slice reaches GitHub.
-- ----------------------------------------------------------------------------
CREATE TABLE IF NOT EXISTS log_improvement_item (
    item_id           VARCHAR PRIMARY KEY,  -- ULID string
    created_at        TIMESTAMP NOT NULL,
    status            VARCHAR NOT NULL,     -- IMPROVEMENT_ITEM_STATUSES
    kind              VARCHAR NOT NULL,     -- open registry id (premura.ui.improvement_kinds)
    summary           VARCHAR NOT NULL,
    suggested_action  VARCHAR,
    privacy_level     VARCHAR NOT NULL,     -- IMPROVEMENT_PRIVACY_LEVELS
    trace_refs_json   VARCHAR,              -- JSON list of compact references
    github_refs_json  VARCHAR                -- JSON list; inert in this slice
);
CREATE INDEX IF NOT EXISTS ix_lii_status ON log_improvement_item(status);
CREATE INDEX IF NOT EXISTS ix_lii_kind   ON log_improvement_item(kind);
