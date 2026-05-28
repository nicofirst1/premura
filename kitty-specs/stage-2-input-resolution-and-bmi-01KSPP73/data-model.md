# Data Model: Stage 2 Input Resolution And BMI

## Overview

This mission introduces a Stage 2 data model for **declared inputs** and their
resolution, not a new warehouse schema. The main entities describe what a Stage
2 consumer asks for, how the engine resolves it, and how the first proof
consumer (BMI) combines those resolved inputs.

## Entities

### 1. Declared Dependency

**Purpose**: State exactly what a Stage 2 consumer needs.

**Fields**:

- `consumer_name` — the Stage 2 answer or tool that owns the dependency
- `depends_on_domain` — one of the semantic domains such as
  `observation_history`, `profile_context`, `nutrition_intake`, or
  `supplement_intake`
- `required_key` — the exact metric or attribute key required
- `failure_mode` — how the consumer behaves if the dependency is missing, stale,
  partial, or unsupported

**Validation rules**:

- `depends_on_domain` must be an allowed semantic domain
- `required_key` must be explicit; a bare domain reference is invalid
- `failure_mode` must be one of the supported honest-refusal behaviors

### 2. Anchor Time

**Purpose**: Define the time context for resolution.

**Fields**:

- `anchor_ts` — the time the consumer is asking about

**Validation rules**:

- must be explicit for time-sensitive consumers
- may default to "now" only when the consumer's question shape allows it

### 3. Resolved Observation Input

**Purpose**: Represent a dependency resolved from observation history.

**Fields**:

- `domain` — `observation_history`
- `required_key`
- `anchor_ts`
- `resolved_value` — latest usable or otherwise policy-valid observation value
- `observed_at`
- `freshness_state`
- `absence_reason` — when not usable
- `caveats` — optional user-visible caveats

**Validation rules**:

- must respect the metric's validity window
- must not silently substitute from another domain
- must expose absence or staleness explicitly

### 4. Resolved Profile Input

**Purpose**: Represent a dependency resolved from profile context as of an anchor
time.

**Fields**:

- `domain` — `profile_context`
- `required_key`
- `anchor_ts`
- `resolved_value` — latest applicable declared value
- `effective_start_utc`
- `effective_end_utc` or equivalent current applicability indicator
- `absence_reason` — when not usable
- `source_kind`

**Validation rules**:

- must resolve by meaning, not by opportunistically reading observation history
- must return the latest valid declaration as of the anchor time
- must expose absence explicitly

### 5. Unsupported Domain Resolution Outcome

**Purpose**: Represent a declared dependency for a valid future domain whose
resolver is not shipped yet.

**Fields**:

- `domain`
- `required_key`
- `anchor_ts`
- `absence_reason`
- `message`

**Validation rules**:

- must be explicit
- must not be silently coerced into another supported domain

### 6. Resolver Registry Entry

**Purpose**: Map one supported semantic domain to its concrete resolver.

**Fields**:

- `domain`
- `resolver_name`
- `module`

**Validation rules**:

- each supported domain has at most one active built-in resolver entry
- unsupported-but-declarable domains do not need a concrete entry yet

### 7. BMI Proof Consumer

**Purpose**: Prove the input-resolution seam using one real cross-domain answer.

**Fields**:

- `consumer_name` — BMI
- `dependencies` — declared profile height + observation weight
- `anchor_ts`
- `result_status`
- `value` — produced only when both dependencies are usable
- `missing_input_report` — when not usable
- `caveats`

**Validation rules**:

- cannot produce a value unless both dependencies resolve honestly
- must not substitute measured height for declared height
- must expose missing or stale prerequisites explicitly

## Relationships

- One **BMI Proof Consumer** has two or more **Declared Dependencies**.
- Each **Declared Dependency** resolves, for a given **Anchor Time**, to exactly
  one of:
  - **Resolved Observation Input**
  - **Resolved Profile Input**
  - **Unsupported Domain Resolution Outcome**
- One **Resolver Registry Entry** serves one supported semantic domain.

## State / Outcome Model

For this mission, resolved inputs should support at least these observable
states:

- usable
- missing
- stale
- unsupported-but-declared

BMI must map those states into either:

- successful proof result
- explicit refusal with missing-input detail

## Non-Goals

- No new warehouse tables in this mission's data model
- No nutrition or supplement concrete resolution model yet
- No new answer-family data model yet
