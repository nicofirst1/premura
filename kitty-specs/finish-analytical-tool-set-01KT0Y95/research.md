# Research: Finish Analytical Tool Set

## Decision: Keep `rolling_mean` distinct from `smoothed_average`

**Rationale**: The roadmap names `rolling_mean` separately from the shipped
`smoothed_average`. To avoid a hidden rename, `rolling_mean` should be the
reviewable moving-window series tool: it emits per-window summary points with
coverage and missingness metadata. `smoothed_average` remains the conservative
single-series smoothing proof tool already shipped.

**Alternatives considered**: Treating `smoothed_average` as already satisfying
`rolling_mean` would close the roadmap item by wording rather than behavior.
Renaming `smoothed_average` would be a bulk terminology change and would risk
breaking existing docs/tests without adding analytical capability.

## Decision: Use declared window parameters and fixed bounds for `rolling_mean`

**Rationale**: A declared window keeps the agent from scanning many windows and
presenting the most favorable one. The current analytical stack already uses a
7-observation default, a 365-observation upper bound, and a 0.5 minimum coverage
concept for smoothing; reusing that posture keeps the tool conservative and
reviewable while allowing the emitted result shape to differ.

**Alternatives considered**: Letting the tool infer the best window would hide
search effort. Allowing unbounded windows would produce misleading summaries over
unsupported spans. Hardcoding metric-specific windows would violate the doctrine's
guide-don't-enumerate rule.

## Decision: Scope `paired_t_test` to anchor-date before/after pairing

**Rationale**: The user confirmed the simple version only. A single declared
anchor date plus before/after windows is enough to prove the paired-comparison
shape without also solving condition labels, arbitrary pair maps, or event
classification. It keeps the mission small and aligns with existing before/after
health questions.

**Alternatives considered**: Caller-supplied condition labels and arbitrary pair
maps are more flexible but create a second source of complexity: pair identity,
condition provenance, and anti-search rules. Those belong in a later extension
after the simple shape is proven.

## Decision: Require pre-declared anchor, windows, and expected direction

**Rationale**: The anchor date, before window, after window, and expected
direction are the paired-test equivalent of a pre-registered hypothesis. They
must exist before the result so an agent cannot scan many dates or interpret the
direction after seeing the estimate.

**Alternatives considered**: Making expected direction optional would invite
post-result narration. Defaulting windows implicitly would make retries and trace
identity harder to audit. Scanning anchor dates is explicitly rejected because it
manufactures the strongest-looking result.

## Decision: Treat paired output as descriptive paired-difference analysis

**Rationale**: The mission name inherits the conventional term `paired_t_test`,
but Premura's safety boundary still applies: the user-facing payload should focus
on pair count, mean paired difference, uncertainty metadata, direction, validity,
and caveats. It must not become a diagnosis, cause claim, or hidden multiple-test
surface. Any p-value/significance policy change would require explicit review.

**Alternatives considered**: Exposing a conventional p-value/significance label
would conflict with the current analytical honesty posture and make n-of-1
observational data look stronger than it is. Renaming the requested tool away
from `paired_t_test` would dodge the roadmap term rather than define a safe
contract for it.

## Decision: Use trace identities as declarations, not disclosure branches

**Rationale**: The shipped trace service already defines a per-tool identity
registry. `rolling_mean` identity should include metric, window, and coverage
threshold. `paired_t_test` identity should include metric, anchor date, before
window, after window, and expected direction. This preserves exact-retry collapse
without editing disclosure-counting logic.

**Alternatives considered**: Falling back to full request hashing would be safe
for exact retries but less reviewable. Editing disclosure-counting code per tool
would violate the trace design's registry seam.

## Decision: Add question types only if the existing closed vocabulary cannot honestly fit

**Rationale**: `rolling_mean` can likely use the existing smoothed-pattern family
only if its result remains the same question shape; otherwise it should add a
reviewed moving-window question type. `paired_t_test` should have its own
reviewed paired-comparison question type because it has different sufficiency and
confound rules from lagged association.

**Alternatives considered**: Reusing `recent_trend` or another descriptive shape
would hide analytical sufficiency. Adding a broad generic `comparison` type would
be too loose for review.
