# Improvement hook (judgment-driven improvement proposals)

> Status: spec + plan for the overnight m4 mission. Implements the
> "improvement hook" named as deferred in
> [`docs/shared/ROADMAP.md`](../../shared/ROADMAP.md) ("it *consumes* a
> judgment, nothing here acts on one"). Branch: `overnight/m4-improvement-hook`
> (from `overnight/m3-judge-ai`). Companion reading:
> [`DOCTRINE.md`](../../shared/DOCTRINE.md),
> [`src/premura/harness/JUDGE_RUBRIC.md`](../../../src/premura/harness/JUDGE_RUBRIC.md),
> ADR 0011, `docs/building/planning/judge-ai.md`.

## Why

The judge AI (m3) writes structured verdicts into `log_judgment`, but nothing
consumes them: a weak band or a failed judgment is recorded and then ignored.
The improvement hook closes that loop one step — it turns judgments into
durable, agent-readable **improvement proposals** ("the operator keeps failing
`economical-tool-use`; look at the prompt's tool guidance") so a maintainer
agent or the human can decide what to change. The hook proposes; it never acts.
It does not edit prompts, harness code, rubrics, or skills, and it never
changes a run's verdict.

## Scope (one sentence)

A deterministic, rule-based scan that reads `log_judgment` rows (plus the
rubric for criterion→category lookup), derives improvement proposals per a
versioned playbook doc, persists them to a new `log_improvement` table through
the harness's sole-writer connection, and is wired post-run behind an opt-in
flag — with no model calls, no lifecycle tooling, and no self-modification.

## Functional requirements

- **FR-1 (store surface).** `src/premura/session_log/schema.sql` gains a
  `log_improvement` table (`CREATE TABLE IF NOT EXISTS`): `improvement_id`
  VARCHAR PK (ULID), `session_id` VARCHAR NOT NULL REFERENCES
  `log_session(session_id)`, `judgment_id` VARCHAR NOT NULL REFERENCES
  `log_judgment(judgment_id)`, `created_at` TIMESTAMP NOT NULL,
  `criterion_id` VARCHAR (nullable — opaque, rubric-owned; NULL for
  judgment-level proposals), `area` VARCHAR NOT NULL (playbook-owned id),
  `summary` VARCHAR NOT NULL, `evidence` VARCHAR NOT NULL,
  `playbook_version` VARCHAR NOT NULL, `status` VARCHAR NOT NULL — plus an
  index on `session_id`. `store.py` gains `PROPOSAL_STATUSES`
  (`frozenset({"open", "dismissed", "addressed"})`) and
  `record_improvement(conn, *, ...) -> str` (returns the ULID), validating:
  status in `PROPOSAL_STATUSES`, non-empty `summary`/`evidence`/`area`,
  referenced session and judgment exist. This mission only ever writes
  `"open"`; the other statuses exist so a later lifecycle mission needs no
  schema migration.
- **FR-2 (read surface).** A read path for both judgments and proposals:
  `read_judgments(log_path, *, session_id) -> list[JudgmentRow]` and
  `read_improvements(log_path, *, session_id=None, status=None) ->
  list[ImprovementRow]`, frozen dataclass rows, strictly read-only connections
  (same discipline as `dossier.build_dossier`), ordered deterministically.
  These are the agent-facing surfaces: an agent lists open proposals through
  them, never via raw SQL.
- **FR-3 (versioned playbook).** A new
  `src/premura/harness/IMPROVEMENT_PLAYBOOK.md`, mirroring `JUDGE_RUBRIC.md`'s
  shape: a `playbook_version:` header; one **improvement area** per closed
  rubric category (`process_honesty`, `goal_adherence`, `tool_use_economy`,
  `failure_recovery`) plus two hook-owned areas: `harness_reliability`
  (triggered by non-`complete` judgment status) and `rubric_drift` (triggered
  by a judged criterion id the current rubric does not define). Each area
  entry: the category or condition it maps from, a `suggested_focus` prose
  line the proposal carries, and grounding guidance. A "Rule for adding an
  area" section (edit doc + bump version, no code/schema change) keeps the
  altitude right: code never hardcodes area semantics, only parses the
  playbook and fails loudly if it is malformed or missing required areas.
- **FR-4 (scan core).** `src/premura/harness/improvement.py` exposes
  `scan_session(log_path, *, session_id) -> list[ProposalResult]`: reads
  judgment rows via FR-2, parses the rubric (criterion→category, reusing the
  m3 rubric parser) and the playbook, and derives proposals by rule:
  judgment `status != "complete"` → one `harness_reliability` proposal;
  each criterion banded `"weak"` → one proposal in the area mapped from its
  rubric category, carrying the criterion's rationale as evidence; a judged
  criterion id absent from the current rubric → one `rubric_drift` proposal.
  Bands `strong`/`adequate`/`not_applicable` produce nothing. The scan is
  pure and deterministic: no model calls, no randomness, no clock reads
  beyond row timestamps.
- **FR-5 (idempotent persistence).** `scan_session` records each derived
  proposal via `record_improvement` with status `"open"`, skipping any
  (judgment_id, criterion_id, area) combination that already has a row —
  re-running the scan over the same judgments writes nothing new and returns
  the same proposals marked as pre-existing.
- **FR-6 (opt-in wiring).** `run_live_trial_ollama` gains
  `improve_run: bool = False`. When `judge_run` and `improve_run` are both
  set and the judge produced a judgment, the harness calls the scan post-run
  through a `_run_post_run_improvement` guard mirroring
  `_run_post_run_judge`: any exception degrades to a logged warning, the
  outcome/verdict is never altered, and a one-line count of proposals is
  logged. `improve_run` without `judge_run` is a loud `ValueError` at entry
  (the hook has nothing to consume).

## Non-functional requirements

- **NFR-1 (sole writer).** The harness remains the only writer of
  `session_log.duckdb`; all FR-2 read surfaces open read-only. Extend the
  existing single-writer test to cover the new surfaces.
- **NFR-2 (no new dependencies).** No new third-party packages
  (`test_no_new_third_party_dependency` must stay green).
- **NFR-3 (honest defaults).** Default OFF; with the flag off, byte-for-byte
  no behavioral change to existing runs. Hook failure can never fail a run.
- **NFR-4 (altitude).** Criterion ids stay rubric-owned and area semantics
  stay playbook-owned — code keys only on the closed vocabularies
  (`CRITERION_BANDS`, `JUDGMENT_STATUSES`, `PROPOSAL_STATUSES`) and on parsed
  doc structure. No `if criterion_id == ...` ladders.
- **NFR-5 (offline tests).** All tests are offline and deterministic
  (synthetic judgments written through the store API); no Ollama, no marker
  escapes into the default suite.

## Out of scope

Acting on proposals (issue/PR creation, prompt editing, any self-
modification), lifecycle tooling for `dismissed`/`addressed` transitions,
model-generated proposal prose, cross-session trend aggregation, the fixture
auto-generator, the analyze-and-answer slice, and any frontier/cloud model
requirement — all remain deferred and named in ROADMAP.md.

## Plan — work packages

- **WP1 — store + read surfaces (FR-1, FR-2, NFR-1).** Schema, vocab,
  `record_improvement`, `read_judgments`, `read_improvements`, validation
  errors; tests in `tests/test_session_log_store.py` (or a sibling module)
  covering happy path, each validation failure, read-only discipline, and the
  single-writer invariant.
- **WP2 — playbook + scan core (FR-3, FR-4, FR-5, NFR-4).**
  `IMPROVEMENT_PLAYBOOK.md`, playbook parser (loud failures), `scan_session`
  with all derivation rules and idempotent persistence; tests in
  `tests/test_improvement.py`: weak-band mapping per category, non-complete
  status, rubric-drift fallback, nothing-on-clean-judgment, re-scan
  idempotency, malformed/missing playbook fails loudly.
- **WP3 — wiring + doc sync (FR-6, NFR-3).** `improve_run` flag, guarded
  post-run call, `improve_run`-without-`judge_run` rejection; CHANGELOG entry;
  ROADMAP/STATUS updated so the improvement hook moves to shipped and the
  remaining deferred items stay named.

One Opus implementation agent builds all three WPs in order on this branch,
test-first (`/tdd`), committing at each green checkpoint; an independent Opus
reviewer then verifies FR/NFR coverage and runs all four gates (`ruff check`,
`ruff format --check`, changed-scope `mypy`, full `pytest`).

## Acceptance

On `overnight/m4-improvement-hook`: all four gates green; a synthetic
end-to-end test proves judgment rows in → open proposals out → readable via
`read_improvements`, twice-scanned with no duplicates; with both flags off,
the existing live-trial tests pass unchanged.
