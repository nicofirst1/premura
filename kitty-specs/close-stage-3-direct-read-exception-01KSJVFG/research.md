# Phase 0 Research — Close the Stage 3 Direct-Read Exception

## Decision 1: Use a separate operator entrypoint, not a flag on the default server

**Decision**

Add a separate operator MCP entrypoint that shares the same server core as the default agent-facing entrypoint, but registers `query_warehouse` in addition to the validity-gated tools.

**Rationale**

- Keeps the default product surface visibly doctrine-compliant.
- Makes the branch between high-guarantee and lower-guarantee operation legible in code, docs, and tests.
- Supports the product decision that an agent may sometimes need raw exploration for advanced questions, but only after explicit user approval.
- Avoids burying product-integrity behavior behind an env var or hidden config branch on the default surface.

**Alternatives considered**

- Same entrypoint with config/env toggle: rejected because it keeps the default surface ambiguous and makes accidental exposure easier.
- Remove raw SQL entirely: rejected because advanced human and explicitly user-approved agent exploration still need a real escape hatch.

## Decision 2: Re-back `list_metrics` and `metric_summary` through new Stage 2 helpers

**Decision**

Add engine-side helpers for a metric catalog and metric validity summary, then make MCP consume those helpers instead of querying `hp.*` directly.

**Rationale**

- The direct-read exception exists because the catalog tools never had Stage 2 equivalents.
- Engine ownership keeps freshness/imputation logic in one place and preserves the Stage 2 -> Stage 3 contract.
- The result shape can be designed for machine branching rather than retrofitted from SQL row aggregates.

**Alternatives considered**

- Keep logic in MCP and merely reshape the payload: rejected because it preserves the architectural breach.
- Express catalog/summary as ordinary signal specs in the existing registry: rejected because these are catalog/summary service functions, not end-user question signals.

## Decision 3: Introduce dedicated result envelopes for catalog and summary responses

**Decision**

Add typed engine result objects for:

- metric catalog entry
- metric validity summary

These should use the existing freshness vocabulary (`current`, `stale`, `unavailable`) and expose explicit fields for sample size, imputed proportion, and gap count.

**Rationale**

- Current `_results.py` envelopes cover status/trend/baseline/change signals, but not catalog/summary semantics.
- A typed envelope prevents free-text coupling and supports FR-002, FR-003, and NFR-003.

**Alternatives considered**

- Return plain dicts from engine helpers: rejected because it weakens the public engine contract and makes drift easier.
- Reuse existing signal result types: rejected because none represent metric metadata plus coverage summary cleanly.

## Decision 4: Use a fixed 30-day recent window for summary coverage metrics

**Decision**

Compute `sample_size`, `imputed_proportion`, and `gap_count` over a fixed recent 30-day rolling window.

**Rationale**

- The spec allows a fixed recent window as an implementation detail.
- Thirty days is long enough to expose sparse vs. dense recent coverage without turning the summary into an all-history aggregate again.
- It is easy to explain and test.

**Alternatives considered**

- Metric-specific windows for coverage metrics: rejected for this mission as unnecessary extra policy surface.
- All-time aggregation: rejected by spec and doctrine because it masks current trustworthiness.

## Decision 5: Treat raw operator mode as a lower-guarantee path with mandatory user approval

**Decision**

The operator entrypoint is allowed for advanced raw exploration, including agent use, but the plan assumes the caller must obtain explicit user approval before switching to that mode. The user-facing explanation belongs in docs and the operator-entrypoint contract; implementation of conversational approval enforcement in an external agent is out of scope here.

**Rationale**

- Matches the clarified doctrine and charter.
- Avoids pretending raw SQL results have the same acuity guarantees as Stage 2-gated outputs.
- Keeps this mission focused on tool-surface integrity while still documenting the policy boundary for downstream agent/UI work.

**Alternatives considered**

- Allow silent agent switching: rejected by user decision.
- Enforce approvals inside the MCP server itself: rejected for this mission because the server does not manage conversation state or user identity today.
