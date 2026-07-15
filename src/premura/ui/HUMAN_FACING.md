# The `human_facing` role and the interview flow

> Status: **authoritative specification** for Premura's Stage 4 human-facing surface — the `human_facing` operating role's contract plus the first-run interview flow. The locked decisions are decision note [0015](../../../docs/building/adr/0015-teaching-disclosure-and-human-facing-promotion.md).
>
> Read first: [`DOCTRINE.md`](../../../docs/shared/DOCTRINE.md) (agent-first; guide don't enumerate). Companion: [`OPERATING_ROLES.md`](OPERATING_ROLES.md) (the role registry this fills in, the answer-audit gate it hands off to), [`STAGES.md`](../../../docs/building/architecture/STAGES.md) §UI (Interview + Teaching), [`DISCLOSURE_RUBRIC.md`](../skills/human-facing-teaching/DISCLOSURE_RUBRIC.md) (the #35 rubric this role consumes as advisory-to-drafting).

## What this is

`human_facing` is already one of the five reference roles registered in `premura.ui.roles` ([OPERATING_ROLES.md](OPERATING_ROLES.md) §Role declarations). Its declaration today is a one-liner: _"never silently stores lifestyle context."_ This spec gives it a full contract — what it may say, when it must hand off to `answer_audit`, how it consumes the #35 disclosure rubric — plus the **interview flow** that runs before any analysis is shown (interview before teaching). It is Stage 4 only: no `hp.*` reads, no direct engine calls (STAGES UI-layering rule).

## Part A — the `human_facing` role contract

> **Implementation.** This contract is implemented in `premura.ui.roles` (the four numbered boundaries + the `present_answer`-only surface), with the bundled `human-facing-teaching` skill (`src/premura/skills/human-facing-teaching/`) applying the rubric self-check before `present_answer`. The track registry is `premura.ui.interview_tracks` and the phase-1 routing surface is the `interview_route` MCP tool with an engine-backed route resolver; the later phases (phase-2 grounding orchestration, phase-3 narration) are not yet built.

Filling the five registry-declaration fields (OPERATING_ROLES.md §Role declarations):

- **`role_id`**: `human_facing`
- **`job`**: Conduct the first-run interview, route the human's goal to analysis, and narrate findings back in calibrated, non-expert language.
- **`surfaces`**: the default MCP interview/profile-capture tools (`profile_context_record`, the interview-track tools below), `present_answer` for every health-interpreting draft. **Never** the analytical tools, the warehouse, or the operator SQL surface.
- **`handoff_outputs`**: a routing decision (interview → analysis), a draft answer submitted to `answer_audit`/`present_answer`, and lifestyle-context capture proposals (never a silent write).
- **`boundaries`** (the assertion boundary):
  1. Never presents a health-interpreting draft except through `present_answer` — inherits the blocking gate unchanged.
  2. Never diagnoses, names a cause, or asserts significance; narrates the tool verdict (`{effect,n,p,ci,is_imputed_pct,validity_status}`), never invents an effect size.
  3. Never silently stores lifestyle/profile context — capture is a proposal the human confirms, one allowlisted fact at a time (DOCTRINE §8).
  4. Never sends data off-machine or writes public GitHub (RUNTIME_AGENT human-in-the-loop rule).

**Handoff to `answer_audit`.** No new gate. `human_facing` is the role the orchestrator returns an audit-failed draft to for the one revision loop (OPERATING_ROLES.md check 4); on conflict the fixed priority `answer_audit > analysis > human_facing` holds — comprehensibility never overrides evidence.

**Disclosure-rubric consumption (#35), locked: advisory-to-drafting only.** The [#35 rubric](../skills/human-facing-teaching/DISCLOSURE_RUBRIC.md) judges whether a _correct_ answer is also _comprehensible and calibrated_. `human_facing` consumes it as an **advisory input to drafting**, not a second gate: it shapes how the role phrases risk, effect size, and "we don't know" before submitting to `present_answer`. The rubric stays authoritative for comprehension; it does **not** fork the deterministic gate. This mirrors the AI-rubric-on-top stance the answer-audit gate already takes (OPERATING_ROLES.md). A single rubric criterion could be promoted to a `present_answer` gating check later, but only by its own decision note — not in v1.

## Part B — the interview flow (bounded abstraction, not a question list)

Per DOCTRINE rule 2 this is **phases + invariants + a track registry with an add rule**, never an enumerated question script.

### Phases

1. **Direction** — establish _what direction_ the human wants (their goal), before any metric is shown. Resolves to a **track** (below), which yields a routing decision into the signal selector. No "analyse everything at once" default.
2. **Grounding** — capture only the baseline profile facts the chosen track needs, through agent-mediated one-fact-at-a-time capture against the closed profile allowlist (DOCTRINE §8). Missing facts are surfaced, never invented.
3. **Route & teach** — hand the routing decision to `analysis`; narrate the returned findings under the Part A boundaries and the #35 rubric.

### Invariants (hold across every phase, every generated question)

- **Interview before metrics.** No analytical number is shown before phase 1 resolves a direction.
- **Agent-mediated capture.** Every fact the interview records goes through the capture tools as a confirmed proposal; the interview never writes a free-text profile store and never renders a human form.
- **Presentation-agnostic.** The flow is a sequence of agent utterances over a text/coding-agent surface today; nothing here assumes a screen, widget, or layout. It must transfer unchanged to a later custom UI.
- **One question at a time, gist-first.** Each question is generated to advance exactly one unresolved slot; phrasing follows the #35 rubric.
- **No silent enrichment.** The interview may _propose_ capturing a lifestyle fact it overheard; it stores nothing without confirmation.

### Question generation (the rule, not the questions)

The interview does not read a fixed script. Given (current phase, resolved slots, chosen track's required slots), it **generates** the next question to close the highest-priority unresolved slot, phrased per the #35 rubric. The _only_ enumerated things are: the phase order (above) and each track's **required-slot set** (declared in the registry, below). Everything a human is actually asked is agent judgment bound by these invariants.

### The track registry (locked: bounded-open, gated on a resolving route)

Health directions live in a **bounded-open registry** `premura.ui.interview_tracks`, mirroring `premura.ui.improvement_kinds` (open registry + add rule), **not** a hardcoded `if direction == "sleep"` ladder and **not** a fixed 8-item list. A track declaration carries:

- `track_id` — functional direction id (e.g. `sleep`, `cardio`).
- `required_slots` — the profile/context slots phase 2 must fill for this track.
- `signal_route` — the signal-selector routing this direction resolves to.

**Admission rule (locked).** An agent may register a new track on the spot, with no central edit, **iff its `signal_route` resolves to a registered signal selector**. A track whose route does not resolve is **refused at registration** — an unresolvable direction is a dead end that would let an agent promise a "hydration deep-dive" with nothing behind it. This is guide-don't-enumerate (the add-rule, not the list) _with_ the health safety rail (no direction without analysis behind it).

The 8 directions STAGES lists (sleep, cardio, metabolic, stress, mental, gut, lab, overview) are **seed instances** — examples of the contract, not a closed set.

_Rejected alternative: a closed allowlist synced to STAGES' 8._ Simpler and strictly safe, but it hardcodes the list DOCTRINE says to replace with a rule and forces a repo PR for every new direction — the friction that pushes agents to "invent their own solution anyway" (the DOCTRINE failure mode). The resolving- route gate keeps the safety of the allowlist (no dead-end direction) without its enumeration.

## Part C — teaching scope (smallest coherent surface)

**In scope:** phases 1–3 over the text/MCP surface; the track registry with the STAGES-8 as seeds; `human_facing` narration bound by Part A + the #35 rubric as advisory. Reuses `present_answer`/`answer_audit` and `profile_context_record` unchanged — no new gate.

**Out of scope (not built):** dual-coded charts and any custom-UI affordance (later-UI, STAGES); a teach-back/comprehension-check loop (no eval surface yet, issue #12); lifestyle-context capture as a stored domain (a separate OPERATING_ROLES concern); the #35 rubric as a _gating_ check; the adversarial narration eval surface (issue #12).

## Implementation notes

- The track registry `premura.ui.interview_tracks` sits beside `premura.ui.roles`. Its route resolver is injected (`set_route_resolver`; the default rejects all, so an un-wired registry admits nothing) because Stage 4 imports no engine code.
- The `interview_route(direction)` MCP tool resolves a direction to its track (`{track_id, signal_route, required_slots, missing_slots}`) and refuses a dead-end direction; the engine-backed resolver (`server.install_interview_route_resolver`) is installed at MCP startup, so a route resolves iff the engine signal selector (`engine.list_by_domain`) has a signal behind that direction. `missing_slots` proposes which allowlisted profile facts phase-2 grounding should capture; the tool writes none itself.
