-- 009_ingest_skip.sql — durable, queryable record of everything the load
-- boundary refused or a parser skipped (m8 WP04).
--
-- Why: unit refusals (WP02's UnitRefusal), batch.skipped_rows, and
-- batch.unmapped_metrics were only ever surfaced in-process (LoadStats /
-- IngestBatch) and never persisted, so nothing computed about a skip survived
-- past the ingest call. hp.ingest_skip gives each skip a durable row joined to
-- its ingest run via batch_id, queryable by kind.
--
-- Shape: append-only, idempotent, mirrors 005_trace_audit.sql. skip_id is a
-- boundary-minted VARCHAR (same idiom as hp.ingest_run.batch_id), not a DB
-- sequence, so rows can be addressed before insert.

CREATE TABLE IF NOT EXISTS hp.ingest_skip (
    skip_id      VARCHAR PRIMARY KEY,
    batch_id     VARCHAR NOT NULL REFERENCES hp.ingest_run(batch_id),
    kind         VARCHAR NOT NULL,   -- 'unit_unconvertible' | 'unmapped_metric' | 'parser_skip'
    raw_field    VARCHAR,            -- vendor field / column label as seen
    metric_id    VARCHAR,            -- nullable — unmapped rows have none yet
    from_unit    VARCHAR,            -- observed (normalized) unit
    to_unit      VARCHAR,            -- the metric's canonical unit
    reason       VARCHAR NOT NULL,   -- human/agent-readable refusal reason
    recorded_at  TIMESTAMP DEFAULT now()
);
CREATE INDEX IF NOT EXISTS ix_is_batch ON hp.ingest_skip(batch_id);
CREATE INDEX IF NOT EXISTS ix_is_kind ON hp.ingest_skip(kind);
