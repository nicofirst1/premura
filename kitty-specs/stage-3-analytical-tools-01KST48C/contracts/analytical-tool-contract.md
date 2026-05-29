# Contract: Analytical Tool Engine Surface

## Purpose

Define the public engine-facing contract future analytical tools register
against. This contract is agent-facing: it makes the safe extension path clear
and reviewable.

## Registry Behavior

- A tool declares an `AnalyticalToolSpec`.
- Registration adds the spec to the analytical registry.
- Invoking a tool goes through the shared analytical dispatch path.
- Adding a tool must not add a per-tool branch to the dispatcher.
- Built-in loading remains static unless a later contract explicitly changes it.

## Invocation Shape

Inputs:

- `tool_name`
- one or more declared metric/input identifiers
- parameters within the tool's declared bounds
- warehouse connection or engine execution context

Outputs:

- `AnalyticalResultEnvelope` for successful analysis
- `RefusalOutcome` wrapped in the same serialized outcome shape for refusals

## Required Guarantees

- Evidence admissibility runs before statistical computation.
- `change_point` uses the reviewed analytical question type
  `level_shift_detection`.
- Smoothed average uses the reviewed analytical question type
  `smoothed_pattern`.
- Refused inputs do not reach computation.
- Non-refusal outcomes include estimate, uncertainty behavior, validity status,
  imputation percentage, sample size, and closed-vocabulary confound checklist.
- Refusal outcomes include a distinct machine-readable reason and no estimate.
- Runtime uses local warehouse evidence only.

## Disallowed Behavior

- Runtime network calls.
- Population-norm comparison.
- Diagnosis, treatment, dosing, medication, emergency, or causal claims.
- Unknown confound keys.
- Registering `change_point` as a Stage 2 `change` result family.

## Acceptance Contract Tests

- Register a trivial analytical tool and invoke it through public dispatch.
- Attempt to emit an unknown confound key and assert validation rejects it.
- Attempt to compute on inadmissible input and assert no estimate is returned.
- Re-run the same tool over the same fixture and assert byte-equivalent output.
