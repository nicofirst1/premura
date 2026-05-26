# Data Model - Implement Grounded Stage 2 Functions

This mission does not require a warehouse schema change. The relevant data model is logical: registry metadata, structured signal results, and MCP tool responses.

## 1. Signal Registration

Represents one Stage 2 engine function that can be discovered, reviewed, and exposed through Stage 3.

| Field | Type | Required | Notes |
|---|---|---|---|
| `name` | string | yes | Stable identifier, used by engine lookup and MCP tool naming. |
| `domain` | list[string] | yes | Health directions the function serves. |
| `inputs` | list[string] | yes | Canonical metric IDs required for the function. |
| `output` | string or null | yes | Derived metric ID if the signal persists output; null for transient results in this mission. |
| `priority` | enum(`high`,`normal`,`low`) | yes | Drives missing-input surfacing. |
| `auto_safe` | boolean | yes | Metadata only for future recompute flows. |
| `revision` | string | yes | Version marker for logic changes. |
| `question` | string | planned additive | Plain-English question this function answers. |
| `family` | enum(`status`,`trend`,`baseline`,`change`) | planned additive | Shared result family for review and MCP serialization. |
| `missing_input_hint` | string | planned additive | User-facing guidance when the input is absent. |
| `caveat_summary` | list[string] | planned additive | Short caveats Stage 3 can surface without adding new claims. |

### Validation rules

- `name` must be unique within the registry.
- `inputs` must refer to canonical metric IDs already present in `hp.dim_metric`.
- `family` must be one of the approved result families for this mission.
- Any future persisted output must stay out of this mission unless explicitly approved.

## 2. Status Result

Used by `resting_hr_status`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `signal_name` | string | yes | Registry name of the function. |
| `metric_id` | string | yes | Canonical metric being summarized. |
| `display_name` | string | yes | User-facing metric label. |
| `value` | number | yes | Latest usable value. |
| `unit` | string | yes | Canonical display unit. |
| `observed_at` | datetime | yes | Timestamp of the source value. |
| `freshness_state` | enum(`current`,`stale`,`unavailable`) | yes | Primary trust signal. |
| `validity_window` | string | yes | Human-readable or ISO duration form used to explain freshness. |
| `caveats` | list[string] | yes | Any explicit warnings. |

### Validation rules

- `value` must only be present when `freshness_state` is not `unavailable`.
- `observed_at` must correspond to the latest usable source row.

## 3. Trend Result

Used by `resting_hr_trend`, `steps_trend`, and `weight_trend`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `signal_name` | string | yes | Registry name of the function. |
| `metric_id` | string | yes | Canonical metric being summarized. |
| `window_start` | datetime | yes | Inclusive lower bound of the trend window. |
| `window_end` | datetime | yes | Inclusive upper bound of the trend window. |
| `trend_direction` | enum(`up`,`down`,`flat`,`unknown`) | yes | Plain direction only, no significance claim. |
| `points` | list[trend point] | yes | Ordered data points used to build the answer. |
| `current_freshness_state` | enum(`current`,`stale`,`unavailable`) | yes | Freshness of the latest relevant point. |
| `imputed_point_count` | integer | yes | Count of points shaped by missing-data policy. |
| `gap_count` | integer | yes | Count of non-imputed gaps in the requested window. |
| `caveats` | list[string] | yes | Warnings about sparsity or imputation. |

### Trend point

| Field | Type | Required | Notes |
|---|---|---|---|
| `ts` | datetime | yes | Point timestamp. |
| `value` | number | yes | Observed or imputed value. |
| `is_imputed` | boolean | yes | Distinguishes imputed from observed. |

### Validation rules

- `points` must be time-ordered.
- `trend_direction` must be `unknown` when there is not enough trustworthy data.
- `steps_trend` must not mark a point as imputed because its metric policy is `none`.

## 4. Own-Baseline Comparison Result

Used by `sleep_deep_pct_baseline`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `signal_name` | string | yes | Registry name of the function. |
| `metric_id` | string | yes | Canonical metric being compared. |
| `latest_value` | number | yes | Latest usable nightly value. |
| `baseline_mean` | number | yes | User's own recent normal. |
| `baseline_window` | string | yes | Describes the period used for the baseline. |
| `comparison_state` | enum(`below`,`within`,`above`,`unknown`) | yes | Relative position versus own baseline. |
| `freshness_state` | enum(`current`,`stale`,`unavailable`) | yes | Trust state for the latest value. |
| `caveats` | list[string] | yes | Includes vendor-estimate and sparsity warnings. |

### Validation rules

- `comparison_state` must describe own-baseline only, never population interpretation.
- `baseline_mean` must be derived from the user's own prior values only.

## 5. Change-Around-Date Result

Used by `hrv_change_around_date`.

| Field | Type | Required | Notes |
|---|---|---|---|
| `signal_name` | string | yes | Registry name of the function. |
| `metric_id` | string | yes | Canonical metric being compared. |
| `anchor_date` | date | yes | User-supplied change date. |
| `before_mean` | number or null | yes | Mean for the window before the anchor date. |
| `after_mean` | number or null | yes | Mean for the window after the anchor date. |
| `delta` | number or null | yes | `after_mean - before_mean`. |
| `before_count` | integer | yes | Number of usable observations before the date. |
| `after_count` | integer | yes | Number of usable observations after the date. |
| `sufficient_data` | boolean | yes | Whether the comparison is trustworthy enough to answer. |
| `caveats` | list[string] | yes | Explicitly disclaims significance and causation. |

### Validation rules

- `delta` must be null when `sufficient_data` is false.
- The result must not include p-values, confidence intervals, or causal interpretation.

## 6. Missing Input Report

Used by Stage 3 whenever a tool cannot produce a grounded answer.

| Field | Type | Required | Notes |
|---|---|---|---|
| `tool_name` | string | yes | MCP tool name. |
| `required_inputs` | list[string] | yes | Full set of required metric IDs. |
| `missing_inputs` | list[string] | yes | Inputs absent from the warehouse. |
| `stale_inputs` | list[string] | yes | Inputs present but outside freshness expectations. |
| `message` | string | yes | Plain-English explanation for the user. |

### Validation rules

- `missing_inputs` and `stale_inputs` may both be empty only when another caveat blocks the answer.
- `message` must not imply diagnosis or external reference data.

## 7. Relationships

- One `SignalRegistration` produces one result family.
- One Stage 3 tool maps one-to-one to one `SignalRegistration` in this mission.
- A Stage 3 tool returns either a family-specific result or a `MissingInputReport`.
- Existing raw MCP tools remain outside this model and unchanged.
