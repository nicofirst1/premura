# Data Model: Model Intake And Profile Context

This mission defines a **semantic data model**, not a storage schema. The fields
below are the minimum contract fields later implementations must be able to
represent, regardless of where they are persisted.

## 1. Baseline Profile Context

### Entity: `ProfileAttribute`

Defines the kind of operator-context value being asserted.

**Required fields**
- `attribute_key`: stable identifier such as `birth_date`, `biological_sex`, or
  `standing_height_declared`
- `value_kind`: `date`, `enum`, `quantity`, `text`, or `boolean`
- `stability_class`: `stable`, `slowly_changing`, or `derived`
- `description`: plain-language meaning

**Validation rules**
- `stability_class=derived` means the attribute is computed from another
  attribute and is not independently edited.
- `ProfileAttribute` names the meaning of the attribute; it does not itself
  store the operator's current value.

### Entity: `ProfileAssertion`

One recorded statement about one baseline profile attribute.

**Required fields**
- `assertion_id`
- `attribute_key`
- `value`
- `effective_start`
- `asserted_at`
- `provenance_kind`: `manual`, `imported`, `derived`, or `corrected`
- `source_reference`: human/audit-visible origin descriptor
- `supersedes_assertion_id` (nullable)

**Validation rules**
- A corrected or newer assertion must not silently overwrite the old one; the
  supersession/correction chain must remain visible.
- `age` is not an independently asserted profile attribute when `birth_date`
  exists; it is derived context at evaluation time.

**State transitions**
- `active` -> `superseded`
- `active` -> `corrected`
- `corrected` and `superseded` remain part of provenance history

## 2. Intake Backbone

### Entity: `IntakeEvent`

One eating, drinking, or supplement-taking occurrence.

**Required fields**
- `intake_event_id`
- `event_kind`: `meal`, `drink`, `supplement`, or `mixed`
- `occurred_at`
- `local_context` (nullable)
- `provenance_kind`
- `source_reference`
- `supersedes_event_id` (nullable)

**Validation rules**
- `IntakeEvent` anchors when consumption happened; it does not by itself imply
  nutrient amounts or doses.
- Corrections must create a visible correction/supersession relationship rather
  than silently mutating history.

### Entity: `IntakeItem`

One consumed thing inside an intake event.

**Required fields**
- `intake_item_id`
- `intake_event_id`
- `item_kind`: `food`, `drink`, or `supplement`
- `label`
- `quantity_description` (nullable)
- `product_reference` (nullable)

**Validation rules**
- An `IntakeEvent` may have multiple `IntakeItem`s.
- `item_kind=supplement` allows but does not require a branded product
  reference; unknown products remain representable.

## 3. Nutrition Domain

### Entity: `NutritionFact`

One energy or nutrient amount attributed to an intake item or event.

**Required fields**
- `nutrition_fact_id`
- `subject_kind`: `event` or `item`
- `subject_id`
- `fact_key`: such as `energy_kcal`, `protein_g`, `carbohydrate_g`, or
  `sodium_mg`
- `amount`
- `unit`
- `estimate_quality`: `exact`, `estimated`, or `partial`

**Validation rules**
- A `NutritionFact` cannot exist without an `IntakeEvent` anchor, directly or
  through its `IntakeItem`.
- Partial nutrition records are valid; unknown nutrients remain absent rather
  than fabricated.

## 4. Supplement Domain

### Entity: `SupplementDose`

The quantity taken of a supplement item.

**Required fields**
- `supplement_dose_id`
- `intake_item_id`
- `dose_amount`
- `dose_unit`
- `ingredient_scope`: `single_ingredient`, `multi_ingredient`, or `unknown`
- `ingredient_reference` (nullable)

**Validation rules**
- A `SupplementDose` must attach to an `IntakeItem` whose `item_kind` is
  `supplement`.
- A supplement may be known only as a branded product; the model must still
  preserve the taken dose even if every underlying ingredient is not known.

## 5. Dependency Declaration

### Entity: `DependencyDeclaration`

The prerequisites a future function or workflow requires.

**Required fields**
- `consumer_name`
- `depends_on_domain`: one or more of `profile_context`, `nutrition_intake`,
  `supplement_intake`, `observation_history`
- `required_keys`: list of specific attribute/fact/dose keys
- `failure_mode`: what happens when the dependency is absent or stale/unknown

**Validation rules**
- A future function that requires profile or intake context must declare it
  explicitly; it must not assume opportunistic presence in measurement history.

## 6. Relationships

- `ProfileAttribute` 1 -> N `ProfileAssertion`
- `IntakeEvent` 1 -> N `IntakeItem`
- `IntakeItem` 1 -> N `NutritionFact`
- `IntakeItem` 0..1 -> N `SupplementDose`
- `IntakeEvent` 1 -> N `NutritionFact` (event-level totals allowed)
- `DependencyDeclaration` references one or more of the domains above

## 7. Overlap Rules With Existing Observation History

- A device-measured value such as smart-scale height is an **observation**.
- A manually declared standing height is **profile context**.
- A meal's calories are **nutrition facts attached to intake**.
- A wearable's `total_kcal` output remains an **observation/interval aggregate**.
- A supplement dose is **intake**, not a body-state observation.
- Narrative context that cannot be normalized remains a **note**, not a catch-all
  replacement for profile/intake structure.

## 8. Positive Invariants

1. Every normalized example must map to exactly one canonical home.
2. Profile assertions, intake records, and observations remain distinguishable
   even when they refer to similar concepts.
3. Corrections and supersessions remain visible in provenance history.
4. No future function may depend on profile or intake context implicitly.
5. Partial nutrition or supplement knowledge is allowed, but fabricated values
   are not.
