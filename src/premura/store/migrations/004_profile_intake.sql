-- 004_profile_intake.sql — concrete warehouse homes for profile context,
-- nutrition intake, and supplement intake.
--
-- Mission: implement-profile-and-intake-storage-01KSMWV1 (WP01).
--
-- Why a dedicated migration instead of reusing hp.fact_measurement /
-- hp.fact_interval / hp.fact_clinical_note: the planning artifacts require a
-- "one-home" rule. Profile assertions, nutrition intake, and supplement intake
-- are three distinct meanings and must never be back-filled into the
-- observation/note tables as a shortcut. This migration makes that separation
-- structural: each domain has its own explicit tables under hp., with its own
-- provenance, supersession, and dedupe columns. There is deliberately no
-- generic JSON catch-all bucket.
--
-- Idempotency: every statement uses CREATE ... IF NOT EXISTS so the normal
-- migration loader (premura.store.duck.run_migrations) can re-run it safely on
-- an already-initialized warehouse. The older observation tables (001) and the
-- clinical-note table (003) are NOT touched here.
--
-- Append/supersede semantics: profile assertions and intake events keep history
-- by inserting a new row that points at the row it corrects
-- (supersedes_assertion_id / supersedes_event_id) and closing the prior row's
-- effective window, rather than overwriting in place.

CREATE SCHEMA IF NOT EXISTS hp;

CREATE SEQUENCE IF NOT EXISTS hp.profile_capture_session_id_seq;
CREATE SEQUENCE IF NOT EXISTS hp.profile_assertion_id_seq;
CREATE SEQUENCE IF NOT EXISTS hp.nutrition_event_id_seq;
CREATE SEQUENCE IF NOT EXISTS hp.nutrition_item_id_seq;
CREATE SEQUENCE IF NOT EXISTS hp.nutrition_quantity_id_seq;
CREATE SEQUENCE IF NOT EXISTS hp.supplement_event_id_seq;
CREATE SEQUENCE IF NOT EXISTS hp.supplement_item_id_seq;
CREATE SEQUENCE IF NOT EXISTS hp.supplement_dose_id_seq;

-- ----------------------------------------------------------------------------
-- Profile context: agent-mediated bounded interview capture.
-- ----------------------------------------------------------------------------

-- One bounded agent-mediated profile interview. Holds session bookkeeping only;
-- it must never store health interpretation text (that is note_history's job).
CREATE TABLE IF NOT EXISTS hp.profile_capture_session (
    capture_session_id  UBIGINT PRIMARY KEY DEFAULT nextval('hp.profile_capture_session_id_seq'),
    started_at          TIMESTAMP NOT NULL,
    finished_at         TIMESTAMP,
    actor_kind          VARCHAR NOT NULL,  -- bounded to supported capture paths, e.g. 'agent'
    actor_ref           VARCHAR,
    notes               VARCHAR
);

-- One stored statement about one bounded baseline profile fact. New assertions
-- for the same attribute_key supersede earlier ones; the earlier row remains in
-- history with its effective_end_utc closed. This is the append/supersede home
-- for profile facts — it is NOT hp.fact_measurement.
CREATE TABLE IF NOT EXISTS hp.profile_context_assertion (
    assertion_id            UBIGINT PRIMARY KEY DEFAULT nextval('hp.profile_assertion_id_seq'),
    capture_session_id      UBIGINT REFERENCES hp.profile_capture_session(capture_session_id),
    attribute_key           VARCHAR NOT NULL,  -- bounded allowlist, e.g. 'birth_date', 'sex'
    value_text              VARCHAR,
    value_num               DOUBLE,
    value_date              DATE,
    unit                    VARCHAR,
    effective_start_utc     TIMESTAMP NOT NULL,
    effective_end_utc       TIMESTAMP,
    recorded_at             TIMESTAMP NOT NULL DEFAULT now(),
    source_kind             VARCHAR NOT NULL,  -- provenance, e.g. 'agent_profile_capture'
    source_ref              VARCHAR,
    supersedes_assertion_id UBIGINT REFERENCES hp.profile_context_assertion(assertion_id),
    raw_payload             JSON
);
-- "Current" lookups (open assertions per attribute) and history walks.
CREATE INDEX IF NOT EXISTS ix_pca_attr_effective
    ON hp.profile_context_assertion(attribute_key, effective_start_utc);
CREATE INDEX IF NOT EXISTS ix_pca_session
    ON hp.profile_context_assertion(capture_session_id);
CREATE INDEX IF NOT EXISTS ix_pca_supersedes
    ON hp.profile_context_assertion(supersedes_assertion_id);

-- ----------------------------------------------------------------------------
-- Nutrition intake: parser-ready normalized seam for eating/drinking events.
-- Distinct from supplement intake and from observation/note history.
-- ----------------------------------------------------------------------------

-- One eating or drinking occurrence produced by a future parser/plugin.
CREATE TABLE IF NOT EXISTS hp.nutrition_intake_event (
    nutrition_event_id  UBIGINT PRIMARY KEY DEFAULT nextval('hp.nutrition_event_id_seq'),
    source_id           VARCHAR NOT NULL REFERENCES hp.dim_source(source_id),
    source_uuid         VARCHAR,
    start_utc           TIMESTAMP NOT NULL,
    end_utc             TIMESTAMP,
    local_tz            VARCHAR,
    meal_label          VARCHAR,  -- optional, e.g. breakfast/lunch/snack
    dedupe_key          VARCHAR NOT NULL UNIQUE,
    ingested_at         TIMESTAMP DEFAULT now(),
    ingest_batch        VARCHAR,
    raw_payload         JSON
);
CREATE INDEX IF NOT EXISTS ix_nie_start  ON hp.nutrition_intake_event(start_utc);
CREATE INDEX IF NOT EXISTS ix_nie_source ON hp.nutrition_intake_event(source_id, source_uuid);

-- One consumed food or drink inside an event.
CREATE TABLE IF NOT EXISTS hp.nutrition_intake_item (
    nutrition_item_id   UBIGINT PRIMARY KEY DEFAULT nextval('hp.nutrition_item_id_seq'),
    nutrition_event_id  UBIGINT NOT NULL REFERENCES hp.nutrition_intake_event(nutrition_event_id),
    item_label          VARCHAR NOT NULL,
    brand_label         VARCHAR,
    serving_text        VARCHAR,
    raw_payload         JSON
);
CREATE INDEX IF NOT EXISTS ix_nii_event ON hp.nutrition_intake_item(nutrition_event_id);

-- One energy or nutrient quantity attached to a nutrition event OR item. These
-- quantity keys stay distinct from body-observation metrics (dim_metric); a meal
-- kcal lives here, a wearable's expended kcal lives in observation history.
CREATE TABLE IF NOT EXISTS hp.nutrition_quantity (
    nutrition_quantity_id   UBIGINT PRIMARY KEY DEFAULT nextval('hp.nutrition_quantity_id_seq'),
    nutrition_event_id      UBIGINT REFERENCES hp.nutrition_intake_event(nutrition_event_id),
    nutrition_item_id       UBIGINT REFERENCES hp.nutrition_intake_item(nutrition_item_id),
    quantity_key            VARCHAR NOT NULL,  -- nutrient/energy key, e.g. 'energy', 'protein'
    value_num               DOUBLE NOT NULL,
    unit                    VARCHAR,
    raw_payload             JSON,
    -- At least one parent must be present (event-level or item-level quantity).
    CHECK (nutrition_event_id IS NOT NULL OR nutrition_item_id IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_nq_event ON hp.nutrition_quantity(nutrition_event_id);
CREATE INDEX IF NOT EXISTS ix_nq_item  ON hp.nutrition_quantity(nutrition_item_id);

-- ----------------------------------------------------------------------------
-- Supplement intake: parser-ready seam for supplement-taking occurrences.
-- Deliberately separate from nutrition intake so the two meanings never merge.
-- ----------------------------------------------------------------------------

-- One supplement-taking occurrence from a future parser/plugin.
CREATE TABLE IF NOT EXISTS hp.supplement_intake_event (
    supplement_event_id UBIGINT PRIMARY KEY DEFAULT nextval('hp.supplement_event_id_seq'),
    source_id           VARCHAR NOT NULL REFERENCES hp.dim_source(source_id),
    source_uuid         VARCHAR,
    ts_utc              TIMESTAMP NOT NULL,
    local_tz            VARCHAR,
    dedupe_key          VARCHAR NOT NULL UNIQUE,
    ingested_at         TIMESTAMP DEFAULT now(),
    ingest_batch        VARCHAR,
    raw_payload         JSON
);
CREATE INDEX IF NOT EXISTS ix_sie_ts     ON hp.supplement_intake_event(ts_utc);
CREATE INDEX IF NOT EXISTS ix_sie_source ON hp.supplement_intake_event(source_id, source_uuid);

-- The product or ingredient taken in one supplement event. At least one of
-- product_label / ingredient_label is expected to be present (enforced in the
-- Python write path, where partial knowledge is representable as NULL).
CREATE TABLE IF NOT EXISTS hp.supplement_item (
    supplement_item_id  UBIGINT PRIMARY KEY DEFAULT nextval('hp.supplement_item_id_seq'),
    supplement_event_id UBIGINT NOT NULL REFERENCES hp.supplement_intake_event(supplement_event_id),
    product_label       VARCHAR,
    ingredient_label    VARCHAR,
    form_label          VARCHAR,  -- e.g. capsule/powder/liquid
    raw_payload         JSON
);
CREATE INDEX IF NOT EXISTS ix_si_event ON hp.supplement_item(supplement_event_id);

-- One taken dose attached to a supplement item. amount_num covers quantitative
-- doses; amount_text preserves qualitative wording when only that exists.
CREATE TABLE IF NOT EXISTS hp.supplement_dose (
    supplement_dose_id  UBIGINT PRIMARY KEY DEFAULT nextval('hp.supplement_dose_id_seq'),
    supplement_item_id  UBIGINT NOT NULL REFERENCES hp.supplement_item(supplement_item_id),
    ingredient_label    VARCHAR,
    amount_num          DOUBLE,
    amount_text         VARCHAR,
    unit                VARCHAR,
    raw_payload         JSON,
    -- A dose must carry at least one amount representation.
    CHECK (amount_num IS NOT NULL OR amount_text IS NOT NULL)
);
CREATE INDEX IF NOT EXISTS ix_sd_item ON hp.supplement_dose(supplement_item_id);
