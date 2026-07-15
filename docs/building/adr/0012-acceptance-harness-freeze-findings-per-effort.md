# The acceptance harness is frozen at current capability; further harness work must be paid for by findings about Premura

> **Status:** Accepted — 2026-06-12

Decided 2026-06-12, the day the harness first ran end-to-end with real local models.

The acceptance evaluation exists to test the project's central bet — that Premura is operable by agents — and to produce findings about _Premura_. By v0.4.0 the investment ratio had inverted: five of the seven consolidated overnight missions (m2–m6: turn capture, judge, improvement hook, fixture generator, answer grading) built the test rig rather than the app, and the post-release fix day (#25/#26 + two more defects) was spent entirely inside the rig. Total findings about Premura itself so far: one — cheap models learn the parser contract fine; their bottleneck is tool-call transport, not the contract design. The rig had grown its own observability stack (a judge that judges the test, an improvement hook that proposes improvements to the test) — the classic meta-work trap, amplified by the overnight runner's natural preference for synthetic, PHI-free, additive missions.

The decisions:

- **Freeze the harness at current capability.** It works end-to-end (fixture generation → tool-loop operator → deterministic grade → session log → judge → improvement proposals). No new tiers, task kinds, judge refinements, or rubric/playbook growth until the rig produces a finding about Premura that we act on. Known harness defects (#24 generated-scenario probe resolution, #27 cold-model availability probe) are fixed only when they block a run someone actually needs.
- **The findings-per-effort rule.** Any proposed harness work must name the Premura finding it is expected to produce, and is judged by that yield — not by the rig's own completeness. "The harness would be more capable" is not a justification.
- **The deterministic floor stays.** The cheap objective layer (`repeatable_check`, the contract gates, the default-suite tests) is kept and maintained as normal regression infrastructure — it is not the expensive part and it guards the rig against rot while frozen.
- **Priority returns to the app.** Next work targets Premura proper — first #23 (supplement/medication recall ingest, which feeds `condition_paired_t_test` with real declared episodes) — and live dogfooding sessions, which are the cheapest and most informative acceptance evaluation available: the operator using Premura on their own data through a coding agent, with real stakes.
- **The overnight runner respects the freeze.** Overnight mission selection must not default to harness work because it is safe; safe-but-meta loses to app-but-supervised.

This does not retract the acceptance evaluation's destination (CONTEXT.md §"Acceptance evaluation", issue #10): the live, judge-graded end-to-end evaluation remains the long-term gate. The freeze is about _sequencing_ — the rig is good enough to start yielding; building it further before it yields is the failure mode this note exists to prevent.
