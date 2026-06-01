# Contract: `paired_t_test`

## Purpose

`paired_t_test` reports a simple declared before/after paired comparison around
one anchor date. In this mission it does not support condition-label pairing,
arbitrary pair maps, or event classification. It is deterministic, local-first,
stateless, and returns an analytical envelope or a structured refusal.

## Engine Contract

### Tool Descriptor

- `name`: `paired_t_test`
- `input_shape`: one admitted ordered series plus before/after anchor-date pairing
- `question_type`: paired comparison
- `result_kind`: `paired_difference_estimate`
- `parameters`: anchor date, before window, after window, expected direction,
  method revision
- `confound_keys`: closed analytical confounds for low sample, high imputation,
  short window support, parameter at limit, vendor estimate input, temporal
  autocorrelation, and life-event sensitivity as applicable

### Required Inputs

- One prepared analytical input series that passed evidence admissibility.
- `anchor_date`: local calendar date separating before and after windows.
- `before_days`: positive integer size of the before window.
- `after_days`: positive integer size of the after window.
- `expected_direction`: `increase` or `decrease`, declared before computation.

### Pairing Semantics

- Build pairs from observations before and after the anchor according to one fixed
  documented rule.
- Do not scan anchor dates, before windows, after windows, or pair-selection
  strategies.
- Do not support condition labels or arbitrary pair maps in this mission.
- Preserve imputation flags from upstream accepted input points.

### Available Outcome

An available outcome must include:

- Tool name and declared parameters.
- Metric id and before/after spans used.
- Raw pair count.
- Mean paired difference as after minus before.
- Observed direction.
- Expected direction.
- Direction-match metadata.
- Uncertainty metadata for the mean paired difference.
- Imputation percentage.
- Validity status and closed-vocabulary confound checklist.
- Plain-language caveats with no cause, diagnosis, treatment, or population-norm
  claim.

### Refusal Outcome

The tool must refuse with no estimate when:

- The input series is refused, stale, missing, or inadmissible.
- The anchor date is missing or malformed.
- `before_days` or `after_days` is outside supported bounds.
- Expected direction is missing or outside the closed set.
- No valid before/after pairs can be built.
- Pair count is below the planned floor.
- Paired differences are constant or otherwise cannot support the method.
- The caller asks for condition pairing, arbitrary pair maps, anchor scanning,
  p-hacking, diagnosis, causation, or treatment advice.

## Agent-Facing Contract

An agent may ask:

> Compare metric M before and after anchor date D, expecting an increase/decrease.

The agent must provide the anchor date, before window, after window, and expected
direction before seeing the result. The agent must narrate the output as a paired
before/after comparison only. It must not say the anchor date caused the change.

The agent must not ask `paired_t_test` to:

- discover the best anchor date;
- discover the best before/after windows;
- use condition labels or arbitrary pair IDs in this mission;
- treat an association or before/after difference as cause;
- diagnose, treat, dose, or compare the operator to population norms.

## Trace Identity

The normalized hypothesis identity for `paired_t_test` includes:

- `metric_id`
- `anchor_date`
- `before_days`
- `after_days`
- `expected_direction`

Exact retries with the same values collapse in session disclosure. Different
anchors, windows, or expected directions are distinct examined hypotheses.

## Deferred Extension

Condition-label pairing may be added in a later mission by defining a new pairing
contract, new identity fields, and new refusal rules. It must not be smuggled
into the simple anchor-date request shape.
