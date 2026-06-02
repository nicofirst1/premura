# Implement-Review Drift Audit — Methodology

> Status: live reference. A reusable method for auditing a completed
> spec-kitty implement-review session to find **why** drift or risk reached the
> merged record — not just that it did.
>
> Companion to the post-merge `spec-kitty-mission-review` (which finds *what*
> drifted). This doc finds the *cause* and the *missing control*. Read
> [`docs/shared/DOCTRINE.md`](../../shared/DOCTRINE.md) first — this methodology
> is itself written a level above (a bounded dimension registry with a rule for
> adding to it, not a fixed checklist).

## Why this exists (agent-first)

Premura is operated and extended by AI agents through the spec-kitty
implement→review→merge loop. When a mission-review later finds a drift (a
fictional identifier, stale metadata, an unmet measurable requirement), the
useful question is not "fix it" but **"which control in the pipeline should have
caught this, and why didn't it?"** Answering that turns a one-off fix into a
durable improvement to the prompts, contracts, and review scope every future
mission inherits.

The recurring lesson behind every drift found so far: **per-WP review verifies
local correctness and data-contract consistency, but the pipeline has no step
that verifies cross-*system* fidelity, reconciles frozen metadata after a gating
decision, or owns a mission-level measurable requirement that no single WP
owns.** Drift survives precisely in the gaps *between* WP scopes and *between* a
WP and the production system.

## When to run

- After a `spec-kitty-mission-review` returns **PASS WITH NOTES** (or worse) —
  audit each note to its cause.
- Periodically across several merged missions, to find a *class* of drift the
  prompts/contracts keep re-admitting.
- Any time a reviewer accepts a "justified deviation" — a deviation that is
  correct but unreconciled is a drift signal, not a closed item.

## Inputs

For the mission(s) under audit, gather:

- `kitty-specs/<mission>/spec.md`, `plan.md`, `quickstart.md`, `contracts/`,
  `data-model.md`, `lanes.json`, `tasks.md`.
- Every `tasks/WP*.md` (frontmatter `requirement_refs` / `owned_files` and body).
- Every `tasks/WP*/review-cycle-*.md` and `status.events.jsonl`.
- The merge commit and the per-WP diffs (`git show`, `git log --oneline`).
- The **production surfaces** the artifacts claim to describe (e.g. the live MCP
  tool registry in `src/premura/mcp/entrypoint.py`, store boundaries, migrations).

## The audit procedure — trace every finding to its missing control

For each drift/risk from the mission-review (or each you discover), produce a
finding by tracing it through five questions. Do not stop at the symptom.

1. **Introduction** — Where and when did it enter? (Which WP, which commit.) Did
   the WP *prompt/contract create the gap* (no authoritative source named) or did
   the implementer deviate despite guidance? Quote the prompt/contract lines.
2. **Controls that should have fired** — Walk the pipeline the artifact passed
   through: WP prompt validation block → contract constraints → per-WP review
   checklist → fix-cycle re-review → merge gate. Name each control it passed.
3. **Why each missed** — For every control in step 2, state the specific reason
   it did not catch the drift (out of scope, no enum/registry pin, frozen
   artifact, no owning WP, qualitative-not-measurable check).
4. **The missing control** — Name the single check that would have caught it and
   the *exact* place it should fire (a named prompt section, a contract field
   constraint, a review dimension, or a new reconciliation/acceptance gate).
5. **Generalizable lesson** — State the *class* of drift, so the fix generalizes
   beyond this instance. Map it to a dimension in the registry below (or add one).

Ground every claim with `file:line` + commit hashes. A finding with no evidence
index is not done.

## Drift-dimension registry (bounded — extend by the rule, don't enumerate)

Each dimension is a *lens* on where drift hides between scopes. Seeded from real
findings; **add a dimension via the rule at the end** rather than treating this
list as closed.

### D1 — Cross-system identifier fidelity
- **Checks:** every identifier in test data / fixtures / examples that names a
  *real-system* thing (tool name, metric id, route, CLI verb, schema key,
  config flag) resolves to the production source that actually emits it.
- **Originates:** synthetic test data authored against a *data contract* that
  types the field as a bare `string` with no registry pin.
- **Catching control:** a review step (or test) asserting `identifier ∈ live
  registry`. Trace the field to the production code, not just to a schema.

### D2 — Frozen-metadata reconciliation after a gating WP
- **Checks:** a contingent/gated WP's `owned_files` / `write_scope` /
  `requirement_refs` still match reality after the gating WP's
  adopt/defer/reject outcome changed the downstream scope.
- **Originates:** task artifacts are frozen at `tasks-finalize`, written
  optimistically; a later gating WP invalidates a dependent's pre-written scope
  and nothing regenerates it.
- **Catching control:** a reconciliation gate at the boundary *after the gating
  WP is approved and before its dependents dispatch* that re-validates the
  dependents' metadata against the gate outcome. Treat a reviewer's "justified
  deviation" as a *metadata-correction trigger*, not a wave-through.

### D3 — Measurable NFR/SC ownership and evidence
- **Checks:** every measurable non-functional requirement / success criterion
  appears in some WP's `requirement_refs` **and** names a *committed* evidence
  artifact in that WP's Definition of Done.
- **Originates:** a measurable claim phrased as contract prose, an "independent
  test," or a quickstart manual step — owned by no WP, self-executed by nothing.
- **Catching control:** a decomposition gate at `/spec-kitty.tasks` mapping each
  measurable NFR/SC to an owning WP + artifact; and a mission-acceptance gate
  that demands the artifact before PASS, not qualitative satisfaction.

### D4 — Derived-representation basis fidelity (compute basis vs. report basis)
- **Checks:** when a tool computes its result from a *derived* representation of
  an input (a local calendar day from a UTC timestamp + tz; a canonical id from a
  raw label; a rounded/bucketed key; a unit-converted value), every piece of
  *reported metadata describing that result* (spans, day/key labels, group counts,
  provenance) is derived from the **same** representation — not recomputed from the
  raw source on a second path.
- **Originates:** two divergent paths in (or across) the producing WP — the
  compute path uses the derived value while the report path recomputes from raw
  (`ts.date()` instead of `local_calendar_day(ts, tz)`). The divergence is
  invisible because acceptance fixtures use inputs where raw ≡ derived
  (naive-noon, tz=UTC timestamps), so the fixture distribution never crosses the
  boundary production inputs cross.
- **Catching control:** a *representational-divergence fixture* — at least one
  acceptance fixture per derived representation where raw ≠ derived (e.g. a
  `local_tz` that shifts an observation across local midnight), asserting reported
  metadata equals the *derived* basis. Fires in the producing WP's Definition of
  Done **and** in a contract field-spec that names each metadata field's basis
  ("spans are local calendar days") so reviewers have a pin. Corollary: when a
  downstream WP is told to *consume the producer's bundle without re-deriving* (a
  dead-code/seam control, see this method's seam guidance), the **producing** WP's
  review owns the bundle's field-basis — downstream deliberately won't re-check it.

### D5 — Gated-decision capability sufficiency (does the chosen approach cover every downstream FR clause?)
- **Checks:** when a gating/research WP selects an approach (provider, library,
  primitive, schema, vocabulary) that *other* WPs must implement against, the
  decision enumerates how that approach satisfies **each clause of each FR the
  downstream WPs own** — especially "X **when available**" completeness clauses
  — not merely that one path was chosen. A positive-path acceptance fixture
  exists for every availability clause (provider supplies X → X is returned),
  *distinct from* the negative/missingness fixture.
- **Originates:** the gating WP carries only its *own* `requirement_refs` (it
  was scoped to *make the decision*, not to *deliver the feature*), so its
  review verifies decision **clarity/singularity** but not **coverage** of the
  downstream FRs, which live in a different WP. The implementing WP then picks
  the *minimum* primitive that passes the clauses it bothered to test and defers
  the rest in a code comment. The miss is doubly masked because a *missingness*
  requirement (FR: "absent → explicit None") and an *availability* requirement
  (FR: "present → returned") are complementary halves of the same field:
  satisfying the missingness half with an **always-None** field looks like the
  field is "handled," so a missingness-only test passes green while the
  availability path is **entirely unimplemented**.
- **Catching control:** (1) the gating WP's `Decision` section must include a
  **clause→primitive coverage map** for every downstream FR clause (filed
  against those FRs, not only the gate's own `requirement_refs`), and the
  gating-WP review verifies *coverage*, not just *clarity*; (2) backstop in the
  implementing WP's Definition of Done — a **positive-path fixture per
  availability clause** (provider returns X ⇒ assert X surfaced), separate from
  the missingness fixture; (3) a code comment that *defers a spec-required
  behavior* ("EFetch deferred; out of first slice") is a **deviation requiring a
  spec amendment or rejection**, never a review-note acceptance (this is the
  "justified deviation = drift signal" rule, applied at the per-WP gate instead
  of only at audit time).

### D6 — Self-describing live-doc lifecycle tense (a pre-merge sync cannot describe its own merge)

- **Checks:** every live status/roadmap doc a mission writes **about its own
  lifecycle state** ("in progress", "on the lane", "not yet merged", "landing
  soon") reads the *post-merge* truth — flipped to merged/landed with the merge
  commit — not the pre-merge tense the sync WP authored.
- **Originates:** the live-doc-sync WP completes and is reviewed **before** the
  squash-merge. At the only moment it can run, the honest text is "in progress";
  its reviewer correctly approves that as accurate-at-the-time. Nothing re-runs on
  the far side of the merge to flip the tense, so the honest pre-merge sentence
  becomes a stale claim the instant the mission merges. (Distinct from "missions
  drop the live-doc-sync WP": here the WP is *present and correct* — the gap is the
  merge boundary it cannot see past.)
- **Catching control:** a **post-merge live-doc reconciliation** owned by the
  orchestrator's close-out (NOT a pre-merge WP), firing after `spec-kitty merge`
  records the WPs `done`: re-read the mission's own `STATUS.md`/`ROADMAP.md`, flip
  any "in progress / on the lane / not yet merged" language about *this* mission to
  the merged state with the merge commit. Never fix this by asking the pre-merge WP
  to write the future. Backed by the 2026-06-02 session-log-substrate finding
  (`docs/history/audits/2026-06-02-session-log-substrate-live-doc-drift-rca.md`).

### D7 — Spec-named edge case lacks an end-to-end acceptance fixture

- **Checks:** every edge case the spec **explicitly enumerates** (an "Edge cases"
  bullet, a Scenario step, a "X → fail / X → refuse" clause) has an **end-to-end**
  acceptance fixture that drives it through the real production path — not only a
  unit test of one component in isolation, and not only the happy path plus one
  contrast path.
- **Originates:** the edge case is *named in the spec* but *owned by no WP's
  fixtures*. Each component WP tests its own slice (the runner emits an error
  envelope; the grader fails on 0 rows) — but in isolation, with constructed
  inputs. The integrating WP (and the first mission-review) exercises the obvious
  paths (good + dishonest, present + absent) and **stops before the spec's failure
  edge case**, because "two paths green" reads as "the story works." The bug hides
  on the path nobody wired end-to-end. (Real finding: a parser that *raises*
  crashed the run at a missing-warehouse open instead of producing the
  spec-promised captured, graded FAIL — every component handled it locally, no test
  drove it through the parent harness. F2 in
  `docs/history/audits/2026-06-02-session-log-substrate-live-doc-drift-rca.md`.)
- **Catching control:** at `/spec-kitty.tasks`, map each spec-enumerated edge case
  to an owning integration WP's Definition of Done as a **named end-to-end
  fixture**; and at mission-review, re-run the spec's edge-case list end-to-end (a
  superset of the happy/contrast paths), treating an unexercised named edge case as
  a coverage defect, not a pass. This sharpens the "Boundary-crossing acceptance
  fixtures" gate (presence-vs-absence) to **spec-enumerated edge cases**.

### Rule for adding a dimension

A new dimension is admissible iff it: (1) names a gap that lives **between** WP
scopes, or **between** a WP and a production system, or **between** a WP and a
mission-level requirement — i.e. somewhere no single per-WP review owns; (2)
states where the drift *originates* and the *one control* that would catch it
and where it fires; (3) is backed by at least one real finding (existing or new)
that the dimension would have caught. A dimension that merely restates a
per-WP local-correctness check (the thing review already does well) is **not**
admissible — those are not where drift hides.

## Output contract — what the results file must contain

Write results to a dated file under `docs/history/audits/` (one per audited
session or batch). It must contain:

- The audited mission(s), merge commit, and the mission-review verdict.
- One finding per drift, each with: drift, root cause(s), controls passed, why
  each missed, the missing control + where it fires, the mapped/created
  dimension, and an evidence index (`file:line` + commits).
- The unifying root cause across findings (the between-the-scopes theme).
- Remediation status per finding (fixed + commit, or open + owner).

## Relationship to `spec-kitty-mission-review`

Mission-review is the *detector* (spec→code fidelity, drift, risk, security on
the merged result). This methodology is the *post-mortem*: it consumes
mission-review's findings and asks why the loop admitted them, then proposes the
control — usually a change to a WP prompt's validation block, a contract field
constraint, or an added pipeline gate — so the next mission cannot repeat it.

## Where durable controls land

spec-kitty is an external orchestrator Premura *consumes*, not code this repo
owns, so durable controls are encoded in the layer Premura controls on top of
it. The standing, cross-mission gates this method has produced live in the
**Fidelity Gates** section of `.kittify/charter/charter.md` — the
boundary-crossing-fixture rule, whole-story acceptance at mission-review,
risks-and-deferrals-are-not-waivers, and the requirement to run this audit after
any non-clean verdict. When an audit names a new durable control, add it there
(or to the contract / WP-prompt it pins), and add any new drift *dimension* to
the registry above. The charter holds the rule; this doc holds the evolving
dimensions.
