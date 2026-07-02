# Premura Stage 2 engine contributor contract

> Audience: humans and AI agents adding a grounded Stage 2 **signal function**
> under `src/premura/engine/`.
> Authority: this file ships with the package and is the source of truth for
> what a Stage 2 signal may do and claim. Its sibling is
> `src/premura/parsers/CONTRACT.md` (the parser-side contract).
> See `docs/building/architecture/STAGES.md` for where Stage 2 sits in the four-stage
> architecture.

## What Stage 2 is

Stage 2 turns the raw, deduplicated facts in the warehouse into a small number
of **grounded, reviewable answers**. A Stage 2 signal reads the user's own data
through a DuckDB connection and returns either a derived measurement row or one
of the shared result envelopes. Stage 3 (MCP) wraps a signal one-to-one and
surfaces it to the user.

A Stage 2 consumer may also declare **cross-domain dependencies** and resolve
them through the input-resolution seam shipped under `premura.engine` — see
"Declaring dependencies through the input-resolution seam" below. The seam is
the next analytical foundation: a domain-aware way to ask for declared inputs,
not a universal prepared-series layer. BMI is the first proof consumer of that
seam.

## Symbols you implement against

All live in this package:

- `signal(...)` / `SignalSpec` (`premura.engine._registry`) — the registration
  decorator and record. The core fields (`name`, `domain`, `inputs`, `output`,
  `priority`, `auto_safe`, `revision`, `fn`) are unchanged and mandatory in
  practice. The additive contributor fields below are optional.
- The result envelopes (`premura.engine._results`) — `StatusResult`,
  `TrendResult`, `BaselineComparisonResult`, `ChangeAroundDateResult`, and the
  cross-cutting `MissingInputReport`. Re-exported from `premura.engine`.
- `RESULT_FAMILIES` (`premura.engine`) — the set of allowed `family` values.
  Closed in this mission to `{status, trend, baseline, change}`; see
  "Answer-family extension trigger" below for the rule that governs growth.
- `DependencyDeclaration`, `ResolutionRequest`, `ResolvedInput`,
  `resolve_dependency`, `SEMANTIC_DOMAINS`, `@resolver(domain=...)`, and
  `RESOLVERS` (`premura.engine`) — the input-resolution seam. All are
  re-exported from `premura.engine`; consumers must reach them through
  `from premura.engine import ...` rather than the private
  `premura.engine._resolution` module.

## What kinds of Stage 2 functions belong here

A function belongs in Stage 2 when it answers an approved question shape from
**the user's own warehouse data** and fits one of the four result families:

| Family | Question shape | Envelope |
|---|---|---|
| `status` | "What is X right now?" | `StatusResult` |
| `trend` | "Which way has X been going?" | `TrendResult` |
| `baseline` | "How does the latest X compare to my own normal?" | `BaselineComparisonResult` |
| `change` | "Did X change around this date?" | `ChangeAroundDateResult` |

Derivation-only signals (like the built-in lab ratios) persist a `derived:*`
row instead of returning an envelope and may leave the additive metadata unset.

If your idea does not fit one of these families, do not stretch a family to
cover it — raise it for review first. Do not invent a fifth ad-hoc shape.

## Additive registry metadata

When a signal answers a user-facing question, declare the contributor metadata
so Stage 3 and reviewers can reason about it. All are optional and default to
"unset", so existing registrations need no change:

- `question` — the plain-English question the signal answers.
- `family` — one of `RESULT_FAMILIES` (`status`/`trend`/`baseline`/`change`).
- `missing_input_hint` — plain-language guidance shown when an input is absent.
- `caveat_summary` — standing, signal-level disclaimers Stage 3 may surface.

`family`, when set, is validated against `RESULT_FAMILIES` at registration time.

## Evidence basis expected

- Answers must come **only** from the user's own data already in the warehouse.
- A `baseline` comparison's baseline must be built from the user's own prior
  values — never a population or external reference range.
- Respect freshness: set the envelope's `freshness_state` honestly and refuse
  (`unavailable` / `sufficient_data = False`) rather than answer on stale or
  too-sparse data.
- Distinguish observed from imputed points; never silently fabricate data.

## Declaring profile and intake prerequisites

Some future signals will need **baseline profile context** (e.g. a declared
standing height), **nutrition intake** (e.g. `protein_g`), or **supplement
intake** (e.g. a dose amount). The meaning of these domains and how they stay
distinct from observations is fixed in
[`docs/building/architecture/PROFILE_AND_INTAKE_CONTRACT.md`](../../../docs/building/architecture/PROFILE_AND_INTAKE_CONTRACT.md).
None of these domains is consumed by a shipped Stage 2 signal today, and none is
a new execution stage — they are semantic data domains later stages may read.

When such a signal is eventually written, it **must declare that profile/intake
prerequisite explicitly**, using the dependency-declaration shape in
[`docs/building/architecture/contracts/profile_and_intake_dependencies.yaml`](../../../docs/building/architecture/contracts/profile_and_intake_dependencies.yaml).
A declaration names:

- `consumer_name` — the signal/tool that has the dependency,
- `depends_on_domain` — which of `profile_context`, `nutrition_intake`,
  `supplement_intake`, `observation_history` it draws on,
- `required_keys` — the **exact** attribute, nutrition-fact, dose, or observation
  metric keys it needs (a bare domain reference is not a declaration),
- `failure_mode` — how it behaves honestly when a prerequisite is absent, stale,
  partial, or unknown.

**Reject hidden fallbacks.** A signal must not quietly assume a value happens to
be present. "Use a measurement if it happens to be there" is **not** a substitute
for declaring a profile/intake prerequisite: finding a height row in observation
history does not satisfy a need for a *declared* profile height, because the same
storage adapter could lay things out differently tomorrow and the meaning of the
requirement must not depend on that. A signal that needs declared profile context
declares it and refuses honestly when it is missing — it does not opportunistically
read whatever observation row is nearby. The meaning of a declared requirement is
satisfied by meaning, not by table shape. The worked examples (BMI, a
protein-intake summary, a supplement-adherence summary) live in that dependency
contract.

## Declaring dependencies through the input-resolution seam

The seam that turns a declared prerequisite into a resolved value is the Stage 2
**input-resolution seam**. It is the next analytical foundation — domain-aware
resolution of *declared* inputs, not a universal prepared-series layer that
quietly collapses every domain into observation-shaped time series.

A consumer declares one dependency with `DependencyDeclaration(consumer_name,
depends_on_domain, required_key, failure_mode)` and asks for its value via
`resolve_dependency(conn, ResolutionRequest(anchor_ts=..., dependency=...))`.
The seam returns a `ResolvedInput` whose `usable` flag and `absence_reason`
encode honest-refusal context; resolvers never raise for ordinary missing data.

Dispatch is **registry-driven**, not an `if`/`elif` chain. `RESOLVERS` is the
static in-tree map from semantic domain to resolver function, populated by the
`@resolver(domain=...)` decorator. The four valid `SEMANTIC_DOMAINS` are:

- `observation_history` — concrete resolver shipped (`premura.engine.views.observation`).
- `profile_context` — concrete resolver shipped (`premura.engine.views.profile`).
- `nutrition_intake` — valid declaration target; resolves to
  `usable=False, absence_reason="unsupported_domain"` until a future mission
  ships a concrete resolver backed by real rows.
- `supplement_intake` — valid declaration target; same explicit
  `unsupported_domain` outcome until a future mission ships its resolver.

Dispatch is **open** by design: adding a new supported domain means landing one
new module under `premura/engine/views/` that registers itself through
`@resolver(domain=...)` and appending its dotted name to
`_BUILTIN_RESOLVER_MODULES`. Existing resolvers are not touched. There is no
filesystem scanning and no third-party plugin loader.

Consumers **must** go through `resolve_dependency` for cross-domain inputs.
Reaching directly into `_query.py`, observation-history SQL, or
`hp.profile_context_assertion` from a cross-domain consumer bypasses the seam
and reintroduces the silent-coercion failure mode the seam exists to prevent.

### Answer-family extension trigger

`RESULT_FAMILIES` is **closed** in this mission to `{status, trend, baseline,
change}`. A new family is added only when both of the following hold:

1. A desired answer genuinely cannot be honestly mapped onto status, trend,
   baseline, or change. Repackaging is not a trigger — if a question can be
   answered as one of the existing families with adjusted wording, prefer that.
2. The new question shape itself has been approved through a dedicated planning
   mission with its own spec, plan, and reviewer sign-off. Adding a family is a
   contract change, not a code-style preference.

Cosmetic packaging concerns (a nicer output struct, a more compact field set)
are not triggers. Likewise, multi-domain inputs alone do not motivate a new
family: BMI is multi-domain and ships under the existing `status` family.

## When to extend `RESULT_FAMILIES`

The trigger above is about *process* — a new family needs a dedicated planning
mission. This section is about *content* — what shape of future domain would
actually justify raising that question. Resolvers (`premura.engine.views`)
are open by design: a new domain's resolver lands without touching existing
ones. Answer families are the opposite — every consumer downstream (Stage 3
tools, MCP envelopes, test fixtures, the future teaching layer) switches on
`family`, so opening the set changes what every one of those consumers must
handle. Keep the dispatching axis (resolvers) pluggable; keep the
type-switching axis (families) closed.

Extending `RESULT_FAMILIES` is worth raising for review when a new domain's
natural answer matches one of these shapes, none of which the current four
families can honestly carry:

- **Categorical / qualitative.** The natural answer is a category, not a
  number — SNP genotype, blood type, a presence/absence flag from a
  microbiome panel. Likely needs an `assertion` or `categorical_status`
  family.
- **Structured uncertainty.** The natural answer carries uncertainty that
  does not fit a single number — a polygenic risk score with a confidence
  interval, an imaging segmentation confidence. Likely needs a `distribution`
  family.
- **Structured, non-scalar input.** The resolved input itself is structured
  rather than scalar — a vector of genome positions, an image mask — and no
  `to_dict()` over the existing envelopes captures it without lying about its
  shape.

Do not stretch an existing family to cover one of these. The cost of a fifth
family entry in `_results.py` is small. The cost of `StatusResult.value:
float | None` quietly holding `1.0` to mean "AG genotype" is that every
Stage 3 tool downstream silently loses type safety.

## Caveats that must be named

- Vendor-estimated metrics (e.g. sleep stages, HRV) must carry an
  "this is a vendor estimate" caveat.
- Sparse or imputed data must be disclosed via `caveats` and the relevant
  counts (`imputed_point_count`, `gap_count`, `before_count`, `after_count`).
- `change`-family results must explicitly disclaim significance and causation.
- When an answer cannot be produced, return a `MissingInputReport` whose
  `message` explains the gap in plain language.

## What Stage 2 must NOT claim

- No diagnosis, treatment advice, or clinical interpretation.
- No population norms, reference ranges, or external comparison data.
- No statistical-significance claims: no p-values, confidence intervals, or
  causal language (especially in the `change` family).
- A `trend` direction is plain direction only — never "significant" change.
- Do not depend on profile or intake context opportunistically. BMI now ships
  as the first cross-domain Stage 2 proof consumer (`name="bmi"`, family
  `status`) and resolves declared height plus weight through the
  input-resolution seam; age-adjusted interpretation remains deferred. Any
  further signal that needs profile or intake context must **declare** the
  prerequisite explicitly (see "Declaring profile and intake prerequisites"
  and "Declaring dependencies through the input-resolution seam" above) and
  must never silently substitute a measurement that happens to be present for
  a declared profile/intake dependency.

## Built-in loading

Built-in signal modules are listed statically in
`premura.engine._BUILTIN_SIGNAL_MODULES` and each exposes
`register_builtin_signals()`. Add a new family module to that list — do not add
filesystem scanning, eager imports, or a third-party plugin/manifest loader.
Importing `premura.engine` must stay lazy: the registry is empty until a query
or compute helper needs the built-in signals.

## Declaring an evidence-admissibility policy

A separate Stage 2 surface decides *whether a value is admissible as evidence
for a given question* — distinct from a signal, which computes an answer. You
declare admissibility through **frozen-dataclass policies**, not a signal.

All names below are re-exported from `premura.engine`; reach them through
`from premura.engine import ...`, never through `premura.engine.policies._*`:

- Closed vocabularies: `QuestionType`, `EvidenceStatus`, `RejectionReason`,
  `FreshnessMode`, `Admissibility`, `TemporalMeaning`, `PolicyShape`,
  `MissingDataBehavior`, `RefusalMode`, plus `CAVEAT_REQUIRED_SHAPES`.
- Declaration dataclasses (frozen, parameters only): `MetricFamilyPolicy`,
  `QuestionRule`, `FreshnessRule`, `SufficiencyRule`, `PolicyExample`.
- Evaluation: `EvidenceCandidate` (input), `EvidenceOutcome` /
  `EvaluationResult` (output), and the pure helper `evaluate_evidence(...)`.
- Built-in defaults + registry: `BUILTIN_POLICIES` / `builtin_policies()`,
  `PolicyRegistry`, `build_builtin_registry()`, `DuplicatePolicyError`.

### How policies are keyed

A policy is a **family-level declaration with per-question modifiers**. One
`MetricFamilyPolicy` covers a metric *family* (e.g. resting heart rate as a
family, not each individual metric id), and its `question_rules` map a closed
`QuestionType` to the freshness/sufficiency behavior for *that question*. The
same family answers "what is X now?" and "how has X trended?" with different
admissibility windows because the question, not the metric, drives the rule.

This is deliberately **not YAML**. No human domain reviewer reads policy files
directly — capture and review are agent-mediated — and typed, code-native
declarations match the rest of Stage 2 and get caught by the model, evaluator,
and defaults tests. A YAML policy layer would add a parser, a schema, and a
second source of truth for zero agent-facing benefit.

### Declarations are parameters only

A policy declaration carries **values, not behavior**: closed enum members,
duration/count thresholds, required-provenance field names, and caveat
strings. It must contain **no expressions, conditionals, callables, SQL, or
network calls**. The single place that turns those parameters into decisions is
`evaluate_evidence`. This separation is the guardrail against a creeping policy
mini-language: if a new rule cannot be expressed as a parameter on the existing
dataclasses, that is a signal to open a future mission, not to embed logic in a
declaration.

### The PubMed boundary

Literature tooling (e.g. a PubMed MCP) may help an agent **author or review** a
policy — choosing a defensible freshness window, sanity-checking a caveat — and
the rationale it produces belongs in `PolicyExample` / caveat text. **Stage 2
must never call PubMed (or any network service) at runtime.** Evaluation is pure
over the candidates the caller passes; literature is rationale captured at
authoring time, never a runtime evidence source.

### How to add a policy

1. If you need background, use a PubMed MCP or other sources **only** during
   research/review — never wire them into runtime.
2. Reuse an existing `QuestionType` and `PolicyShape` where the question fits.
3. Add a family-level `MetricFamilyPolicy` to the built-in defaults, with a
   `QuestionRule` per relevant question type.
4. Capture rationale, caveats, and at least one admissible and one refusal
   `PolicyExample` so the intent survives without reading the mission folder.
5. Run the policy model, evaluator, and defaults tests
   (`tests/test_engine_policy_model.py`, `tests/test_engine_policy_evaluator.py`,
   `tests/test_engine_policy_defaults.py`) plus the public-surface test.

### What not to do (this mission)

- Do **not** add YAML policy files or any external policy config.
- Do **not** add runtime literature fetching or any network call to evaluation.
- Do **not** add a custom evaluator branch for one metric; if a metric needs
  behavior the parameters cannot express, that is a future mission.
- Do **not** introduce a new `QuestionType`, `RejectionReason`, or a fifth
  result family. New question types or result families change the authoring
  contract and require a dedicated future mission with its own sign-off.

## Extending or reviewing a Stage 3 analytical tool

A Stage 3 analytical tool is a different surface from a Stage 2 signal. A signal
answers one of the four descriptive families; an analytical tool computes a
deterministic *estimate* (change point, smoothed pattern, association) over one
or more already-admitted input series and returns an `AnalyticalResultEnvelope`
— an estimate **plus** mandatory validity metadata and a confound checklist, or
a first-class refusal carrying no estimate. The names below are re-exported from
`premura.engine`: `AnalyticalToolSpec`, `AnalyticalResultEnvelope`,
`AnalyticalInputSeries`, `PairedAnalyticalInput`,
`PreRegisteredAssociationHypothesis`, `AnalyticalQuestionType`, `ConfoundKey`,
`prepare_input_series`, `prepare_paired_input`,
`prepare_before_after_paired_input`. `engine.list_analytical_tools()` returns exactly
`change_point`, `smoothed_average`, `correlate`, `rolling_mean`, `paired_t_test`,
and `condition_paired_t_test` — six tools. The first five are the bounded
"finished" set; `condition_paired_t_test` is the reviewed condition-label pairing
extension `paired_t_test` deferred (see its section below). The rules a *seventh*
tool must follow — and the bounded shapes the newest tools commit to — are below.

The same invariants from the policy layer hold here: the engine is **stateless,
deterministic, offline** — no clock, no network, no resampling. The only "now"
the analytical layer touches is consumed upstream when `prepare_input_series`
admits a window; everything after is pure over the prepared inputs.

### `correlate` — pre-registered, lagged *association*, never significance

`correlate` is the first **multi-input** analytical tool. Its locked
architecture is design decision note
[`0008`](../../../docs/building/adr/0008-correlate-pre-registered-lagged-association.md).
The *statistical* choices (Spearman's rho, the effective-sample-size band, the
paired-sample floor, the `common_cause_plausible` key, the lag ceiling) are
normative **here**, in the rules below; the investigation that selected them —
the rationale, alternatives, and evidence — is recorded in the frozen research
note
[`CORRELATE_METHODOLOGY_RESEARCH.md`](../../../docs/history/research/CORRELATE_METHODOLOGY_RESEARCH.md).
Read both before changing it. The rules that govern any review or extension:

- **Association, not causation.** `correlate` reports a signed monotonic
  *association* with an effect size and an honest plausible **range** — it must
  never compute or return a p-value, the word "significant," or any causal
  claim. The forbidden quantities are refused **before** computation: any extra
  positional or keyword argument (a request for a p-value, a significance test, a
  tolerance window, or a lag scan) is rejected with `unsupported_parameter`, so a
  narrating model can never launder certainty the data cannot support.
- **Lag is a caller-declared, directional, whole-day offset — never scanned and
  never a tolerance.** The hypothesis reads "left at day *D* associates with
  right at day *D + lag*"; the engine shifts the responding series by that whole
  number of days and pairs on the same local calendar day. Lag defaults to 0 and
  is asymmetric. Choosing the lag (or pair) that maximizes the coefficient is
  p-hacking by another name — the engine never does it. Large lags require an
  explicit caller-supplied justification; the deterministic engine never does the
  literature research that justifies one.
- **Paired inputs go through `prepare_paired_input`.** It takes two
  already-admitted `AnalyticalInputSeries` plus the
  `PreRegisteredAssociationHypothesis`, applies the declared lag to the right
  series, pairs same-day-after-lag observations, **narrows the overlap window to
  the actual paired days**, and records the imputed-pair fraction and a
  reproducible paired source summary. It computes no coefficient. It propagates
  each constituent series' admissibility verdict verbatim rather than re-running
  the evidence policy, and refuses (no estimate) when the hypothesis is malformed,
  either series was refused, or the raw paired count is below the conservative
  floor.
- **The uncertainty band is corrected for autocorrelation, never thresholded.**
  Switching to a rank coefficient does **not** fix autocorrelation, so the band is
  computed on an *effective* sample size `N_eff` (a Bartlett-type variance
  inflation over the rank series, with imputed pairs down-weighted), not the raw
  count, and back-transformed via Fisher's z. The result is a *plausible range
  given how little independent information a short, day-to-day-correlated window
  holds* — present it that way, never as a 95% confidence interval. When `N_eff`
  falls far below the raw count the result carries `temporal_autocorrelation`;
  when too much of the window is imputed it carries `high_imputation`; and the
  tool **refuses** when the raw paired sample or `N_eff` is below the floor rather
  than show a confident-looking spurious association to a non-expert.

### `rolling_mean` — a declared moving-window summary, never a window scan

`rolling_mean` reports a moving level over **one** admitted ordered series across
a **caller-declared window**. The window is fixed before the result exists; the
engine **must not scan windows** or keep the window that looks strongest — that is
p-hacking by another name. It is a different tool from `smoothed_average`, not a
rename: `smoothed_average` is a conservative trailing smoothed pattern, while
`rolling_mean` is an explicit moving-window summary that surfaces per-point
**coverage and imputation** so a narrator can see exactly how much of each window
was real data. The rules any review or extension must hold:

- **Caller-declared `window` and `min_coverage`, never inferred.** The window is a
  positive integer; `min_coverage` is a threshold in `[0.0, 1.0]`. Each emitted
  point summarizes only observations inside that trailing window; long gaps stay
  visible through coverage and missingness metadata rather than being silently
  filled.
- **Available envelope fields.** An available result carries the tool name and
  declared parameters, the input metric id and admitted input span, the ordered
  rolling-mean points, the window size and minimum coverage, per-point coverage and
  imputation counts, the emitted-point count and source sample size, validity
  status, a closed-vocabulary confound checklist, and concise caveats with **no
  prediction, significance, or causal claim**.
- **Refusal classes (no estimate).** Refuse when the input series is
  refused/stale/missing/inadmissible, when `window` is zero/negative/beyond the
  supported maximum, when `min_coverage` is outside `[0.0, 1.0]`, when no window
  reaches the required coverage, or when the caller asks the tool to choose or scan
  windows.
- **Trace identity.** The normalized hypothesis identity is `metric_id`, `window`,
  `min_coverage`. Exact retries collapse; different windows or coverage thresholds
  are distinct examined hypotheses.

### `paired_t_test` — a declared before/after anchor-date comparison, no significance, no cause

`paired_t_test` reports a **simple before/after paired comparison around one
caller-declared anchor date** over one admitted ordered series. Its name follows
the colloquial label, but its honesty boundary is strict and matches the rest of
the analytical layer:

- **It is not a significance test.** It computes and returns **no p-value and no
  significance verdict**. It reports a **paired difference** — the mean of
  *after minus before* — with a **descriptive uncertainty band** (the dispersion
  of the paired differences), observed direction, expected direction, and a
  direction-match flag. Present the band as *how spread out the paired differences
  are*, never as a 95% confidence interval and never as evidence the difference is
  "significant." Reject the forbidden quantities **before** computation, the same
  way `correlate` does: a request for a p-value, a significance test, a tolerance
  window, or a scan is refused with `unsupported_parameter` so a narrating model
  cannot launder certainty the data cannot support.
- **It names no cause.** The anchor date is a comparison boundary, never a stated
  cause of any change. Available caveats carry no cause, diagnosis, treatment, or
  population-norm claim.
- **Anchor-date pairing only — condition-label pairing is a separate tool.**
  `paired_t_test`'s only pairing rule is before/after around one declared anchor
  date. It builds pairs from observations before and after the anchor by one fixed
  documented rule and **must not** support condition labels, arbitrary pair maps,
  or event classification, and **must not** scan anchor dates, before/after
  windows, or pair-selection strategies. Broader **condition-label pairing** is
  **not** smuggled into this shape: it ships as the sibling
  `condition_paired_t_test` tool (its own section below), built on its own pairing
  contract, request shape, trace-identity fields, and refusal rules. The
  anchor-date request shape, behavior, and trace identity are unchanged.
- **Required inputs.** One admitted series, an `anchor_date` (local calendar date),
  positive-integer `before_days` and `after_days`, and an `expected_direction`
  (`increase` or `decrease`) declared before computation.
- **Available envelope fields.** Tool name and declared parameters, metric id and
  the before/after spans used, raw pair count, mean paired difference (after minus
  before), observed direction, expected direction, direction-match metadata,
  uncertainty metadata for the mean paired difference, imputation percentage,
  validity status, and a closed-vocabulary confound checklist.
- **Refusal classes (no estimate).** Refuse when the input series is
  refused/stale/missing/inadmissible, when the anchor date is missing or malformed,
  when `before_days`/`after_days` is outside supported bounds, when the expected
  direction is missing or outside the closed set, when no valid before/after pairs
  can be built, when the pair count is below the conservative floor, when the
  paired differences are constant (the method cannot proceed), or when the caller
  asks for condition pairing, arbitrary pair maps, anchor/window scanning,
  p-hacking, diagnosis, causation, or treatment advice.
- **Trace identity.** The normalized hypothesis identity is `metric_id`,
  `anchor_date`, `before_days`, `after_days`, `expected_direction`. Exact retries
  collapse; different anchors, windows, or expected directions are distinct
  examined hypotheses.

### `condition_paired_t_test` — a declared condition-label paired difference, no significance, no cause

`condition_paired_t_test` is the reviewed **condition-label pairing** extension
that `paired_t_test` deferred. It reports a paired difference between **off-label**
and **on-label** declared periods of **one** operator's series. It is a *separate
registered tool* with its own pairing contract, request shape, trace-identity
fields, and refusal rules — the anchor-date `paired_t_test` is unchanged. Its
honesty boundary matches the rest of the family.

- **The condition label is operator vocabulary, never an enum.** The caller
  declares **one** non-empty condition label (a string the operator chose, e.g.
  `"on_magnesium"`). There is no condition list, no label registry, and no
  validation against a vocabulary — the contract constrains the *shape* (one
  label, declared episodes, the one fixed pairing rule), not the *content*. A
  *list* of labels is a scan attempt and is refused at the boundary.
- **The one fixed pairing rule (the paired unit is the episode).** The caller
  declares a set of non-overlapping on-condition **episodes**, each a closed
  local-calendar-day range `[start_day, end_day]` (`end_day >= start_day`). Each
  episode contributes **one pair**: the **off value** is the mean of usable
  observations on days in `[start_day - before_days, start_day)` that fall
  **outside every declared episode**; the **on value** is the mean of usable
  observations on days in `[start_day, min(start_day + after_days - 1, end_day)]`;
  the **difference is on − off**. Day keying and last-write-wins per local calendar
  day follow the anchor-date conventions. The estimate is the mean of the
  per-episode differences with a descriptive dispersion band.
- **No scanning.** One label, one declared episode set, one declared window pair,
  one declared expected direction per request. Lists of labels, candidate episode
  sets, or window lists are refusals, not iterations. Multiplicity across requests
  is the session trace's job.
- **It is not a significance test and names no cause.** Like `paired_t_test` it
  emits **no p-value and no significance verdict**, and the label is
  operator-declared, not a verified condition — it only splits the windows and is
  never stated as a cause. Available caveats carry no cause, diagnosis, treatment,
  or population-norm claim. A forbidden quantity (a p-value, a significance test, a
  scan) is refused **before** computation with `unsupported_parameter`. A constant
  set of per-episode differences has no honest band, so the tool refuses.
- **No silent salvage.** An episode whose before-window intersects another declared
  episode, or that lacks at least one usable observation in either window, is
  **excluded with a per-episode disclosure** (episode start + machine-readable
  reason) carried in the estimate. No invented values.
- **Required inputs.** One admitted series; one `condition_label`; a set of
  non-overlapping `episodes`; positive-integer `before_days` and `after_days`; and
  an `expected_direction` (`increase`/`decrease`) declared before computation.
- **Available envelope fields.** Tool name and declared parameters, metric id, mean
  per-episode difference (on − off), observed/expected direction + match flag, the
  echoed label, `episode_count_declared`, `episode_count_used`, the per-episode
  exclusions, window parameters, method revision, the descriptive dispersion band
  (`interval_kind="descriptive_dispersion_band"`), imputation percentage, validity
  status, and a closed-vocabulary confound checklist.
- **Refusal classes (no estimate).** Refuse when the input series is
  refused/stale/missing/inadmissible; fewer than two episodes are declared;
  declared episodes overlap; a window is non-positive or out of bounds; the
  expected direction is missing or outside the closed set; fewer than two episodes
  remain usable after exclusions; the per-episode differences are constant; or the
  caller asks for a label list, candidate episode/window scanning, p-hacking,
  diagnosis, causation, or treatment advice.
- **Trace identity.** The normalized hypothesis identity is `metric_id`,
  `condition_label`, the declared `episodes` set (order-insensitive), `before_days`,
  `after_days`, `expected_direction` — the fields ADR-0009 anticipated for this
  family ("grouping/event, windows, contrast, params"). Exact retries collapse;
  a different label, episode set, window, or expected direction is a distinct
  examined hypothesis.

### Confounds are a closed, rule-shaped vocabulary — not an enumerated list

A non-refusal analytical result must carry its confound checklist drawn from the
closed `ConfoundKey` vocabulary; keys outside the set are rejected at
registration, so agents cannot mint their own quality labels. The keys describe
**axes of risk**, not specific confounders: `common_cause_plausible` is the
canonical correlation confound — *a third, unmeasured variable could plausibly
drive both series, so the association may be spurious rather than a direct
relationship*. It is deliberately one rule-shaped flag, not an enumerated list of
candidate causes; the candidate (illness, a training block) stays open and
**agent-supplied**, reinforcing association-not-causation at the data layer. Add a
new key only as a reviewed contract change through a dedicated mission, the same
bar as a new `QuestionType` or result family — never as an ad-hoc string for one
tool.

### Literature is authoring/review context, never runtime

PubMed or other literature tooling may help an agent **author or review** an
analytical tool — picking a defensible lag ceiling, sanity-checking the band
language, deciding whether a large lag is plausible — and that rationale belongs
in the research note and caveat text. The analytical engine must **never** call
PubMed or any network service at runtime: computation is pure over the prepared
inputs the caller passes. PubMed grounding and a session-scoped reproducible
research trace / multiplicity audit are **separate, deferred missions** (see
[ROADMAP.md](../../../docs/shared/ROADMAP.md) and design decision note `0008`),
not part of this tool — per-call honesty cannot see an agent that ran many
hypotheses and surfaced the one that fit, which is a stateful session-layer
concern by design.

## Tests and review notes a contributor must include

- Follow the repo's test-first rule. Assert through **public** imports
  (`from premura import engine`) and observable behavior, against temporary
  DuckDB fixtures — not internal mocks.
- Cover at least one success path and the refusal paths (missing input, stale
  data, insufficient data) for your signal.
- Include a PR note stating which family the signal uses, what evidence it
  reads, and which caveats it always names.

## Reviewer checklist

When reviewing a Stage 2 signal PR, confirm:

- The signal fits one of the four families and uses the matching envelope.
- `name` is unique in the registry; `family` (if set) is a valid family.
- Answers read only the user's own data; baselines are own-baseline only.
- Freshness and refusal states are set honestly; no answer on bad data.
- Required caveats are present; no diagnosis, norms, or significance claims.
- Any profile/intake dependency is **declared explicitly** (per the
  dependency-declaration contract), never satisfied by opportunistically reading
  a value that happens to be present in observation history.
- Built-in registration uses the static module list, not a new loader.
- Tests assert through public imports against DuckDB fixtures and cover refusal
  paths.

### Reviewing an evidence-policy change

When reviewing a new or changed `MetricFamilyPolicy`, confirm:

- It uses **existing** `QuestionType` values and `RejectionReason` values — a
  new question type or rejection reason is a future mission, not a PR.
- It claims **no clinical authority**: no diagnosis, treatment, reference
  ranges, population norms, or significance/causation language; caveats stay
  plain-English.
- Its rejection reasons stay **distinct** — each refusal maps to one specific,
  machine-readable reason, not an overloaded catch-all.
- Any PubMed/literature note is **rationale only** (in `PolicyExample`/caveat
  text), never a runtime dependency of evaluation.
- It includes worked examples for **both** admissible and refusal behavior so
  intent is reviewable without re-deriving it.
- The declaration is **parameters only** — no expressions, callables, SQL, or
  network calls smuggled into the dataclass.
