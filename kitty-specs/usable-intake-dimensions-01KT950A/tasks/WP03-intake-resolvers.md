---
work_package_id: WP03
title: Intake resolvers (both domains)
dependencies: []
requirement_refs:
- FR-001
- FR-002
- NFR-003
- NFR-005
- NFR-006
planning_base_branch: master
merge_target_branch: master
branch_strategy: Plan/base branch master; final merge target master. Execution worktree allocated per computed lane from lanes.json.
subtasks:
- T011
- T012
- T013
- T014
- T015
- T016
history:
- 2026-06-04T11:52:07Z created by /spec-kitty.tasks
authoritative_surface: src/premura/engine/views/
execution_mode: code_change
owned_files:
- src/premura/engine/views/nutrition_intake.py
- src/premura/engine/views/supplement_intake.py
- src/premura/engine/__init__.py
- tests/test_intake_resolvers.py
tags: []
---

# WP03 — Intake resolvers (both domains)

## Objective

Turn `nutrition_intake` and `supplement_intake` from `unsupported_domain` into
**usable resolved inputs** through the existing `@resolver(domain=...)` seam,
with explicit no-fallback behavior and **no special-casing in the shared
resolution path**. Foundation of the read chain (WP04 depends on it). Satisfies
**FR-001, FR-002, NFR-003, NFR-005**, and the resolver half of **NFR-006**.

## Context (use the shipped seam; do not invent one)

- The seam: `@resolver(domain=...)` from `src/premura/engine/_registry.py`;
  `resolve_dependency(...)` and `SEMANTIC_DOMAINS` (which already lists both
  intake domains) in `src/premura/engine/_resolution.py`.
- **Template to copy**: `src/premura/engine/views/profile.py` and
  `observation.py` — they register via the decorator and return a `ResolvedInput`
  with `usable` / `absence_reason` / `message`, with **no hidden fallback** into
  another domain.
- Registration: append the two new module dotted-names to
  `_BUILTIN_RESOLVER_MODULES` in `engine/__init__.py` (currently lists only
  `views.observation` and `views.profile`). This is the only `__init__.py` edit
  in the mission — WP04's signals do **not** touch `__init__.py`.
- The intake tables your resolvers read are listed in
  [data-model.md](../data-model.md) §2; the generic payload fields are specified
  there too.

**Resolvers stay generic.** They resolve one declared key/matcher to a domain
payload + honest availability context. They do **not** compute trend direction or
adherence verdicts — that is WP04's job. (BMI is the precedent: resolver supplies
declared inputs; signal owns the answer.)

## Subtasks

### T011 — `nutrition_intake` resolver (`engine/views/nutrition_intake.py`)
- `@resolver(domain="nutrition_intake")`.
- Returns the generic payload from data-model §2: `matched_key`, `window_days`,
  ordered daily `points`, `days_with_data`, `window_day_count`, `latest_logged_at`,
  `freshness_state`, `day_basis`.
- **Day basis**: when the intake event carries `local_tz`, bucket by **local
  calendar day**; otherwise fall back to naive-UTC day and set `day_basis`
  accordingly. Never silently mix bases.

### T012 — `supplement_intake` resolver (`engine/views/supplement_intake.py`)
- `@resolver(domain="supplement_intake")`.
- Caller-declared **matcher** over product/ingredient identity (not a hardcoded
  supplement list — C-007).
- Returns: `matcher`, `window_days`, `logged_days`, `logged_day_count`,
  `window_day_count`, `latest_logged_at`, `freshness_state`, `day_basis`.

### T013 — Register both modules
- Append `premura.engine.views.nutrition_intake` and
  `premura.engine.views.supplement_intake` to `_BUILTIN_RESOLVER_MODULES`.

### T014 — No-fallback regression (NFR-003)
- A declared intake dependency with no matching intake row resolves to an
  explicit non-usable outcome.
- **Key test**: a same-named *observation* row (e.g. an observation that happens
  to share a key) never satisfies an intake dependency. Resolvers read intake
  tables only.

### T015 — Structural-generalization test (NFR-005)
- Assert the shared `resolve_dependency` path has **no per-domain branch** for the
  two intake domains — both are reached purely via the registry decorator, exactly
  like `observation_history` / `profile_context`.

### T016 — Local-midnight resolver test (NFR-006)
- Using a row whose `local_tz` puts it on a different local day than its UTC date,
  assert `day_basis == "local_calendar_day"` and that the resolved day set uses
  the **local** day, not the UTC date.

## Branch Strategy

Plan/base branch **master**; final merge target **master**. Worktree per lane in
`lanes.json`. Implement with: `spec-kitty agent action implement WP03 --agent <name>`.
No dependency — can start immediately, in parallel with WP01.

## Test Strategy (test-first)

Write `tests/test_intake_resolvers.py` first: assert `resolve_dependency(...)` for
each domain returns a usable payload for seeded rows and an honest non-usable
outcome otherwise. Seed intake rows via `persist_intake_batch(...)` (already
shipped) — this WP does **not** depend on WP01/WP02; it seeds rows directly.
Black-box through `resolve_dependency`, not resolver internals.

## Definition of Done

- [ ] Both domains resolve usable rows to the generic payload; refuse honestly when none/stale (FR-001/FR-002).
- [ ] No-fallback regression green: an observation row never satisfies an intake dependency (NFR-003).
- [ ] Structural-generalization test green: no per-domain branch in the shared seam (NFR-005).
- [ ] Local-midnight resolver test green: `day_basis = local_calendar_day`, local day used (NFR-006).
- [ ] Resolvers compute no answer semantics (no trend/adherence verdict).
- [ ] ruff + ruff format + mypy + pytest green.

## Risks

- **Resolver overfit to one signal.** Mitigation (R5): payloads stay
  domain-level/generic per data-model §2; signal-specific interpretation is WP04.
- **Hidden fallback.** Mitigation: T014 explicitly proves no observation-row
  satisfaction.

## Reviewer Guidance

- Confirm registration is the only `__init__.py` change and WP04 won't need it.
- Confirm the no-fallback and structural-generalization tests actually assert the
  invariant (not a trivially-true check).
- Confirm `day_basis` is set on every payload and the local-midnight test crosses
  the boundary.
