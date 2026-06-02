# Implement-Review Drift Audit — finish-analytical-tool-set-01KT0Y95

> Method: [`docs/building/agents/implement-review-drift-audit.md`](../../building/agents/implement-review-drift-audit.md).
> This audit consumes a post-merge mission-review note and asks *why the
> implement→review→merge loop admitted it*, then names the missing control so the
> next mission cannot repeat it. It is not a bug report — the bug is already
> fixed; this is the post-mortem on the **control gap**.

## Audited subject

| Field | Value |
|---|---|
| Mission | `finish-analytical-tool-set-01KT0Y95` — Finish Analytical Tool Set |
| Mission merge commit | `984cc48` (squash of WP01–WP06 into `master`) |
| Mission-review verdict | **PASS WITH NOTES** (OpenCode, senior mission reviewer, 2026-06-01) |
| Reviewer HEAD | `26619bc` (pre-fix; confirmed ancestor of the fix) |
| Finding audited | DRIFT-1 / RISK-1 — paired-span metadata reported on a UTC-date basis instead of the local-calendar-day basis used for pairing |
| Remediation | **FIXED** in `7af861f` "fix: report paired spans using local days" (+ regression test) |
| Audit HEAD | `7af861f` |

The mission-review **detector worked**: it found the drift on the merged record.
This audit targets the per-WP loop, so the post-merge detector is not the *only*
net that catches this class.

## Finding DRIFT-1 — span metadata basis diverged from pairing basis

Traced through the method's five questions.

### 1. Introduction — where/when it entered

- Entered in WP03's `src/premura/engine/paired_inputs.py` (WP03 lane commit
  `09ec654`, merged at `984cc48`). WP03 owns the file end-to-end; the bug is
  entirely inside one WP's owned scope, not a hand-off omission.
- **The contract did *not* create the gap by silence** — `data-model.md` names
  the basis correctly: `anchor_date` is a "local calendar date"
  (`data-model.md:67`) and `before_window_start`/`after_window_start` are the
  "actual before/after span" (`data-model.md:109-110`). The implementer even
  encoded the intent in a comment: *"Window spans reflect the actual paired days
  used (so the admissible paired span WP04 reports under FR-006 is honest)."*
- It is therefore an **implementer slip against a correct contract**: pairing
  inclusion keyed each observation by `local_calendar_day(point.ts,
  point.local_tz)` (pre-fix `paired_inputs.py:539`), but the span report
  recomputed dates from the *raw* timestamp — `min(d.date() for d in
  used_before_days)` over `[pairs[i].before_ts …]` (pre-fix `:607-612`). The
  local day was already in hand and silently discarded.
- **Effect:** correct pair *selection* (estimate is right), but a before/after
  span label off by one local day for any observation whose UTC date ≠ its
  `local_tz` calendar day (near-midnight readings). Reviewer's runtime repro:
  `local_tz='-05:00'` UTC timestamps crossing midnight → spans reported one day
  later than the local days actually compared.

### 2. Controls the artifact passed through

1. WP03 implement prompt (TDD + integration/dead-code check).
2. The mission contract / `data-model.md` field definitions.
3. WP03 per-WP review (acceptance fixtures + scope).
4. WP04 per-WP review (FR-006 fields present in the serialized envelope).
5. Orchestrator scheduling / merge gate.
6. Post-merge mission-review — **CAUGHT it** (out of scope for "why it reached
   the merge", but recorded: the detector is the backstop, not the prevention).

### 3. Why each control missed

- **WP03 prompt:** demanded "honest spans" and an integration check, but the
  integration check I wrote pointed at the *WP04 consumption seam* ("don't
  re-derive pairs; consume the bundle") — it never said "test a timezone where
  the local day diverges from the UTC date." No representational-divergence
  fixture was required.
- **Contract / data-model:** named the basis ("local calendar date") as prose,
  not as a **test-enforced field constraint** and not as a **fixture mandate**.
  Prose intent with no pin is invisible to a green test suite.
- **WP03 review:** every acceptance fixture it ran used the shared helper
  `_point()` with naive-noon timestamps and **no `local_tz`** — so UTC date ≡
  local day and the span assertions passed *trivially*. The reviewer did not
  author a divergence fixture, so the two bases never separated under test.
- **WP04 review:** FR-006 is a "fields present + values plausible" check. The
  reviewer correctly verified WP04 only *serializes* WP03's bundle and does not
  re-derive — which is exactly why it **trusted the upstream span value** and did
  not re-audit its basis. The dead-code/seam control ("consume, don't re-derive")
  inadvertently guaranteed that nobody downstream re-checked the bundle's basis.
- **Orchestrator prompts (mine):** I pressed hard on the WP03→WP04 seam, the
  anchor-date-only scope, and the no-significance honesty boundary — but I never
  asked either agent to exercise a local-vs-UTC date boundary. The orchestrator
  prompt is itself a control, and it missed too.

### 4. The missing control

A **representational-divergence fixture** requirement: for any tool that computes
on a *derived* representation of an input, at least one acceptance fixture must
use inputs where the derived value differs from the raw source, asserting that
**reported metadata uses the derived basis**. It should fire in two places:

- the **producing WP's Definition of Done** ("include a divergence fixture for
  every derived representation"); and
- a **contract field-spec** that names each metadata field's basis (e.g.
  "`*_window_*` are local calendar days") so a reviewer has a concrete pin.

This is precisely what the fix added: `7af861f` introduced
`test_span_metadata_uses_local_days_when_utc_dates_differ`
(`tests/test_engine_before_after_pairs.py`) — 8 before / 8 after points at
`hour=2, local_tz="-05:00"` whose UTC date is the *next* day — and changed the
span computation to read `pairs[i].before_day` (the local day now carried on
`BeforeAfterPair.before_day`/`after_day`) instead of `ts.date()`
(`paired_inputs.py:614-618`). The test also asserts `first.before_ts.date() !=
first.before_day`, locking the boundary open so it cannot silently re-close.

### 5. Generalizable lesson → dimension

This is a new class, added to the registry as **D4 — Derived-representation basis
fidelity (compute basis vs. report basis)**. The drift hides in two gaps at once:

- **between a WP's compute path and its report path** — one uses the derived
  value, the other recomputes from raw; and
- **between the fixture distribution and the production input distribution** —
  fixtures (naive-noon, tz-less) never cross the local-vs-UTC boundary that real
  health-export timestamps cross, so the divergence is structurally invisible to
  every gate.

It also rides the **WP03→WP04 seam**: FR-006's "admissible paired span" is
*produced* by WP03 and *reported* by WP04, and the seam discipline that prevents
dead code (downstream consumes the bundle, doesn't re-derive) is exactly what
left the bundle's basis unowned downstream. Hence D4's corollary: **the producing
WP's review owns a consumed field's basis.**

## Evidence index

| Claim | Reference |
|---|---|
| Pairing keyed by local calendar day | `paired_inputs.py:539` (pre-fix) → `local_calendar_day(point.ts, point.local_tz)` |
| Span recomputed from raw timestamp | `paired_inputs.py:607-612` (pre-fix) → `min(d.date() for d in used_before_days)` |
| Comment claims honesty the code didn't deliver | `paired_inputs.py` §8 bundle comment (pre-fix) |
| Contract names the local basis | `data-model.md:67,109-110` |
| FR-006 requires the admissible paired span | `spec.md:137` |
| Fixtures used naive-noon, no `local_tz` | `tests/test_engine_before_after_pairs.py` `_point()` helper, `REFERENCE`/noon timestamps |
| Reviewed (pre-fix) HEAD | `26619bc`, ancestor of fix |
| Fix + regression test | `7af861f` (`paired_inputs.py:219-220,614-618`; `tests/test_engine_before_after_pairs.py::test_span_metadata_uses_local_days_when_utc_dates_differ`) |
| Regression green at audit HEAD | `pytest -k "span_metadata_uses_local_days or window"` → 5 passed |

## Unifying root cause

The project-wide **test-fixture convention is blind to the local-vs-UTC date
boundary**. Synthetic series are built from naive-noon, timezone-less timestamps,
where every derived representation (local calendar day) coincides with the raw
one (UTC date). Any analytical tool that *derives* a local representation for
computation can therefore *report* a raw-basis label and still pass every per-WP
gate. No control in the loop — prompt, contract pin, per-WP review, or seam
discipline — owns the question **"do the fixtures cross the representational
boundaries that production inputs cross?"** The post-merge mission-review is
currently the only place that boundary is exercised, and only by manual
reviewer initiative.

## Remediation status

| Item | Status |
|---|---|
| Span metadata reports local calendar days | **FIXED** — `7af861f` (`paired_inputs.py:614-618`; `BeforeAfterPair.before_day/after_day`) |
| Regression fixture with `local_tz` where UTC date ≠ local day | **FIXED** — `7af861f` `test_span_metadata_uses_local_days_when_utc_dates_differ` |
| Drift dimension registry extended | **DONE** — D4 added to `docs/building/agents/implement-review-drift-audit.md` |
| Systemic prevention (below) | **OPEN** — recommendations for the next missions |

## Prevention — stop the class, not just this instance

1. **Adopt the divergence-fixture rule (D4) as a DoD item.** Any WP whose tool
   derives a representation (local day, canonical id, bucket key, unit
   conversion) must ship ≥1 acceptance fixture where derived ≠ raw, asserting
   reported metadata uses the derived basis. Add this line to the
   implement-prompt validation block and the review checklist for engine tools.

2. **Fix the fixture distribution at the source.** The naive-noon `_point()`
   convention is the real hole. Provide a shared time-series fixture builder that
   **defaults to tz-aware timestamps** (or randomizes hour + `local_tz`), so new
   tests cross the midnight boundary *by default* rather than only when an author
   remembers to. A timezone-less fixture should be the deliberate exception, not
   the default.

3. **Pin metadata basis in the contract, testably.** In `data-model.md` and
   `src/premura/engine/CONTRACT.md`, state each temporal/derived metadata field's
   basis as a constraint a reviewer can check ("`*_window_*` fields are local
   calendar days; never `timestamp.date()`"), and require metadata to **reuse the
   derived value**, never recompute from raw on a second path.

4. **Make seam-trust an explicit hand-off of ownership.** When a downstream WP is
   instructed to consume a producer's bundle without re-deriving (good — it
   prevents dead code), the **producing WP's review must explicitly own the
   bundle's field semantics/basis**, because downstream will deliberately not
   re-check them. State this in both prompts so the responsibility isn't dropped
   in the seam.

5. **Cheap static smell as a backstop.** Flag any module that imports
   `local_calendar_day` (or any normalizer) **and** also calls `.date()` /
   `.isoformat()` on a raw timestamp for output — a one-line grep/ruff-style
   check that surfaces exactly this compute-vs-report divergence before review.

6. **Run this audit method after every PASS-WITH-NOTES**, not only on request, so
   a "justified deviation" or a single medium note becomes a durable control
   change rather than a one-off patch.
