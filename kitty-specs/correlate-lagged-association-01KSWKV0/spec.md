# Correlate Lagged Association Specification

## Mission Type

software-dev

## Background

Premura already has a Stage 3 analytical contract, two single-series proof tools,
and an admissibility gate that refuses bad evidence before computation. The next
analytical-depth step is `correlate`: the first multi-input tool over two
prepared daily health series.

This mission makes a specific n-of-1 question answerable: whether two of the
operator's own metrics show an association over the days both were measured,
possibly at a caller-declared whole-day lag. For example, an agent may ask
whether training load today is associated with HRV tomorrow, or whether sleep
duration and resting heart rate move oppositely over overlapping measured days.

The honesty contract is locked by
`docs/adr/0008-correlate-pre-registered-lagged-association.md`: the tool reports
association, not causation or significance. It never scans many lags and keeps
the best one. It requires a pre-registered hypothesis before the result exists:
metric pair, integer-day lag, and expected direction. It returns an effect-size
estimate plus an honest uncertainty band and validity/confound metadata, or it
refuses with no estimate.

The scientific choices are settled by
`docs/history/research/CORRELATE_METHODOLOGY_RESEARCH.md`: Spearman's rho is the
v1 coefficient, uncertainty is widened by an effective-sample-size adjustment,
raw paired samples below 20 are refused, low effective sample size is refused,
unjustified lags are limited to +/-3 days, and `common_cause_plausible` is the
reviewed confound vocabulary extension.

## Scope

### In Scope

- Add `correlate` as the first multi-input Stage 3 analytical tool.
- Prepare and align two admissible daily analytical input series by same local
  calendar day after applying one caller-specified integer-day lag.
- Narrow `overlap_start`, `overlap_end`, and `overlap_sample_size` to the paired
  overlap used by the correlation run.
- Require a pre-registered hypothesis containing the two metric identifiers, the
  lag, and the expected direction before any coefficient is computed.
- Report Spearman's rho, an autocorrelation-adjusted association band, effective
  sample size, raw paired sample size, lag metadata, imputation percentage, and
  closed-vocabulary confound metadata.
- Add the reviewed `common_cause_plausible` confound key and emit it by rule when
  the caller identifies a plausible common-cause candidate before computation.
- Expose `correlate` on the default agent-facing surface while keeping all
  statistical work in the engine-owned analytical path.
- Keep all output descriptive, local-first, non-diagnostic, non-causal, and free
  of p-values or significance claims.
- Update the relevant analytical contract, engine contract, and planning/status
  docs needed for agents to add or review follow-on analytical tools correctly.

### Out Of Scope

- A session-scoped association ledger, reproducible research trace, or audit
  skill that counts how many hypotheses were tried.
- PubMed runtime grounding, literature fetching, or network access from the
  analytical layer.
- Paired tests, broader significance testing, p-values, multiplicity correction,
  or claims that an association is significant.
- Automatic lag scanning, automatic metric-pair search, or choosing the lag that
  maximizes the coefficient.
- Kendall, Pearson, distance correlation, block bootstrap, or any user-facing
  coefficient selection in v1.
- New user interface or teaching-layer screens.
- Unrelated ruff, mypy, parser, roadmap, or cleanup work.

## User Scenarios & Testing

### Primary Scenario: Agent Tests a Pre-Registered Lagged Association

An agent acting for the operator asks whether two admissible metrics are
associated at a declared lag, such as whether training load today is negatively
associated with HRV one day later. Before the result exists, the agent declares
the two metrics, lag, and expected direction. The tool pairs the two series on
same local calendar days after applying the lag, refuses if the overlap is too
weak, or returns the association estimate with uncertainty, validity, and
confound metadata.

Acceptance test: given two admissible daily series with at least 20 paired days,
adequate effective sample size, lag 1, and expected negative direction,
`correlate` returns a complete association envelope containing Spearman's rho,
the association band, raw and effective sample counts, paired overlap metadata,
lag metadata, and no causation or significance language.

### Secondary Scenario: Agent Requests an Unsupported Lag

An agent asks for an association at a lag outside the free +/-3 day range without
providing a justification, or asks for a lag beyond the hard supported maximum.
The tool refuses before pairing or computation.

Acceptance test: a lag of 4 days without justification returns a structured
refusal with no estimate; a lag beyond 14 days returns a structured refusal even
when a justification is provided.

### Secondary Scenario: Paired Overlap Is Too Weak

An agent asks a valid pre-registered question, but the two series have too few
same-day pairs after applying lag, too much imputation, or too little effective
sample size because both series are temporally autocorrelated. The tool refuses
or returns a strongly caveated result according to the declared thresholds.

Acceptance test: fewer than 20 raw paired days returns a refusal; effective
sample size below 12 returns a refusal; 20-49 paired days or effective sample
size below 30 returns an available result only when the hard floors are met and
the `low_sample_size` caveat is present.

### Secondary Scenario: Plausible Common Cause Is Pre-Declared

An agent knows, before computation, that a third factor such as illness, travel,
or a training block could plausibly drive both metrics. The agent includes that
candidate with the hypothesis. The result surfaces the `common_cause_plausible`
confound key and carries the candidate in plain language without turning it into
a cause claim.

Acceptance test: when the pre-registered hypothesis includes a plausible common
cause candidate, the result includes `common_cause_plausible`; when no candidate
is supplied, the result still carries non-causal wording but does not emit that
specific key solely by default.

### Secondary Scenario: Result Contradicts the Expected Direction

An agent declares a positive association but the observed association is negative.
The tool returns the estimate honestly and records that the result opposed the
pre-registered direction. It does not rewrite the hypothesis after seeing the
data.

Acceptance test: opposite-direction fixtures return the observed coefficient and
a machine-readable indication that the observed direction differed from the
pre-registered direction, with no retroactive change to the declared hypothesis.

### Edge Cases

- One input is admissible and the other is stale, inadmissible, or missing.
- Both inputs are admissible but have no same-day pairs after lag is applied.
- The lag is inside +/-3 days, outside +/-3 days with justification, outside +/-3
  days without justification, or beyond 14 days.
- The raw paired sample count is below 20, between 20 and 49, or at least 50.
- The effective sample size is below 12, between 12 and 29, or at least 30.
- One or both series include accepted imputed points.
- One or both paired series are constant or have insufficient rank variation.
- The requested expected direction does not match the observed direction.
- A caller tries to omit the hypothesis, omit expected direction, pass a
  tolerance window, request a p-value, request significance, or ask the tool to
  choose the best lag.

## Functional Requirements

| ID | Status | Requirement | Acceptance Criteria |
|---|---|---|---|
| FR-001 | Draft | The system SHALL add `correlate` as a Stage 3 analytical tool for association between exactly two admissible daily input series. | `correlate` is registered as an analytical tool, appears on the default agent-facing surface, and accepts two prepared analytical inputs rather than a single series. |
| FR-002 | Draft | The system SHALL add a reviewed analytical question type for lagged association rather than reusing a single-series question type. | The closed analytical question vocabulary contains a lagged-association value used by `correlate`, and admissibility mapping never passes a free-form question string. |
| FR-003 | Draft | The system SHALL prepare paired analytical inputs by applying one caller-specified integer-day lag and pairing observations on the same local calendar day. | Test fixtures show that paired days are selected only after applying the declared lag; no symmetric timestamp tolerance or lag scan is used. |
| FR-004 | Draft | The system SHALL narrow overlap metadata to the actual paired overlap used by the correlation run. | The prepared paired input metadata reports `overlap_start`, `overlap_end`, and `overlap_sample_size` matching the paired days that reach computation. |
| FR-005 | Draft | The system SHALL require pre-registration of metric pair, integer-day lag, and expected direction before computing an association. | Calls missing any required hypothesis field return a structured refusal with no estimate. |
| FR-006 | Draft | The system SHALL refuse lag requests outside the supported bounds. | Lags within +/-3 days do not require justification; lags from 4 through 14 days require caller-supplied justification; absolute lag greater than 14 days is refused. |
| FR-007 | Draft | The system SHALL compute and report Spearman's rho as the v1 association estimate. | Available results include a signed Spearman's rho value in the estimate payload and expose no user-facing coefficient choice. |
| FR-008 | Draft | The system SHALL report an autocorrelation-adjusted association band and effective sample size instead of p-values or significance. | Available results include the association band and effective sample size; serialized outputs contain no p-value, significance flag, or significance wording. |
| FR-009 | Draft | The system SHALL refuse when raw paired sample size is below 20. | Fixtures with 19 or fewer paired days return a structured refusal and no estimate. |
| FR-010 | Draft | The system SHALL refuse when effective sample size is below 12. | Fixtures with at least 20 raw paired days but effective sample size below 12 return a structured refusal and no estimate. |
| FR-011 | Draft | The system SHALL emit low-sample caveats for marginal paired support. | Available results with 20-49 raw paired days or effective sample size from 12 through 29 include `low_sample_size`; results at or above 50 paired days and effective sample size at least 30 do not include `low_sample_size` solely for sample count. |
| FR-012 | Draft | The system SHALL account for accepted imputed pairs in the association validity metadata. | Pairs where either side is imputed contribute half weight to effective sample size, imputation percentage is reported across paired inputs, and imputed-pair percentage at or above 20% emits `high_imputation`. |
| FR-013 | Draft | The system SHALL emit `short_overlap_window` when the paired calendar overlap is shorter than 28 days. | Available results with paired overlap spanning fewer than 28 local calendar days include `short_overlap_window`. |
| FR-014 | Draft | The system SHALL add `common_cause_plausible` as a closed confound key and emit it only by rule. | The closed confound vocabulary accepts `common_cause_plausible`; results include it when the pre-registered hypothesis names at least one plausible common-cause candidate and do not include it solely because the tool is correlation. |
| FR-015 | Draft | The system SHALL record whether the observed association direction matches the pre-registered expected direction. | Available results include machine-readable direction alignment metadata without changing the pre-registered hypothesis. |
| FR-016 | Draft | The system SHALL refuse unsupported association requests before computation. | Missing inputs, stale or inadmissible inputs, no paired overlap, insufficient rank variation, invalid lag, missing hypothesis, and unsupported parameters each return a structured refusal with no estimate. |
| FR-017 | Draft | The system SHALL expose `correlate` through the default agent-facing surface by delegating to the engine-owned analytical path. | The wrapper performs no statistical computation and returns only serialized engine analytical envelopes or refusals. |
| FR-018 | Draft | The system SHALL update agent-facing docs to explain Lag and Association usage for `correlate`. | Relevant docs describe lag as directional and caller-specified, association as non-causal, and list the exclusions: no lag scan, no p-value, no significance, no cause claim. |

## Non-Functional Requirements

| ID | Status | Requirement | Measurement |
|---|---|---|---|
| NFR-001 | Draft | `correlate` SHALL be deterministic. | For identical inputs, hypothesis, policies, and parameters, repeated runs produce byte-equivalent serialized outputs in 100% of acceptance fixtures. |
| NFR-002 | Draft | `correlate` SHALL remain local-first and offline. | Static checks and tests show no network-access modules, PubMed calls, or literature-fetching calls are reachable from the analytical runtime path. |
| NFR-003 | Draft | `correlate` SHALL always return a complete analytical envelope for available outcomes. | 100% of available results include inputs, parameters, estimate, uncertainty band, validity status, imputation percentage, raw paired sample size, effective sample size, overlap metadata, and confound checklist. |
| NFR-004 | Draft | `correlate` SHALL keep refusal reasons distinct and testable. | Tests cover at least 8 refusal classes: missing hypothesis, invalid lag, inadmissible input, no paired overlap, raw paired sample below 20, effective sample below 12, constant series, and unsupported parameter. |
| NFR-005 | Draft | `correlate` SHALL avoid significance and causal language. | 100% of serialized outputs and built-in caveats avoid `significant`, `p-value`, `cause`, `effect`, `impact`, `driver`, diagnosis, treatment, dosing, emergency, and population-norm claims except inside explicit forbidden-language tests. |
| NFR-006 | Draft | Plain-language caveats SHALL be concise enough for agent narration. | Each built-in caveat is 280 characters or fewer. |
| NFR-007 | Draft | The paired-preparation contract SHALL be inspectable. | 100% of available and refused paired-preparation outcomes expose enough input identifiers, lag, overlap, sample-count, and refusal metadata for a reviewer to reproduce the pairing decision. |

## Constraints

| ID | Status | Constraint | Rationale |
|---|---|---|---|
| C-001 | Draft | `correlate` MUST report association only, never causation. | The tool answers whether two metrics move together or oppositely; it cannot establish why. |
| C-002 | Draft | `correlate` MUST NOT compute or return p-values, significance labels, or multiplicity-adjusted statistics. | The roadmap rejects statistical theater for confounded n-of-1 observational data. |
| C-003 | Draft | `correlate` MUST NOT scan lags, scan metric pairs, or select the strongest result. | Lag and expected direction are pre-registered hypotheses, not optimization targets. |
| C-004 | Draft | Pairing MUST use same local calendar-day pairs after lag, not a symmetric timestamp tolerance. | Lag models physiological delay; tolerance windows blur direction and create arbitrary matches. |
| C-005 | Draft | The analytical engine MUST remain stateless. | Session-level multiplicity accounting belongs to a later ledger/trace mission, not the deterministic engine. |
| C-006 | Draft | Runtime analytical code MUST NOT call PubMed, external literature, network services, or remote APIs. | Literature can inform authoring and review, but runtime analysis stays local and deterministic. |
| C-007 | Draft | V1 MUST expose Spearman only; Kendall, Pearson, distance correlation, and block bootstrap are excluded from this mission. | The first multi-input tool should settle one conservative method rather than present a method menu. |
| C-008 | Draft | Future block-bootstrap support, if added later, MUST be deterministic using a hypothesis-derived seed and a fixed block-length rule of `ceil(sqrt(raw_paired_sample_size))`. | The v1 result shape should not block future uncertainty upgrades, but v1 must not implement them. |
| C-009 | Draft | Built-in analytical publication MUST preserve the existing explicit/static loading posture unless a later mission changes that publication contract. | Agents need predictable reviewable publication, not implicit filesystem discovery. |
| C-010 | Draft | The mission MUST preserve Premura's guide-don't-enumerate doctrine. | The tool should define pairing, lag, and confound rules agents can apply, not hardcode a catalog of metric pairs or plausible causes. |

## Key Entities

- **Lag**: The caller-specified whole-day offset between the two metrics before
  pairing. It is directional, asymmetric, and never discovered by scanning.
- **Association**: The non-causal statement that two metrics move together or
  oppositely over paired measured days, with strength and uncertainty.
- **Pre-registered hypothesis**: The declared metric pair, lag, expected
  direction, optional lag justification, and optional common-cause candidate(s)
  recorded before the coefficient is computed.
- **Paired analytical input**: The aligned two-series input used by `correlate`,
  with overlap metadata narrowed to actual paired days.
- **Raw paired sample size**: The number of same-day pairs after lag is applied.
- **Effective sample size**: The autocorrelation- and imputation-aware support
  count used to widen the association band and refuse overconfident results.
- **Association band**: A plain-language uncertainty range around Spearman's rho
  that expresses plausible association strength without making a significance or
  repeated-sampling claim.
- **Common-cause candidate**: A caller-supplied plausible third factor that could
  drive both metrics and triggers the `common_cause_plausible` confound key.
- **Refusal outcome**: A structured no-estimate result explaining why the
  association cannot honestly be computed.

## Success Criteria

| ID | Criterion | Measurement |
|---|---|---|
| SC-001 | An agent can ask a pre-registered two-metric association question and receive an honest deterministic answer when evidence supports it. | Acceptance fixtures show available `correlate` results for supported inputs with complete association, uncertainty, sample, lag, overlap, and confound metadata. |
| SC-002 | Weak or malformed association requests cannot produce a coefficient. | 100% of missing-hypothesis, invalid-lag, inadmissible-input, no-overlap, below-20-pair, below-12-effective-sample, and constant-series fixtures return no-estimate refusals. |
| SC-003 | Correlation-specific honesty risks are structurally surfaced. | Available results expose temporal autocorrelation, low sample size, short overlap, high imputation, life-event sensitivity, and common-cause confounds when their declared trigger rules apply. |
| SC-004 | The result cannot be narrated as significance or cause without contradicting the payload. | Serialized outputs and caveats contain no p-values, significance labels, causal claims, diagnostic claims, treatment advice, or population-norm comparisons in 100% of tests. |
| SC-005 | The multi-input analytical contract proves the existing overlap design. | Paired-preparation tests show overlap metadata narrowed to actual paired days and consumed by `correlate` without changing the existing single-series envelope shape. |
| SC-006 | Agents can review and extend the analytical surface without re-deciding correlation policy. | Updated docs and tests state the pairing, lag, sample-floor, effective-sample, imputation, and confound rules in one reviewable place. |

## Assumptions

- ADR-0008 is the locked architecture and honesty contract for this mission.
- `CORRELATE_METHODOLOGY_RESEARCH.md` is the authoritative research input for
  coefficient choice, sample floors, lag bounds, and confound-key choice.
- The mission may extend closed vocabularies only through reviewed changes: a
  lagged-association analytical question type and `common_cause_plausible`.
- Effective sample size uses rank-transformed paired values and autocorrelation
  terms through lags `1..min(7, floor(raw_paired_sample_size / 4))`; noisy or
  undefined autocorrelation terms contribute zero rather than introducing
  non-deterministic behavior.
- Imputed paired values are accepted when upstream admissibility accepts them,
  but each pair with either side imputed contributes half weight to effective
  sample size and to the imputation validity calculation.
- Association-band wording will use the phrase "association band" and describe a
  plausible range after accounting for autocorrelation; it will not use
  "confidence interval", "significant", or "p-value".
- The hard floors are 20 raw paired days and effective sample size 12. The
  marginal-support thresholds are fewer than 50 raw paired days or effective
  sample size below 30.
- The session-layer ledger/audit trace is a later mission and is not needed for a
  single deterministic `correlate` call to be honest about its own inputs.

## Dependencies

- `docs/adr/0008-correlate-pre-registered-lagged-association.md` for the locked
  correlate architecture and honesty contract.
- `docs/history/research/CORRELATE_METHODOLOGY_RESEARCH.md` for the scientific
  choices and implementation-decision inputs.
- `CONTEXT.md` §"Analysis" for the canonical meanings of Lag and Association.
- `docs/product/DOCTRINE.md` for the agent-first and guide-don't-enumerate rules.
- `docs/adr/0007-evidence-admissibility-as-a-declared-contract.md` for the
  admissibility foundation this mission builds on.
- `src/premura/engine/CONTRACT.md` for the grounding doctrine and PubMed runtime
  boundary.
- `src/premura/engine/analytical_contract.py` for closed analytical vocabularies,
  tool registration, dispatch, and result-envelope validation.
- `src/premura/engine/analytical_inputs.py` for prepared input and overlap
  metadata behavior.
- Existing Stage 3 analytical tool tests and MCP public-surface tests for the
  required delegation and envelope patterns.
