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

This document is the **meaning contract**, not the storage design. It does not
choose the DuckDB layout — but, as of the
`implement-profile-and-intake-storage-01KSMWV1` mission, a concrete storage
adapter that satisfies this contract now exists (see "Concrete storage now
exists" below). The rule for this surface is unchanged:

- **Meaning is strict and authoritative here.** Whatever the storage adapter
  does, the meaning below must survive unchanged.
- **Storage is the adapter's choice.** This document is still the fixed point; a
  future adapter could re-shape the tables as long as it preserves these
  meanings. The current adapter is the *first* such choice, not a constraint
  baked into the contract.

Two things follow from that, and they matter for review:

- These three domains are **not** a new fifth stage. Premura still has four
  stages — ingest, signal processing, MCP, and user interface (see
  [STAGES.md](STAGES.md)). Profile context and intake are data domains that
  later stages read; they are not a new step in the pipeline.
- The shipped capability is bounded. Baseline profile context now has a real
  **agent-mediated capture** path; nutrition and supplement intake have real
  **storage and a normalized load path**, but **no built-in importer for any
  specific nutrition/supplement source ships** — adapting a particular source
  into these tables is follow-on parser/plugin work. No profile-dependent Stage 2
  answer (BMI, age-adjusted interpretation) ships either. What is and is not built
  is itemized under "Concrete storage now exists" and "What stays deferred".

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

## Why meaning was fixed before storage

Premura fixed meaning early and deferred mechanism. If this document had
committed to tables and columns up front, every later storage choice would have
had to re-open the boundary question to change them. By contracting on meaning
first, the storage mission below could pick a persistence shape that represents
the entities, honours the invariants, and answers the declared dependencies —
without re-litigating which domain anything belongs to. The contract stays the
fixed point; the storage adapter sits underneath it.

## Concrete storage now exists

The `implement-profile-and-intake-storage-01KSMWV1` mission added a storage
adapter that satisfies this contract. It lives in migration
`src/premura/store/migrations/004_profile_intake.sql` and is exercised through
`src/premura/store/profile_intake.py`. The semantic vocabulary above maps onto it
as follows (the contract names are the *meaning*; the table/column names are the
*current adapter*):

- **Baseline profile context** → `hp.profile_capture_session` (one bounded
  capture session, bookkeeping only) and `hp.profile_context_assertion` (one
  recorded assertion per row). A profile *attribute* is a key in the closed
  allowlist (`src/premura/profile_fields.py`: `birth_date`, `sex`,
  `standing_height_cm`); a profile *assertion* is a row. Correction lineage is
  the `supersedes_assertion_id` self-reference plus the closed `effective_end_utc`
  of the superseded row — the append/supersede semantics the contract requires,
  enforced in `record_profile_context`. The declared-height attribute ships as
  `standing_height_cm` (the contract's `standing_height_declared` meaning).
- **Nutrition intake** → `hp.nutrition_intake_event` → `hp.nutrition_intake_item`
  → `hp.nutrition_quantity`. An intake event, an intake item, and a nutrition
  fact respectively. Quantity keys (e.g. `energy`, `protein`) stay distinct from
  body-observation `metric_id`s; partial records are allowed (unknown nutrients
  are absent, never zero).
- **Supplement intake** → `hp.supplement_intake_event` → `hp.supplement_item`
  → `hp.supplement_dose`. The dose preserves the amount actually taken even when
  the ingredient breakdown is unknown.

Two contract rules are now **structural**, not just prose:

- **One-home separation.** Each domain has its own tables under `hp.`; there is
  deliberately no JSON catch-all bucket and nothing writes these meanings into
  `hp.fact_measurement` / `hp.fact_interval` / note storage. The back-door the
  contract forbids is unavailable because no such column exists.
- **Bounded capture.** `record_profile_context` validates every write against the
  allowlist at the store boundary; an unsupported or derived key (such as `age`)
  raises before any row is written. Provenance for the agent path is
  `source_kind="agent_profile_capture"`.

What the adapter does **not** add: any built-in importer for a specific
nutrition/supplement source. `persist_intake_batch` loads a normalized
`IntakeBatch` idempotently (dedupe on the `dedupe_key` UNIQUE constraint), but
producing that batch from a real meal-logging or supplement export is the
parser/plugin follow-on work named below.

## What stays deferred

Storage and the agent-mediated profile-capture path now ship. Explicitly still
deferred to later missions:

- parsers/plugins that adapt a specific nutrition or supplement source into the
  intake tables (there is a load path and a normalized seam, but no built-in
  importer for any particular source),
- any new Stage 2 signal or Stage 3 MCP tool that *consumes* these domains —
  BMI and age-adjusted interpretation included (`age` remains derived, never
  stored),
- user-facing teaching copy for the captured domains.

When those missions run, the open questions should be implementation and workflow
choices only — not a re-litigation of which domain profile and intake data belong
to, nor of how the data is stored.
