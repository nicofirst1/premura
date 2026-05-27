# Data Model: Implement Profile And Intake Storage

## Overview

This mission introduces concrete warehouse entities for three profile/intake
domains while keeping the capture paths distinct:

- **Profile context** is captured through an agent-mediated bounded interview.
- **Nutrition intake** and **supplement intake** are persisted through a
  parser-ready normalized seam that future source-specific parsers can target.

## Entities

### 1. ProfileCaptureSession

Purpose: anchor one bounded agent-mediated profile interview.

Fields:

- `capture_session_id`: unique session identifier
- `started_at`: when the session began
- `finished_at`: when the session completed
- `actor_kind`: expected value `agent`
- `actor_ref`: optional agent/tool identity
- `notes`: optional session note

Validation rules:

- `actor_kind` must be bounded to supported capture paths for this mission.
- Session rows must not store health interpretation text.

### 2. ProfileContextAssertion

Purpose: one stored statement about one bounded baseline profile fact.

Fields:

- `assertion_id`: unique identifier
- `capture_session_id`: optional link to `ProfileCaptureSession`
- `attribute_key`: bounded allowlist value, for example `birth_date`, `sex`,
  `standing_height_cm`
- `value_text`: optional typed storage slot
- `value_num`: optional typed storage slot
- `value_date`: optional typed storage slot
- `unit`: optional unit where relevant
- `effective_start_utc`: when the asserted value became effective
- `effective_end_utc`: when the value stopped being effective, if superseded
- `recorded_at`: when Premura stored the assertion
- `source_kind`: provenance label such as `agent_profile_capture`
- `source_ref`: optional external/session reference
- `supersedes_assertion_id`: optional link to the assertion this one corrects
- `raw_payload`: optional diagnostic payload

Validation rules:

- `attribute_key` must appear in the profile allowlist.
- Exactly one typed value slot must be populated.
- `age` is not a stored attribute in this mission; it remains derivable from
  `birth_date` plus evaluation date.

State transitions:

- New assertion for the same `attribute_key` may supersede an earlier one.
- Earlier assertion remains in history; it is not overwritten in place.

### 3. NutritionIntakeEvent

Purpose: one eating or drinking occurrence from a future parser/plugin.

Fields:

- `nutrition_event_id`: unique identifier
- `source_id`: provenance descriptor
- `source_uuid`: source-stable row/event id when available
- `start_utc`: event start time
- `end_utc`: optional event end time
- `local_tz`: optional timezone
- `meal_label`: optional label such as breakfast/lunch/snack
- `dedupe_key`: warehouse uniqueness key
- `ingest_batch`: optional ingest batch id for source-artifact loads
- `raw_payload`: optional raw source payload

Validation rules:

- `dedupe_key` must be unique.
- Event rows must never be stored in `hp.fact_measurement` or notes instead.

### 4. NutritionIntakeItem

Purpose: one consumed food or drink inside an event.

Fields:

- `nutrition_item_id`: unique identifier
- `nutrition_event_id`: parent event
- `item_label`: human-readable food/drink label
- `brand_label`: optional vendor/brand label
- `serving_text`: optional source-facing serving description
- `raw_payload`: optional raw source payload

Validation rules:

- Every item belongs to exactly one event.

### 5. NutritionQuantity

Purpose: one energy or nutrient quantity attached to an event or item.

Fields:

- `nutrition_quantity_id`: unique identifier
- `nutrition_event_id`: optional parent event
- `nutrition_item_id`: optional parent item
- `quantity_key`: nutrient or energy key
- `value_num`: numeric amount
- `unit`: canonical or source unit
- `raw_payload`: optional raw source payload

Validation rules:

- At least one of `nutrition_event_id` or `nutrition_item_id` must be present.
- Quantity keys remain distinct from body-observation metrics.

### 6. SupplementIntakeEvent

Purpose: one supplement-taking occurrence from a future parser/plugin.

Fields:

- `supplement_event_id`: unique identifier
- `source_id`: provenance descriptor
- `source_uuid`: source-stable row/event id when available
- `ts_utc`: event time
- `local_tz`: optional timezone
- `dedupe_key`: warehouse uniqueness key
- `ingest_batch`: optional ingest batch id
- `raw_payload`: optional raw source payload

Validation rules:

- `dedupe_key` must be unique.

### 7. SupplementItem

Purpose: the product or ingredient taken in one supplement event.

Fields:

- `supplement_item_id`: unique identifier
- `supplement_event_id`: parent event
- `product_label`: optional branded product name
- `ingredient_label`: optional ingredient name
- `form_label`: optional form such as capsule/powder/liquid
- `raw_payload`: optional raw source payload

Validation rules:

- At least one of `product_label` or `ingredient_label` must be present.

### 8. SupplementDose

Purpose: one taken dose attached to a supplement item.

Fields:

- `supplement_dose_id`: unique identifier
- `supplement_item_id`: parent item
- `ingredient_label`: optional explicit ingredient the dose refers to
- `amount_num`: optional numeric amount
- `amount_text`: optional free-text amount when only qualitative wording exists
- `unit`: optional dose unit
- `raw_payload`: optional raw source payload

Validation rules:

- At least one of `amount_num` or `amount_text` must be present.

## Relationships

- `ProfileCaptureSession` 1:N `ProfileContextAssertion`
- `NutritionIntakeEvent` 1:N `NutritionIntakeItem`
- `NutritionIntakeEvent` 1:N `NutritionQuantity`
- `NutritionIntakeItem` 1:N `NutritionQuantity`
- `SupplementIntakeEvent` 1:N `SupplementItem`
- `SupplementItem` 1:N `SupplementDose`

## One-Home Rules

- `ProfileContextAssertion` is never stored as `hp.fact_measurement`.
- `NutritionQuantity` is never stored as a wearable/body measurement.
- `SupplementDose` is never merged into nutrition intake or note history.

## Planned Storage Shape

Planned migration: `src/premura/store/migrations/004_profile_intake.sql`

Planned service module: `src/premura/store/profile_intake.py`

The persistence service should expose two write paths:

1. `record_profile_context(...)` for bounded profile capture
2. `persist_intake_batch(...)` for parser-produced nutrition/supplement records
