# Phase 0 Research: Session Research Trace and Multiplicity Disclosure

## Decision: Use explicit MCP research sessions

**Rationale**: Explicit sessions produce a stable `session_id`, make trace grouping reproducible, and avoid hidden per-connection state that is difficult to test or replay. This matches the confirmed planning alignment and ADR-0009.

**Alternatives considered**: Implicit sessions per MCP connection/client context. Rejected because connection state is less visible, less reproducible, and more likely to produce ambiguous disclosures.

## Decision: Store canonical trace records in `trace.*` tables in the existing DuckDB warehouse

**Rationale**: The trace needs durable local state and exact warehouse context. Keeping it in the warehouse file preserves locality and queryability. Keeping it out of `hp.*` preserves the existing meaning boundary: `hp.*` contains health facts; `trace.*` contains tool-use provenance.

**Alternatives considered**: Markdown files, JSONL sidecars, or `hp.*` tables. Markdown/JSONL are too easy to omit or edit and weaker for bounded disclosure queries. `hp.*` would collapse provenance into health facts and drag trace logs into health-export semantics.

## Decision: Keep the analytical engine stateless and record around MCP dispatch

**Rationale**: ADR-0008 requires the engine to stay pure: no clock, session state, filesystem, or network. The MCP layer observes analytical tool calls and can record before/after dispatch without changing tool math or result envelopes.

**Alternatives considered**: Passing a session object into engine tools or recording from `premura.engine`. Rejected because it would break the determinism invariant and create coupling between analysis and session auditing.

## Decision: `N` is unique normalized examined hypotheses, not raw calls

**Rationale**: The denominator should measure search effort while avoiding retry inflation. A request counts when it is a valid analytical request that varies the analytical question and reaches data or evidence/admissibility, including refusals. Exact retries are visible through the raw call count but deduplicated from `N`.

**Alternatives considered**: Count every raw call. Rejected because retries and repeated exports would inflate the denominator. Count only available results. Rejected because refused calls are still attempted hypotheses and can hide search effort.

## Decision: Each analytical tool declares a normalized hypothesis identity

**Rationale**: This follows the project doctrine to guide rather than enumerate. The trace layer should not hardcode a central branch for every tool forever. Each analytical tool contributes an identity made from the parameters that define the examined hypothesis.

**Alternatives considered**: Use request JSON as-is or maintain a central counting switch. Raw JSON is unstable across irrelevant ordering/default differences. A central switch invites drift whenever new tools are added.

## Decision: `K` is explicit surfaced marks, not effect-size thresholding

**Rationale**: Surfaced means selected for presentation in the answer, not statistically significant. The engine must not call results notable or significant. The agent marks surfaced calls through the session layer with a role and rationale; if no marks exist, surfaced count is unavailable.

**Alternatives considered**: Infer surfaced from effect size, available status, or final-answer text. Effect-size thresholds smuggle in significance-like judgment. Final-answer inference belongs to a future audit skill and should not become canonical.

## Decision: Ship the audit-consumer contract, not the audit skill

**Rationale**: The trace is the trustworthy input a later audit skill needs. Building interpretation and recording together would couple two concerns before the canonical record exists. This mission should retire the measurement gap first.

**Alternatives considered**: Implement the audit skill in the same mission. Rejected as broader scope and a higher risk of mixing recording with evaluation.

## Decision: Provide a single disclosure/export read path

**Rationale**: The primary use case asks for raw call count, unique hypothesis count, surfaced count or unavailable status, refusal breakdown, and stable references together. A single bounded query simplifies the MCP contract and acceptance testing.

**Alternatives considered**: Separate tools for each count and export shape. Rejected because fragmented reads make it easier for agents to omit part of the disclosure.
