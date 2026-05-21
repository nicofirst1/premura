# Premura

Premura is a local-first personal health-data warehouse. It ingests user-exported artifacts into one canonical warehouse, derives answerable signals from that warehouse, and routes user questions through health directions instead of treating all data as one undifferentiated stream.

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

## Example dialogue

Dev: If a Garmin GDPR zip and a Health Connect database both contain the same heart-rate record, which one becomes the signal source?

Domain expert: The warehouse keeps canonical rows, but the signal should come from the higher-priority source artifact after dedupe.

Dev: And if the user chooses the sleep health direction, do we surface raw rows?

Domain expert: No. The signal selector should choose signals that answer the question, and the UI can add teaching if the user needs help understanding them.
