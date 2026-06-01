# Data Model: Finish Analytical Tool Set

## RollingMeanRequest

The caller's declared moving-window summary request.

Fields:

- `metric_id`: canonical metric identifier for the admitted ordered series.
- `window`: positive integer count of observations in each moving window.
- `min_coverage`: minimum fraction of non-imputed points required for an emitted
  summary point.

Validation rules:

- `metric_id` must be non-empty.
- `window` must be positive and no larger than the supported maximum.
- `min_coverage` must be in `[0.0, 1.0]`.
- The request must not ask the tool to choose the best window.

## RollingMeanPoint

One emitted moving-window summary point.

Fields:

- `ts`: timestamp for the right edge of the window.
- `value`: rolling mean for the window.
- `window_observation_count`: observations present in the window.
- `window_expected_count`: requested window size.
- `coverage`: `window_observation_count / window_expected_count`.
- `imputed_observation_count`: number of upstream-accepted imputed points in the
  window.

Validation rules:

- `coverage` must be at least `min_coverage` for emitted points.
- Long gaps do not produce fabricated points.
- Imputed inputs remain visible in counts and caveats.

## RollingMeanEstimate

The available estimate payload for `rolling_mean`.

Fields:

- `points`: ordered `RollingMeanPoint` values.
- `window`: copied from the request.
- `min_coverage`: copied from the request.
- `emitted_point_count`: number of emitted summary points.
- `input_sample_size`: number of admitted source points.
- `method_revision`: reviewable method version.

Validation rules:

- Available results require at least one emitted point.
- Points are ordered by timestamp.
- No p-value, significance, prediction, or causal field exists.

## BeforeAfterPairedRequest

The caller's declared simple paired-comparison request.

Fields:

- `metric_id`: canonical metric identifier for the admitted ordered series.
- `anchor_date`: local calendar date separating before and after windows.
- `before_days`: positive integer count of days before the anchor to include.
- `after_days`: positive integer count of days after the anchor to include.
- `expected_direction`: closed value describing the expected sign of after minus
  before: `increase` or `decrease`.

Validation rules:

- The anchor date is required before computation.
- `before_days` and `after_days` must be positive and within supported bounds.
- `expected_direction` is required.
- The request must not ask the tool to scan anchor dates or windows.

## BeforeAfterPair

One matched before/after observation pair.

Fields:

- `pair_index`: deterministic pair order from nearest-to-anchor outward or another
  documented fixed rule.
- `before_ts` / `after_ts`: source timestamps.
- `before_value` / `after_value`: numeric values used in the paired difference.
- `before_is_imputed` / `after_is_imputed`: accepted imputation flags.
- `difference`: `after_value - before_value`.

Validation rules:

- Both values must be finite numbers.
- Pair construction follows one fixed documented rule and never searches for the
  most favorable pair set.
- If either side is imputed, the pair contributes to imputation metadata.

## BeforeAfterPairedInput

The post-admissibility paired input consumed by `paired_t_test`.

Fields:

- `metric_id`: canonical metric identifier.
- `request`: `BeforeAfterPairedRequest`.
- `pairs`: ordered `BeforeAfterPair` values.
- `before_window_start` / `before_window_end`: actual before span.
- `after_window_start` / `after_window_end`: actual after span.
- `raw_pair_count`: number of valid pairs.
- `is_imputed_pct`: percentage of pairs with either side imputed.
- `refusal`: optional refusal when no usable paired input exists.

Validation rules:

- A refused paired input carries no computation-ready pairs.
- Available paired inputs populate both window spans and raw pair count.
- Pair count equals the number of pair records.

## PairedTTestEstimate

The available estimate payload for the simple paired comparison.

Fields:

- `mean_difference`: mean of `after - before` across pairs.
- `observed_direction`: `increase`, `decrease`, or `zero`.
- `expected_direction`: copied from the request.
- `direction_matches_hypothesis`: boolean.
- `raw_pair_count`: count of valid pairs.
- `uncertainty`: uncertainty metadata for the mean paired difference.
- `method_revision`: reviewable method version.

Validation rules:

- Available results require raw pair count at or above the planned floor.
- Refused results carry no estimate.
- No diagnosis, treatment, causation, or population-norm field exists.

## AnalyticalResultEnvelope

The existing serialized analytical outcome returned to agents.

Fields for the new tools:

- `tool_name`: `rolling_mean` or `paired_t_test`.
- `status`: `available` or `refused`.
- `inputs`: metric and window/pairing metadata.
- `parameters`: declared request parameters.
- `estimate`: tool-specific estimate when available.
- `uncertainty`: present when the method can honestly express it.
- `validity_status`: machine-readable validity status.
- `is_imputed_pct`: imputation percentage.
- `sample_size`: source sample size or pair count.
- `confound_checklist`: closed-vocabulary confound entries.
- `caveats`: concise plain-language caveats.
- `refusal`: refusal outcome when status is `refused`.

Validation rules:

- Available outcomes must carry estimate and validity metadata.
- Refused outcomes must carry no estimate.
- Forbidden concepts are absent: hidden search, diagnosis, treatment, causation,
  emergency guidance, and population-norm comparison.

## TraceIdentity

The normalized hypothesis identity used by session research trace accounting.

Fields:

- `tool_name`: analytical tool name.
- `identity`: tool-specific canonical object.

Rules:

- `rolling_mean` identity includes metric id, window, and minimum coverage.
- `paired_t_test` identity includes metric id, anchor date, before window, after
  window, and expected direction.
- Exact retries collapse; different windows, anchors, or directions remain
  distinct examined hypotheses.

## Relationships

- `RollingMeanRequest` produces one `RollingMeanEstimate` or one refusal.
- `RollingMeanEstimate` contains many `RollingMeanPoint` values.
- `BeforeAfterPairedRequest` controls one `BeforeAfterPairedInput`.
- `BeforeAfterPairedInput` contains many `BeforeAfterPair` values.
- `PairedTTestEstimate` is present only inside an available analytical envelope.
- `TraceIdentity` summarizes requests for session disclosure and never changes
  engine computation.
