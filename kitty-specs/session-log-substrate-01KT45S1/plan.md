# Implementation Plan: Session Log Substrate (Slice One)

**Branch**: `master` (base + merge target) | **Date**: 2026-06-02 | **Spec**: [spec.md](spec.md)
**Input**: Feature specification from `kitty-specs/session-log-substrate-01KT45S1/spec.md`

**Branch contract**: Current branch at plan start `master`; planning/base branch
`master`; final merge target `master`; `branch_matches_target = true`.

## Summary

Build slice one of the loggable/testable/auditable **session log**: a separate
local DuckDB file (OTel GenAI shape, hand-written — ADR 0011) recording every
step of an operating run plus two-origin ingest provenance; a **sandbox** (full
temp copy of the tracked tree) with an in-sandbox subprocess **ingest runner**; a
**harness** that is the sole writer of the log; a minimal **runtime contract
checker**; a **deterministic grader** that recomputes three rules
(loaded / runtime-valid / honest-about-gaps) from ground truth (sandbox warehouse
+ committed synthetic fixture) and never trusts parser self-report; a **repeatable
check** (fake scripted agent installing committed good + dishonest reference
parsers) wired into CI; and a **live-trial seam** (Driver/Operator protocols +
Fitbit config) with model wiring deferred. The mission also carries the FR-130
doctrine update (runtime build-and-use parser boundary).

Approach is grounded in the existing code seams: `premura.trace`
(connection-agnostic, hand-written DuckDB rows), `store/loader.py` (`LoadStats`,
`validate_batch_against_warehouse`), `parsers/base.py` (`IngestBatch`, the
`derived:` raise at `base.py:387`), and the `tmp_path`/`duck.initialize` test
idiom. Design decisions and rejected alternatives: [research.md](research.md).

## Technical Context

**Language/Version**: Python 3.11+ (single language; charter-mandated stack).
**Primary Dependencies**: DuckDB ≥1.1, python-ulid, polars (parse), pydantic-settings
(config) — all already in the project. **No new runtime dependency** (NFR-003).
**Storage**: the session log's **own** local DuckDB file, separate from
`health.duckdb` and from `trace.*` (ADR 0011 / D1). Idempotent `CREATE IF NOT
EXISTS` DDL applied by the package's own `init_schema()`, not the warehouse
migration runner.
**Testing**: pytest, test-first (DIRECTIVE_034), black-box through public
interfaces asserting observable outputs — DuckDB row counts in the log file, the
returned verdict, raised exceptions, file bytes (DIRECTIVE_036). `tmp_path` for
sandboxes; outside-boundary substitutes (config paths, subprocess runner, fake
operator) are permitted.
**Target Platform**: macOS / Linux local; offline-capable (NFR-002).
**Project Type**: single project (library + harness; no frontend).
**Performance Goals**: the repeatable check completes well within a normal unit
suite (target < a few seconds/run); no hard NFR beyond determinism.
**Constraints**: deterministic byte-identical verdict (NFR-001); zero new deps
and zero network (NFR-002/003); PHI containment — log local-only, sandboxes torn
down, no real data committed (NFR-004, C-003); single-writer log (NFR-008);
no graded rule trusts self-report (NFR-006).
**Scale/Scope**: one bounded flow (parser build for one Fitbit category);
~6 small modules + fixtures + doc edits.

## Charter Check

*GATE: must pass before Phase 0. Re-checked after Phase 1 (below).*

| Gate (charter) | Status | How this plan satisfies it |
| --- | --- | --- |
| **Test-first, no horizontal slicing** (DIRECTIVE_034) | PASS | Each WP writes a failing test before production code; vertical slices (one capability + its test), enumerated in Phasing. |
| **Black-box via public interfaces** (DIRECTIVE_036) | PASS | Tests assert on session-log DuckDB rows, the verdict object, raised exceptions, file bytes — never patch inside-boundary collaborators. Sandbox uses config-path + subprocess substitutes (permitted). |
| **Quality gates: ruff+mypy+pytest green** | PASS | Quickstart lists the commands; gates run per WP for changed scope; type hints on public fns. |
| **Modularity / smallest diff** (DIRECTIVE_024) | PASS | New code is additive: `session_log/`, `parsers/contract_check.py`, `harness/`; existing seams untouched except the additive config path and FR-130 doc edits. |
| **PHI hygiene; no PHI in logs/tests/commits** | PASS | Fixture is synthetic (public structure, made-up values). Real Fitbit data is live-trial-only, local, never committed. The log is PHI-bearing by design but local-only and, in this slice, only ever a throwaway sandbox file. |
| **Risk boundaries** (esp. #2 offline, #4 human-on-the-loop, #5 PHI) | PASS | Runs fully offline; FR-130 keeps PR-back as the human-approved external action (boundary #4); build-and-use is internal autonomous work. |
| **Design altitude — guide, don't enumerate** (DIRECTIVE_010/altitude) | PASS | Capture is one rule (every step recorded); step shape is a named external standard (OTel GenAI); fixtures derive from a rule, not a per-vendor list; grader rules are rubric clauses, not a metric whitelist. |
| **Fidelity gates** | PASS (planned) | NFR/SC → WP ownership table below; acceptance fixtures cross the production boundary (real ingest into a real DuckDB file) and test presence vs absence (good vs dishonest parser); live-doc sync WP included; FR-130 deferral of live-trial model wiring is a **named follow-up**, not a silent waiver (D4). |

No charter amendment required: FR-130 aligns with risk-boundary #4 and is
human-approved in-conversation; it is not a charter risk-boundary change.

## Project Structure

### Documentation (this feature)

```
kitty-specs/session-log-substrate-01KT45S1/
├── plan.md            # this file
├── research.md        # Phase 0 — decisions D1–D7
├── data-model.md      # Phase 1 — tables + in-memory contracts
├── quickstart.md      # Phase 1 — how to run the check / gates / trial
├── contracts/         # Phase 1 — interface seams + JSON schemas
└── tasks.md           # Phase 2 — NOT created here (/spec-kitty.tasks)
```

### Source Code (repository root)

```
src/premura/
├── config.py                      # + session_log_path property (additive)
├── session_log/
│   ├── __init__.py
│   ├── schema.sql                 # log_session, log_step, log_ingest_provenance (own file)
│   └── store.py                   # connect / init_schema / writer fns (sole-writer surface)
├── parsers/
│   └── contract_check.py          # NEW minimal runtime-valid checker (pure fn)
└── harness/
    ├── __init__.py
    ├── sandbox.py                 # full temp copy of tracked tree; temp warehouse+log paths; teardown
    ├── ingest_runner.py           # runs INSIDE sandbox (subprocess); emits JSON outcome envelope
    ├── grader.py                  # deterministic 3-rule verdict (recompute, never trust)
    ├── repeatable_check.py        # fake scripted agent: install reference parser, run, write log, grade
    └── live_trial.py              # Driver/Operator protocols + LiveTrialConfig (model wiring deferred)

tests/
├── fixtures/session_log/
│   ├── fitbit_heart_rate_synthetic.csv
│   ├── fixture_fields.yaml        # ground-truth complete source-field set (D6)
│   └── parsers/
│       ├── good_fitbit_hr.py      # passes all 3 rules
│       └── dishonest_fitbit_hr.py # silently drops a field → must FAIL
├── test_session_log_store.py
├── test_contract_check.py
├── test_sandbox.py
├── test_grader.py
├── test_repeatable_check.py
└── test_live_trial_seam.py

docs/  (FR-130 + doc sync)
├── building/planning/operating-agent-roles.md   # replace review-before-use sentence
├── building/adr/0010-...                          # adjust "separate from codebase extension" line
├── shared/DOCTRINE.md                             # clarifying build-and-use line
└── shared/STATUS.md (+ ROADMAP if owned)          # live-doc sync
```

**Structure Decision**: single-project library layout. The harness lives under
`src/premura/harness/` (product code, importable by tests) rather than under
`tests/` so the live trial can reuse it at runtime later. The session log is its
own package with its own file/schema (never a warehouse migration). Reference
parsers + fixture live under `tests/fixtures/` (installed into sandboxes only;
**not** shipped production parsers — preserving Fitbit as a genuinely unsupported
target).

## NFR / Success-Criteria ownership (fidelity gate)

Every measurable requirement must be owned by a WP with a committed evidence
artifact (assigned concretely at `/spec-kitty.tasks`). Provisional map:

| Req | Evidence artifact | Likely WP |
| --- | --- | --- |
| NFR-001 byte-identical verdict | `test_repeatable_check.py::test_verdict_stable_across_runs` | repeatable-check WP |
| NFR-002 clean-clone offline | repeatable check runs with no network/private data | repeatable-check WP |
| NFR-003 zero new deps | `pyproject.toml` unchanged deps + import audit test | session-log WP |
| NFR-004 PHI containment | test: no export/sync path; sandbox teardown removes files | sandbox WP |
| NFR-005 live trial never blocks | live trial not referenced by any CI/pytest default gate | live-trial-seam WP |
| NFR-006 no self-report trust | `test_grader.py::test_dishonest_parser_fails` (claim says fine, verdict fails) | grader WP |
| NFR-007 silent-drop detection | `test_grader.py` over `dishonest_fitbit_hr` | grader + fixtures WP |
| NFR-008 single-writer | `test_session_log_store.py::test_single_writer` | session-log WP |
| SC-001..SC-006 | covered by the above + quickstart end-to-end | repeatable-check WP |
| SC-007 docs consistent | grep/test asserting no review-before-use sentence remains | doctrine-docs WP |

## Phasing sketch (WP breakdown happens at /spec-kitty.tasks)

Vertical, test-first slices, dependency-ordered:

1. **Session-log store** — `session_log/` (schema + writers) + `config.session_log_path`. Tests: row capture, single-writer, status/run_kind vocab.
2. **Runtime contract checker** — `parsers/contract_check.py`. Tests: each clause pass/fail from captured evidence.
3. **Sandbox + ingest runner** — `harness/sandbox.py`, `harness/ingest_runner.py`. Tests: temp copy built from tracked tree, runner emits valid envelope, teardown.
4. **Fixtures** — synthetic CSV + `fixture_fields.yaml` + good/dishonest reference parsers. Tests: fixture manifest matches CSV header; each reference parser behaves as labeled.
5. **Grader** — `harness/grader.py` (3 rules, deterministic). Tests: good→PASS, dishonest→FAIL with `silent_drops`, verdict excludes ids/timestamps.
6. **Repeatable check** — `harness/repeatable_check.py` wiring 1–5 end-to-end. Tests: full PASS + FAIL paths, byte-identical verdict across runs (CI gate-able).
7. **Live-trial seam** — `harness/live_trial.py` protocols + config; fake-operator test; model wiring deferred (named follow-up).
8. **Doctrine docs + live-doc sync (FR-130)** — edit operating-agent-roles.md, ADR 0010, DOCTRINE.md; sync STATUS/ROADMAP. Test/grep asserting SC-007.

## Complexity Tracking

No charter violations to justify. One scope refinement (not a violation):

| Item | Why | Handling |
| --- | --- | --- |
| Live-trial model wiring deferred (D4) | Keeps a foundational slice small and deterministic; live trial never blocks (NFR-005) | Named follow-up recorded here + in `contracts/live-trial-seam.md`; SC-005 refined (seam exercised by a fake operator) — explicit, not a silent waiver (DIRECTIVE_010). |

## Risks (must resolve to a task / non-goal / acceptance check before WP approval)

- **R1 — Determinism leak.** Ids/timestamps in the log are nondeterministic; if
  the verdict accidentally embeds them, NFR-001 fails. → Mitigation: verdict
  schema excludes ids/timestamps (D5); owned by `test_verdict_stable_across_runs`.
- **R2 — Sandbox copy heft/flakiness.** Copying the tree per run could be slow or
  pick up junk. → Mitigation: copy only `git ls-files` tracked paths, exclude
  `data/`,`.venv`,`.git`,`kitty-specs/`,`.worktrees/`; owned by `test_sandbox.py`.
- **R3 — Honesty rule false-confidence if two fields share a metric.** → Mitigation:
  fixture-authoring constraint — distinct `canonical_metric` per mappable field
  (D6); owned by the fixtures WP test.
- **R4 — Subprocess runner contract drift.** Envelope shape must match what the
  harness expects. → Mitigation: JSON-schema-validated envelope
  (`contracts/ingest-outcome-envelope.schema.json`); owned by a runner test.
- **R5 — Live-trial deferral read as a waiver.** → Resolved: named follow-up +
  refined SC-005 (D4), not accepted as-is.

## Post-Phase-1 Charter Re-check

Re-evaluated after generating data-model + contracts: still PASS. The design adds
no new dependency, keeps the research trace untouched (C-002), keeps capture as a
rule with an external standard for shape (altitude), and routes every measurable
NFR/SC to an owning WP with a boundary-crossing evidence fixture. No new gate
violations introduced.
