# Premura

Premura is a local-first personal health-data warehouse. It ingests user-exported artifacts into one canonical warehouse, derives answerable signals from that warehouse, and routes user questions through health directions instead of treating all data as one undifferentiated stream.

## Maintainer mental model

The primary maintainer is an AI researcher, not a day-to-day software engineer. They understand software broadly but do not work in SE/agile/PM vocabulary. Agent communication and doc edits should:

- Favor plain English over jargon. Describe a concept in a sentence rather than using a one-word term the reader has to look up.
- Use research-flavored vocabulary where this project has chosen it — see the **Planning** subsection under Language below for canonical term swaps (e.g. "ablation study" rather than "spike", "design decision note" rather than "ADR").
- Explain any SE-native term in one short line the first time it appears in a new doc.
- Do not introduce invented coinages (e.g. "decomposition surface", "compression bias") or Jira-isms (e.g. "epic", "story points"). If a concept genuinely needs a name, name it after a familiar idea, not after the methodology that originated it.

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
