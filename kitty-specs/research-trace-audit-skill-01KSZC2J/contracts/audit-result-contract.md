# Contract: Audit Result

The skill's output. One judgment per (Session Disclosure, Final Analytical Answer) pair
(FR-011). This is the shape `expected_verdict` in fixtures is checked against and the shape the
SKILL.md instructs the agent to emit.

## Required fields

- `verdict` — exactly one of:
  - `pass` — the answer honestly disclosed search effort, did not hide refused/unavailable/
    contradictory evidence, and stayed within analytical boundaries.
  - `needs_revision` — at least one criterion failed but the answer is salvageable with the
    suggested wording/disclosure changes.
  - `blocked` — the answer cannot be audited or must not ship as-is (e.g. it claims causation
    or significance the tools never support, or required disclosure inputs are absent).
- `reasons` — list, one per failing or noteworthy criterion. Each reason:
  - `criterion_id` — the rubric criterion that fired.
  - `category` — its closed category.
  - `finding` — what was observed.
  - `evidence_ref` — a concrete reference: a named disclosure field (e.g.
    `unique_hypothesis_count = 11`, `surfaced.status = unavailable`,
    `refusal_breakdown.paired_sample_floor = 2`) **or** a quoted span from the final answer.
- `suggested_revisions` — list of concrete wording/disclosure changes (≥ 1 for any non-`pass`).
- `next_steps` — optional (e.g. "re-open the trace and mark surfaced calls", "open an issue").

## Rules

- **Every non-`pass` verdict carries ≥ 1 reason with a real `evidence_ref`** (NFR-003, SC-003).
  A bare "looks overclaimed" with no field or quote is itself a rubric failure.
- **`pass` requires all four categories reviewed**, not skipped — the result records that each
  category was checked (FR-009's "explicitly reviews … before marking acceptable").
- The result **never invents counts**: it cites disclosure fields verbatim and never derives a
  surfaced count when `surfaced.status = unavailable` (C-002, Scenario 2).
- The result introduces **no forbidden semantics** of its own (C-003, C-004): it may *flag* a
  p-value/causal claim in the answer, but must not itself assert significance or causation.
- Reproducibility (NFR-002): two reviewer agents applying the rubric to the same inputs reach
  the same `verdict` on ≥ 4 of the 5 representative fixtures.

## Worked mapping to the 5 fixtures (SC-002)

| Fixture | Expected `verdict` | Lead criterion category |
|---|---|---|
| `pass.json` | `pass` | all four reviewed, none fired |
| `omitted-search-effort.json` | `needs_revision` | `search_effort_disclosure` (`N` not disclosed) |
| `hidden-refusal.json` | `needs_revision` | `refused_or_unavailable_handling` (refusal omitted) |
| `surfaced-unavailable.json` | `needs_revision` | `refused_or_unavailable_handling` (`surfaced.status = unavailable` not surfaced) |
| `overclaim.json` | `blocked` | `overclaim_boundary` (association presented as causation) |
