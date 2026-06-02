---
work_package_id: WP05
title: Deterministic grader
dependencies:
- WP01
- WP02
- WP04
requirement_refs:
- FR-060
- FR-061
- FR-062
- FR-063
- FR-064
- FR-065
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T018
- T019
- T020
- T021
agent: "claude:opus:python-reviewer:reviewer"
shell_pid: "68053"
history:
- timestamp: '2026-06-02T13:00:02Z'
  actor: tasks
  action: created
authoritative_surface: src/premura/harness/grader.py
execution_mode: code_change
owned_files:
- src/premura/harness/grader.py
- tests/test_grader.py
tags: []
---

# WP05 — Deterministic grader

## Objective

Build the **deterministic auto-grader**: it reads the session-log
provenance + the disposable sandbox warehouse + the committed fixture manifest and
**recomputes** three rules, returning a byte-stable verdict. It must **never trust
a precomputed boolean** for a rule it could check itself (FR-061), and it writes
its recomputed runtime-subset result back as `contract_pass` (FR-065). The verdict
excludes ids/timestamps so it is byte-identical across runs (D5; NFR-001 is proven
in WP06, but the verdict's determinism property lives here).

Read first: `contracts/grader-verdict.schema.json`,
`contracts/runtime-contract-check.md`, `data-model.md` (verdict + reconciliation
D6), spec §"Pass" (the source-of-truth table).

## Context / grounding

- `check_runtime_contract(...)` from WP02 (pure fn over captured evidence + a
  warehouse conn).
- The fixture manifest from WP04 (`fixture_fields.yaml`) is **ground truth**: each
  source field has `canonical_metric` (a distinct metric_id) or `null`.
- The session-log provenance row (WP01) supplies captured `declared_metrics`,
  `emitted_metric_ids`, `unmapped_metrics`, `skipped_rows`, loader counts.
- "Boundary truth" = the sandbox warehouse contents (row counts; which metrics are
  present in `hp.fact_*`/observations).

## Subtasks

### T018 — verdict structure + `loaded` rule

**Steps** — `src/premura/harness/grader.py`:
- Define the verdict shape per `grader-verdict.schema.json` (a dataclass with an
  `as_dict()` producing sorted lists and **no** ids/timestamps), or return a plain
  dict — either way it must serialize deterministically.
- `grade(*, provenance, warehouse_conn, fixture_manifest) -> Verdict` where
  `provenance` is the captured ingest-provenance (declared/emitted/unmapped/
  skipped + loader counts) — passed in, not re-read with trust.
- `loaded` rule (FR-062): query the sandbox warehouse for the loaded row count for
  the run's metrics; `passed = warehouse_rows > 0 and warehouse_rows ==
  logged_rows_inserted` (consistency). Record `warehouse_rows`,
  `logged_rows_inserted`.

### T019 — `runtime_valid` rule

**Steps** (FR-063):
- Call `check_runtime_contract(declared_metrics=..., emitted_metric_ids=...,
  warehouse_conn=..., ingest_run_ok=...)` using the **captured** sets (so the
  grader recomputes "declared = emitted", "no derived", "declared in dim_metric",
  "produced batch") rather than trusting any stored flag.
- `runtime_valid.passed = result.runtime_valid`; `violations = result.violations`.
- The grader writes this back as `contract_pass` (FR-065) — document that the
  caller (WP06/WP07) persists it via `record_ingest_provenance(contract_pass=...)`;
  the grader is the **only** producer of that value.

### T020 — `honest_about_gaps` reconciliation

**Steps** (FR-064; D6) — the genuinely-measured honesty check:
- Load the fixture manifest's complete `source_fields`.
- For each field F:
  - if `F.canonical_metric` is set → **handled** iff (that metric is **present in
    the sandbox warehouse**) **or** (F.name in `unmapped_metrics`/`skipped_rows`);
  - if `F.canonical_metric` is null → **handled** iff (F.name in
    `unmapped_metrics`/`skipped_rows`);
  - else → **silent drop**.
- `silent_drops = sorted(unhandled field names)`; `passed = not silent_drops`.
- "metric present in warehouse" is a query against `warehouse_conn` (boundary
  truth), **not** the parser's emitted list — so a parser lying about emission is
  still caught.

### T021 — grader tests

**Steps** — `tests/test_grader.py` (test-first). Build the evidence by actually
running the WP04 reference parsers into an `empty_warehouse` (or a sandbox
warehouse) so the warehouse contents are real boundary truth:
- `test_good_parser_passes`: good reference parser loaded → all three rules pass,
  `passed True`, `silent_drops == []`.
- `test_dishonest_parser_fails_honesty`: dishonest parser → `honest_about_gaps`
  fails with `silent_drops == ["altitude_m"]`, overall `passed False` — **even
  though** the parser's own `unmapped_metrics` claim looks clean (NFR-006: verdict
  contradicts self-report).
- `test_loaded_rule_consistency`: tamper logged `rows_inserted` ≠ warehouse rows →
  `loaded` fails.
- `test_runtime_valid_uses_recompute`: craft declared≠emitted captured sets →
  `runtime_valid` fails regardless of any stored flag.
- `test_verdict_excludes_ids_and_timestamps`: serialize two verdicts from
  independent runs (different ids/timestamps upstream) → identical bytes (D5).

## Definition of Done

- [ ] `grade()` recomputes all three rules from ground truth + captured evidence;
      no rule trusts a precomputed boolean (FR-061).
- [ ] `honest_about_gaps` uses the fixture manifest + warehouse contents, catching
      the dishonest parser's silent drop (NFR-006/NFR-007).
- [ ] Verdict serialization is deterministic (sorted, no ids/timestamps).
- [ ] `tests/test_grader.py` green.
- [ ] `ruff` (check+format), `mypy src/premura/harness/grader.py`, `pytest -q
      tests/test_grader.py` green.

## Risks / reviewer guidance

- **R3 (plan)**: the "metric present" check can be fooled if two source fields map
  to the same metric — WP04's distinct-metric constraint prevents it; reviewer
  confirms the grader relies on that and does not silently coalesce.
- Reviewer: the decisive test is `test_dishonest_parser_fails_honesty` — confirm
  the parser's `unmapped_metrics` claim is "clean" yet the verdict still FAILs
  (this is the whole point of the slice).
- `contract_pass` must be produced **only** here, then persisted by the caller.

## Implementation command

```bash
spec-kitty agent action implement WP05 --agent <name>
```

## Activity Log

- 2026-06-02T13:56:45Z – claude:opus:python-implementer:implementer – shell_pid=62198 – Started implementation via action command
- 2026-06-02T14:01:39Z – claude:opus:python-implementer:implementer – shell_pid=62198 – Ready for review: deterministic three-rule grader recomputing loaded/runtime_valid/honest_about_gaps from warehouse+manifest+captured sets; verdict validates against grader-verdict.schema.json; catches dishonest altitude_m drop
- 2026-06-02T14:02:21Z – claude:opus:python-reviewer:reviewer – shell_pid=68053 – Started review via action command
- 2026-06-02T14:04:38Z – claude:opus:python-reviewer:reviewer – shell_pid=68053 – Review passed: all 3 rules recompute from ground truth, none reads a parser self-report. loaded=SELECT COUNT over hp.fact_* cross-checked vs logged rows_inserted; runtime_valid delegates to WP02 check_runtime_contract over captured declared/emitted+live dim_metric (no stored flag); honest_about_gaps queries SELECT DISTINCT metric_id from warehouse for presence, reconciled against fixture_fields.yaml. Dishonest parser caught: silent_drops==[altitude_m], passed==False while its unmapped_metrics stays clean. Schema validated via jsonschema.validate against the file for both PASS and FAIL verdicts; runtime_valid bool->passed mapping correct. Determinism test uses two independent ingests (fresh sandbox+subprocess each) yielding byte-identical json.dumps. Verdict carries no ids/timestamps, arrays sorted. Gates green: ruff check+format, mypy clean, 7/7 pytest.
