# Data Model: Correlate Lagged Association

## PreRegisteredAssociationHypothesis

The caller's declared question, recorded before computation.

Fields:

- `left_metric_id`: canonical metric identifier for the first series.
- `right_metric_id`: canonical metric identifier for the second series.
- `lag_days`: signed integer whole-day lag applied before pairing.
- `expected_direction`: closed value describing the expected sign: `positive` or
  `negative`.
- `lag_justification`: optional plain-language rationale required when
  `abs(lag_days)` is 4 through 14.
- `common_cause_candidates`: optional tuple of plain-language candidate common
  causes supplied before computation.

Validation rules:

- Both metric identifiers must be non-empty.
- `expected_direction` is required.
- `abs(lag_days) <= 3` is accepted without justification.
- `4 <= abs(lag_days) <= 14` requires `lag_justification`.
- `abs(lag_days) > 14` is refused.
- The hypothesis must not include a tolerance window, p-value request,
  significance request, or instruction to choose the best lag.

## PairedAnalyticalInput

The two-series post-admissibility input consumed by `correlate`.

Fields:

- `left_metric_id` / `right_metric_id`: metric identifiers.
- `question_type`: the lagged-association analytical question type.
- `pairs`: ordered paired values after lag and same-local-calendar-day matching.
- `window_start` / `window_end`: combined usable analysis window.
- `overlap_start` / `overlap_end`: first and last paired local calendar day used.
- `overlap_sample_size`: raw paired sample count.
- `is_imputed_pct`: percentage of pairs where either side is imputed.
- `freshness_status`: combined freshness/admissibility summary.
- `source_summary`: provenance for both inputs and policy mapping.
- `refusal`: optional refusal outcome when pairing cannot produce usable input.

Validation rules:

- Pairing happens only after applying `lag_days`.
- Pairing uses same local calendar day only.
- Pairs must be ordered by paired day.
- Usable paired inputs require non-null overlap metadata.
- `overlap_sample_size` equals the number of pairs.
- A refused paired input carries no pairs and no estimate-bearing metadata.

## PairedObservation

One paired day used for association.

Fields:

- `paired_day`: local calendar day after lag alignment.
- `left_ts` / `right_ts`: source timestamps for traceability.
- `left_value` / `right_value`: numeric values used for ranking.
- `left_is_imputed` / `right_is_imputed`: accepted imputation flags.

Validation rules:

- Both values must be finite numbers.
- If either side is imputed, the pair counts as imputed for imputation
  percentage and half-weighted effective support.

## CorrelateEstimate

The available estimate payload.

Fields:

- `coefficient`: Spearman's rho.
- `coefficient_method`: fixed value `spearman_rho` for v1.
- `observed_direction`: `positive`, `negative`, or `zero`.
- `expected_direction`: copied from the pre-registered hypothesis.
- `direction_matches_hypothesis`: boolean.
- `raw_paired_sample_size`: count of paired days.
- `effective_sample_size`: autocorrelation- and imputation-adjusted support.
- `association_band`: lower/upper range around Spearman's rho.
- `lag_days`: copied from the hypothesis.
- `method_revision`: reviewable method version.

Validation rules:

- No p-value or significance field exists.
- `coefficient` and band bounds stay within `[-1.0, 1.0]`.
- Available results require `raw_paired_sample_size >= 20` and
  `effective_sample_size >= 12`.

## CorrelateResultEnvelope

The serialized analytical outcome returned to agents.

Fields:

- `tool_name`: fixed value `correlate`.
- `status`: `available` or `refused`.
- `inputs`: metric identifiers and paired overlap metadata.
- `parameters`: pre-registered hypothesis and method parameters.
- `estimate`: `CorrelateEstimate` when available; absent for refusal.
- `uncertainty`: association-band metadata and method notes.
- `validity_status`: machine-readable validity status.
- `is_imputed_pct`: imputation percentage across paired inputs.
- `sample_size`: raw paired sample count.
- `effective_sample_size`: adjusted support count.
- `confound_checklist`: closed-vocabulary confound entries.
- `caveats`: concise non-causal plain-language caveats.
- `refusal`: refusal outcome when status is `refused`.

Validation rules:

- Available outcomes must carry estimate, uncertainty, validity, sample, overlap,
  and confound metadata.
- Refused outcomes must carry no estimate.
- Forbidden concepts are absent: p-values, significance, causation, diagnosis,
  treatment, dosing, emergency guidance, and population-norm comparison.

## RefusalOutcome

Structured refusal inherited from the analytical contract.

Required refusal classes for this mission:

- Missing or malformed pre-registered hypothesis.
- Invalid lag or missing required lag justification.
- Left or right input inadmissible, stale, missing, or unsupported.
- No paired overlap after lag.
- Raw paired sample size below 20.
- Effective sample size below 12.
- Constant series or insufficient rank variation.
- Unsupported parameter such as lag scan, tolerance window, p-value, or
  significance request.

## Confound Rules

- `temporal_autocorrelation`: emit when effective sample size is less than half
  raw paired sample size.
- `low_sample_size`: emit when raw paired sample size is 20-49 or effective
  sample size is 12-29.
- `short_overlap_window`: emit when paired calendar overlap spans fewer than 28
  days.
- `high_imputation`: emit when imputed-pair percentage is at least 20%.
- `life_event_sensitive`: emit when existing metric-family caveats or source
  summary indicate ordinary life events may shift the metric level.
- `common_cause_plausible`: emit when the pre-registered hypothesis includes at
  least one common-cause candidate.

## Relationships

- `PreRegisteredAssociationHypothesis` controls lag, direction, and common-cause
  metadata for one `PairedAnalyticalInput`.
- `PairedAnalyticalInput` contains many `PairedObservation` values.
- `CorrelateEstimate` is present only inside an available
  `CorrelateResultEnvelope`.
- `RefusalOutcome` replaces `CorrelateEstimate` whenever any gate fails.
