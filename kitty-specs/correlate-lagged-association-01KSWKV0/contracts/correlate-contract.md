# Contract: `correlate`

## Purpose

`correlate` reports a pre-registered lagged association between two admissible
daily health series. It is deterministic, local-first, stateless, and returns an
analytical envelope or a structured refusal.

## Engine Contract

### Tool Descriptor

- `name`: `correlate`
- `input_shape`: `paired_ordered_daily_series`
- `question_type`: lagged association
- `result_kind`: `correlate_association_estimate`
- `parameters`: pre-registered hypothesis fields, lag, and method revision
- `confound_keys`: existing analytical confounds plus `common_cause_plausible`

### Required Inputs

- Two prepared analytical input series that passed evidence admissibility.
- A `PreRegisteredAssociationHypothesis` with metric pair, integer-day lag, and
  expected direction.
- Optional lag justification for lags from 4 through 14 days.
- Optional common-cause candidates supplied before computation.

### Pairing Semantics

- Apply `lag_days` to the appropriate series according to the hypothesis.
- Pair observations only when they land on the same local calendar day after lag.
- Do not use timestamp tolerance windows.
- Do not scan lags or metric pairs.
- Narrow paired overlap metadata to the paired days that reach computation.

### Available Outcome

An available outcome must include:

- Spearman's rho.
- Observed direction.
- Expected direction.
- Direction-match metadata.
- Association band.
- Raw paired sample size.
- Effective sample size.
- Lag metadata.
- Imputation percentage.
- Paired overlap metadata.
- Validity status.
- Closed-vocabulary confound checklist.
- Plain-language caveats with no significance or causal claims.

### Refusal Outcome

The tool must refuse with no estimate when:

- The pre-registered hypothesis is missing or malformed.
- The lag is unsupported or requires a missing justification.
- Either input is inadmissible or refused.
- No paired overlap remains after lag.
- Raw paired sample size is below 20.
- Effective sample size is below 12.
- Either series has insufficient rank variation.
- The caller asks for p-values, significance, tolerance pairing, lag scan, or
  automatic best-fit selection.

## Agent-Facing Contract

An agent may ask:

> Are metric A and metric B associated at lag K, in expected direction D?

The agent must provide the hypothesis before seeing the result. If the agent has
a plausible common-cause candidate, it should include it before computation. The
agent must narrate the result as association only.

The agent must not ask `correlate` to:

- identify the best lag;
- find the best metric pair;
- compute significance;
- explain what caused the association;
- diagnose, treat, dose, or compare the operator to population norms.

## Compatibility Notes

- The analytical dispatch path is already variadic, so the tool can receive two
  prepared series without a dispatcher branch.
- The existing single-series `AnalyticalInputSeries` shape remains valid. Paired
  preparation narrows overlap metadata for the correlation run rather than
  changing the single-series shape.
- The later session ledger/audit trace can count calls by the pre-registered
  hypothesis identity without changing the engine result shape.
