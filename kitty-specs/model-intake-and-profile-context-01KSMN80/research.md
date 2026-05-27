# Research: Model Intake And Profile Context

No unresolved planning unknowns remain. This file records the design decisions
that the implementation plan will treat as fixed.

## Decision 1 — Keep storage agnostic, but make semantics strict

- **Decision**: Do not choose a concrete warehouse layout in this mission.
  Instead, define a strict contract for what profile context, nutrition intake,
  and supplement intake mean.
- **Rationale**: The main risk is not storage flexibility; it is semantic drift.
  Prematurely choosing tables or columns would make later agents route around the
  plan if the shape blocks their task. A strict semantic contract avoids that
  provocation while still preventing ad-hoc meanings.
- **Alternatives considered**:
  - Choose a concrete DuckDB schema now — rejected because it would settle the
    adapter before the port and would create avoidable migration pressure.
  - Leave both storage and semantics open — rejected because agent-reviewed PRs
    would quickly fork the meaning of profile, intake, and dose.

## Decision 2 — Put strictness at the contract boundary, not in storage

- **Decision**: Treat the strict boundary as the stable contract consumers depend
  on: canonical entity shapes, required fields, dependency declarations, and
  invariants. Storage remains an adapter concern.
- **Rationale**: This is the ports/adapters split that makes the plan useful for
  agent-heavy work. The contract is stable and reviewable; the persistence shape
  can evolve as long as it still satisfies that contract.
- **Alternatives considered**:
  - Rely on prose definitions alone — rejected because two agents could both
    claim compliance while encoding incompatible shapes.
  - Make the warehouse schema itself the contract — rejected because it makes the
    most change-prone layer the least adaptable.

## Decision 3 — Review by positive invariants first, forbidden shortcuts second

- **Decision**: Lead the contract with a small set of positive invariants, then
  attach forbidden shortcuts as concrete examples of what violating each
  invariant would look like.
- **Rationale**: Forbidden-shortcut lists are open-ended; they only catch the
  cases we predicted. Positive invariants are broader and give reviewers a more
  durable basis for rejecting novel drift.
- **Alternatives considered**:
  - Only publish a forbidden-shortcuts list — rejected because it degenerates
    back into taste and misses off-list improvisations.
  - Only publish entity definitions — rejected because definitions without
    invariants do not tell reviewers what must never be broken.

## Decision 4 — Agent review requires machine-applicable gates

- **Decision**: Represent the Phase 1 contract in versioned artifacts that later
  implementations can validate mechanically, and require tests or checks for the
  load-bearing invariants.
- **Rationale**: The expected first-pass reviewers are agents. A prose-only rule
  is too weak: it creates review argument instead of a pass/fail gate. Even if
  some invariants remain partly human-reviewed, the important ones must map to a
  detectable signal.
- **Alternatives considered**:
  - Human-review prose only — rejected because it does not materially reduce
    agent drift.
  - Full storage-schema enforcement now — rejected because it over-corrects by
    freezing the adapter rather than checking the contract.

## Decision 5 — No API contract is generated for this mission

- **Decision**: The planning artifacts under `contracts/` are domain contracts,
  not REST or GraphQL endpoints.
- **Rationale**: This mission defines a canonical data boundary, not a new user
  action surface. The useful contract here is entity/invariant/dependency shape,
  not transport.
- **Alternatives considered**:
  - Invent placeholder endpoints — rejected because that would be false
    specificity and leak implementation detail into a storage-agnostic mission.
