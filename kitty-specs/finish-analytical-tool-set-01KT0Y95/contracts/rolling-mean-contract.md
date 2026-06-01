# Contract: `rolling_mean`

## Purpose

`rolling_mean` reports a declared moving-window summary over one admitted ordered
health series. It is deterministic, local-first, stateless, and returns an
analytical envelope or a structured refusal.

## Engine Contract

### Tool Descriptor

- `name`: `rolling_mean`
- `input_shape`: single ordered admitted series
- `question_type`: moving-window pattern, or the reviewed existing smoothed
  pattern type if planning confirms it honestly fits
- `result_kind`: `rolling_mean_estimate`
- `parameters`: `window`, `min_coverage`, method revision
- `confound_keys`: closed analytical confounds for low sample, high imputation,
  short overlap/window support, parameter at limit, vendor estimate input,
  temporal autocorrelation, and method limits as applicable

### Required Inputs

- One prepared analytical input series that passed evidence admissibility.
- A positive integer `window`.
- A `min_coverage` threshold in `[0.0, 1.0]`.

### Window Semantics

- The window is caller-declared before computation.
- The tool must not scan windows or select a window because it looks strongest.
- Each emitted point summarizes only observations inside that trailing window.
- Long gaps remain visible through coverage and missingness metadata.

### Available Outcome

An available outcome must include:

- Tool name and declared parameters.
- Input metric id and admitted input span.
- Ordered rolling-mean points.
- Window size and minimum coverage.
- Per-point coverage and imputation counts.
- Emitted point count and source sample size.
- Validity status and closed-vocabulary confound checklist.
- Plain-language caveats with no prediction, significance, or causal claims.

### Refusal Outcome

The tool must refuse with no estimate when:

- The input series is refused, stale, missing, or inadmissible.
- `window` is zero, negative, or beyond the supported maximum.
- `min_coverage` is outside `[0.0, 1.0]`.
- No window reaches the required coverage.
- The caller asks the tool to choose or scan windows.

## Agent-Facing Contract

An agent may ask:

> Summarize metric M with a W-observation rolling mean.

The agent must provide one metric and one declared window. The agent must narrate
the output as a descriptive moving-window summary, not as a prediction, clinical
finding, significant trend, or cause.

The agent must not ask `rolling_mean` to:

- find the best window;
- compare many windows and keep the strongest-looking result;
- predict future values;
- diagnose, treat, dose, or compare the operator to population norms.

## Trace Identity

The normalized hypothesis identity for `rolling_mean` includes:

- `metric_id`
- `window`
- `min_coverage`

Exact retries with the same values collapse in session disclosure. Different
windows or coverage thresholds are distinct examined hypotheses.
