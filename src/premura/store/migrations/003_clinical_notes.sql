-- 003_clinical_notes.sql — narrative commentary / diagnosis note storage.

CREATE SEQUENCE IF NOT EXISTS hp.note_id_seq;

CREATE TABLE IF NOT EXISTS hp.fact_clinical_note (
    note_id       UBIGINT PRIMARY KEY DEFAULT nextval('hp.note_id_seq'),
    ts_utc        TIMESTAMP NOT NULL,
    source_id     VARCHAR NOT NULL REFERENCES hp.dim_source(source_id),
    language      VARCHAR,
    text          VARCHAR NOT NULL,
    dedupe_key    VARCHAR NOT NULL UNIQUE,
    ingest_batch  VARCHAR,
    raw_payload   JSON
);

CREATE INDEX IF NOT EXISTS ix_fcn_ts_source ON hp.fact_clinical_note(ts_utc, source_id);
