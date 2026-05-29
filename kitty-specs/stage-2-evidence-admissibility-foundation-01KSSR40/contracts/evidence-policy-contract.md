# Contract: Stage 2 Evidence Policy Declarations

## Purpose

This contract describes how future agents should author Stage 2 evidence-admissibility policies.

The contract is declarative but code-native: policies are frozen Python dataclass declarations backed by closed enums. They are not YAML files, not arbitrary functions, and not a policy mini-language.

## Contract Rules

### CR-001: Policies are family-level declarations

A policy declaration describes a metric family or explicit family group. It may list example metrics, but it must not become a one-off custom branch for each metric.

### CR-002: Question behavior is declared with per-question rules

Each family-level policy declares how it behaves for supported question types. A policy should not be duplicated once per `(family, question_type)` pair unless a future mission proves that family-level rules are insufficient.

### CR-003: Declarations are parameters only

Allowed declaration content:

- closed enum values
- duration or count thresholds
- required provenance fields
- caveat strings
- refusal modes
- examples
- rationale and source notes

Forbidden declaration content:

- executable functions
- expressions
- conditional operators
- arbitrary predicates
- dynamic imports
- network calls
- hidden SQL

The evaluator owns all branching.

### CR-004: PubMed is for authoring and review, not runtime

Agents may use PubMed MCP or other literature tools when proposing or reviewing a policy. The resulting Stage 2 declaration must encode only local deterministic parameters and plain-language rationale. The Stage 2 evaluator must not call PubMed or any network service.

### CR-005: Rejection reasons stay distinct

The evaluator must preserve distinct reasons such as stale evidence, sparse evidence, missing timestamp, missing context, and wrong evidence kind. A generic quality score is not sufficient.

### CR-006: Examples are part of the contract

Each representative policy shape should have examples that future tests can execute. Positive examples may live with the built-in declaration. Negative examples should focus on refusal and rejection cases.

### CR-007: Policy changes are reviewable

Every policy declaration includes a version and rationale. A change to admissibility behavior is a contract change, not a refactor-only implementation detail.

## Required Vocabulary

Initial closed vocabularies:

- Question type: `current_status`, `recent_trend`, `long_term_control`, `historical_baseline`
- Evidence outcome: `admissible`, `rejected`, `insufficient`
- Rejection reason: `stale_for_question`, `too_sparse`, `missing_timestamp`, `missing_required_context`, `wrong_evidence_kind`, `unsupported_policy`
- Freshness mode: `strict_window`, `preferred_window`, `baseline_relative`, `caveat_only`, `valid_until_superseded`

Adding to these vocabularies changes the authoring contract and should happen in a future mission unless the addition is explicitly included in this mission's tasks.

## Public Behavior Contract

Given:

- a question type
- one or more evidence candidates
- registered metric-family policies

The evaluator returns:

- admissible evidence, separated from rejected and insufficient evidence
- preserved provenance for every outcome
- machine-readable rejection reasons
- plain-English messages and caveats
- a refusal outcome when no admissible evidence remains

The evaluator never returns diagnosis, treatment advice, medication advice, emergency guidance, population norms, p-values, confidence intervals, or causal claims.

## Agent Authoring Checklist

Before adding or changing a policy declaration, an agent must answer:

- What family of evidence does this policy cover?
- Which question types can it honestly support?
- What temporal meaning does this evidence have?
- What freshness or recency parameters apply?
- What evidence density is required?
- What provenance fields are mandatory?
- What caveats must always travel with the result?
- When must the evaluator refuse?
- What positive and negative examples prove the behavior?
- Was PubMed or other literature used during review, and if so what settled parameter did it justify?
