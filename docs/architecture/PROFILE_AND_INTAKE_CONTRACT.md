# Profile and intake contract

> Status: authoritative. Source of truth for what counts as baseline profile
> context, nutrition intake, and supplement intake, and how each stays distinct
> from observed measurements and narrative notes.
>
> Companion to [STAGES.md](STAGES.md) and [UPDATE_STRATEGY.md](UPDATE_STRATEGY.md).
> The machine-readable surfaces that this document explains in prose live next to
> it under `docs/architecture/contracts/`:
> [profile_and_intake_entities.yaml](contracts/profile_and_intake_entities.yaml),
> [profile_and_intake_examples.yaml](contracts/profile_and_intake_examples.yaml),
> [profile_and_intake_invariants.yaml](contracts/profile_and_intake_invariants.yaml),
> and [profile_and_intake_dependencies.yaml](contracts/profile_and_intake_dependencies.yaml).
> Captured 2026-05-27.

## What this document is, and is not

This is a meaning contract. It says where each kind of personal-context and
intake data lives in Premura's model, what each entity means, and how to tell
these domains apart from the data Premura already stores. It is the agreed shape
of what these domains contain — the thing later ingest, signal-processing, and
user-facing work can build on without re-deciding the boundary each time.

It is **not** a storage design. On purpose, this document does not choose a
DuckDB table layout, a migration, an object-relational model, or an API. The
rule for this whole surface is short:

- **Keep storage open.** Any future adapter may persist this however it likes.
- **Make meaning strict.** Whatever the adapter chooses, the meaning below must
  survive unchanged.

Two things follow from that, and they matter for review:

- These three domains are **not** a new fifth stage. Premura still has four
  stages — ingest, signal processing, MCP, and user interface (see
  [STAGES.md](STAGES.md)). Profile context and intake are data domains that
  later stages read; they are not a new step in the pipeline.
- Nothing here describes a feature the operator already has. There is no capture
  screen, no importer, and no Stage 2 answer shipped by this contract. This
  document fixes meaning so that those follow-on pieces have one home to build
  against. The deferred work is named at the end.

## The three new domains

### Baseline profile context

Baseline profile context is the set of **stable or slowly-changing personal
attributes** about the operator that future reasoning needs but that do not fit
the "observed at a time, with source provenance" shape of a measurement. Birth
date, biological sex, and a height the operator simply *states about themselves*
are profile context.

Profile context separates two ideas that are easy to blur:

- A **profile attribute** is the *meaning* of a context value — what
  `birth_date` or `standing_height_declared` is, what kind of value it holds,
  and whether it is permanent, slowly-changing, or derived from another
  attribute. The attribute does not hold the operator's current value.
- A **profile assertion** is one *recorded statement* of that attribute's value:
  what the value is, when it became effective, who supplied it, where it came
  from, and which earlier assertion (if any) it supersedes or corrects.

Profile context comes in three flavours, and the model keeps them distinct:

- **Permanent** — does not change after it is known. Birth date is permanent.
- **Slowly-changing** — can legitimately change over a lifetime and so needs an
  effective time. A declared standing height is slowly-changing.
- **Derived** — computed from another attribute at the moment it is needed, and
  never edited on its own. Age is derived from birth date and the evaluation
  date. The model deliberately refuses to let age be asserted independently when
  birth date exists, so the two can never silently disagree.

### Nutrition intake

Nutrition intake covers **food, drink, energy, and nutrient consumption** — what
the operator ate or drank, when, and what that consumption contained.

Nutrition intake separates the *occurrence* from the *quantities*:

- An **intake event** anchors a single eating or drinking occurrence in time. It
  says consumption happened; on its own it does not say how many calories or
  grams of protein were involved.
- An **intake item** is one food or drink consumed inside an event. An event can
  hold several items (a sandwich and a coffee).
- A **nutrition fact** is one energy or nutrient amount attached to an item or to
  the event as a whole — `energy_kcal`, `protein_g`, `sodium_mg`, and so on,
  each with an amount and a unit.

Nutrition records may be **complete or partial**. A record that knows only the
meal's total energy, or only the meal label, is still a valid intake record.
Unknown nutrients are simply absent — the model never invents them, and an
unknown micronutrient is never recorded as zero.

### Supplement intake

Supplement intake covers **supplement products, their ingredients, and the doses
taken**. It reuses the intake backbone (an intake event holding intake items) and
adds one domain-specific piece:

- A **supplement dose** is the quantity taken of a supplement item — the amount,
  the unit, and what was known about the product or ingredients at record time.

A supplement record stays honest about how much it knows. It may describe a
branded product whose full ingredient breakdown is unknown, a single named
ingredient, or a multi-ingredient stack. The model preserves the **dose that was
actually taken** even when the underlying ingredients are not all known, and it
never fabricates an ingredient list from a brand name alone.

## How these differ from observation history and note history

Premura already has two well-defined homes that this contract must not absorb
(see Constraint C-002 in the mission spec). The lines are:

- **Observation history** is what a device or lab *measured*, stored as canonical
  rows in `hp.fact_measurement` / `hp.fact_interval` with provenance (see
  [STAGES.md](STAGES.md), Ingest). A smart scale's height reading and a wearable's
  daily `total_kcal` are observations. They are facts about a measurement event.
- **Note history** is narrative free text that cannot be normalized into a
  structured value. A clinical comment in prose is a note. Notes are not a
  catch-all that absorbs anything the structured domains find inconvenient.

Against those, the new domains draw three clean lines:

1. **Declared context is not a measurement.** A height the operator *states* is a
   profile assertion; a height a *device emits* is an observation. They may both
   exist and they mean different things — one is the operator's account of
   themselves, the other is an instrument reading. The model keeps them as
   separate entities rather than collapsing them into one "height" value.
2. **Intake is not a body observation.** A meal's calories are nutrition facts
   attached to an intake event, not a body-state measurement. A supplement dose
   is intake, not a reading about the body. A wearable's energy-expenditure
   output stays an observation, because the device measured it.
3. **Structured intake and context are not notes.** Food, doses, and profile
   values get first-class structure precisely so that future work does not have
   to mine them out of free text. Narrative that genuinely cannot be normalized
   stays a note; it does not become a dumping ground.

## How overlap cases work

The hard cases are the ones where the *same real-world subject* shows up in more
than one domain. The contract resolves these by meaning, not by name:

- **Declared standing height vs measured smart-scale height.** Same physical
  quantity, two homes. The declared value is profile context (the operator's
  account); the measured value is observation history (the instrument's reading).
  A future function that needs "height" must say which one it wants.
- **Meal energy vs wearable total kcal.** Both are "calories," but a meal's
  energy is nutrition intake (a quantity attributed to something consumed) while
  a wearable's daily total is an observation (energy expenditure the device
  reported). They never merge into one number.
- **Age vs birth date.** Age is not stored or asserted; it is derived from birth
  date at evaluation time, so the two cannot drift apart.

The governing rule is one-home classification: every normalized example has
exactly **one** canonical home — `profile_context`, `nutrition_intake`,
`supplement_intake`, `observation_history`, or `note_history`. There is no
`context`, `misc`, or `metadata` bucket. If something seems to need two homes,
that is a sign two different meanings are being conflated, and the model keeps
them apart. The worked examples are enumerated in
[profile_and_intake_examples.yaml](contracts/profile_and_intake_examples.yaml).

## Provenance and time semantics

Every first-class entity in these domains names both where it came from and when
it applies. Concretely:

- **Provenance.** Each profile assertion, intake event, and the records hanging
  off them carry a provenance kind — `manual`, `imported`, `derived`, or
  `corrected` — and a human-readable source reference. This keeps a hand-entered
  value distinguishable from an imported one, so later reasoning can describe its
  basis honestly.
- **Effective time.** A profile assertion records when its value became effective
  (`effective_start`) separately from when it was written down (`asserted_at`).
  An intake event records when consumption happened (`occurred_at`).
- **Corrections stay visible.** When a value is corrected or a newer assertion
  replaces an older one, the change is recorded as a *new* assertion that points
  back at what it supersedes — it does not silently overwrite history. This is a
  different shape from the warehouse rebuild flows in
  [UPDATE_STRATEGY.md](UPDATE_STRATEGY.md): here the correction lineage is part of
  the data's meaning, not a maintenance operation.

## How future functions declare what they need

A future signal-processing or interpretation function that needs profile or
intake data must **declare that dependency explicitly**. It states which domains
it draws on, the exact keys it needs (for example `standing_height_declared`,
`protein_g`, or `dose_amount`), and how it behaves honestly when a prerequisite
is missing, stale, partial, or unknown.

The point of the declaration is to stop functions from quietly assuming a value
happens to be present. Finding a height row in observation history is **not** a
substitute for declaring that a function needs declared profile height — the same
adapter could store things differently tomorrow, and the meaning of the
requirement must not depend on that. The required shape and worked examples (BMI,
a protein-intake summary, a supplement-adherence summary) are in
[profile_and_intake_dependencies.yaml](contracts/profile_and_intake_dependencies.yaml).

## Why storage is intentionally not prescribed here

Premura prefers to fix meaning early and defer mechanism. If this document
committed to tables and columns now, every later storage choice would have to
re-open the boundary question to change them. By contracting on meaning instead,
a future mission can pick whatever persistence shape fits — extra columns on an
existing dimension, new tables, an entirely separate store — as long as it can
represent the entities, honour the invariants, and answer the declared
dependencies. The contract is the fixed point; the storage adapter is free to
move underneath it.

## What stays deferred

This contract decides *where data lives and what it means*. It does not ship the
machinery to put data there. Explicitly deferred to later implementation
missions:

- import paths and parsers for profile or intake data,
- manual-entry workflows,
- any new Stage 2 signal or Stage 3 MCP tool that consumes these domains
  (BMI and age-adjusted interpretation included),
- the concrete storage adapter and any migration it needs,
- user-facing teaching copy.

When those missions run, the open questions should be implementation and workflow
choices only — not a re-litigation of which domain profile and intake data belong
to.
