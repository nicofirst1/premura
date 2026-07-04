# Teaching-disclosure rubric and human_facing role: the locked decisions

A 2026-07-04 maintainer design-interview promoted the parked teaching-disclosure
evidence base ([`teaching-disclosure-research.md`](../planning/teaching-disclosure-research.md))
and the issue #36 draft into two specifications
([`DISCLOSURE_RUBRIC.md`](../architecture/DISCLOSURE_RUBRIC.md),
[`HUMAN_FACING.md`](../architecture/HUMAN_FACING.md)), run as one combined design
window (issues #35 + #36). Four decisions were locked. (1) **One rubric, dual-consumed** —
`DISCLOSURE_RUBRIC.md` is a single artifact read both as the `human_facing`
role's drafting self-check and as issue #12's adversarial narration eval, not a
narration rubric split from a separate eval rubric; it follows the sibling
`AUDIT_RUBRIC.md` shape (four closed dimensions + an add-a-criterion rule) and
never re-judges the honesty the answer-audit gate already owns. Comprehension is
measured without a human by an adversarial naive-reader model that restates the
gist and is scored against the verbatim tool output on the `gist_fidelity`
dimension (the mechanism issue #12 implements). (2) **The rubric is
advisory-to-drafting, not a second gate** — `human_facing` consumes it to shape
phrasing before `present_answer`; the deterministic answer-audit gate stays the
only gate, mirroring the AI-rubric-on-top stance, promotable to a gating check
only by its own later note. (3) **Interview tracks are a bounded-open registry
gated on a resolving route** — an agent registers a new `interview_track` with no
central edit iff its `signal_route` resolves to a registered signal selector; an
unresolvable direction is refused at registration. This is guide-don't-enumerate
(the add-rule, not the list) with the health safety rail (no direction promised
without analysis behind it); the closed-allowlist alternative was rejected for
hardcoding the list DOCTRINE says to replace with a rule. The STAGES-8 directions
ship as seed instances. (4) **The teaching MVP cut-line** is phases 1–3 over the
text/MCP surface reusing `present_answer`/`answer_audit`/`profile_context_record`
unchanged; dual-coded charts, a teach-back comprehension loop, rubric-as-gate,
and the issue #12 eval surface are named-deferred. Concept lineage: decision note
0013 (operating-roles promotion pattern); build-and-use boundary unchanged.
