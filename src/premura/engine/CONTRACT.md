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
- Do not depend on profile or intake context opportunistically. No shipped
  Stage 2 signal consumes profile/intake data today; profile-dependent answers
  (e.g. BMI, age-adjusted interpretation) remain deferred. A future signal that
  needs such context must **declare** the prerequisite explicitly (see "Declaring
  profile and intake prerequisites" above) and must never silently substitute a
  measurement that happens to be present for a declared profile/intake
  dependency.

## Built-in loading

Built-in signal modules are listed statically in
`premura.engine._BUILTIN_SIGNAL_MODULES` and each exposes
`register_builtin_signals()`. Add a new family module to that list — do not add
filesystem scanning, eager imports, or a third-party plugin/manifest loader.
Importing `premura.engine` must stay lazy: the registry is empty until a query
or compute helper needs the built-in signals.

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
