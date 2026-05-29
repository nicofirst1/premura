# Premura Stage 2 engine contributor contract

> Audience: humans and AI agents adding a grounded Stage 2 **signal function**
> under `src/premura/engine/`.
> Authority: this file ships with the package and is the source of truth for
> what a Stage 2 signal may do and claim. Its sibling is
> `src/premura/parsers/CONTRACT.md` (the parser-side contract).
> See `docs/architecture/STAGES.md` for where Stage 2 sits in the four-stage
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
[`docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md`](../../../docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md).
None of these domains is consumed by a shipped Stage 2 signal today, and none is
a new execution stage — they are semantic data domains later stages may read.

When such a signal is eventually written, it **must declare that profile/intake
prerequisite explicitly**, using the dependency-declaration shape in
[`docs/architecture/contracts/profile_and_intake_dependencies.yaml`](../../../docs/architecture/contracts/profile_and_intake_dependencies.yaml).
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
