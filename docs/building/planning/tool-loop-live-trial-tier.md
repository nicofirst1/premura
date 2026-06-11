# Tool-loop live-trial tier — mission spec (draft, promoted)

> **Status: PROMOTED 2026-06-11.** The queue gate cleared (intake
> source-adaptation shipped, first real vendor parser merged 2026-06-11) and this
> draft was promoted via `/spec-kitty.specify` to mission
> `tool-loop-live-trial-tier-01KTVG26` — the authoritative spec is now
> [`kitty-specs/tool-loop-live-trial-tier-01KTVG26/spec.md`](../../../kitty-specs/tool-loop-live-trial-tier-01KTVG26/spec.md).
> This document remains as the historical scoping record (corrected premise and
> design rationale); do not extend it.

> **Read first:** [`DOCTRINE.md`](../../shared/DOCTRINE.md) (agent-first; design a
> level above) and the
> [follow-up audit](../../history/audits/2026-06-04-live-trial-tool-loop-14b-followup.md)
> that motivates and bounds this work.

## Premise (corrected)

The earlier framing — *"a separate tier is needed because cheap models hit a
capability floor when given tools"* — was **reversed** by the 2026-06-04 clean
re-test: the tool-loop spike measured **harness context quality**, not operator
capability. A local 14B is comfortably above the floor with a coherent brief, and
the tier likely does **not** need a frontier model.

So this mission is **not** a capability remedy. It is two things:

1. **Context-plumbing hardening** of the multiturn/tool harness so a capable
   *local* operator is given a fair brief, and
2. a **separately-scored tier** that exercises the *full* path (read context →
   author a parser → run a real ingest → answer) as **headroom** above the
   constrained one-shot floor signal — never a replacement for it.

## Goal

A capable local operator can run the live trial through a multiturn, tool-using
loop over its **own** data, scored as its own tier, with the same honesty and
containment guarantees the one-shot path already enforces.

## In scope

- A **coherent single brief** for the tool loop (no self-contradiction between the
  contract prompt and the loop instructions).
- **Context the operator can actually use:** the parser-contract API served
  un-truncated or as a focused summary that always includes the class the operator
  must build, plus the data sample the production one-shot operator already shows.
- A **tool contract** the operator calls during the loop, defined as a bounded
  abstraction (what a tool may read/do, and its guarantees) rather than a fixed
  enumerated list. The spike's READ (source/context, manifest **excluded**) and RUN
  (a real warehouse ingest) are the first concrete instances of that contract.
- A **separate tier score** recorded alongside — not overwriting — the one-shot
  floor result, so the two signals stay comparable (the schema already records
  `operator_model` / `driver_model`).
- A sharper **declared-gap** contract line so a consumed-but-renamed source column
  (e.g. `timestamp` → `ts_utc`) is declared accounted, not silently absorbed.

## Out of scope

- Any requirement for a frontier or cloud model. The backend stays **local Ollama**
  (inherits the local-only `OLLAMA_URL` guard).
- Any new model-backend abstraction beyond local Ollama.
- Replacing or weakening the constrained one-shot floor probe.
- Any CI/default-gate change — the tool-loop path stays behind the `live_trial`
  marker and can never block CI.
- Promoting this spec while the intake source-adaptation gate is unmet.

## Proposed requirements (at altitude — refine at promotion)

**Functional**

- **FR-T1:** The tool loop runs from one coherent brief; no instruction in the
  brief contradicts another (the spike's fence-vs-no-fence defect cannot recur).
- **FR-T2:** Whatever context the operator is served always includes the parser
  API surface it must implement against (no truncation that drops the target
  class); the data sample is shown as the one-shot operator shows it.
- **FR-T3:** The operator interacts through a defined tool contract; **C-005 holds
  by physical exclusion** — no tool can reach the fixture manifest or any
  ground-truth mapping, at any turn.
- **FR-T4:** A completed tool-loop trial records a tier-tagged result distinct from
  the one-shot floor result, comparable by operator model.
- **FR-T5:** A source column the operator consumes under a renamed field is
  declared accounted (or an explicit gap); silent absorption is a self-reconcile
  failure, not a pass.

**Non-functional**

- **NFR-T1:** Backend stays local-only (inherits Mission A's `OLLAMA_URL` guard);
  no prompt or sample leaves the machine.
- **NFR-T2:** Real-data no-persist and synthetic-only persistence/retention rules
  are unchanged (inherits Mission A's synthetic-only `keep_sandboxes`).
- **NFR-T3:** The tool-loop path is `live_trial`-marked and never blocks CI.
- **NFR-T4:** Reuse the existing sandbox / runner / grader / store / scoreboard
  machinery; the loop is new orchestration over them, not a fork.
- **NFR-T5:** The tier is defined by a **rule** (what counts as a tool, how a tier
  is scored), not by an enumerated, hardcoded model/tool list.

## Open questions (resolve at promotion)

- Focused API **summary** vs. full un-truncated contract in context — which gives
  the cleaner brief without blowing the local context window?
- How many turns / what stop condition for the loop, and how is "regression across
  turns" (seen in the 7B spike) detected rather than rewarded?
- Does the tier reuse `OllamaOperator`'s retry semantics, or is multiturn a
  distinct operator that the seam's closed factories can also vend?

## Promotion criteria

1. The intake source-adaptation mission has shipped (the queue gate).
2. This draft is reviewed against the live
   [audit](../../history/audits/2026-06-04-live-trial-tool-loop-14b-followup.md)
   and current `live_trial.py` / `live_trial_ollama.py` behavior.
3. Promote via `/spec-kitty specify` from this draft.
