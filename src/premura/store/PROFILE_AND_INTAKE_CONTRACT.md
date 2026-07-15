# Profile and intake contract

> Status: authoritative. Source of truth for what counts as baseline profile context, nutrition intake, and supplement intake, and how each stays distinct from observed measurements and narrative notes.
>
> Companion to [STAGES.md](../../../docs/building/architecture/STAGES.md) and [UPDATE_STRATEGY.md](UPDATE_STRATEGY.md). The machine-readable surfaces that this document explains in prose live next to it under `profile_intake_contracts/`: [profile_and_intake_entities.yaml](profile_intake_contracts/profile_and_intake_entities.yaml), [profile_and_intake_examples.yaml](profile_intake_contracts/profile_and_intake_examples.yaml), [profile_and_intake_invariants.yaml](profile_intake_contracts/profile_and_intake_invariants.yaml), and [profile_and_intake_dependencies.yaml](profile_intake_contracts/profile_and_intake_dependencies.yaml).

## What this document is, and is not

This is a meaning contract. It says where each kind of personal-context and intake data lives in Premura's model, what each entity means, and how to tell these domains apart from the data Premura already stores. It is the agreed shape of what these domains contain — the thing later ingest, signal-processing, and user-facing work can build on without re-deciding the boundary each time.

This document is the **meaning contract**, not the storage design. It does not choose the DuckDB layout; a concrete storage adapter that satisfies it exists (see "Storage adapter" below). The rule for this surface:

- **Meaning is strict and authoritative here.** Whatever the storage adapter does, the meaning below must survive unchanged.
- **Storage is the adapter's choice.** This document is still the fixed point; a future adapter could re-shape the tables as long as it preserves these meanings. The current adapter is the _first_ such choice, not a constraint baked into the contract.

Two things follow from that, and they matter for review:

- These three domains are **not** a new fifth stage. Premura still has four stages — ingest, signal processing, MCP, and user interface (see [STAGES.md](../../../docs/building/architecture/STAGES.md)). Profile context and intake are data domains that later stages read; they are not a new step in the pipeline.
- The capability is bounded. Baseline profile context has an **agent-mediated capture** path; nutrition and supplement intake have **storage, a normalized load path, and concrete resolvers**, but **no built-in importer for any specific nutrition/supplement source** — adapting a particular source into these tables is follow-on parser/plugin work. A BMI signal is the worked cross-domain example over the input-resolution seam (declared height from profile context plus weight from observation history); age-adjusted interpretation is not yet built. What is and is not built is itemized under "Storage adapter" and "What stays deferred".

## The three new domains

### Baseline profile context

Baseline profile context is the set of **stable or slowly-changing personal attributes** about the operator that future reasoning needs but that do not fit the "observed at a time, with source provenance" shape of a measurement. Birth date, biological sex, and a height the operator simply _states about themselves_ are profile context.

Profile context separates two ideas that are easy to blur:

- A **profile attribute** is the _meaning_ of a context value — what `birth_date` or `standing_height_declared` is, what kind of value it holds, and whether it is permanent, slowly-changing, or derived from another attribute. The attribute does not hold the operator's current value.
- A **profile assertion** is one _recorded statement_ of that attribute's value: what the value is, when it became effective, who supplied it, where it came from, and which earlier assertion (if any) it supersedes or corrects.

Profile context comes in three flavours, and the model keeps them distinct:

- **Permanent** — does not change after it is known. Birth date is permanent.
- **Slowly-changing** — can legitimately change over a lifetime and so needs an effective time. A declared standing height is slowly-changing.
- **Derived** — computed from another attribute at the moment it is needed, and never edited on its own. Age is derived from birth date and the evaluation date. The model deliberately refuses to let age be asserted independently when birth date exists, so the two can never silently disagree.

### Nutrition intake

Nutrition intake covers **food, drink, energy, and nutrient consumption** — what the operator ate or drank, when, and what that consumption contained.

Nutrition intake separates the _occurrence_ from the _quantities_:

- An **intake event** anchors a single eating or drinking occurrence in time. It says consumption happened; on its own it does not say how many calories or grams of protein were involved.
- An **intake item** is one food or drink consumed inside an event. An event can hold several items (a sandwich and a coffee).
- A **nutrition fact** is one energy or nutrient amount attached to an item or to the event as a whole — `energy_kcal`, `protein_g`, `sodium_mg`, and so on, each with an amount and a unit.

Nutrition records may be **complete or partial**. A record that knows only the meal's total energy, or only the meal label, is still a valid intake record. Unknown nutrients are simply absent — the model never invents them, and an unknown micronutrient is never recorded as zero.

### Supplement intake

Supplement intake covers **supplement products, their ingredients, and the doses taken**. It reuses the intake backbone (an intake event holding intake items) and adds one domain-specific piece:

- A **supplement dose** is the quantity taken of a supplement item — the amount, the unit, and what was known about the product or ingredients at record time.

A supplement record stays honest about how much it knows. It may describe a branded product whose full ingredient breakdown is unknown, a single named ingredient, or a multi-ingredient stack. The model preserves the **dose that was actually taken** even when the underlying ingredients are not all known, and it never fabricates an ingredient list from a brand name alone.

> **Declaration and resolution.** `nutrition_intake` and `supplement_intake` are valid declaration targets in the Stage 2 input-resolution surface, and each has a concrete resolver behind it (see [INTAKE_DIMENSIONS.md](../engine/INTAKE_DIMENSIONS.md)). A consumer names a domain in a `DependencyDeclaration` and the seam resolves it; a declaration with no matching, fresh row resolves to an explicit non-usable outcome (`usable=False`, `absence_reason="missing"` or `"stale"`). The contract is deliberately strict here: an unresolved domain never silently falls back into observation history.

## Domain-vs-shape rubric

Future contributors will keep finding new kinds of data and asking the same question: **is this a new SEMANTIC DOMAIN, or a new SHAPE inside an existing domain?** The answer governs whether a new resolver is needed at all. The rubric:

1. **A new domain has a distinct MEANING contract.** Observation history is timestamped, source-provenanced facts a device or lab measured. Profile context is a declared assertion with an effective time (the operator's account of themselves). Nutrition and supplement intake are events with attached quantities (what was consumed and how much). If a proposed data type does not fit any of these meaning shapes, it is a candidate for a new domain. If it does fit one of them, it is not.
2. **Temporal shape alone is NOT a domain.** "This data is episodic," "this data arrives in bursts," "this data is denser than weight observations" — none of these is enough. Sparse blood-marker rows and dense wearable rows are both observation history because they share the observation meaning contract. A new sampling cadence is a `dim_metric` policy concern, not a domain concern.
3. **Numeric value alone is NOT a domain.** A number can fit profile context (a declared standing height), observation history (a smart scale's measured height), or a nutrition fact (a meal's `energy_kcal`). The same numeric shape may belong in any of three domains depending on what the number _means_. The model already enumerates the canonical worked example of this ambiguity (declared height vs measured height) and keeps them apart.
4. **A new domain must support a NEW QUESTION TYPE.** A genuinely new domain unlocks a question none of the existing domains can answer honestly. If the same question can be answered by adding a new `metric_id` under `observation_history`, prefer that — registering a metric is much cheaper than declaring a fifth semantic domain. Domains are the bounded surface; metrics are the unbounded one.
5. **When in doubt, propose it as a deliberate contract change**, not by adding a domain string. The four-domain set (`observation_history`, `profile_context`, `nutrition_intake`, `supplement_intake`) is the bounded semantic surface. Extending it is a contract change, not a code style preference; it requires its own design and review.

These rules also govern whether a proposal needs a **new resolver**. A new resolver is added only when a new (or existing-but-not-yet-resolved) declared semantic domain is involved. Adding a metric, adjusting a freshness window, or shipping a new Stage 2 answer over already-resolved domains does _not_ require a new resolver — it goes through the existing observation or profile resolver.

## How these differ from observation history and note history

Premura already has two well-defined homes that this contract must not absorb. The lines are:

- **Observation history** is what a device or lab _measured_, stored as canonical rows in `hp.fact_measurement` / `hp.fact_interval` with provenance (see [STAGES.md](../../../docs/building/architecture/STAGES.md), Ingest). A smart scale's height reading and a wearable's daily `total_kcal` are observations. They are facts about a measurement event.
- **Note history** is narrative free text that cannot be normalized into a structured value. A clinical comment in prose is a note. Notes are not a catch-all that absorbs anything the structured domains find inconvenient.

Against those, the new domains draw three clean lines:

1. **Declared context is not a measurement.** A height the operator _states_ is a profile assertion; a height a _device emits_ is an observation. They may both exist and they mean different things — one is the operator's account of themselves, the other is an instrument reading. The model keeps them as separate entities rather than collapsing them into one "height" value.
2. **Intake is not a body observation.** A meal's calories are nutrition facts attached to an intake event, not a body-state measurement. A supplement dose is intake, not a reading about the body. A wearable's energy-expenditure output stays an observation, because the device measured it.
3. **Structured intake and context are not notes.** Food, doses, and profile values get first-class structure precisely so that future work does not have to mine them out of free text. Narrative that genuinely cannot be normalized stays a note; it does not become a dumping ground.

## How overlap cases work

The hard cases are the ones where the _same real-world subject_ shows up in more than one domain. The contract resolves these by meaning, not by name:

- **Declared standing height vs measured smart-scale height.** Same physical quantity, two homes. The declared value is profile context (the operator's account); the measured value is observation history (the instrument's reading). A future function that needs "height" must say which one it wants.
- **Meal energy vs wearable total kcal.** Both are "calories," but a meal's energy is nutrition intake (a quantity attributed to something consumed) while a wearable's daily total is an observation (energy expenditure the device reported). They never merge into one number.
- **Age vs birth date.** Age is not stored or asserted; it is derived from birth date at evaluation time, so the two cannot drift apart.

The governing rule is one-home classification: every normalized example has exactly **one** canonical home — `profile_context`, `nutrition_intake`, `supplement_intake`, `observation_history`, or `note_history`. There is no `context`, `misc`, or `metadata` bucket. If something seems to need two homes, that is a sign two different meanings are being conflated, and the model keeps them apart. The worked examples are enumerated in [profile_and_intake_examples.yaml](profile_intake_contracts/profile_and_intake_examples.yaml).

## Provenance and time semantics

Every first-class entity in these domains names both where it came from and when it applies. Concretely:

- **Provenance.** Each profile assertion, intake event, and the records hanging off them carry a provenance kind — `manual`, `imported`, `derived`, or `corrected` — and a human-readable source reference. This keeps a hand-entered value distinguishable from an imported one, so later reasoning can describe its basis honestly.
- **Effective time.** A profile assertion records when its value became effective (`effective_start`) separately from when it was written down (`asserted_at`). An intake event records when consumption happened (`occurred_at`).
- **Corrections stay visible.** When a value is corrected or a newer assertion replaces an older one, the change is recorded as a _new_ assertion that points back at what it supersedes — it does not silently overwrite history. This is a different shape from the warehouse rebuild flows in [UPDATE_STRATEGY.md](UPDATE_STRATEGY.md): here the correction lineage is part of the data's meaning, not a maintenance operation.

## How future functions declare what they need

A future signal-processing or interpretation function that needs profile or intake data must **declare that dependency explicitly**. It states which domains it draws on, the exact keys it needs (for example `standing_height_declared`, `protein_g`, or `dose_amount`), and how it behaves honestly when a prerequisite is missing, stale, partial, or unknown.

The point of the declaration is to stop functions from quietly assuming a value happens to be present. Finding a height row in observation history is **not** a substitute for declaring that a function needs declared profile height — the same adapter could store things differently tomorrow, and the meaning of the requirement must not depend on that. The required shape and worked examples (BMI, a protein-intake summary, a supplement-adherence summary) are in [profile_and_intake_dependencies.yaml](profile_intake_contracts/profile_and_intake_dependencies.yaml).

## Why meaning was fixed before storage

Meaning was fixed before mechanism. If this document had committed to tables and columns up front, every later storage choice would have had to re-open the boundary question. By contracting on meaning first, a storage adapter can pick a persistence shape that represents the entities, honours the invariants, and answers the declared dependencies — without re-litigating which domain anything belongs to. The contract stays the fixed point; the storage adapter sits underneath it.

## Storage adapter

A storage adapter that satisfies this contract lives in migration `src/premura/store/migrations/004_profile_intake.sql` and is exercised through `src/premura/store/profile_intake.py`. The semantic vocabulary above maps onto it as follows (the contract names are the _meaning_; the table/column names are the _current adapter_):

- **Baseline profile context** → `hp.profile_capture_session` (one bounded capture session, bookkeeping only) and `hp.profile_context_assertion` (one recorded assertion per row). A profile _attribute_ is a key in the closed allowlist (`src/premura/profile_fields.py`: `birth_date`, `sex`, `standing_height_cm`); a profile _assertion_ is a row. Correction lineage is the `supersedes_assertion_id` self-reference plus the closed `effective_end_utc` of the superseded row — the append/supersede semantics the contract requires, enforced in `record_profile_context`. The declared-height attribute ships as `standing_height_cm` (the contract's `standing_height_declared` meaning).
- **Nutrition intake** → `hp.nutrition_intake_event` → `hp.nutrition_intake_item` → `hp.nutrition_quantity`. An intake event, an intake item, and a nutrition fact respectively. Quantity keys (e.g. `energy`, `protein`) stay distinct from body-observation `metric_id`s; partial records are allowed (unknown nutrients are absent, never zero).
- **Supplement intake** → `hp.supplement_intake_event` → `hp.supplement_item` → `hp.supplement_dose`. The dose preserves the amount actually taken even when the ingredient breakdown is unknown.

Two contract rules are **structural**, not just prose:

- **One-home separation.** Each domain has its own tables under `hp.`; there is deliberately no JSON catch-all bucket and nothing writes these meanings into `hp.fact_measurement` / `hp.fact_interval` / note storage. The back-door the contract forbids is unavailable because no such column exists.
- **Bounded capture.** `record_profile_context` validates every write against the allowlist at the store boundary; an unsupported or derived key (such as `age`) raises before any row is written. Provenance for the agent path is `source_kind="agent_profile_capture"`.

What the adapter does **not** add: any built-in importer for a specific nutrition/supplement source. `persist_intake_batch` loads a normalized `IntakeBatch` idempotently (dedupe on the `dedupe_key` UNIQUE constraint), but producing that batch from a real meal-logging or supplement export is the parser/plugin follow-on work named below.

## What stays deferred

Storage, the agent-mediated profile-capture path, and the Stage 2 **input-resolution seam** are implemented (see [`src/premura/engine/_resolution.py`](../engine/_resolution.py) and `src/premura/engine/CONTRACT.md`): observation history, profile context, and both intake domains have concrete resolvers, and a BMI signal is the worked cross-domain consumer. Not yet built:

- parsers/plugins that adapt a specific nutrition or supplement source into the intake tables (there is a load path and a normalized seam, but no built-in importer for any particular source),
- further profile-dependent Stage 2 signals beyond BMI — **age-adjusted interpretation** is the next candidate (`age` stays derived from `birth_date`, never stored),
- user-facing teaching copy for the captured domains.

When those changes are made, the open questions should be implementation and workflow choices only — not a re-litigation of which domain profile and intake data belong to, nor of how the data is stored.
