---
work_package_id: WP06
title: Live-doc sync (pre-merge tense)
dependencies:
- WP04
requirement_refs:
- FR-007
planning_base_branch: master
merge_target_branch: master
branch_strategy: Planning artifacts for this feature were generated on master. During /spec-kitty.implement this WP may branch from a dependency-specific base, but completed changes must merge back into master unless the human explicitly redirects the landing branch.
subtasks:
- T019
- T020
- T021
agent: "claude:fable:implementer:implementer"
shell_pid: "80123"
history:
- date: '2026-06-11T14:19:42Z'
  action: created
  by: /spec-kitty.tasks
authoritative_surface: docs/shared/
execution_mode: code_change
owned_files:
- docs/shared/STATUS.md
- docs/shared/CHANGELOG.md
- docs/shared/ROADMAP.md
tags: []
---

# WP06 — Live-doc sync (pre-merge tense)

## Objective

Bring the three live docs (`docs/shared/CHANGELOG.md`, `docs/shared/STATUS.md`,
`docs/shared/ROADMAP.md`) in line with what this mission builds — in **honest
pre-merge tense**. Charter drift dimension D6 is explicit: this WP runs and is
reviewed BEFORE the merge, so it structurally cannot describe its own merge.
Write "in progress / on the mission lanes / not yet merged"; the
orchestrator's post-merge close-out (NOT this WP) flips tense and adds the
merge commit. Do not write the future.

## Context you need

- Read first: the charter's Fidelity Gates §"Post-merge live-doc
  reconciliation" (D6) — it defines this WP's tense rule.
- Read each owned doc fully before editing (they have established voice,
  entry formats, and capped-length conventions — STATUS is a capped snapshot,
  CHANGELOG is the dated record, ROADMAP is forward-looking; facts are
  single-homed across them, so don't duplicate a fact all three places).
- What exists when you run (WP04 merged into your lane's base): the scoreboard
  tier axis (WP01), the renamed-field rule (WP02), the tool contract module
  (WP03), the loop + entry point (WP04). WP05 (edge fixtures + gated test) may
  still be in flight on a parallel lane — describe it as part of the mission's
  scope, not as landed, unless your lane base contains it.
- Source material for accurate wording: mission `spec.md` (the corrected
  premise — context quality, not capability floor), `research.md`,
  `contracts/tool-loop-tier.md`, and the promoted draft's banner at
  `docs/building/planning/tool-loop-live-trial-tier.md` (already updated at
  specify time — do not edit it; it is not in your owned files).
- Vocabulary: use the maintainer vocabulary from `CONTEXT.md` §"Maintainer
  mental model" — plain English over jargon; "tier" = a separately-scored way
  of running the live trial.

## Subtasks

### T019 — CHANGELOG entry

**Purpose**: the dated record of what this mission adds.

**Steps**:
1. Read `docs/shared/CHANGELOG.md` and match the existing entry format
   (date-keyed, mission-referenced — see the 2026-06-04 and 2026-06-11
   entries for shape).
2. Add a 2026-06-11-or-later entry for mission
   `tool-loop-live-trial-tier-01KTVG26` (pre-merge tense: "adds", "in
   progress on mission lanes"):
   - the tool-loop live-trial tier: multiturn, tool-using path over the same
     sandbox/runner/grader/store machinery, scored as its own tier
     (`tier="tool_loop"`) alongside — never replacing — the one-shot floor;
   - the corrected premise it implements (the 2026-06-04 audit's reversal:
     harness context quality, not a capability floor) with a link to the
     audit at `docs/history/audits/2026-06-04-live-trial-tool-loop-14b-followup.md`;
   - the sharpened renamed-field declared-gap rule (consumed-under-rename must
     be declared; now stated in both drawer prompts and pinned by a fixture
     test);
   - containment unchanged: local-only endpoint, synthetic-only persistence,
     `live_trial` marker (never blocks CI).
3. Keep it one entry, compact, link-bearing (mission dir + audit), no
   requirement-ID jargon — plain English.

**Validation**: entry reads correctly in pre-merge tense; links resolve
(relative paths correct from `docs/shared/`).

### T020 — STATUS.md update

**Purpose**: the capped current-state snapshot stays truthful.

**Steps**:
1. Read `docs/shared/STATUS.md` fully; find where the live-trial/harness
   surface is described (the TL;DR and/or shipped-surface sections — the
   2026-06-04 reframe already mentions the live-trial seam and the one-shot
   tier).
2. Update minimally (STATUS is capped — amend in place, don't append a
   parallel paragraph): the live trial now has TWO tiers in the codebase —
   the shipped one-shot floor and the tool-loop tier **in progress on this
   mission's lanes (not yet merged)** with a pointer to
   `kitty-specs/tool-loop-live-trial-tier-01KTVG26/` for detail.
3. If STATUS carries a "what's next / in flight" line that still says tier
   work is parked/queued behind the intake gate, fix it (the gate cleared
   2026-06-11) — that's exactly the stale-claim class this WP exists to catch.

**Validation**: no sentence in STATUS claims the tool loop is merged/shipped;
no sentence still claims it is parked.

### T021 — ROADMAP reconciliation

**Purpose**: the forward-looking doc stops pointing at this work as future.

**Steps**:
1. Read `docs/shared/ROADMAP.md`; locate every mention of the tool-loop tier
   / live-trial tier work ("tier work sits behind...", "next experiments",
   the §"Profile and intake" gate language referencing it, if any).
2. Reconcile each: the gate is cleared and the tier mission is **specified,
   planned, and in implementation** (pre-merge tense; name the mission slug).
   What stays forward-looking, keep forward-looking (e.g. anything the spec
   lists as out of scope: multi-model tournaments, tier auto-selection,
   frontier drivers — those remain future and may be worth a named bullet so
   the boundary is recorded).
3. Cross-check against the other two docs that no fact got duplicated into
   two homes (single-home rule from the docs-restructure mission).

**Validation**: zero remaining "parked behind the intake gate" language
anywhere in the three docs; out-of-scope items still listed as future, not
implied as part of this mission.

## Definition of Done

- [ ] CHANGELOG entry added in the established format, pre-merge tense,
      linking mission dir + motivating audit.
- [ ] STATUS reflects two tiers (one shipped, one in progress on lanes), no
      stale "parked" claims, cap respected.
- [ ] ROADMAP reconciled; out-of-scope future work still clearly future.
- [ ] No edits outside the three owned docs; no fact duplicated across them;
      nothing written in post-merge tense (D6).

## Risks / notes for the reviewer

- Reviewer: D6 is the gate — scan every added/changed sentence for future or
  merged tense about THIS mission ("landed", "shipped", "merged") and reject
  on sight; "in progress / not yet merged" is the only honest claim a
  pre-merge WP can make about itself.
- Reviewer: check the single-home rule — the audit-reversal story belongs in
  the CHANGELOG entry (with the audit link), not retold in STATUS and ROADMAP.
- This WP has no code to test; the quality gates are reading gates. Run
  `uv run pytest -q` anyway to confirm a docs-only diff (zero test deltas).

## Activity Log

- 2026-06-11T19:08:04Z – claude:fable:implementer:implementer – shell_pid=80123 – Started implementation via action command
