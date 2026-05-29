# Data Model: Stage 3 Analytical Tools

This mission adds transient analytical contract shapes. It does not add new
warehouse tables.

## AnalyticalToolSpec

Declares one deterministic analytical tool.

Fields:

- `name`: unique snake_case tool name, such as `change_point`.
- `description`: plain-language description for agents and reviewers.
- `input_shape`: declared input-series requirements.
- `parameters`: supported parameter names, bounds, defaults, and refusal behavior.
- `result_kind`: declared result shape produced by the tool.
- `confound_keys`: closed-vocabulary confound keys the tool may emit.
- `revision`: version string for reviewable changes.

Validation rules:

- `name` must be unique in the analytical registry.
- `confound_keys` must be drawn from the committed confound vocabulary.
- Parameter bounds must produce structured refusals when violated.
- Registration must not require a per-tool dispatcher branch.

## AnalyticalInputSeries

The engine-owned input shape passed to analytical methods after admissibility
evaluation.

Fields:

- `metric_id`: canonical metric identifier.
- `points`: ordered timestamp/value points.
- `window_start` / `window_end`: usable analysis window.
- `overlap_start` / `overlap_end`: common usable overlap window for tools that
  compare or align multiple prepared inputs; for single-series tools this equals
  the usable analysis window.
- `overlap_sample_size`: usable point count inside the overlap window.
- `sample_size`: count of usable observed or accepted points.
- `is_imputed_pct`: percentage of accepted points marked imputed.
- `freshness_status`: current freshness/admissibility status.
- `source_summary`: machine-readable provenance/source summary.
- `refusal`: optional refusal outcome when the series is not usable.

Validation rules:

- Points must be ordered by timestamp.
- Refused inputs must not be passed to statistical computation.
- `sample_size` and `is_imputed_pct` must match the accepted points.
- `overlap_start`, `overlap_end`, and `overlap_sample_size` must be present even
  for single-series tools so future multi-input tools inherit the same contract.
- Freshness and admissibility status must be available to the result envelope.

## AnalyticalResultEnvelope

The serialized shape returned by analytical tools.

Fields:

- `tool_name`: analytical tool name.
- `status`: `available` or a distinct refusal status.
- `inputs`: input identifiers and prepared-window metadata.
- `parameters`: effective parameters after validation.
- `estimate`: tool-specific estimate payload, absent for refusals.
- `uncertainty`: method-defined uncertainty payload or explicit unavailable marker.
- `validity_status`: machine-readable validity status.
- `is_imputed_pct`: imputation percentage across analytical inputs.
- `sample_size`: usable sample count.
- `confound_checklist`: closed-vocabulary confound entries.
- `caveats`: concise plain-language caveats.

Validation rules:

- Non-refusal results must include `estimate` and required metadata.
- Refusal results must include a distinct reason and no estimate.
- Unknown confound keys are rejected.
- Caveats must not claim diagnosis, causation, treatment, emergency guidance, or
  population norms.

## RefusalOutcome

Explains why an analytical request cannot honestly run.

Fields:

- `reason`: distinct machine-readable reason.
- `message`: concise plain-language explanation.
- `missing_or_bad_inputs`: relevant input identifiers, if any.
- `parameter_name`: relevant parameter name, if any.

Validation rules:

- A refusal outcome must not include an estimate.
- Reasons must stay distinct enough for agents to branch without parsing prose.

## ChangePointEstimate

Tool-specific estimate for `change_point`.

Fields:

- `change_point_at`: estimated timestamp/date for the level shift.
- `level_before`: estimated level before the shift.
- `level_after`: estimated level after the shift.
- `direction`: `up`, `down`, or `unknown`.
- `method`: committed conservative method name/revision.

Validation rules:

- Must not name or imply cause.
- Must include uncertainty behavior in the surrounding envelope.

## SmoothedAverageEstimate

Tool-specific estimate for smoothed average.

Fields:

- `smoothed_points` or `smoothed_value`: smoothed output.
- `smoothing_window`: effective smoothing window.
- `method`: committed conservative method name/revision.
- `coverage`: usable coverage summary for the smoothing window.

Validation rules:

- Must disclose the smoothing window and unsupported parameter refusals.
- Must not imply prediction or significance.
