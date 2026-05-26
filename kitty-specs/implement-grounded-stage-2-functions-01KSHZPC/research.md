# Phase 0 Research - Implement Grounded Stage 2 Functions

## Decision 1: Stage 3 exposure pattern

**Decision**: Keep the existing raw warehouse MCP tools and add six new explicit Stage 3 tools backed by Stage 2 for the approved question shapes.

**Rationale**:

- The current Stage 3 surface does not already contain user-facing tools for these six answers.
- Replacing `query_warehouse`, `list_metrics`, or `metric_summary` would widen scope and break existing Stage 3 utility behavior without closing more of the documented debt.
- New signal-backed tools let the mission reduce direct-read debt exactly where the research intended while preserving current exploratory capabilities.

**Alternatives considered**:

- Replace the raw tools entirely: rejected because the current raw tools still support exploratory workflows outside this mission's scope.
- Hide the new answers behind `query_warehouse`: rejected because it would keep the user-facing contract raw-table-centric and would not encode freshness or caveat semantics.

## Decision 2: Engine seam hardening approach

**Decision**: Keep `SignalSpec` core identity and execution fields, but add minimal contributor-facing metadata and standard result envelopes, plus an engine-side contract doc.

**Rationale**:

- The research explicitly said the existing seam mostly survives, and only the contributor surface needs to grow beyond a bare registration record.
- An additive change keeps locality of change high and lets future contributors extend the system through the current registry model instead of a redesigned plugin system.
- Standard result envelopes reduce ambiguity for both Stage 3 tool wrappers and future PR authors.

**Alternatives considered**:

- Docs-only contract with no code seam change: rejected because the user wants future agents to extend the app more easily in practice, not just on paper.
- A separate external manifest or plugin loader: rejected because it adds architectural weight without helping the six approved functions land sooner.

## Decision 3: Result-shape standardization

**Decision**: Define four shared result families for this mission: status, trend, own-baseline comparison, and change-around-date.

**Rationale**:

- The six approved functions already cluster into those four families.
- Shared result families let MCP tools serialize responses consistently and make tests easier to write against public contracts.
- This matches the research taxonomy without taking on the still-unshipped signal selector.

**Alternatives considered**:

- Let each function invent its own ad-hoc response shape: rejected because it would make Stage 3 exposure and future agent-contributed PRs harder to review.
- Force all functions into one generic result object: rejected because the fields needed for a trend or before/after comparison are meaningfully different from a current-status answer.

## Decision 4: Built-in signal layout

**Decision**: Keep lazy engine loading, but expand built-in signal registration beyond `lab_ratios.py` into modules grouped by signal family or closely related domains.

**Rationale**:

- The current engine import surface already guarantees a lazy registry boundary.
- Grouping the six new functions by family keeps code reviewable and future additions local.
- This is the smallest extension of the current design.

**Alternatives considered**:

- Put all six functions into `lab_ratios.py`: rejected because the file would stop matching its purpose.
- Auto-discover all modules at import time: rejected because it weakens the current open-boundary and lazy-load posture.

## Decision 5: Testing strategy

**Decision**: Use test-first delivery through public engine helpers and public MCP tool calls, with temporary DuckDB fixtures for each success and failure path.

**Rationale**:

- The charter requires test-first loops and public-interface assertions.
- Existing test coverage already proves this repo can validate engine and MCP behavior using temporary DuckDB warehouses.
- The six new functions are health-data behavior, so fixture-backed tests are required anyway.

**Alternatives considered**:

- Mock-heavy internal unit tests: rejected because they violate the repo's black-box testing direction.
- Only end-to-end MCP tests: rejected because engine-level public helpers still need focused validation to keep feedback loops short.

## Decision 6: Profile-precondition support

**Decision**: Do not implement profile-precondition handling in code in this mission.

**Rationale**:

- None of the six approved functions require stable profile context.
- The research and spec both keep issue `#6` explicitly out of scope.
- A partial profile-precondition mechanism would risk smuggling issue `#6` into this mission without resolving the model properly.

**Alternatives considered**:

- Add placeholder profile fields now: rejected because it would create an implied storage decision before the issue is resolved.
- Back-door profile data through existing measurement rows: rejected by the research findings and the charter's trust requirements.
