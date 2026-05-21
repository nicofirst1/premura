-- 001_init.sql — initial star schema for the premura warehouse.
-- Long-format star: one fact row per observation, two dims (metric, source).
-- Two fact tables differ by cardinality: point-in-time (fact_measurement) vs. interval (fact_interval).

CREATE SCHEMA IF NOT EXISTS hp;

CREATE SEQUENCE IF NOT EXISTS hp.measurement_id_seq;
CREATE SEQUENCE IF NOT EXISTS hp.interval_id_seq;

CREATE TABLE IF NOT EXISTS hp.dim_metric (
    metric_id      VARCHAR PRIMARY KEY,
    display_name   VARCHAR NOT NULL,
    canonical_unit VARCHAR NOT NULL,
    value_kind     VARCHAR NOT NULL,  -- 'instantaneous' | 'aggregate' | 'interval'
    description    VARCHAR
);

CREATE TABLE IF NOT EXISTS hp.dim_source (
    source_id            VARCHAR PRIMARY KEY,
    source_kind          VARCHAR NOT NULL,  -- 'health_connect' | 'garmin_gdpr' | 'sleep_as_android' | 'bmt'
    app_package          VARCHAR,
    app_name             VARCHAR,
    device_manufacturer  VARCHAR,
    device_model         VARCHAR,
    first_seen           TIMESTAMP,
    last_seen            TIMESTAMP
);

CREATE TABLE IF NOT EXISTS hp.fact_measurement (
    measurement_id  UBIGINT PRIMARY KEY DEFAULT nextval('hp.measurement_id_seq'),
    ts_utc          TIMESTAMP NOT NULL,
    local_tz        VARCHAR,
    metric_id       VARCHAR NOT NULL REFERENCES hp.dim_metric(metric_id),
    value_num       DOUBLE,
    value_text      VARCHAR,
    unit            VARCHAR NOT NULL,
    source_id       VARCHAR NOT NULL REFERENCES hp.dim_source(source_id),
    source_uuid     VARCHAR,
    dedupe_key      VARCHAR NOT NULL UNIQUE,
    ingested_at     TIMESTAMP DEFAULT now(),
    ingest_batch    VARCHAR,
    raw_payload     JSON
);
CREATE INDEX IF NOT EXISTS ix_fm_ts_metric    ON hp.fact_measurement(ts_utc, metric_id);
CREATE INDEX IF NOT EXISTS ix_fm_metric_ts    ON hp.fact_measurement(metric_id, ts_utc);
CREATE INDEX IF NOT EXISTS ix_fm_source_uuid  ON hp.fact_measurement(source_uuid);

CREATE TABLE IF NOT EXISTS hp.fact_interval (
    interval_id   UBIGINT PRIMARY KEY DEFAULT nextval('hp.interval_id_seq'),
    metric_id     VARCHAR NOT NULL REFERENCES hp.dim_metric(metric_id),
    start_utc     TIMESTAMP NOT NULL,
    end_utc       TIMESTAMP NOT NULL,
    local_tz      VARCHAR,
    value_num     DOUBLE,
    value_text    VARCHAR,
    source_id     VARCHAR NOT NULL REFERENCES hp.dim_source(source_id),
    source_uuid   VARCHAR,
    parent_uuid   VARCHAR,  -- e.g. sleep_stage.parent = sleep_session.source_uuid
    dedupe_key    VARCHAR NOT NULL UNIQUE,
    ingested_at   TIMESTAMP DEFAULT now(),
    ingest_batch  VARCHAR,
    raw_payload   JSON
);
CREATE INDEX IF NOT EXISTS ix_fi_start_metric ON hp.fact_interval(start_utc, metric_id);
CREATE INDEX IF NOT EXISTS ix_fi_parent       ON hp.fact_interval(parent_uuid);

CREATE TABLE IF NOT EXISTS hp.ingest_run (
    batch_id          VARCHAR PRIMARY KEY,
    started_at        TIMESTAMP DEFAULT now(),
    finished_at       TIMESTAMP,
    source_kind       VARCHAR,
    source_path       VARCHAR,
    source_sha256     VARCHAR,
    rows_inserted     BIGINT,
    rows_skipped_dup  BIGINT,
    notes             VARCHAR
);
CREATE INDEX IF NOT EXISTS ix_ir_sha ON hp.ingest_run(source_sha256);
