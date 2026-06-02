---
work_package_id: WP02
title: Runtime contract checker
dependencies: []
requirement_refs:
- FR-050
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T007
- T008
- T009
agent: "claude:opus:python-reviewer:reviewer"
shell_pid: "29012"
history:
- timestamp: '2026-06-02T13:00:02Z'
  actor: tasks
  action: created
authoritative_surface: src/premura/parsers/contract_check.py
execution_mode: code_change
owned_files:
- src/premura/parsers/contract_check.py
- tests/test_contract_check.py
tags: []
---

# WP02 — Runtime contract checker

## Objective

Build the **minimal runtime-valid checker that does not exist today** (FR-050): a
**pure function over captured evidence** so the grader can *recompute* the
runtime-valid subset of `parsers/CONTRACT.md` and never *trust* a precomputed flag
(FR-061). It computes only the **runtime tier**; the reviewer-checklist tier
(decision-tree order, fixtures, PR notes, ontology diff) is explicitly out of
scope (needs a per-field resolution map we do not capture in slice one).

Read first: `contracts/runtime-contract-check.md`, `src/premura/parsers/CONTRACT.md`
(runtime-valid list vs reviewer checklist ~line 116), and `src/premura/parsers/base.py:387`
(the existing `derived:` raise) and `src/premura/store/loader.py:112` (the
`dim_metric` existence raise) — this checker **recomputes** those facts from
captured evidence rather than relying on the loader/parser having raised.

## Context / grounding

- `base.py:387`: parsers must not emit `derived:` metrics — recompute by scanning
  the captured `emitted_metric_ids`.
- `loader.validate_batch_against_warehouse` (loader.py:112–129): raises if a
  declared metric is absent from `hp.dim_metric` — recompute by querying the
  (sandbox) warehouse `hp.dim_metric` for the declared set.
- The function takes a **warehouse connection** (the sandbox warehouse) so the
  `dim_metric` clause is checked against boundary truth, not a hardcoded list.

## Subtasks

### T007 — `ContractCheckResult` + clauses 1–2

**Purpose**: The result type and the two evidence-only clauses.

**Steps** — `src/premura/parsers/contract_check.py`:
```python
@dataclass(slots=True)
class ContractCheckResult:
    runtime_valid: bool
    violations: list[str]            # sorted "<clause>: <detail>"

def check_runtime_contract(
    *,
    declared_metrics: list[str],
    emitted_metric_ids: list[str],
    warehouse_conn: duckdb.DuckDBPyConnection,
    ingest_run_ok: bool,
) -> ContractCheckResult: ...
```
- Clause `no_derived_emitted`: any emitted id starting with `derived:` → violation
  `"no_derived_emitted: <sorted ids>"`.
- Clause `declared_equals_emitted`: `set(declared) != set(emitted)` → violation
  listing the symmetric difference (sorted).

### T008 — clauses 3–4

**Steps**:
- Clause `declared_exist_in_dim_metric`: query
  `SELECT metric_id FROM hp.dim_metric WHERE metric_id IN (...)` against
  `warehouse_conn`; any declared metric missing → violation with the sorted
  missing set. (Mirror loader.py:112–129's query shape.)
- Clause `produced_batch_without_raising`: `ingest_run_ok` is False → violation
  `"produced_batch_without_raising: ingest_run failed"`.
- `runtime_valid = not violations`; `violations` sorted for determinism.

### T009 — tests

**Steps** — `tests/test_contract_check.py` (test-first):
- `test_all_clauses_pass`: declared == emitted, no derived, all in `dim_metric`
  (seed via `empty_warehouse` fixture which loads `dim_metric`), `ingest_run_ok`
  True → `runtime_valid` True, `violations == []`.
- `test_derived_emitted_fails`: emitted includes `derived:foo` → violation present,
  `runtime_valid` False.
- `test_declared_not_equal_emitted_fails`.
- `test_declared_missing_from_dim_metric_fails`: declare a metric_id absent from
  seed `dim_metric` → violation.
- `test_ingest_run_not_ok_fails`.
- `test_violations_sorted`: deterministic ordering.

Use the existing `empty_warehouse` fixture (conftest) for `warehouse_conn` so the
`dim_metric` seed is present (boundary truth), per DIRECTIVE_036 (assert on
observable function output).

## Definition of Done

- [ ] `check_runtime_contract` implements all four clauses, recomputed from
      captured evidence + the warehouse conn; `violations` sorted.
- [ ] `tests/test_contract_check.py` green, covering each clause pass and fail.
- [ ] No reliance on the parser/loader having raised — the checker derives the
      facts itself (so the grader's verdict never rests on trust).
- [ ] `ruff` (check+format), `mypy src/premura/parsers/contract_check.py`,
      `pytest -q tests/test_contract_check.py` green.

## Risks / reviewer guidance

- Keep the function **pure** w.r.t. inputs (no global state, no file writes).
- Reviewer: confirm the `dim_metric` clause queries the passed `warehouse_conn`,
  not a module-level constant — otherwise it's enumerating, not checking
  (altitude).
- This WP does **not** compute honesty (that's the grader's reconciliation) and
  does **not** write `contract_pass` anywhere.

## Implementation command

```bash
spec-kitty agent action implement WP02 --agent <name>
```

## Activity Log

- 2026-06-02T13:22:59Z – claude:opus:python-implementer:implementer – shell_pid=25468 – Started implementation via action command
- 2026-06-02T13:25:07Z – claude:opus:python-implementer:implementer – shell_pid=25468 – Ready for review
- 2026-06-02T13:25:44Z – claude:opus:python-reviewer:reviewer – shell_pid=29012 – Started review via action command
- 2026-06-02T13:27:23Z – claude:opus:python-reviewer:reviewer – shell_pid=29012 – Review passed: signature matches contract exactly (declared_metrics, emitted_metric_ids, warehouse_conn, ingest_run_ok kw-only; ContractCheckResult{runtime_valid:bool, violations:sorted list[str]}); all 4 runtime clauses recomputed from evidence (derived: scan, set-equality, live hp.dim_metric query on passed conn mirroring loader.py:112-129, ingest_run_ok); reviewer-checklist tier correctly out of scope; violations sorted, no ids/timestamps; 6 tests = per-clause independent failing + all-clean pass, black-box; ruff/format/mypy/pytest all green; scope = only 2 owned files.
