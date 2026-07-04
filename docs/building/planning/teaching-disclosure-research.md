# Teaching-layer disclosure research — evidence base (promoted, kept for history)

> **Status: PROMOTED 2026-07-04, kept for history.** The bounded artifact this
> note called for now ships as
> [`DISCLOSURE_RUBRIC.md`](../architecture/DISCLOSURE_RUBRIC.md) and the
> consuming role as [`HUMAN_FACING.md`](../architecture/HUMAN_FACING.md)
> (decision note [0015](../adr/0015-teaching-disclosure-and-human-facing-promotion.md),
> issues #35/#36). This page is retained as the *evidence base and rationale*
> that motivated them; the §"Open questions" below are answered in the promoted
> specs (one rubric dual-consumed; comprehension measured by an adversarial
> naive-reader restating the gist). Read the specs for the authoritative
> contract; read on here for *why*.

> **Read first:** [`DOCTRINE.md`](../../shared/DOCTRINE.md) (agent-first; design a
> level above). Companion reading:
> [`VISION.md`](../../history/product/VISION.md) Pillar 5 (Teaching),
> [`FULL_APP_DEVELOPMENT_PLAN.md`](../product/FULL_APP_DEVELOPMENT_PLAN.md)
> Phase 5 (interview + teaching MVP — the weakest-validated bet),
> [`STAGES.md`](../architecture/STAGES.md) §UI/Teaching,
> [`OPERATING_ROLES.md`](../architecture/OPERATING_ROLES.md) (narration/audit
> rules, the `teaching_gap` outcome), the
> [`research-trace-audit` skill](../../../src/premura/skills/research-trace-audit/)
> and its audit-consumer contract, and issue #12 (adversarial narration eval).

## Why this exists

When the **teaching / user-interaction agent profile** gets built — the runtime
persona that hands analytical findings *back to the human beneficiary* — it will
need a foundation in how to **disclose medical information to a non-expert**
without misleading them and without overclaiming. Today that profile has honesty
*guards* (the research trace, the audit-consumer contract, the PubMed narration
rules) but **no evidence base for the disclosure act itself**: how to phrase a
risk, an effect size, an uncertainty, a "we don't know," so a non-expert forms an
accurate belief rather than a confident wrong one.

The dev plan already names teaching as the **highest combined severity × likelihood
risk** in the project. This note is the upstream of de-risking it: ground the
teaching profile in known science before scoping the profile, not after.

## The reframe — narration first, custom UI later (not UI-free)

The repo's older language frames teaching as a UI concern ("dual-coded charts",
"the UI is the only stage that does presentation"). The correction is about
**sequencing, not absence**: the *first* surface is **text through a coding agent**
(Claude Code, OpenCode — no custom UI yet), and a **custom UI is a deliberate later
destination**. So for the work that comes first the real "interface" is the agent's
**narration**, and the research must be **presentation-agnostic**: a disclosure
rubric that holds for agent narration *now* and transfers to a custom UI *later*,
rather than layout/visualization findings that only pay off once a UI exists. The
deliverable feeds *how the agent communicates*, and it plugs directly into the
narration/disclosure machinery that already exists:

- The runtime agent never invents effect sizes — it calls a tool, receives
  `{effect, n, p, ci, is_imputed_pct, validity_status}`, and **narrates** that.
  This research governs the *narration* half of that contract.
- The [`research-trace-audit`](../../../src/premura/skills/research-trace-audit/)
  skill and the audit-consumer contract already judge an answer for
  search-effort disclosure, hidden refusals, and overclaiming. A teaching-disclosure
  rubric is the natural companion: it judges whether a *correct* answer was also
  *comprehensible and calibrated* for a non-expert.
- Issue #12 (adversarial narration eval) is the eval surface this research would
  give criteria to.

## What the research must produce (at altitude)

Per doctrine, the output is **not** a list of approved phrasings or a fixed FAQ.
It is a **disclosure rubric / contract** — a bounded set of rules the teaching
agent fills in per finding, plus the rule for adding a rule. Shape it like the
existing `AUDIT_RUBRIC.md`: closed criteria categories + an explicit extension
rule, not an enumeration.

Candidate fields to survey (the *inputs* to that rubric, not the rubric itself):

- **Risk communication / health literacy** — natural frequencies vs percentages
  (Gigerenzer), absolute vs relative risk, denominator neglect, framing effects.
- **Numeracy & risk literacy** — Peters; fuzzy-trace theory / gist-vs-verbatim
  (Reyna): non-experts reason on the *gist*, so the gist must be the true one.
- **Cognitive load** — the existing thread, **recast** as load on the *listener
  during disclosure* (sequencing, chunking, progressive disclosure), not screen
  layout. The starting corpus already exists: VISION Pillar 5 cites the sibling
  **immokalkul UI audit** (`~/repos/personal/immokalkul/docs/audits/UI/research.md`,
  the 8 frameworks — Nielsen, Sweller cognitive load, progressive disclosure, dual
  coding, JTBD, etc.). That survey is UI-framed; the work here is to **re-derive
  the narration-relevant subset** for an agent-text-first surface.
- **Shared decision-making / teach-back** — confirming comprehension instead of
  assuming it; how an agent does teach-back conversationally.
- **Calibrated uncertainty communication** — saying "we don't know" and "this is
  weak evidence" in a way a non-expert weights correctly, tied to
  `validity_status` / `is_imputed_pct` and the existing `surfaced unavailable`
  honesty rule.

## Constraints inherited from the project

- **Non-diagnostic, descriptive, local-first.** The teaching profile narrates the
  operator's own data and fetched literature; it never diagnoses, names a cause,
  or sends data off the machine. The disclosure rubric must hold that line — good
  communication must not become implied diagnosis.
- **Agent-mediated, not human-form-driven.** No assumption of a human-operated UI;
  the unit of study is the agent's spoken/written disclosure.
- **Composes with existing honesty contracts**, does not fork them: the trace
  audit-consumer contract and PubMed narration rules stay authoritative; this adds
  a comprehension/calibration layer on top.

## Open questions (resolve at scoping)

- Is the deliverable one rubric, or two (a *narration* rubric for the agent + an
  *eval* rubric for issue #12 that scores against it)?
- How is "comprehension" measured for an agent eval without a human in the loop —
  an adversarial "naive reader" model that must restate the gist correctly?
- Where does the rubric live — alongside `research-trace-audit` as a sibling skill,
  or as a contract the teaching profile reads, or both?
- How much of the existing cognitive-load research carries over vs. needs redoing
  for the disclosure (listener-load) frame?

## Gating

1. The teaching / interview layer (Phase 5) is scoped or at least committed — this
   research is its upstream, not a standalone deliverable.
2. The intake source-adaptation work (the current open queue item per
   [ROADMAP](../../shared/ROADMAP.md) §"Profile and intake") is not blocked on this
   and should not wait for it.
3. Promote by turning the surveyed evidence into a bounded disclosure rubric, then
   `/spec-kitty specify` the teaching profile against it.
