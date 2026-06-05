# Contract — `Scenario` and the registry

> The bounded abstraction the mission introduces (FR-001). A new acceptance source is
> added by **registering a scenario**, with **no change to the shared grading logic**.

## A scenario is

`Scenario(name, source_path, manifest_path, reference_parser, strategy)` — frozen.

- `name` is unique within the registry.
- `source_path` is a synthetic, obviously-fake artifact (no PHI, NFR-004).
- `manifest_path` is **grader-only** ground truth; it MUST NOT appear on any
  operator-visible path (prompt or sandbox tree) — C-005.
- `reference_parser` is the layer-1 known-good parser import target.
- `strategy` is a `DrawerGradingStrategy` (see drawer-grading-contract.md).

## Registry guarantees

- The registry exposes ≥ 2 scenarios: the existing observation source and the new
  intake source (NFR-006 / SC-003).
- Registering a scenario is the **only** edit required to add a source. The shared
  grade path MUST NOT name a drawer, a table, or a scenario (NFR-005). This is asserted
  structurally by `test_scenario_no_fork.py`.

## What a scenario MUST NOT do

- It MUST NOT carry, or make reachable, the ground-truth mapping to the operator
  (C-005).
- It MUST NOT introduce a parallel grader or a second copy of the sandbox / runner /
  store / scoreboard layers (NFR-005). It reuses them.

## Failure clause (testable)

If adding a hypothetical third scenario would require editing the shared grade
orchestration (not just registering a `Scenario`), the abstraction has failed FR-001.
