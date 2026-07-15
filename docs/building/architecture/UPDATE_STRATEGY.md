# Warehouse update strategy

> Status: authoritative. Source of truth for warehouse update kinds and support level.
>
> Companion to [STAGES.md](STAGES.md) and the engine surface at `src/premura/engine/__init__.py`. Defines the six shapes a warehouse update can take and which ones the v2 architectural skeleton handles today versus which are queued for follow-up missions.

A "warehouse update" is anything that changes the rows in `hp.fact_measurement` / `hp.fact_interval` / `hp.dim_metric`, or the meaning of those rows, after the warehouse already exists. The six shapes below are intentionally exhaustive — every plausible change to **observation history** collapses into one of them.

> Profile assertions and intake corrections are a **different update shape** and do not fit any of the six below. They are covered separately under [Correction and supersession](#correction-and-supersession-profile-and-intake) at the end of this document — they are _not_ a seventh rebuild flow.

## The six update kinds

### (a) New ingest — **handled today**

A new file lands in `data/inbox/`; one of the existing parsers (`hc`, `garmin`, `saa`, `bmt`) reads it and appends rows.

- Mechanism: `premura ingest [--source ...]`.
- Idempotency: `ingest_run.source_sha256` + `dedupe_key UNIQUE` per row.
- Stage: 1 (Ingest).

### (b) Schema migration — **handled today**

Additive DuckDB schema changes (new columns, new tables) live as numbered SQL files under `src/premura/store/migrations/NNN_*.sql` and are applied by `store.duck.run_migrations(conn)` on every bootstrap.

- Example: `src/premura/store/migrations/002_dim_metric_ontology.sql` added `category`, `validity_window`, `missing_data_policy`, `aliases`, `loinc`, `ieee1752` to `hp.dim_metric`.
- All migrations MUST be idempotent (`ADD COLUMN IF NOT EXISTS`, etc.).
- Constraint: existing `hp.*` columns are not removed or repurposed in place — destructive schema changes route through (e) instead.

### (c) Ontology seed refresh — **handled today**

`src/premura/dim_metric.yaml` is the source of truth for `hp.dim_metric` rows (canonical `metric_id`s, units, validity windows, missing-data policy, aliases, LOINC / IEEE 1752.1 cross-references). On every bootstrap, `store.duck.seed_dim_metric` re-applies the YAML via INSERT…ON CONFLICT UPDATE.

- Adding a row, fixing a unit, growing the `aliases` list, attaching a LOINC code: edit `dim_metric.yaml`, run any `premura` command, the row is refreshed.
- Constraint: rows MAY be added or updated; rows MUST NOT be removed in this mission, since `hp.fact_measurement` references them. Vocabulary _renames_ route through (e).

### (d) Derived-signal invalidation — **deferred**

When a Stage 2 signal function's derivation logic materially changes, any already-persisted `derived:*` row in `hp.fact_measurement` becomes stale. The skeleton ships the metadata required to detect this, but not the revalidation command.

- The `revision` field on `SignalSpec` (see `src/premura/engine/_registry.py`) is stored in the `raw_payload` of each persisted derived row at compute time, so a future `premura revalidate` command can identify outputs whose spec revision no longer matches and recompute them.
- Today: re-deriving requires deleting the stale `derived:*` rows manually and re-running ingest. A first-class `premura revalidate` verb is queued for a follow-up mission.

### (e) Full rebuild from raw — **deferred**

A clean rebuild of `hp.fact_measurement` / `hp.fact_interval` from the raw artifacts in `data/raw/`, with the _current_ parser code and the _current_ ontology. This is the project's chosen escape hatch for non-additive changes: canonical-vocabulary renames, schema redesigns, parser bug fixes that retroactively reinterpret historical rows.

- Why this exists: Premura prefers fewer migrations. The cost of one rebuild is bounded (raws are kept on disk and encrypted at export time); the cost of supporting in-place rewrite logic forever is not.
- Concrete near-term consumer: the legacy v1 `metric_id` → final canonical vocabulary rename happens via rebuild, not in-place migration.
- Today: there is no `premura rebuild` verb. The follow-up mission that owns the canonical-vocabulary rewrite will introduce it.

### (f) Parser updates — **deferred**

When an existing parser's mapping logic changes (a vendor field was previously dropped and is now mapped, an alias was wrong, a unit was mis-converted), the already-ingested rows from that parser need to be re-derived.

- Mechanism, when it ships: drop and re-ingest the affected source from raw via path (e), or, for additive cases, run a targeted re-ingest of files whose `ingest_run.source_sha256` hash is on record.
- Why this is its own kind: parser changes and ontology evolution are separate concerns. (c) updates the ontology without touching raws or parsers; (f) changes how raws are interpreted. Conflating them invites silent reinterpretation of historical data.
- Today: parser changes that are purely additive (new metric, new alias) compose with (a) — re-ingest picks them up on the next run. Parser changes that _reinterpret_ an already-mapped field are deferred to the same follow-up mission that owns (e).

## Quick reference

| Update kind                     | Handled now | Mechanism                                                  |
| ------------------------------- | ----------- | ---------------------------------------------------------- |
| (a) new ingest                  | yes         | `premura ingest`                                           |
| (b) schema migration            | yes         | `src/premura/store/migrations/NNN_*.sql`                   |
| (c) ontology seed refresh       | yes         | `src/premura/dim_metric.yaml` + `seed_dim_metric`          |
| (d) derived-signal invalidation | deferred    | future `premura revalidate` keyed on `SignalSpec.revision` |
| (e) full rebuild from raw       | deferred    | future `premura rebuild` over `data/raw/`                  |
| (f) parser updates              | deferred    | future re-ingest / rebuild flow                            |

## Why the split

The first three update kinds compose cleanly: they are append-only or declaratively idempotent, so they ship with the skeleton. The latter three require either delete-and-recompute logic (d, f) or full re-execution of the parsing layer (e). Those are real commands with real failure modes (disk usage, encryption-key handling for raws, transactionality across millions of rows) and deserve their own implementation mission rather than being bolted onto the skeleton.

The skeleton's job is to make sure the _metadata required by_ (d), (e), and (f) is already in place: `SignalSpec.revision`, the `dim_metric.yaml` authoritative ontology, the per-row `source_sha256` and `dedupe_key`, and the encrypted raws preserved in `data/raw/` by the export pipeline. Future missions can add the verbs without re-litigating the data model.

## Correction and supersession (profile and intake)

The six update kinds above govern **observation history** — the device/lab measurements in `hp.fact_measurement` / `hp.fact_interval`. They all share one assumption: the warehouse is rebuildable from raws, so the chosen escape hatch for hard changes is to re-derive from the original artifacts (kind (e)).

The new semantic domains fixed in [PROFILE_AND_INTAKE_CONTRACT.md](PROFILE_AND_INTAKE_CONTRACT.md) — baseline profile context, nutrition intake, and supplement intake — change differently, and the difference matters enough to call out explicitly so future work does not reach for the wrong tool.

### Correction/supersession is not raw-history rebuild

When a profile value is wrong, or a newer value supersedes an older one (the operator updates a declared standing height, corrects a recorded meal, or fixes a supplement dose), the intended shape is **a new assertion that points back at what it supersedes or corrects** — not a rebuild and not a silent in-place overwrite.

- The correction is itself a recorded statement, with its own provenance (`corrected`) and its own effective time. The superseded value is not deleted; the lineage from old to new stays visible.
- This is **part of the data's meaning**, not a maintenance operation. There is no raw artifact to re-parse: a declared height or a logged meal has no upstream vendor export to rebuild from. The correction _is_ the new authoritative statement, and history is the chain of statements.

Contrast this with observation history:

| Aspect               | Observation history (kinds (a)–(f))               | Profile / intake correction                                                   |
| -------------------- | ------------------------------------------------- | ----------------------------------------------------------------------------- |
| Source of truth      | Raw artifacts in `data/raw/`                      | The chain of recorded assertions/records                                      |
| Fixing a wrong value | Re-ingest or rebuild from raw (kind (e)/(f))      | Add a superseding assertion that references the prior one                     |
| History model        | Reconstructible from raws                         | Correction lineage is intrinsic data                                          |
| Deletion             | Append-only rows; rebuild replaces them wholesale | Prior assertion is retained and marked superseded, never silently overwritten |

So "correct a profile value" and "rebuild the warehouse" are **not** the same operation. A rebuild re-executes parsers over preserved raws; a profile/intake correction records a new statement and keeps the prior one visible. Conflating the two would either lose correction lineage (if treated as a rebuild) or pretend declarations have a raw artifact to rebuild from (they do not).

### What ships today and what remains deferred

Baseline profile assertions now have a concrete mechanism: dedicated profile tables, `premura profile-fields` / `premura profile-record`, and the matching agent-mediated MCP capture tools record one allowlisted profile fact at a time and supersede the prior open assertion while keeping history.

Structured nutrition and supplement intake storage also exists, but source adaptation and correction workflow remain follow-on work. A future parser can load normalized intake records through the intake load path; a future correction workflow should still follow the shape above by adding a new statement/record and preserving lineage rather than pretending intake corrections are warehouse rebuilds.
