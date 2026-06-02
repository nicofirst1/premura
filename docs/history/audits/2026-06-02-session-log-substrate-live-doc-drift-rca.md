# Drift Audit RCA — Session Log Substrate (slice one): post-merge live-doc drift

> Method: [`docs/building/agents/implement-review-drift-audit.md`](../../building/agents/implement-review-drift-audit.md).
> Run because the `spec-kitty-mission-review` returned **PASS-WITH-NOTES** —
> the charter "Close the loop" gate requires the audit + a durable control before
> the next mission of similar shape.

## Audited mission

- **Mission:** `session-log-substrate-01KT45S1` (Session Log Substrate, slice one).
- **Merge commit:** `798493b` (squash; 8 WPs, all `done`).
- **Mission-review verdict:** PASS-WITH-NOTES. The primary user story (Scenario A
  repeatable check + Scenario C honesty-by-reconciliation) runs end-to-end; every
  FR/NFR/SC is WP-owned with a committed, passing evidence artifact; drift
  dimensions D1/D4/D5 and the cross-WP JSON contracts are clean; security/PHI
  clean. **One note:** the live status docs still described the merged slice as
  "in progress / not yet merged."

## Finding F1 — Live status docs stale after merge (the WP that syncs them runs before the merge it must describe)

- **Drift.** Post-merge, `docs/shared/STATUS.md` §"Runtime build-and-use parser
  boundary" still read **"in progress"** and **"Still in flight … implemented on
  the mission lane and not yet merged,"** and `docs/shared/ROADMAP.md` item 5 read
  **"Loggable session substrate — in progress."** The slice was fully merged in
  `798493b`. Evidence (pre-fix): `STATUS.md:313`, `STATUS.md:334-336`,
  `ROADMAP.md:35`.

- **Root cause.** The live-doc-sync task (WP08 / T031) is owned by a work package
  that **completes and is reviewed before the mission merges.** At the only moment
  WP08 can run, the truthful tense *is* "in progress / on the lane / not yet
  merged" — so WP08 wrote exactly that, and its reviewer correctly approved it as
  accurate-at-the-time (the WP08 review even verified the docs said "in progress,"
  not a fabricated "done"). Nothing in the pipeline re-runs after the squash-merge
  to flip the tense to past. The sync WP **structurally cannot** describe its own
  merge.

- **Controls it passed (and why each missed):**
  1. *WP08 prompt / live-doc-sync task.* Missed: it fires pre-merge; "in progress"
     was the honest state then. Asking WP08 to write "merged" would have been a
     false claim at WP08 time.
  2. *WP08 per-WP review.* Missed: the reviewer's job was local correctness —
     "do the docs match reality now?" They did, mid-mission. Per-WP review owns a
     point-in-time snapshot, not the post-merge future.
  3. *Merge gate (`spec-kitty merge`).* Missed: the merge runs a stale-**assertion**
     check over claims, but has no step that reconciles a mission's own live status
     docs against the fact that the mission just merged. ("No likely-stale
     assertions detected" — it does not look at STATUS/ROADMAP tense.)
  4. *Mission-review.* Caught it — but as a detector at the very end, not a control
     that prevents it. The note is exactly what this audit converts into a gate.

- **The missing control.** A **post-merge live-doc reconciliation**: after
  `spec-kitty merge` records the WPs `done`, the mission's own live status docs
  (`STATUS.md`, `ROADMAP.md`) are re-read and any "in progress / on the lane / not
  yet merged" language about *this* mission is flipped to the merged/landed state
  with the merge commit. It fires **after the merge, owned by the orchestrator's
  close-out (not a pre-merge WP)** — because a pre-merge WP cannot truthfully
  describe its own merge. This is now a charter Fidelity Gate (see below) and a new
  registry dimension **D6**.

- **Generalizable lesson (the class of drift).** *Tense/lifecycle drift in
  self-describing live docs.* Any artifact a mission writes **about its own
  lifecycle state** ("in progress," "on the lane," "not yet merged," "shipping
  soon") is authored at a point strictly before the state it will end in, by a step
  that cannot see past the merge boundary. The honest pre-merge text becomes a lie
  the moment the merge lands, and no per-WP control owns the post-merge truth. The
  fix is never "make the pre-merge WP write the future" — it is a reconciliation
  step on the far side of the boundary.

- **Remediation status.** **Fixed** in this commit: `STATUS.md` and `ROADMAP.md`
  updated to the merged state (commit `798493b`, with the merge commit cited).
  Durable control landed: charter Fidelity Gate "Post-merge live-doc
  reconciliation" + registry dimension **D6** below.

## Unifying root cause (between-the-scopes theme)

Consistent with this method's standing lesson: per-WP review verifies local,
**point-in-time** correctness, and drift survives in the gap **between a WP and a
later pipeline event it cannot observe** — here, the squash-merge that changes the
very lifecycle state the WP just described. The live-doc-sync WP is not defective;
the pipeline lacked a control on the *post-merge* side of the boundary. This is the
same shape as the recurring "missions drop the live-doc-sync WP" lesson, sharpened:
even when the sync WP *is present and correct*, a pre-merge sync cannot describe
its own merge.

## Durable controls landed by this audit

1. **Charter Fidelity Gate — "Post-merge live-doc reconciliation"** added to
   `.kittify/charter/charter.md` §"Fidelity Gates".
2. **Drift dimension D6** added to the registry in
   `docs/building/agents/implement-review-drift-audit.md`.

## Evidence index

- Pre-fix drift: `docs/shared/STATUS.md:313`, `:334-336`; `docs/shared/ROADMAP.md:35`.
- Merge: commit `798493b` ("squash merge of mission"); `spec-kitty merge` output
  ("Recording merged work packages as done"; "No likely-stale assertions detected").
- WP08 correctness mid-mission: `tests/test_doctrine_build_and_use.py` (5 passed);
  WP08 review verified "in progress," not a fabricated "done."
- Fix: this commit updates `STATUS.md` §"Runtime build-and-use parser boundary"
  and `ROADMAP.md` item 5 to the merged state.

---

## Addendum — second mission-review (OpenCode), post-merge: failure-path + contract findings

A second independent mission-review of the same merged mission returned **FAIL**,
then **PASS-WITH-NOTES** after remediation. Its findings are recorded here as part
of the same close-the-loop (the charter requires auditing every non-clean verdict).
Fixes landed on master in `cc31030` (DRIFT-1/RISK-2/DRIFT-2/RISK-3/RISK-1) and
`3dd43b0` (RISK-4), each independently re-verified.

### Finding F2 — Ingest-failure path crashed instead of producing a captured, graded failed run (HIGH)

- **Drift.** The spec edge case (`spec.md:117-124`) + FR-080 promise that a parser
  that **raises** still yields a failed `ingest_run` step and a failed grader
  verdict ("no partial credit"). In the merged code a parser raising in
  `parse()` was caught in `ingest_runner.py` **before** `duck.initialize(warehouse)`
  ran, so the sandbox warehouse file was never created; the parent then did
  `duck.connect(warehouse_path, read_only=True)` (`repeatable_check.py:314`,
  `live_trial.py:457`) on a non-existent file → DuckDB raised → the run **aborted
  before** `record_ingest_provenance` and `finish_session`. The failed run was
  neither gradeable nor auditable — a direct miss against FR-080.
- **Controls that should have fired & why each missed.**
  1. *WP03 review* — verified the runner emits a schema-valid `status:error`
     envelope, but in isolation; it never wired that envelope through the parent
     harness. (Cross-worktree: the parent is WP06/WP07.)
  2. *WP05 grader review* — verified the `loaded` rule fails on 0 rows, but the
     test **constructed** an empty-warehouse connection directly; it never reached
     the parent code path that opens a *missing* warehouse.
  3. *WP06/WP07 review* — exercised the happy path and the dishonest-but-**successful**
     path end-to-end; **no end-to-end test drove a parser that raises.** The spec
     *named* this edge case, but no acceptance fixture exercised it.
  4. *My mission-review (first pass)* — re-ran the primary story (good + dishonest)
     but **also stopped at the successful paths** — it did not run the spec's named
     failure edge case end-to-end. This is the gap dimension **D7** names.
- **Missing control → D7** (below): a spec-*named* edge case must have an
  **end-to-end acceptance fixture**, exercised in the owning integration WP's
  Definition of Done *and* re-run at mission-review — not only the happy/contrast
  paths. The boundary-crossing-fixture gate required presence-vs-absence; D7
  sharpens it to **spec-enumerated edge cases**, not just the obvious two paths.
- **Remediation.** Shared helper `open_sandbox_warehouse_for_grading` materializes
  an empty (seeded, 0-row) warehouse when missing, so the grader returns a
  deterministic FAIL on all three rules with the `ingest_run` step + provenance
  recorded and the session finished. New end-to-end raising-parser/operator tests
  (`test_raising_parser_yields_captured_failed_run`,
  `test_raising_operator_yields_captured_failed_run`) proven non-hollow (fail
  pre-fix with the missing-warehouse crash, pass post-fix). Commit `cc31030`.

### Finding F3 — Cross-WP contract looseness (MEDIUM)

- **Drift.** (a) `skipped_rows` items were typed as any object in the envelope
  schema, but the grader credits a declared skip only via `row["raw_field"]` — a
  schema-valid skip without `raw_field` was invisible to honesty reconciliation
  (false `silent_drop`). (b) The shipped `run_live_trial` signature
  (`config, *, driver, operator, repo_root, parser_attr, source=None`) diverged
  from the contracted `(config, *, driver, operator)`.
- **Why it missed.** The WP07 per-WP review judged the extra `run_live_trial`
  params "sandbox plumbing, not signature drift" and waved them through — a
  contracted-signature change should have been a **contract amendment** under the
  charter's "justified deviation = drift signal" rule, applied at the per-WP gate.
- **Remediation.** Envelope schema now requires `skipped_rows[].raw_field`
  (grader-key agreement) with a crediting test; `contracts/live-trial-seam.md`
  reconciled to the shipped signature with the named-deferral rationale. `cc31030`.

### Finding F4 — Acceptance tests skipped (not failed) on missing committed fixtures (LOW)

- **Drift.** The decisive acceptance suites guarded on committed WP04 fixtures with
  `pytest.mark.skipif(...)` — sensible *in-flight* (a WP's test shouldn't fail
  because a sibling WP's fixtures aren't in its worktree yet), but post-merge a
  vanished committed fixture would **silently skip** the gate rather than block it.
- **Remediation.** Replaced with a hard `FileNotFoundError` at collection time
  (verified: a missing fixture now errors, not skips). `3dd43b0`.

### Durable control added by this addendum — registry dimension D7

**D7 — Spec-named edge case lacks an end-to-end acceptance fixture** added to the
registry in `docs/building/agents/implement-review-drift-audit.md`, plus a
sharpening of the charter "whole-story acceptance" gate to re-run the spec's
enumerated edge cases end-to-end, not only the happy and contrast paths.
