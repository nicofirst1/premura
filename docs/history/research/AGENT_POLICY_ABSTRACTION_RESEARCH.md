# premura — Agent Policy Abstraction Research

> Status: proposal/archive. Research summary to inform planning vocabulary, not
> a runtime contract.
>
> Generated: 2026-05-29
> Scope: names and design guidance for bounded abstractions that help AI agents
> author safe, reviewable Stage 2 evidence policies.

## Purpose

Capture the research behind a planning shift for the Stage 2 evidence
admissibility mission.

The user clarified that Premura should not pre-enumerate every domain, metric,
and question policy. Because this repository is meant to be operated and
extended by AI agents for a human operator, the better goal is to give future
agents a bounded way to author policies for new cases without freehanding unsafe
logic.

## Summary

There is no single settled name for this exact pattern. The closest established
family is:

- contract-first or schema-first policy design
- policy-as-code, especially declarative policy
- design by contract
- executable specification
- agent-computer interface or AI scaffolding
- controlled vocabulary or knowledge schema
- declarative guardrails

For Premura, the most precise phrase is:

**contract-first, declarative evidence-admissibility policy layer**

Plain English version:

Premura should define a small, typed declaration shape that future agents fill
in when adding Stage 2 evidence behavior. A deterministic evaluator checks those
declarations. Agents are guided, but not allowed to invent unsafe logic from
scratch.

## Most Applicable Terms

### Policy-as-code

Useful because Premura wants policies to be explicit, versioned, testable, and
evaluated deterministically.

For this mission, policy-as-code does not mean adopting a third-party policy
engine. It means treating admissibility rules as reviewable artifacts rather
than prose hidden in implementation details.

### Contract-first / schema-first design

Useful because future agents should fill a bounded declaration rather than write
free-form policy logic.

The declaration shape becomes the contract. It says what a policy must state:
question shape, evidence basis, freshness stance, sufficiency rule, provenance,
caveats, refusal behavior, and examples.

### Design by contract

Useful because each Stage 2 signal or policy must state its obligations and
invariants.

Examples:

- what evidence it is allowed to use
- when it must refuse
- what caveats must always be attached
- which kinds of questions it can honestly support

### Executable specification

Useful because declarations should include examples that double as tests.

A good policy declaration should say not only "this supports long-term control"
but also provide positive and negative examples that the evaluator or tests can
check.

### Agent-computer interface

Useful because Premura is not only a human-facing codebase. It is a repository
where future AI agents are expected to add parsers, signals, and analytical
behavior.

The repository should therefore expose shapes that make the safe action easy and
the unsafe action hard.

## Recommended Pattern For Premura

Premura should not try to ship a complete policy table for every future metric.
Instead, it should ship a small declaration contract and a deterministic
evaluator.

The contract should let future agents declare:

- the policy identity and version
- the question types the policy supports
- the evidence basis it expects
- the temporal meaning of the evidence
- freshness or recency handling
- sufficiency and missing-data rules
- required provenance
- standing caveats
- refusal modes
- positive and negative examples

The evaluator should produce machine-readable outcomes such as:

- admissible
- rejected
- insufficient

Rejection reasons should stay distinct. For example:

- stale for this question
- too sparse
- missing timestamp
- missing required context
- wrong evidence kind for the question
- unsupported policy declaration

## Design Guidelines

- Keep question types closed unless a later mission expands them.
- Keep outcome statuses and rejection reasons closed so future agents cannot
  invent vague categories.
- Allow new metric families through new declarations, not custom evaluator
  branches for each metric.
- Separate temporal meaning from freshness. For example, "A1C integrates over
  months" is not the same as "A1C is fresh for N days."
- Require provenance fields on every candidate and every outcome.
- Treat caveats as structured data, not prose-only notes.
- Put examples beside declarations and make those examples testable.
- Version policies so changes to interpretation are reviewable.
- Prefer explicit refusal over soft caveats when evidence is wrong for the
  question.
- Keep the policy layer local and descriptive; it should not pretend to be
  clinical authority.

## Pitfalls To Avoid

### Policy sprawl

One-off per-metric rules become unreviewable. The mission should introduce a
bounded declaration shape and representative examples, not a large bespoke table.

### Prose-only contracts

Agents will paraphrase prose inconsistently. Important safety rules need typed
fields, closed vocabularies, and tests.

### Generic quality scores

A single score hides the difference between stale evidence, sparse evidence,
missing timestamps, and wrong question type. Those states need separate reasons.

### Silent fallback

"Use whatever row exists" reintroduces the exact failure Premura is trying to
avoid. If a signal needs a declared kind of evidence, it should say so.

### Open-ended vocabularies

Future agents should not be able to invent values like `semi_currentish` or
`probably_valid`. Closed vocabularies prevent drift.

### Arbitrary code in declarations

If declarations can run arbitrary code, reviewability is lost. Extension should
happen by adding declarations and examples, not hidden executable branches.

### Overclaiming clinical authority

These policies should state what Premura can honestly use from the local
warehouse. They should not claim to be universal medical rules.

## Example Declaration Shape

This is illustrative, not a committed runtime schema:

```yaml
policy_id: integrated_long_term_control
policy_version: 1
metric_family: a1c_like_long_horizon_marker
applies_to_metrics:
  - a1c
supported_question_types:
  current_status: inadmissible
  recent_trend: limited
  long_term_control: admissible
  historical_baseline: admissible
temporal_meaning: integrates_over_months
freshness:
  strict_window_days: null
  preferred_window_days: 120
evidence_density:
  min_observations: 1
  min_span_days: null
required_context:
  - observed_at
standing_caveats:
  - "This marker reflects longer-term control, not what is happening right now."
rejection_reasons:
  stale_for_question: true
  wrong_question_type: true
refusal_mode: no_admissible_evidence
examples:
  - question_type: current_status
    evidence_age_days: 90
    expected: rejected
  - question_type: long_term_control
    evidence_age_days: 90
    expected: admissible
```

## Implication For The Current Mission

The Stage 2 Evidence Admissibility Foundation should be reframed from "enumerate
all evidence policies" to "provide the contract that future agents use to author
safe evidence policies."

That means the mission should:

- create a declaration contract for Stage 2 evidence policies
- validate that declarations are complete and use closed vocabularies
- include representative examples, not exhaustive coverage
- provide enough evaluator behavior to prove admissible, rejected, and
  insufficient outcomes
- avoid broad refactors of existing signals unless one narrow proof integration
  is needed

## Source Anchors

- Open Policy Agent / Rego: declarative policy-as-code over structured data.
  <https://www.openpolicyagent.org/docs/latest/policy-language/>
- JSON Schema: declarative structure and constraint validation.
  <https://json-schema.org/overview/what-is-jsonschema>
- OpenAPI Specification: machine-readable contract-first interface descriptions
  for humans and tools. <https://spec.openapis.org/oas/latest.html>
- Design by Contract / Eiffel: explicit obligations, preconditions,
  postconditions, and invariants.
  <https://www.eiffel.org/doc/eiffel/ET-_Design_by_Contract_%28tm%29%2C_Assertions_and_Exceptions>
- SWE-agent paper: agent-computer interface framing for purpose-built software
  environments used by AI agents. <https://arxiv.org/abs/2405.15793>
- Gherkin / Cucumber: executable examples as tests and documentation.
  <https://cucumber.io/docs/gherkin/reference/>

## Related research

- [AGENT_OPERATED_SOFTWARE_PRIOR_ART.md](AGENT_OPERATED_SOFTWARE_PRIOR_ART.md)
  — wider literature map (May 2026): what already exists for building software
  to be operated by agents, the policy-as-code/guardrail tooling, and the
  evidence-admissibility gap premura's Stage 2 work targets.
