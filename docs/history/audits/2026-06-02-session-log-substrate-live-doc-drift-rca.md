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
