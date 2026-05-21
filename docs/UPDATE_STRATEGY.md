# Warehouse update strategy

> Companion to [STAGES.md](STAGES.md) and the engine surface at
> `src/premura/engine/__init__.py`. Defines the six shapes a warehouse update
> can take and which ones the v2 architectural skeleton handles today versus
> which are queued for follow-up missions.

A "warehouse update" is anything that changes the rows in `hp.fact_measurement`
/ `hp.fact_interval` / `hp.dim_metric`, or the meaning of those rows, after
the warehouse already exists. The six shapes below are intentionally
exhaustive — every plausible change collapses into one of them.

## The six update kinds

### (a) New ingest — **handled today**

A new file lands in `data/inbox/`; one of the existing parsers (`hc`,
`garmin`, `saa`, `bmt`) reads it and appends rows.

- Mechanism: `hpipe ingest [--source ...]`.
- Idempotency: `ingest_run.source_sha256` + `dedupe_key UNIQUE` per row.
- Stage: 1 (Ingest).

### (b) Schema migration — **handled today**

Additive DuckDB schema changes (new columns, new tables) live as numbered
SQL files under `src/premura/store/migrations/NNN_*.sql` and are applied by
`store.duck.run_migrations(conn)` on every bootstrap.

- Example: `src/premura/store/migrations/002_dim_metric_ontology.sql` added
  `category`, `validity_window`, `missing_data_policy`, `aliases`, `loinc`,
  `ieee1752` to `hp.dim_metric`.
- All migrations MUST be idempotent (`ADD COLUMN IF NOT EXISTS`, etc.).
- Constraint: existing `hp.*` columns are not removed or repurposed in
  place — destructive schema changes route through (e) instead.

### (c) Ontology seed refresh — **handled today**

`src/premura/dim_metric.yaml` is the source of truth for `hp.dim_metric` rows
(canonical `metric_id`s, units, validity windows, missing-data policy,
aliases, LOINC / IEEE 1752.1 cross-references). On every bootstrap,
`store.duck.seed_dim_metric` re-applies the YAML via INSERT…ON CONFLICT
UPDATE.

- Adding a row, fixing a unit, growing the `aliases` list, attaching a LOINC
  code: edit `dim_metric.yaml`, run any `hpipe` command, the row is
  refreshed.
- Constraint: rows MAY be added or updated; rows MUST NOT be removed in this
  mission, since `hp.fact_measurement` references them. Vocabulary
  *renames* route through (e).

### (d) Derived-signal invalidation — **deferred**

When a Stage 2 signal function's derivation logic materially changes, any
already-persisted `derived:*` row in `hp.fact_measurement` becomes stale.
The skeleton ships the metadata required to detect this, but not the
revalidation command.

- The `revision` field on `SignalSpec` (see `src/premura/engine/_registry.py`)
  is stored in the `raw_payload` of each persisted derived row at compute
  time, so a future `hpipe revalidate` command can identify outputs whose
  spec revision no longer matches and recompute them.
- Today: re-deriving requires deleting the stale `derived:*` rows manually
  and re-running ingest. A first-class `hpipe revalidate` verb is queued
  for a follow-up mission.

### (e) Full rebuild from raw — **deferred**

A clean rebuild of `hp.fact_measurement` / `hp.fact_interval` from the raw
artifacts in `data/raw/`, with the *current* parser code and the *current*
ontology. This is the project's chosen escape hatch for non-additive
changes: canonical-vocabulary renames, schema redesigns, parser bug fixes
that retroactively reinterpret historical rows.

- Why this exists: Premura prefers fewer migrations. The cost of one
  rebuild is bounded (raws are kept on disk and encrypted at export time);
  the cost of supporting in-place rewrite logic forever is not.
- Concrete near-term consumer: the legacy v1 `metric_id` → final canonical
  vocabulary rename happens via rebuild, not in-place migration.
- Today: there is no `hpipe rebuild` verb. The follow-up mission that owns
  the canonical-vocabulary rewrite will introduce it.

### (f) Parser updates — **deferred**

When an existing parser's mapping logic changes (a vendor field was
previously dropped and is now mapped, an alias was wrong, a unit was
mis-converted), the already-ingested rows from that parser need to be
re-derived.

- Mechanism, when it ships: drop and re-ingest the affected source from raw
  via path (e), or, for additive cases, run a targeted re-ingest of files
  whose `ingest_run.source_sha256` hash is on record.
- Why this is its own kind: parser changes and ontology evolution are
  separate concerns. (c) updates the ontology without touching raws or
  parsers; (f) changes how raws are interpreted. Conflating them invites
  silent reinterpretation of historical data.
- Today: parser changes that are purely additive (new metric, new alias)
  compose with (a) — re-ingest picks them up on the next run. Parser
  changes that *reinterpret* an already-mapped field are deferred to the
  same follow-up mission that owns (e).

## Quick reference

| Update kind                       | Handled now | Mechanism                                                |
|-----------------------------------|-------------|----------------------------------------------------------|
| (a) new ingest                    | yes         | `hpipe ingest`                                           |
| (b) schema migration              | yes         | `src/premura/store/migrations/NNN_*.sql`                  |
| (c) ontology seed refresh         | yes         | `src/premura/dim_metric.yaml` + `seed_dim_metric`         |
| (d) derived-signal invalidation   | deferred    | future `hpipe revalidate` keyed on `SignalSpec.revision` |
| (e) full rebuild from raw         | deferred    | future `hpipe rebuild` over `data/raw/`                   |
| (f) parser updates                | deferred    | future re-ingest / rebuild flow                          |

## Why the split

The first three update kinds compose cleanly: they are append-only or
declaratively idempotent, so they ship with the skeleton. The latter three
require either delete-and-recompute logic (d, f) or full re-execution of the
parsing layer (e). Those are real commands with real failure modes
(disk usage, encryption-key handling for raws, transactionality across
millions of rows) and deserve their own implementation mission rather than
being bolted onto the skeleton.

The skeleton's job is to make sure the *metadata required by* (d), (e), and
(f) is already in place: `SignalSpec.revision`, the `dim_metric.yaml`
authoritative ontology, the per-row `source_sha256` and `dedupe_key`, and
the encrypted raws preserved in `data/raw/` by the export pipeline. Future
missions can add the verbs without re-litigating the data model.
