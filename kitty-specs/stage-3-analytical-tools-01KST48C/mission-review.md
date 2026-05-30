# Mission Review Report: `stage-3-analytical-tools-01KST48C`

**Reviewer**: OpenCode  
**Date**: 2026-05-29  
**Mission**: `stage-3-analytical-tools-01KST48C` — Stage 3 Analytical Tools  
**Baseline commit**: `3c34171c35eb37d382263980271b3f991f841826`  
**Implementation merge commit**: `7255b04`  
**HEAD at review**: `3d3ff65d80f282352dc5ec5967faaeb60f9dff6f`  
**WPs reviewed**: WP01-WP06

**Validation run during review**:

- `uv run pytest tests/test_engine_analytical_contract.py tests/test_engine_analytical_inputs.py tests/test_engine_analytical_tools.py tests/test_engine_analytical_public_surface.py tests/test_mcp_analytical_tools.py -q`: 80 passed
- `uv run pytest -q`: 466 passed
- `uv run ruff check .`: fails on pre-existing line-length issues
- `uv run ruff format --check .`: fails on broad pre-existing formatting drift
- `uv run mypy src`: fails on broad pre-existing typing issues

## FR Coverage Matrix

| FR ID | Brief | WP Owner | Test File(s) | Adequacy | Finding |
|---|---|---|---|---|---|
| FR-001 | Analytical contract / registry without dispatch ladder | WP02, WP05 | `tests/test_engine_analytical_contract.py`, `tests/test_engine_analytical_public_surface.py` | ADEQUATE | — |
| FR-002 | MCP wrappers delegate to engine path | WP06 | `tests/test_mcp_analytical_tools.py` | ADEQUATE | — |
| FR-003 | Evaluate admissibility before computation | WP03 | `tests/test_engine_analytical_inputs.py`, `tests/test_mcp_analytical_tools.py` | PARTIAL | DRIFT-1 |
| FR-004 | Input-series contract with overlap metadata | WP03 | `tests/test_engine_analytical_inputs.py` | PARTIAL | RISK-1 |
| FR-005 | Mandatory analytical result envelope | WP02, WP05 | `tests/test_engine_analytical_contract.py`, `tests/test_engine_analytical_public_surface.py` | ADEQUATE | — |
| FR-006 | Closed confound checklist vocabulary | WP02 | `tests/test_engine_analytical_contract.py` | ADEQUATE | — |
| FR-007 | `change_point` proof tool | WP04 | `tests/test_engine_analytical_tools.py`, `tests/test_mcp_analytical_tools.py` | ADEQUATE | — |
| FR-008 | Smoothed average proof tool | WP04 | `tests/test_engine_analytical_tools.py`, `tests/test_mcp_analytical_tools.py` | ADEQUATE | — |
| FR-009 | Proof tools on default MCP surface | WP06 | `tests/test_mcp_analytical_tools.py`, `tests/test_mcp_server.py`, `tests/test_mcp_signal_tools.py` | ADEQUATE | — |
| FR-010 | No causation / diagnosis / treatment claims | WP04, WP06 | `tests/test_engine_analytical_tools.py`, `tests/test_mcp_analytical_tools.py` | ADEQUATE | — |
| FR-011 | Resolve analytical evidence-policy question-shape strategy | WP01, WP03 | `tests/test_engine_analytical_inputs.py` | PARTIAL | DRIFT-1 |
| FR-012 | Keep `change_point` separate from Stage 2 `change` family | WP04 | `tests/test_engine_analytical_tools.py` | ADEQUATE | — |

## Drift Findings

### DRIFT-1: Analytical question types are not actually added to the evidence-policy vocabulary

**Type**: LOCKED-DECISION VIOLATION  
**Severity**: HIGH  
**Spec reference**: FR-011  
**Plan/research reference**: `research.md` D4, `plan.md` Phase 1 design decisions

**Evidence**:

- `docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md:123-137` says the mission extends the closed evidence-policy `QuestionType` vocabulary with `level_shift_detection` and `smoothed_pattern`.
- `docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md:190-193` explicitly rejects reusing `historical_baseline` / `recent_trend` and rejects free-form question names.
- `src/premura/engine/policies/_model.py:78-85` still defines only the existing descriptive `QuestionType` values: `current_status`, `recent_trend`, `long_term_control`, `historical_baseline`.
- `src/premura/engine/analytical_contract.py:47-64` adds a separate `AnalyticalQuestionType`, not new values in the evidence-policy `QuestionType`.
- `src/premura/engine/analytical_inputs.py:111-118` maps both analytical values to `QuestionType.RECENT_TREND`.
- `tests/test_engine_analytical_inputs.py:362-366` locks in that mapping rather than testing true evidence-policy vocabulary extension.

**Analysis**:

The implementation creates a parallel analytical enum and then gates both analytical tools through the existing descriptive `RECENT_TREND` rule. That contradicts the research note's locked decision that forcing these questions onto existing descriptive shapes was rejected because it distorts level-shift detection and hides analytical sufficiency requirements.

This is not just wording drift. Runtime admissibility for `level_shift_detection` and `smoothed_pattern` is governed by `RECENT_TREND` policies, so future policy authors cannot declare freshness/sufficiency specifically for analytical question types through the existing evidence-policy vocabulary.

**Impact**:

The proof tools may be safe enough for the current narrow surface because they add method-level refusals, but the mission's contract promise is not fully realized. Later analytical tools would inherit a misleading "analytical question type" layer that is actually a wrapper around `RECENT_TREND`.

## Risk Findings

### RISK-1: `AnalyticalInputSeries` can be constructed without required overlap/window metadata

**Type**: BOUNDARY-CONDITION  
**Severity**: MEDIUM  
**Spec reference**: FR-004  
**Location**: `src/premura/engine/analytical_inputs.py:185-195`, `src/premura/engine/analytical_inputs.py:219-231`

**Evidence**:

- `spec.md:40-42` requires prepared analytical inputs to include aligned values plus overlap, sample size, freshness, imputation, source, and refusal metadata.
- `data-model.md:37-54` requires `overlap_start`, `overlap_end`, and `overlap_sample_size` to be present even for single-series tools.
- `src/premura/engine/analytical_inputs.py:185-195` defaults `window_start`, `window_end`, `overlap_start`, and `overlap_end` to `None`.
- `src/premura/engine/analytical_inputs.py:219-231` validates ordering, sample size, imputation percentage, and overlap count bounds, but does not require non-refusal inputs to have non-null window/overlap timestamps.
- `tests/test_engine_analytical_inputs.py:170-188` verifies overlap fields only through `prepare_input_series`, not direct construction of the public dataclass.

**Analysis**:

The normal `prepare_input_series` path does populate overlap fields, so the current proof tools are protected in the happy path. But the public model type itself does not enforce the contract. A future tool author can construct a non-refusal `AnalyticalInputSeries` with computation points and no overlap/window metadata, and `points_for_computation` will return the points.

**Impact**:

This is a future-extension risk rather than an immediate proof-tool bug. It weakens the "bounded contract agents fill in" promise because the type allows a malformed analytical input series that the spec says should not exist.

## Silent Failure Candidates

No mission-specific silent failure candidates found.

| Location | Condition | Silent result | Spec impact |
|---|---|---|---|
| — | — | — | — |

The new analytical code generally returns explicit refusal envelopes or raises clear errors for programming mistakes such as unknown tool names.

## Security Notes

No blocking security findings found.

| Finding | Location | Risk class | Recommendation |
|---|---|---|---|
| No new runtime network calls found | `src/premura/engine/analytical*.py`, `src/premura/mcp/server.py` | Network boundary | Keep PubMed/literature grounding out of runtime analytical code. |
| MCP wrappers use existing read-only warehouse path | `src/premura/mcp/server.py:529-532`, `src/premura/mcp/server.py:535-593` | Data access boundary | Acceptable, though wrappers call private `_query` helpers; future cleanup could expose a public engine helper for analytical evidence loading. |

## Static Gate Notes

The full test suite passes: `466 passed`.

Static gates are not clean in this checkout:

- `uv run ruff check .` fails on line-length issues in `tests/test_mcp_signal_tools.py` and `tests/test_parsers/test_sleep_as_android.py`.
- Baseline checks show these line-length issues existed before the mission for the sampled files.
- `uv run ruff format --check .` reports broad pre-existing formatting drift.
- `uv run mypy src` reports broad pre-existing typing issues, including a sampled pre-existing `_query.py` error.

These do not appear introduced by the mission implementation, but they mean the charter's full static-gate expectation is not currently green without a documented pre-existing-failure exception.

## Final Verdict

**FAIL**

### Verdict rationale

The implementation substantially delivers the proof tools, default MCP exposure, result envelope discipline, no-network boundary, and test coverage. However, DRIFT-1 is a high-severity locked-decision violation: the mission's research and plan explicitly rejected mapping analytical question types onto existing descriptive `QuestionType` values, but the implementation does exactly that internally by mapping both proof tools to `QuestionType.RECENT_TREND`. This undermines the evidence-policy contract extension promised by FR-011 and the research note. RISK-1 is non-blocking but should be fixed or documented before future tool authors rely on the input-series contract.

### Open items

- Fix DRIFT-1 by either truly extending the evidence-policy `QuestionType` vocabulary with `level_shift_detection` and `smoothed_pattern`, or formally amend the research/plan/spec to accept the analytical-to-`RECENT_TREND` bridge as the intended design.
- Tighten `AnalyticalInputSeries` validation so usable inputs require `window_start`, `window_end`, `overlap_start`, and `overlap_end`.
- Document the current pre-existing static-gate failures if this mission is accepted despite global `ruff` / `mypy` failures.

---
---

# Second Independent Review (concurring)

**Reviewer**: claude (Opus 4.8), senior mission reviewer
**Date**: 2026-05-29
**Method**: full spec/contract absorption + five parallel file-level evidence
traces (contract, input-prep, proof-tools, public-surface, MCP) with file:line
citations and "would the test fail if the impl were deleted?" adequacy judgments,
then personal verification of the load-bearing claims.
**Relationship to the OpenCode review above**: independent. I reached the same
**FAIL** verdict on the same gating finding, arrived at separately, and I am
recording corroborating evidence plus additional lower-severity findings. I also
note for the record that the Spec Kitty implement-review loop that produced this
mission **approved all six WPs (including WP03) and did not catch DRIFT-1** — the
per-WP reviews verified the analytical→descriptive bridge map for *internal*
soundness (closed, complete, no dropped rejection reasons) but never traced it
against the WP01 research note's explicitly rejected alternative. This is the
canonical "per-WP review misses a cross-WP contract gap" failure.

## Concurrence on the gating finding (DRIFT-1) — CONFIRMED, HIGH, blocking

I independently verified every link in OpenCode's DRIFT-1 chain:

- **Decision of record (WP01 research note)** `docs/history/research/STAGE3_ANALYTICAL_TOOLS_RESEARCH.md`:
  - D4, lines 128-129: *"The mission therefore **extends the closed evidence-policy `QuestionType` vocabulary** with two reviewed values: `level_shift_detection`, `smoothed_pattern`."*
  - Alternatives rejected, lines 190-191: *"**Reusing `historical_baseline` / `recent_trend` for the analytical questions** — rejected; it distorts level-shift detection and hides analytical sufficiency."*
- **What shipped**:
  - `src/premura/engine/policies/_model.py:81-84` — `QuestionType` still has **only** the four descriptive values; `level_shift_detection`/`smoothed_pattern` were **never added** to the evidence-policy vocabulary.
  - `src/premura/engine/analytical_inputs.py:111-118` — `ANALYTICAL_TO_DESCRIPTIVE_QUESTION` maps **both** `LEVEL_SHIFT_DETECTION` and `SMOOTHED_PATTERN` → `QuestionType.RECENT_TREND`. The module's own comment (lines 121-122) states "both gate on the descriptive `RECENT_TREND` admissibility rule" — i.e. it does the exact thing the note rejected.

**Why this is a locked-decision violation, not a defensible reading.** The
research note does not merely say "introduce reviewed analytical question types"
(which a separate enum would satisfy); it specifies the *mechanism* — extend the
evidence-policy `QuestionType` vocabulary — and it enumerates "reusing
`recent_trend`" as a **rejected** alternative with a stated reason. The shipped
design routes both analytical questions' admissibility through `RECENT_TREND`,
so the evaluator never sees an analytical question type. The concrete runtime
consequence the note warned about is real: a policy author **cannot** declare
freshness/sufficiency rules specific to `level_shift_detection` vs
`smoothed_pattern` through the evidence policy, because `evaluate_evidence`
only ever receives `RECENT_TREND`. The separate `AnalyticalQuestionType` enum is
collapsed to `RECENT_TREND` *before* the evaluator, so it is cosmetic at the
admissibility layer — exactly the "hides analytical sufficiency" outcome.

**Severity HIGH is correct.** This defeats the mission's central promise ("make
the safe extension shape real") at the admissibility layer, even though the two
proof tools are not themselves unsafe (they layer method-level refusals —
`min_side_observations`, window/coverage bounds — on top of the `RECENT_TREND`
gate, so current output is honest). The violation is to the *contract and the
locked decision*, not to the proof tools' numeric output. Per the review
rubric, an undocumented HIGH finding makes the verdict **FAIL**.

**Root cause (for the fix).** WP02's owned-files set excluded
`policies/_model.py`, so the implementer placed the analytical question types in a
local enum "[a] later WP can wire ... into the evidence-policy enum if needed."
WP03's owned-files set *also* excluded `policies/_model.py`, so WP03 bridged to
`RECENT_TREND` instead of extending the enum. The owned-files partition made the
spec-faithful implementation impossible within either WP's scope, and no WP owned
"extend `QuestionType`." A correct fix requires a WP (or amendment) that owns
`policies/_model.py` and adds the two values as first-class evidence-policy
question types with their own admissibility rules — **or** a formal amendment to
the research note/plan/spec accepting the analytical→`RECENT_TREND` bridge as the
intended design (which would also need to drop line 190's rejection).

## Concurrence on RISK-1 — CONFIRMED, MEDIUM

`AnalyticalInputSeries.__post_init__` (`analytical_inputs.py:197-231`) enforces,
for a usable (non-refusal) series: non-empty `metric_id`, `question_type` is an
`AnalyticalQuestionType`, imputation in `[0,100]`, points ordered, `sample_size
== len(points)`, `overlap_sample_size <= sample_size`. It does **not** require
`window_start`, `window_end`, `overlap_start`, or `overlap_end` to be non-`None`.
A future tool author can construct a usable series with points and null
window/overlap timestamps; `points_for_computation` will return the points. The
happy path through `prepare_input_series` populates these (lines ~470-475), so
the current proof tools are protected — this is a future-extension contract gap,
not a present defect. MEDIUM, non-blocking.

## Additional findings from this review (all LOW, non-blocking)

These were not in the OpenCode review; none change the verdict (DRIFT-1 already
gates it), but they belong in the acceptance record:

- **NFR-006 (caveat ≤280 chars) is unenforced and untested**, though **compliant
  in fact** — the longest analytical caveat is 152 chars (others 141/130/76).
  `AnalyticalResultEnvelope.validate()` performs no length check. Per NFR-006's
  escape clause I record reviewer approval that the *current* caveats are within
  bound; recommend a length assertion in `validate()` so future tools stay bound.
- **FR-005 confound checklist not enforced non-empty** — `confound_checklist`
  defaults to `()` (`analytical_contract.py:406`) and `validate()` accepts an
  empty checklist. Both proof tools always populate it, so no shipped tool is
  affected; flag if FR-005 intends "checklist actively considered."
- **`validity_status` value is unvalidated** — `validate()` rejects only `None`
  (`analytical_contract.py:443-452`); any string, including `""`, passes. No
  closed vocabulary. LOW robustness gap.
- **Minimal public surface has no negative guard test** — tests assert the 15
  intended symbols are present in `engine.__all__` but never assert private
  helpers (`dispatch`, `analytical_tool`, `REGISTRY`, `validate_confound_keys`)
  are absent; future API creep would pass CI.
- **NFR-001 determinism asserted at dict-equality, not literal JSON bytes** in the
  engine-tool test (the public-surface test does use `json.dumps(sort_keys=True)`,
  which normalizes order). Holds in fact (fixed key order in `to_dict`); slightly
  weaker than the NFR's literal wording.
- **`change_point` selection criterion not pinned by a divergent fixture** — no
  test uses a series where "largest standardized difference" and "largest raw
  gap" select different splits, so a regression to raw-gap ranking could survive.
- **Idempotency of `load_builtin_analytical_tools()` only exercised indirectly.**

## What this review confirms PASSES (so the fix scope stays narrow)

Traced with file:line evidence; all adequately tested unless noted above:
FR-001 (registry + branchless `dispatch`), FR-002/C-001 (MCP wrappers contain
**no** SQL and **no** statistics — the only `conn.execute` in `server.py` is the
pre-existing operator `query_warehouse` at line 75 — delegation is spy-tested),
FR-005 envelope field enforcement (5 of 6 fields; see confound note), FR-006
(closed 8-key vocabulary, rejects outsiders), FR-007/FR-008 (the proof-tool math
is real and correct — standardized level difference `gap/pooled_std`, trailing
rolling mean with None-on-undercoverage and `Uncertainty.unavailable()`),
**FR-010 (CRITICAL honesty — independent source grep found no bare positive
causal/diagnostic/predictive/significance claim; every match is a negated denial,
comment, or identifier; doctrine tests fail on an injected causal claim)**,
FR-012 (`change_point` registers only via the analytical contract; `RESULT_FAMILIES`
untouched), C-002/C-003/NFR-005 (local-first; no network reachable; subprocess
import-leak test), C-006 (static built-in loading; AST test forbids
scanning/plugins), NFR-002/NFR-003/NFR-004 (JSON-safe serialization; six distinct
evaluator-driven refusal reasons), and security (bound `?` SQL parameters,
validated params, upper bounds delegated to engine refusal, read-only warehouse,
no injection/unbounded-work surface). The refusal-before-compute seam is
defense-in-depth (`points_for_computation` raises **and** a `__post_init__`
invariant forbids points on a refused series). Full suite green on `master`
(466 passed, 0 failed).

## Final Verdict (second reviewer): **FAIL** — concurring

The mission is one narrow, well-understood drift away from acceptance. Eleven of
twelve FRs and all eight constraints are satisfied with adequate tests; the
critical honesty boundary (FR-010) and the wrapper boundary (C-001) genuinely
hold. **DRIFT-1 is the sole blocker**: the shipped admissibility wiring routes
both analytical question types through `QuestionType.RECENT_TREND`, which is the
design the WP01 research note explicitly rejected, and never extends the
evidence-policy `QuestionType` vocabulary as the decision of record committed.
Because this is an undocumented HIGH-severity locked-decision violation, the
verdict is FAIL until either (a) the two analytical question types become
first-class evidence-policy `QuestionType` values with their own admissibility
rules, or (b) the research note/plan/spec are formally amended to adopt the
`RECENT_TREND` bridge (removing the line-190 rejection). All other findings
(RISK-1 MEDIUM; the LOW items above) are non-blocking follow-ups.

---
---

# Resolution — DRIFT-1 fixed (post-review, uncommitted on `master`)

**Date**: 2026-05-29 · **By**: claude (Opus 4.8), at maintainer request ("fix the
code based on the review"), approach **minimal faithful** (selected by the
maintainer).

DRIFT-1 (the sole blocker) is resolved. The analytical question types are now
first-class evidence-policy question types; nothing routes them onto a
descriptive shape.

**Changes (working tree, not yet committed):**
- `src/premura/engine/policies/_model.py` — `QuestionType` gains
  `LEVEL_SHIFT_DETECTION` and `SMOOTHED_PATTERN`; the "belongs to a future
  mission" comment updated to record this reviewed addition (D4).
- `src/premura/engine/analytical_inputs.py` — the bridge map was renamed
  `ANALYTICAL_TO_DESCRIPTIVE_QUESTION` → `ANALYTICAL_TO_POLICY_QUESTION` and now
  maps each analytical question to the first-class `QuestionType` of the same
  name (no `RECENT_TREND` collapse). The evaluator receives the analytical
  question type unchanged.
- `src/premura/engine/policies/_defaults.py` — the five recent-run family shapes
  (`serial_average_short_run`, `rolling_recent_pattern`, `baseline_relative`,
  `slow_trajectory_method_sensitive`, `sparse_lab_analyte_specific`) declare
  `QuestionRule`s for both analytical questions, reusing each shape's recent-run
  rule. The three non-recent-run shapes (long-term-control, profile facts, acute
  spot) declare neither, so analytical questions on those families honestly
  refuse (`UNSUPPORTED_POLICY` → `unsupported_question`).
- `src/premura/engine/analytical_contract.py` — `AnalyticalQuestionType`
  docstring reframed: it mirrors the first-class policy question types; the
  "kept separate on purpose / collapsing would distort" rationale (which
  described the rejected design) is removed.
- Tests — the three `_recent_trend_policy` fixtures register rules under the
  analytical question types; the wiring test was rewritten to assert no
  analytical question maps to a descriptive shape; two lock tests were added
  (`test_recent_trend_rule_does_not_serve_analytical_questions` in
  `test_engine_analytical_inputs.py` — a same-family RECENT_TREND-only policy
  must refuse analytical questions; `test_analytical_question_rules_are_declared_on_recent_run_families`
  in `test_engine_policy_defaults.py` — locks the per-family rules).

**Verification:** full suite **468 passed** (was 466 + 2 lock tests); `ruff
check`/`ruff format --check`/`mypy` clean on all changed files. An independent
adversarial re-review confirmed DRIFT-1 resolved and faithful to D4, with no new
issues, and verified the fix by injecting the regression (re-pointing the map at
`RECENT_TREND`) and watching the lock test fail.

**Verdict after fix: PASS WITH NOTES.** The blocking finding is cleared. Remaining
open follow-ups are unchanged and non-blocking: RISK-1 (MEDIUM —
`AnalyticalInputSeries` overlap/window invariant) and the LOW items (NFR-006
length guard, FR-005 confound-checklist enforcement, `validity_status`
validation, negative `__all__` guard test). The changes are uncommitted; commit
when ready.
