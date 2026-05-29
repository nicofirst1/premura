# Research: Stage 2 Evidence Admissibility Foundation

## Decision: Use a frozen-dataclass policy registry, not YAML declarations

**Rationale**: There will be no domain or medical reviewer reading policy source files directly. The strongest argument for YAML would be direct non-engineer review of the declaration artifact. Without that reviewer, the repository's existing Stage 2 pattern is stronger: typed Python dataclasses and enums define contracts in `_results.py` and `_resolution.py`.

The policy layer should still be declarative. Future agents should add bounded policy declarations, not freehand logic. Those declarations can be frozen dataclass instances validated at construction and registration time.

**Alternatives considered**:

- YAML declarations loaded into dataclasses: rejected because it adds a mapping layer without a direct human reviewer benefit.
- YAML-only policy files: rejected because it risks schema drift and would still need validation code.
- Arbitrary Python policy functions: rejected because it lets agents hide logic in one-off branches.

## Decision: Keep PubMed MCP outside Stage 2 runtime

**Rationale**: Stage 2 must remain local, deterministic, and warehouse-only. PubMed MCP is useful for agents doing research while authoring or reviewing policy declarations, but runtime policy evaluation must not depend on network access or external literature calls.

The policy declaration may carry rationale text or source notes, but the evaluator only uses local candidate evidence and declaration parameters.

**Alternatives considered**:

- Calling PubMed from Stage 2: rejected because it violates the local deterministic boundary.
- Deferring PubMed entirely: rejected as unnecessary; agents can still use PubMed during planning/review.

## Decision: Key policies by metric family with per-question modifiers

**Rationale**: A full `(metric_family, question_type)` matrix would duplicate declarations and invite drift. Family-level declarations let Premura express one temporal meaning and evidence basis, then specify how that family behaves for each question type.

This matches the design-altitude charter rule: guide agents with a bounded abstraction instead of hardcoding an exhaustive table.

**Alternatives considered**:

- One declaration per `(family, question_type)`: rejected as too duplicative.
- One global policy for all families: rejected as too vague and unsafe.

## Decision: Keep declarations parameters-only

**Rationale**: Banning arbitrary Python is not enough. A declarative layer can still decay into a mini-language if declarations contain expressions, conditionals, or operators. Policy declarations should contain only closed enum values, windows, thresholds, required fields, caveats, refusal modes, examples, and source notes.

The evaluator owns all branching.

**Alternatives considered**:

- Embedded expressions in declarations: rejected because it hides logic in data.
- A general policy engine: rejected as overbuilt for this foundation.

## Decision: Use lightweight validation

**Rationale**: The foundation needs early failure for incomplete or incoherent declarations, but not a heavyweight schema framework. Frozen dataclasses can validate required fields, enum consistency, and example expectations in `__post_init__` or a registration helper.

**Alternatives considered**:

- A JSON Schema or OPA-like validation layer: rejected as too heavy for current repo conventions.
- Prose-only validation through reviewer checklist: rejected because agents need machine-checkable guardrails.

## Decision: Use representative policy shapes plus broad family assignment

**Rationale**: The spec requires coverage for at least 10 metric families or family groups. That should not mean 10 bespoke rule implementations. The foundation should define a smaller number of reusable evidence-rule shapes and assign at least 10 families to those shapes.

**Alternatives considered**:

- Exhaustive per-metric coverage: rejected because it over-enumerates and will age poorly.
- Only two or three examples: rejected because it does not meet the spec acceptance bar.

## Research Sources

- `docs/history/research/STAGE2_EVIDENCE_ADMISSIBILITY_RESEARCH.md`
- `docs/history/research/AGENT_POLICY_ABSTRACTION_RESEARCH.md`
- `docs/architecture/STAGES.md`
- `src/premura/engine/CONTRACT.md`
- `.kittify/charter/charter.md`
