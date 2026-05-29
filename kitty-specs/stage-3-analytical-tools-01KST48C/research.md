# Phase 0 Research: Stage 3 Analytical Tools

## Decision: Phase 0 Research Note Is In This Mission

The analytical-depth research note is part of this mission and must complete
before code work. It will live in the project documentation history and provide
the rationale that later implementation work follows.

### Rationale

The spec deliberately depends on decisions that affect contract shape:
change-point method, smoothed-average method shape, analytical question types,
and confound vocabulary. Those decisions need a durable rationale before tests
and data shapes lock them in.

### Alternatives Considered

- Defer research to a separate mission: rejected because implementation planning
  would start with unresolved contract choices.
- Encode the choices directly in code comments: rejected because Premura's
  planning and review process needs durable, citeable design rationale.

## Decision: Use Conservative, Interpretable Methods

The proof methods are `change_point` and smoothed average. Both are implemented
as conservative descriptive tools and refuse unsupported evidence rather than
produce fragile estimates.

### Rationale

Premura's first analytical tools exist to prove the contract and reduce LLM
narration risk, not to maximize statistical coverage. Conservative, explainable
methods are easier for agents to narrate honestly and easier for reviewers to
validate.

### Alternatives Considered

- Full significance-testing suite: rejected as too broad for the first contract
  slice and too easy to overstate in n-of-1 data.
- Correlation as second proof method: considered in the draft, but replaced by
  smoothed average through planning discovery.

## Decision: `change_point` Is a Stage 3 Analytical Tool

`change_point` must not be registered as a Stage 2 `change` family signal. It is
a Stage 3 analytical tool over admissible evidence, with its own analytical
result envelope.

### Rationale

Stage 2 answer families remain closed. A `change_point` estimate answers a
different statistical question than the existing `hrv_change_around_date` style
before/after comparison.

### Alternatives Considered

- Extend Stage 2 `change`: rejected because the spec explicitly forbids changing
  `RESULT_FAMILIES` and because it would blur descriptive answer families with
  statistical analysis.

## Decision: Smoothed Average Is the Second Proof Method

The second proof method is a smoothed average tool that summarizes a noisy series
with declared smoothing/window metadata and the same analytical envelope.

### Rationale

Smoothed average is useful for agent-mediated pattern finding without implying
causation or significance. It exercises the input-series contract, imputation
visibility, parameter bounds, and metadata envelope without requiring broader
hypothesis testing.

### Alternatives Considered

- Correlation: useful later, but introduces two-input overlap and causal
  narration risks earlier than needed.
- Paired tests: deferred because broad significance testing is out of scope.

## Decision: Change-Point Method Shape

The initial `change_point` method is a single-level-shift detector over one
admissible, ordered series. It scans candidate split points that leave at least a
declared minimum number of usable observations on both sides, computes the before
and after means for each candidate, and chooses the candidate with the largest
absolute standardized level difference. The result reports the selected split
time, before level, after level, direction, method revision, sample counts, and
an uncertainty payload that describes support around the selected split rather
than a p-value.

### Rationale

This shape is deterministic, inspectable, and easy to explain. It avoids broad
change-point libraries, p-values, and model assumptions that would invite
overconfident interpretation in n-of-1 data.

### Alternatives Considered

- Bayesian online change-point detection: rejected for the first slice because
  priors and posterior explanations add review burden.
- Multiple change-point segmentation: rejected because the first proof tool only
  needs to prove the contract and refusal behavior.
- Visual-only before/after comparison: rejected because the mission needs a
  deterministic computed estimate the agent can narrate.

## Decision: Smoothed-Average Method Shape

The smoothed-average proof tool computes a deterministic trailing rolling mean
over one admissible, ordered series using a declared window and minimum coverage.
It does not fill long gaps or invent missing observations. Each output point or
summary value carries the effective window, usable count, imputation percentage,
coverage, and method revision. If the method cannot provide a natural confidence
interval, the uncertainty payload explicitly states that uncertainty is not
defined for this method and relies on validity/confound metadata instead.

### Rationale

A trailing rolling mean is a conservative pattern summary that agents can explain
without implying prediction, causation, or statistical significance. It also
exercises parameter validation, imputation reporting, and metadata propagation.

### Alternatives Considered

- Centered smoothing: rejected for the first surface because it can use future
  observations relative to a point and is harder to narrate in agent workflows.
- Exponential smoothing: deferred because alpha selection becomes another policy
  decision.
- Interpolation-heavy smoothing: rejected because missingness must remain visible.

## Decision: Add Reviewed Analytical Question Types

Analytical admissibility introduces reviewed closed `QuestionType` values for the
two proof shapes instead of forcing them onto existing descriptive families:
`level_shift_detection` for `change_point` and `smoothed_pattern` for smoothed
average. These names are contract vocabulary, not user-facing labels.

### Rationale

The existing policy vocabulary is intentionally closed, and the proof tools ask
questions that are not the same as current status, recent trend, long-term
control, or historical baseline. Adding reviewed analytical question types keeps
the evaluator honest without opening arbitrary strings.

### Alternatives Considered

- Reuse existing `historical_baseline` / `recent_trend`: rejected because it
  distorts level-shift detection and hides analytical sufficiency requirements.
- Let each tool pass a free-form question name: rejected because it violates the
  closed-vocabulary policy contract.

## Decision: Confound Vocabulary Is Closed and Runtime-Owned

The research note may propose confound keys, but the implementation contract owns
the committed runtime vocabulary and its validation tests.

### Rationale

Closed keys prevent agents from inventing values like "probably fine" or hiding
distinct risks under generic quality labels.

### Committed Initial Vocabulary

- `high_imputation`
- `low_sample_size`
- `short_overlap_window`
- `parameter_at_limit`
- `vendor_estimate_input`
- `temporal_autocorrelation`
- `life_event_sensitive`
- `method_uncertainty_unavailable`

### Alternatives Considered

- Free-form caveat strings only: rejected because agents cannot reliably branch
  on prose.
- Numeric quality score: rejected because it collapses distinct refusal and
  confound reasons.

## Decision: No New Runtime Network Dependency

Analytical runtime stays offline and uses only local warehouse evidence plus
in-tree deterministic code.

### Rationale

Local-first operation and no runtime literature fetching are charter boundaries.
Literature grounding comes later and should attach to tool-grounded analysis, not
free-form narration.

### Alternatives Considered

- Runtime PubMed checks: rejected as out of scope and a local-first violation for
  this mission.
