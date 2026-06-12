-- 007_condition_episode.sql — warehouse home for operator-declared condition
-- episodes (the agent-mediated capture follow-up named-deferred by the
-- condition_paired_t_test work; ROADMAP §"Near-term roadmap" item 2).
--
-- What a row is: one operator assertion "I was in <condition_label> from
-- start_day through end_day" (end_day NULL = ongoing at declaration time).
-- The label is operator vocabulary — any non-empty string, never validated
-- against an enum or registry, and never a verified medical condition. The
-- analytical seam is unchanged: episodes still arrive at the engine inside a
-- pre-registered request; this table only lets the MCP wrapper load a stored
-- declaration instead of forcing the caller to re-declare per request.
--
-- Why a dedicated table (one-home rule): an episode is neither a profile
-- assertion (hp.profile_context_assertion is a closed allowlist of baseline
-- attributes), nor intake, nor a clinical note. Same append/supersede posture
-- as profile capture: corrections append a new row linking back via
-- supersedes_episode_id (the superseded row gets superseded_at closed);
-- withdrawals set retracted_at + a reason. History is never overwritten or
-- deleted.
--
-- Idempotency: CREATE ... IF NOT EXISTS throughout, safe for the normal
-- migration loader (premura.store.duck.run_migrations) to re-run.

CREATE SCHEMA IF NOT EXISTS hp;

CREATE SEQUENCE IF NOT EXISTS hp.condition_episode_id_seq;

CREATE TABLE IF NOT EXISTS hp.condition_episode (
    episode_id            UBIGINT PRIMARY KEY DEFAULT nextval('hp.condition_episode_id_seq'),
    condition_label       VARCHAR NOT NULL,   -- operator vocabulary, never an enum
    start_day             DATE NOT NULL,      -- local calendar day, inclusive
    end_day               DATE,               -- inclusive; NULL = ongoing at declaration
    declared_at           TIMESTAMP NOT NULL DEFAULT now(),
    capture_session_id    UBIGINT REFERENCES hp.profile_capture_session(capture_session_id),
    source_kind           VARCHAR NOT NULL,   -- e.g. 'agent_condition_capture'
    source_ref            VARCHAR,
    supersedes_episode_id UBIGINT REFERENCES hp.condition_episode(episode_id),
    superseded_at         TIMESTAMP,          -- set on THIS row when a correction supersedes it
    retracted_at          TIMESTAMP,          -- set when the operator withdraws the declaration
    retraction_reason     VARCHAR,
    note                  VARCHAR,
    raw_payload           JSON,
    CHECK (end_day IS NULL OR end_day >= start_day)
);

-- "Current declared set for a label" is the hot read (the analysis path).
CREATE INDEX IF NOT EXISTS ix_ce_label_start
    ON hp.condition_episode(condition_label, start_day);
CREATE INDEX IF NOT EXISTS ix_ce_supersedes
    ON hp.condition_episode(supersedes_episode_id);
