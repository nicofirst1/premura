# Drift Root-Cause Audit: `session-research-trace-01KSYT4A`

**Author**: claude:opus (orchestrator of the implement-review loop)
**Date**: 2026-05-31
**For review by**: another agent (independent verification of the root-cause analysis and process recommendations below)
**Status**: drift fixed in commit `15db268`; this document explains *how it slipped through*, not *what the fix is*.

## Verifiable anchors

- Mission merge commit: `b0e86be`. WP→done commits: `8f9e2d2`/`9d104f2`/`98ce70c`/`3c496b4`.
- Independent mission review (FAIL): `kitty-specs/session-research-trace-01KSYT4A/mission-review.md` (OpenCode/GPT-5.5).
- Remediation commit: `15db268` (`fix(trace): close mission-review drift findings…`), 4 files, +234/−12, 4 new regression tests, full suite 635 passed.
- Per-WP remediation bookkeeping: `spec-kitty agent tasks add-history` entries on WP01/WP02/WP03.

A reviewing agent should be able to confirm every claim below from these artifacts plus `git show`.

---

## 1. What happened

The implement-review loop took all 4 WPs through implement → independent per-WP review → approve with **zero rejection cycles**, then merged. A subsequent **mission-level** review returned **FAIL** with three real drift findings (two HIGH, one MEDIUM) and two risks. I independently re-verified all three against the merged code; they are genuine. So: four green per-WP reviews shipped a feature whose central guarantee (a *measured, internally consistent* multiplicity disclosure) was violable.

This is not a story about a careless reviewer. Each per-WP review ran the WP's tests (green) and checked its stated acceptance criteria (met). The defect is **structural**: of *what* was tested, not *how well*.

---

## 2. The findings (recap)

| ID | Spec | Sev | One-line |
|----|------|-----|----------|
| DRIFT-1 | FR-008 / AS-3 | HIGH | Pre-question validation failures (empty metric_id) recorded & counted toward N/raw. |
| DRIFT-2 | FR-010 / NFR-006 | HIGH | Same call markable surfaced twice → K can exceed N, breaking raw ≥ N ≥ K. |
| DRIFT-3 | NFR-003 | MED | `finish_recorded_call` could re-finalize and mutate a completed call. |
| RISK-1 | (judgment) | MED | Unknown `session_id` dispatched anyway → unmeasured-but-trusted results. |
| RISK-2 | (doc) | LOW | `entrypoint.py` module docstring omitted `correlate` + the trace tools. |

---

## 3. Root cause, per finding

The common shape: **tests asserted the spec's positive examples; they did not assert the spec's negative invariants** (the `MUST NOT`s). Acceptance was "demonstrate X works," never "prove ¬X is impossible."

### DRIFT-1 — the FR was tested at the wrong altitude (cross-WP contract gap)
FR-008 ("pre-question validation failures MUST NOT count") was conceptually filed under **WP02** (hypothesis identity + the counting logic). But the *violation* lives in **WP03**'s boundary **ordering**: `_dispatch_analytical_with_trace` records *before* it dispatches, and parameter validation lives *inside* dispatch (`entrypoint.py` record-at-133, dispatch-at-143; the `ValueError` is raised by `mcp/server.py`). So:
- WP02 tested identity dedup at the service layer — never saw the MCP ordering.
- WP03's exclusion test (`test_list_metrics_and_metric_summary_are_not_recorded`) covered *catalog* tools, never a *malformed analytical* call.
- No test ever sent a traced `change_point(metric_id="  ")`.

The FR was *defined* in one WP, *enforced* (or not) in another, and *tested* in neither at the enforcement point. This is exactly the failure my own memory note `per-wp-reviews-miss-cross-wp-contract-gaps` warns about — and I still missed it, because I mapped the FR to a WP owner, not to its **enforcement point**.

### DRIFT-2 — the natural reading of the spec hid the adversarial case
Spec: "K = count of surfaced-marked calls." The code implemented `count = len(mark_rows)`. The WP02 test (`test_surfaced_marks_set_k_and_carry_roles`) marked **two different calls**, so `len(marks)` *happened* to equal distinct calls — the test passed while being blind to the bug. "K = count of marks" reads as obviously-correct prose, so no one wrote the one adversarial test (same call, two roles) that distinguishes "mark rows" from "surfaced calls." The schema also lacked a `UNIQUE(session_id, call_id)` to make the bug structurally impossible.

### DRIFT-3 — a sanctioned UPDATE masked an unsanctioned one
WP01 deliberately allowed an insert-then-finalize write shape (nullable terminal columns), so an `UPDATE trace.tool_call` in `finish_recorded_call` *looks* like normal operation. The append-only property (NFR-003) was "tested" only *positively* — results/marks reference immutable `call_id`s — never by *attempting* the forbidden mutation (a second finalize). The first UPDATE being legitimate camouflaged that the second is a violation. Negative testing (try to mutate; assert it's rejected) was absent.

### RISK-1 — a defensible local choice with a non-local cost
The implementer chose "don't swallow the analytical answer" on a bad session — locally reasonable. But it trades away the mission's core rail (measured, not self-reported) for a typo. No per-WP criterion framed "unknown session during *recording*" (FR-015 only named disclosure/export), so nothing forced the decision into the open. It surfaced only at mission altitude, where the end-to-end guarantee is visible.

### RISK-2 — ownership seam
The docstring is in `entrypoint.py` (WP03-owned source); doc-sync was WP04-owned but scoped to `docs/` + `kitty-specs/`. Source-embedded docs fell between the two WPs' scopes.

---

## 4. Why the orchestration did not catch it

1. **Reviewers re-ran the authors' tests.** A reviewer whose evidence is "the WP's suite is green" inherits the author's blind spots verbatim. Green tests prove the enumerated cases, not the invariants.
2. **I derived review criteria from the WP prompts + FR list.** Those enumerate positive acceptance scenarios. I added emphasis on the *known* risks (dead code, engine purity) and those were genuinely well-covered — but the *unknown* risks (the `MUST NOT`s no one had turned into a test) had no champion.
3. **Cross-WP invariants have no owner.** `raw ≥ N ≥ K` spans WP01 (schema), WP02 (counting), WP03 (recording). Each per-WP review saw one slice; the invariant only exists end-to-end. There was no mission-level invariant test until this remediation added partial coverage.
4. **The catching layer was optional.** `/spec-kitty-mission-review` — the step that *did* find everything — ran only because I suggested it post-merge. It was a recommendation, not a gate.

---

## 5. What would have caught it earlier (recommendations for the reviewing agent to weigh)

Ordered by leverage:

1. **Make mission-review a pre-merge gate**, not a post-merge suggestion. It found 5/5 here; it is the highest-leverage change. Cost: one extra review pass before `spec-kitty merge`.
2. **Mission-level invariant/property tests, owned outside any WP.** E.g. a property test: for any sequence of MCP operations on a session, `raw ≥ N ≥ K` (or K unavailable) holds; and `disclosure_text` never contains "significant". These guard the seams no single WP owns.
3. **Reviewer mandate: one adversarial test per `MUST NOT` / NFR.** For every negative invariant in the spec, the reviewer must *attempt the forbidden thing* and assert it fails. Convert the spec's `MUST NOT` list into a negative-test checklist at plan/tasks time.
4. **Map each FR to its *enforcement point*, not just a WP owner.** During `tasks`, annotate where each FR is *defined*, *enforced*, and *consumed*. FR-008's enforcement point is the WP03 record/validate ordering — testing it at WP02 (its nominal owner) was guaranteed to miss it.
5. **Push invariants into the schema where cheap.** `UNIQUE(session_id, call_id)` on `trace.surfaced_mark` would have made DRIFT-2 unrepresentable. Prefer "impossible by construction" over "guarded by a service check" when the constraint is static.
6. **Orchestrator: stop trusting "the author's suite is green."** When dispatching a review, require the reviewer to add at least one test the author did *not* write, targeting a negative invariant.

---

## 6. Residual / open for the reviewer

- The DRIFT-2 fix is enforced at the **service layer** (`mark_surfaced` one-per-call guard + distinct-call K count), not yet by a schema constraint. A follow-up migration adding `UNIQUE(session_id, call_id)` to `trace.surfaced_mark` would make it structural (recommendation #5). Deferred deliberately to avoid a schema migration in a hot-fix.
- DRIFT-1's discriminator is "dispatch raised `ValueError` ⇒ pre-question validation ⇒ discard." This relies on the server raising `ValueError` *only* for parameter validation. That holds today (`mcp/server.py` validation guards), but a future engine path that raises `ValueError` for a non-validation reason would be wrongly discarded. A reviewing agent should confirm whether a typed exception (e.g. a dedicated `ParameterValidationError`) is worth introducing to make the discriminator explicit rather than type-coincidental.
- RISK-1 was resolved as **refuse** (user decision). If any caller legitimately passes a stale session id expecting best-effort analysis, that path now returns `not_found` instead of a result — confirm no internal caller relies on the old behavior.

---

## 7. Bottom line

The loop optimized for "every enumerated requirement is demonstrated." The drift lived in the **un-enumerated negative space** — the `MUST NOT`s no acceptance scenario turned into a test, and the cross-WP invariants no single WP owned. The fix for *this* mission is shipped and tested; the fix for the *process* is to make negative-invariant testing and mission-level review mandatory rather than incidental.
