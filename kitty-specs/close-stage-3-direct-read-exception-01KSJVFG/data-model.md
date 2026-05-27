# Data Model — Close the Stage 3 Direct-Read Exception

## Overview

This mission does not alter the DuckDB warehouse schema. It introduces Stage 2 result objects and Stage 3 surface distinctions so that metric catalog/summary reads are validity-gated and raw SQL is isolated behind an operator-only entrypoint.

## Entities

### Metric Catalog Entry

Represents one metric on the default agent-facing catalog surface.

| Field | Type | Description |
|---|---|---|
| `metric_id` | string | Canonical metric identifier |
| `label` | string | Human-readable metric name if available |
| `validity_status` | enum | `current`, `stale`, or `unavailable` |
| `validity_window` | string or null | Declared freshness window from metric metadata |
| `missing_data_policy` | string or null | Declared missing-data policy |
| `latest_observation_at` | datetime or null | Timestamp of the most recent usable observation |
| `latest_value` | number or null | Most recent usable value; absent when unavailable |
| `unit` | string or null | Canonical unit |
| `message` | string | Plain-language explanation of availability/trust |

**Validation rules**

- `validity_status` uses existing Stage 2 freshness vocabulary only.
- `latest_value` is null when the metric is unavailable or unknown.
- No raw row-count field is exposed on this surface.

### Metric Validity Summary

Represents the default agent-facing per-metric summary surface.

| Field | Type | Description |
|---|---|---|
| `metric_id` | string | Canonical metric identifier |
| `validity_status` | enum | `current`, `stale`, or `unavailable` |
| `latest_observation_at` | datetime or null | Timestamp of most recent usable observation |
| `latest_value` | number or null | Most recent usable value |
| `unit` | string or null | Canonical unit |
| `validity_window` | string or null | Declared freshness window |
| `missing_data_policy` | string or null | Declared missing-data policy |
| `sample_size` | integer | Count of observations in the recent window |
| `imputed_proportion` | float | Fraction of points imputed in the recent window |
| `gap_count` | integer | Count of uncovered gaps in the recent window |
| `window_days` | integer | Fixed recent-window span used for coverage metrics |
| `message` | string | Plain-language explanation of trust / absence |

**Validation rules**

- `sample_size`, `imputed_proportion`, and `gap_count` are always present as explicit machine-branchable fields.
- `imputed_proportion` is `0.0` when the missing-data policy forbids imputation.
- All-time extrema (`min`, `max`, `avg`) are not present.

### Operator Entry Point Surface

Represents the lower-guarantee MCP surface for expert or explicitly user-approved raw exploration.

| Field | Type | Description |
|---|---|---|
| `entrypoint_name` | string | Distinct operator entrypoint command |
| `registered_tools` | list[string] | Default tool set plus `query_warehouse` |
| `disclosure_required` | boolean | Indicates the caller must disclose lower-guarantee mode to the user |
| `approval_required` | boolean | Indicates explicit user approval is required before agent use |

**Validation rules**

- Default entrypoint excludes `query_warehouse`.
- Operator entrypoint differs from default only by explicitly operator-scoped registrations in this mission.

## Relationships

- A `Metric Catalog Entry` and a `Metric Validity Summary` both derive from warehouse facts plus metric metadata.
- The operator entrypoint is a surface distinction over the same underlying server core and warehouse, not a second datastore.

## State transitions

### Validity Status

| From | To | Trigger |
|---|---|---|
| `current` | `stale` | Latest usable observation ages past the declared validity window |
| `stale` | `current` | Fresh usable observation arrives |
| `current` or `stale` | `unavailable` | No usable observations remain after filtering |
| `unavailable` | `current` or `stale` | A usable observation appears and is evaluated against freshness |
