---
work_package_id: WP02
title: Renamed-field declared-gap rule (FR-009)
dependencies: []
requirement_refs:
- C-002
- FR-009
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
base_branch: kitty/mission-tool-loop-live-trial-tier-01KTVG26
base_commit: bf4fb43f63d85e13203bbcf5a7b7b0eafab6d201
created_at: '2026-06-11T18:12:57.232382+00:00'
subtasks:
- T005
- T006
- T007
shell_pid: "53614"
agent: "claude:fable:reviewer:reviewer"
history:
- date: '2026-06-11T14:19:42Z'
  action: created
  by: /spec-kitty.tasks
authoritative_surface: src/premura/harness/live_trial_ollama.py
execution_mode: code_change
owned_files:
- src/premura/harness/live_trial_ollama.py
- tests/test_self_reconcile_renamed_field.py
- tests/test_live_trial_ollama.py
tags: []
---

# WP02 — Renamed-field declared-gap rule (FR-009)

## Objective

Make the sharpened declared-gap rule real and proven (spec FR-009, SC-007): a
source column the parser **consumes under a renamed output field** (the
audit's `timestamp` → `ts_utc` case) must be declared accounted (listed in the
parser's mapped-columns set) or be an explicit gap — a consumed-but-undeclared
column is a self-reconcile **failure**. Phase-0 research (research.md §R-6)
found the existing gate's arithmetic *should* already fail this case; this WP
proves it with a committed deterministic fixture test (test-first,
DIRECTIVE_034) and states the rule explicitly in both drawer contract prompts.

**Hard boundary (C-002)**: the one-shot tier's *behavior* is untouched. The
prompt edits are wording-only; the gate (`self_reconcile.py`) changes ONLY if
the new test proves a hole — which research says it will not.

## Context you need

- Read first: `kitty-specs/tool-loop-live-trial-tier-01KTVG26/spec.md`
  (FR-009, acceptance scenario 5, SC-007) and `research.md` §R-6.
- The gate: `src/premura/harness/self_reconcile.py` (NOT in your owned files —
  read it, do not edit it unless T005 turns up a genuine hole; if it does,
  STOP and flag it in your WP report so ownership can be amended — do not
  silently widen scope).
  Key fact: `accounted = mapped_columns ∪ batch.unmapped_metrics ∪
  {row.raw_field for row in skipped_rows}`; `unaccounted = source_columns −
  accounted`; pass iff source has columns and unaccounted is empty.
- The prompts you sharpen: `_OBSERVATION_CONTRACT_PROMPT` and
  `_INTAKE_CONTRACT_PROMPT` in `src/premura/harness/live_trial_ollama.py`.
  Both already contain a decision-tree RULES block whose rule 2 ends "NEVER
  silently drop a column: EVERY column in the source header must be either in
  {MAPPED} or declared as a gap."
- The synthetic fixture header (the test's source):
  `tests/fixtures/session_log/fitbit_heart_rate_synthetic.csv` — read its
  header row in the test rather than hardcoding column names.
- WHY this matters (carry into docstrings): in the 2026-06-04 clean re-test, a
  local 14B's only near-miss was consuming the `timestamp` column into
  `ts_utc` without listing it — the column was *used* but invisible to the
  honesty account. The rule makes "consumed under any output name" explicitly
  a consumption that must be declared.

## Subtasks

### T005 — Failing fixture test: renamed-field absorption FAILS the gate

**Purpose**: SC-007's committed deterministic evidence, written before any
production edit.

**Steps**:
1. Create `tests/test_self_reconcile_renamed_field.py` (new file, default
   suite, no model, no network).
2. Build a minimal in-test parser batch that mimics the audit case against the
   committed synthetic CSV:
   - Construct an `IngestBatch` (import from `premura.parsers.base`) whose
     measurements were built consuming BOTH the bpm column and the timestamp
     column (the timestamp feeding `ts_utc` — the renamed output field).
   - Supply `mapped_columns` containing ONLY the bpm column — the timestamp
     column is neither mapped nor declared in `unmapped_metrics`/`skipped_rows`
     (the silent absorption).
   - You are exercising `self_reconcile(source_path, batch, mapped_columns)`
     directly — its public interface (DIRECTIVE_036); read the real fixture
     CSV header to learn the exact column names.
3. Assert: `result.passed is False` AND the timestamp column name is in
   `result.unaccounted` (sorted list).
4. Add the positive contrast (presence vs absence, charter fidelity gate):
   the same batch with the timestamp column added to `mapped_columns` (it WAS
   consumed — declaring it accounted is the honest statement) passes, provided
   every other header column is accounted (declare any remaining columns as
   gaps via `unmapped_metrics` in the test setup).
5. Run it: per research §R-6 the FAIL assertion should already pass — that is
   the *proof the gate already enforces FR-009*, and the test pins it against
   regression. If instead the gate unexpectedly PASSES the absorption case,
   STOP: report the hole (plan risk R4) — fixing `self_reconcile.py` needs an
   ownership amendment, not a silent out-of-scope edit.

**Validation**: test green in the default suite; deterministic (no model, no
randomness); file ends up ~60–100 lines.

### T006 — Sharpen the observation contract prompt

**Purpose**: FR-009's brief half — the rule must be *stated* to the operator,
not just enforced after the fact (the brief is what makes the trial fair).

**Steps**:
1. In `_OBSERVATION_CONTRACT_PROMPT` (in `live_trial_ollama.py`), extend RULES
   item 2 (or add an explicit clause right after it) with the renamed-field
   case. Suggested wording (adapt to fit the existing voice — imperative,
   compact):
   ```
   A column you CONSUME under any output name (e.g. a timestamp column you
   parse into ts_utc) is still a consumed column: add it to
   {_MAPPED_COLUMNS_CONST}. Renaming is not declaring.
   ```
2. Keep the f-string interpolation intact (`{_MAPPED_COLUMNS_CONST}` /
   `{_PARSER_ATTR}` are real interpolations in that literal — mind the braces).
3. This prompt is served by BOTH tiers (the tool loop embeds the same drawer
   contract surface — see contracts/tool-loop-tier.md §2), so wording must not
   contradict either tier's protocol: do not add any "output only the module"
   style directive; touch only the column-accounting rule.

**Validation**: `uv run pytest -q` green — especially
`tests/test_live_trial_ollama.py` (you own it: if an existing test pins the
old prompt text, update that assertion to the sharpened text — assert on the
rule's presence, not the full prompt string).

### T007 — Sharpen the intake contract prompt; suites stay green

**Purpose**: the same rule for the intake drawer (FR-008 symmetry — the rule
is drawer-agnostic, so both prompts state it).

**Steps**:
1. Apply the equivalent clause to `_INTAKE_CONTRACT_PROMPT` RULES (intake's
   consumed columns fill event fields: timestamp, item label, quantity —
   "consumed under any output name" reads identically).
2. Add (or extend) a prompt-invariant test in `tests/test_live_trial_ollama.py`
   asserting BOTH prompts contain the renamed-field clause (substring match on
   a stable phrase like "Renaming is not declaring") AND still contain every
   required API class name they already carry (`IngestBatch`, `Measurement`,
   `IntakeBatch`, `ParseOutput`, etc. — pin the class-name list from the
   prompts' Target API blocks). This doubles as the SC-006 anchor WP03's brief
   test will build on.
3. Full gates: `uv run pytest -q`, `uv run ruff check` + `ruff format --check`
   on owned files, `uv run mypy` on the changed scope.

**Validation**: full default suite green; both prompts carry the clause; zero
behavioral diffs (prompt text constants and tests are the entire diff).

## Definition of Done

- [ ] `tests/test_self_reconcile_renamed_field.py` committed: absorption case
      FAILS with the column named in `unaccounted`; declared case passes
      (presence AND absence exercised).
- [ ] Both drawer prompts state the renamed-field rule; interpolations intact.
- [ ] No edit to `self_reconcile.py` (or an explicitly reported hole +
      ownership amendment if research §R-6 was wrong).
- [ ] Full default suite green; ruff + mypy clean; zero files outside
      `owned_files` touched.

## Risks / notes for the reviewer

- Reviewer: verify the test consumes the timestamp column in the batch it
  builds (i.e., measurements genuinely derive `ts_utc` from it) — a test that
  merely omits a column from `mapped_columns` without consuming it anywhere
  tests ordinary unaccounted columns, not the *renamed-field absorption* case
  the spec names.
- Reviewer: confirm prompt edits are inside the two prompt constants only —
  any other diff in `live_trial_ollama.py` is scope creep against C-002.
- The fixture CSV is synthetic and committed — no PHI concerns (C-001 holds).

## Activity Log

- 2026-06-11T18:12:58Z – claude:fable:implementer:implementer – shell_pid=41176 – Assigned agent via action command
- 2026-06-11T18:23:42Z – claude:fable:implementer:implementer – shell_pid=41176 – Ready for review: FR-009 proven by committed fixture test (gate already enforced it, no self_reconcile.py edit); both drawer prompts state the renamed-field rule; prompt-invariant test pins clause + API names
- 2026-06-11T18:24:14Z – claude:fable:reviewer:reviewer – shell_pid=53614 – Started review via action command
- 2026-06-11T18:30:05Z – claude:fable:reviewer:reviewer – shell_pid=53614 – Review passed: FR-009 proven by deterministic fixture test exercising real self_reconcile (absorption FAILS with timestamp in unaccounted, declared case PASSES); batch genuinely consumes timestamp into ts_utc; both drawer prompts state the renamed-field rule via live _DRAWER_PROBES dispatch; prompt-invariant test pins clause + API names; self_reconcile.py untouched; diff confined to 3 owned files; full suite 1059 passed, ruff+format+mypy clean
