# Premura

Premura is a local-first personal health-data warehouse. It ingests user-exported artifacts into one canonical warehouse, derives answerable signals from that warehouse, and routes user questions through health directions instead of treating all data as one undifferentiated stream.

## Maintainer mental model

The primary maintainer is an AI researcher, not a day-to-day software engineer. They understand software broadly but do not work in SE/agile/PM vocabulary. Agent communication and doc edits should:

- Favor plain English over jargon. Describe a concept in a sentence rather than using a one-word term the reader has to look up.
- Use research-flavored vocabulary where this project has chosen it — see the **Planning** subsection under Language below for canonical term swaps (e.g. "ablation study" rather than "spike", "design decision note" rather than "ADR").
- Explain any SE-native term in one short line the first time it appears in a new doc.
- Do not introduce invented coinages (e.g. "decomposition surface", "compression bias") or Jira-isms (e.g. "epic", "story points"). If a concept genuinely needs a name, name it after a familiar idea, not after the methodology that originated it.

### Explaining a plan, design, or review to the maintainer

When the maintainer asks you to *explain* work (not write the spec itself), this layered plain-English walkthrough has worked well — prefer it over a jargon-dense summary:

1. **What this is** — one line placing the thing ("a draft plan for the next mission").
2. **What it proposes, in everyday terms** — translate each technical idea inline, anchored to a concrete health example (resting heart rate is a good default). Never leave a technical word unglossed.
3. **The key idea / why it's built this way** — name the one real design tension and how it's handled (e.g. *guide, don't enumerate*).
4. **The reviews / tradeoffs** — what came up and how it resolved, in plain terms.
5. **Where it stands + a low-pressure next step** — end with the current state and an optional next action, not a push to proceed.

Keep it warm and readable; favor short sections over dense tables, and explain any unavoidable technical term the first time it appears.

## Language

### Data shape

**Source artifact**:
A user-exported file consumed by ingest, such as a Health Connect database, Garmin GDPR zip, Sleep as Android CSV, or Body Measurement Tracker CSV.
_Avoid_: import, feed, payload dump

**Warehouse**:
The DuckDB file that becomes the system of record after ingest. It stores canonical rows, not vendor-shaped tables.
_Avoid_: database dump, cache, mirror

**Canonical metric**:
A reviewable metric name and canonical unit used in the warehouse, such as `weight`, `hrv_rmssd`, or `body_fat_pct`.
_Avoid_: field, column meaning, vendor metric

**Ingest batch**:
The complete unit handed from ingest to the warehouse seam for one source artifact. It contains the rows to persist plus the provenance and declarations needed to validate and load them.
_Avoid_: parse result, loader payload, import blob

### Personal context and intake

These three domains have a fixed meaning contract ([PROFILE_AND_INTAKE_CONTRACT.md](docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md)) and now have concrete warehouse homes (migration `004_profile_intake.sql`). They are kept strictly distinct from observation history (what a device/lab measured) and note history (un-normalizable free text).

**Baseline profile context**:
Stable or slowly-changing personal facts the operator *states about themselves* — birth date, biological sex, a declared standing height. These are the operator's own account, not an instrument reading, and they live in `hp.profile_context_assertion`, never in the measurement tables.
_Avoid_: profile fields, user settings, demographics blob.

**Profile assertion**:
One recorded statement of a baseline profile fact, with its value, when it became effective, and where it came from. A correction is a *new* assertion that supersedes the prior one (history is kept, never overwritten).
_Avoid_: profile row, current value (a profile fact is a lineage of assertions, not a single mutable cell).

**Agent-mediated profile capture**:
The supported way baseline profile facts get recorded: the agent records one allowlisted attribute at a time through the profile-capture tools, stamped with provenance `agent_profile_capture`. The allowlist is closed (`premura.profile_fields`); a derived key such as `age` is rejected, not stored. This is the default — there is no human-filled profile form.
_Avoid_: onboarding form, profile wizard, manual entry (as the default).

**Nutrition intake / supplement intake**:
What the operator ate, drank, or supplemented — consumption, not a body measurement. A meal's energy is a nutrition quantity on an intake event; a wearable's expended kcal stays an observation. These land in their own `hp.nutrition_intake_*` / `hp.supplement_intake_*` tables. *Storing* them exists today; *adapting a specific source* into them is follow-on parser/plugin work, not a built-in importer.
_Avoid_: food log table, calorie tracker, built-in MyFitnessPal import.

### Signal processing

**Signal**:
A validity-checked, question-ready value or series selected from the warehouse for a user question. A signal may be raw or derived, but it is always shaped to answer something.
_Avoid_: stat, feature, datapoint

**Derived signal**:
A signal computed from one or more canonical metrics and persisted with a `derived:` metric_id. It belongs to signal processing, not ingest.
_Avoid_: parser output, synthetic field, convenience calculation

**Signal selector**:
The logic that ranks which signals can answer a user question given the actual warehouse contents and freshness rules.
_Avoid_: recommender, query planner, search index

### Analysis

**Lag**:
The directional, whole-day time-offset at which one metric's relationship to another is examined — metric X on a given day compared against metric Y some number of days later. It models a *physiological delay* (lactose eaten today, gut symptoms a day or two later; a hard training day today, suppressed overnight HRV tomorrow), so it is asymmetric and always caller-specified. It is **not** a symmetric "close-enough timestamp" measurement tolerance, and it is never discovered by scanning many offsets and keeping the best-fitting one.
_Avoid_: tolerance window, time-shift fudge, lead/lag scan.

**Association** (what a correlation reports):
A descriptive statement that two metrics move together (or oppositely) over the days both were measured. It carries a strength and an honest uncertainty, never a direction of cause. "My HRV and my training load are associated at a one-day lag" is admissible; "my training load lowers my HRV" is not.
_Avoid_: effect, impact, driver, link, relationship (these smuggle in causation).

### User intent

**Health direction**:
The user-facing entry point for exploration, such as sleep, energy, mood, movement, recovery, or longevity. It is a routing choice, not a metric.
_Avoid_: tab, category, dashboard lane

**Teaching**:
The user-interface behavior that explains a metric or signal in plain language with progressive disclosure. It is part of the UI stage, not signal processing.
_Avoid_: tooltip copy, commentary layer, marketing text

### Operations

**Ingest run**:
One recorded execution of ingest for a specific source artifact, tracked with counts, hashes, and timing in `hp.ingest_run`.
_Avoid_: job, sync, import attempt

**Dedupe planner**:
The module at the warehouse seam that applies source priority and matching tolerance rules to a validated ingest batch before persistence. It decides which rows survive against existing warehouse state.
_Avoid_: duplicate filter, conflict resolver, merge helper

### Planning

**Mission**:
A substantial unit of work managed via spec-kitty, with its own spec, plan, and breakdown into work packages. Examples: M1 (lock the MCP/warehouse boundary), M2 (first MCP analytical surface), M3 (lab ingest + sparse-signal foundations).
_Avoid_: epic, story.

**Work package (WP)**:
The smallest implementable slice inside a mission — roughly one PR's worth. WPs live inside `kitty-specs/<slug>/`.
_Avoid_: subtask, story point.

**Ablation study**:
A timeboxed exploration to answer a single question or reduce one specific uncertainty. The output is knowledge (a design decision note), not necessarily merged code. If the result is a working approach, the reference branch may serve as a feasibility demo.
_Avoid_: spike.

**Feasibility demo**:
Working code that demonstrates an approach is feasible end-to-end. Often the artifact produced by a successful ablation study. May or may not be merged.
_Avoid_: PoC, proof of concept.

**Design decision note**:
A short doc — one paragraph or two — capturing a design choice and the reason it won. Lives under `docs/adr/`. The folder name `adr/` is kept for filesystem stability, but in prose call them "design decision notes."
_Avoid_: ADR, architecture decision record (in prose; the folder name `adr/` is fine).

**First sort**:
The initial classification of an incoming issue — what it is, whether it's real, who picks it up. Drives the move from the `needs-triage` label to one of the other labels (`needs-info`, `ready-for-agent`, `ready-for-human`, `wontfix`).
_Avoid_: triage (in prose; the label string `needs-triage` is fixed).

#### Concepts to describe in plain English rather than name

The following SE concepts come up but don't need their own glossary term. When they appear in prose, describe the specific thing rather than using the abstract jargon:

- **boundary** / **contract** / **seam** — say "where stage X hands off to stage Y" or "the agreed shape of what flows between them."
- **protocol** — say "a type declaration that says which methods must exist," or refer to the specific Python class by name (`PluginParser`, `IngestBatch`).
- **WIP** — say "active" or "in progress."
- **timebox** — say "time budget" or "1-week budget."
- **decomposition** — say "breakdown."

#### Avoid entirely

These invented coinages from prior drafts should be removed in future passes; when the underlying concept needs to be referenced, describe it directly:

- decomposition surface, partition rule, compression bias, five-step planning loop, discipline rules, cross-stage labeling.

## Example dialogue

Dev: If a Garmin GDPR zip and a Health Connect database both contain the same heart-rate record, which one becomes the signal source?

Domain expert: The warehouse keeps canonical rows, but the signal should come from the higher-priority source artifact after dedupe.

Dev: And if the user chooses the sleep health direction, do we surface raw rows?

Domain expert: No. The signal selector should choose signals that answer the question, and the UI can add teaching if the user needs help understanding them.
