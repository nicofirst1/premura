---
name: premura-parser-generator
description: Generate a new Premura `PluginParser` for an unmapped health-data vendor export. Use when the user asks to "add a parser for X", "ingest a new wearable", "support a new source", "write a parser plugin for <vendor>", or any variant of teaching Premura to read an unfamiliar CSV/JSON/SQLite/zip dump from a wearable, app, or clinical export. Walks the author through the federated parser contract and produces a parser module under `src/premura/parsers/` plus the matching `dim_metric.yaml` rows.
---

# Premura parser generator

You are helping the user add a new parser plugin to Premura — the personal
health-data warehouse. A "parser" reads a single vendor's GDPR export (CSV,
JSON, SQLite, zip-of-the-above, etc.) and produces normalized data tagged with
canonical `metric_id` values from the project's ontology.

A source can carry two **separate seams** of data, and a parser may emit either
or both:

- **Observations** — point-in-time measurements and bounded intervals carried in
  an `IngestBatch` (the original, default path).
- **Normalized intake** — nutrition (eating/drinking occurrences) and supplement
  (supplement-taking occurrences) carried in an `IntakeBatch`. Intake is **not**
  an observation and never becomes a `fact_measurement` / `fact_interval` /
  note row.

The two seams are intentionally separate so a parser cannot back-fill intake
into the fact tables just because that path exists (a meal's *consumed* kcal is
`nutrition_intake`; a wearable's *expended* kcal is an observation — same unit,
different meaning, different home).

## Authoritative contract — read this first

**Do not embed the contract here.** The authoritative parser contract ships
with the package at:

> `src/premura/parsers/CONTRACT.md`

Read that file before you write any code. It defines:

- `PluginParser` (structural protocol) and `IngestBatch` (the parser-to-loader
  seam) — the exact symbols your parser must satisfy.
- The decision tree mapping raw vendor field names onto canonical
  `metric_id` values.
- Rules for `unmapped_metrics`, `language_detected`, `confidence`, and strict
  batch validation.
- How `dim_metric.yaml` extensions interact with the parser.

If `CONTRACT.md` ever disagrees with this skill, `CONTRACT.md` wins.

## When to invoke this skill

Trigger this skill when the user is asking to extend Premura with a *new
source*, not when they are debugging an existing one. Concrete cues:

- "Add a parser for <vendor>" / "support <wearable>" / "ingest <app>'s
  export".
- A new file format showing up in `data/inbox/` that none of the existing
  parsers (`hc`, `garmin`, `saa`, `bmt`) handle.
- The user pastes a sample export and asks "what would this look like as a
  parser?".

Do **not** invoke for: bug fixes inside an existing parser, schema
migrations, changes to the ingest CLI, or general DuckDB questions.

## What you produce

A typical run of this skill yields, all under `src/premura/parsers/<source>/`
(or a single module if the parser is small):

1. A parser module exposing the `PluginParser` protocol from
   `src/premura/parsers/base.py`.
2. Any new canonical `metric_id` rows appended to `src/premura/dim_metric.yaml`,
   one per metric the parser declares via `declares_metrics()`.
3. A short test fixture under `tests/test_parsers/` exercising at least one
   sample row per declared metric, plus the `unmapped_metrics` surface for any
   field the contract's decision tree skipped.

Keep the parser local: no network calls, no API keys, no language detection
beyond the `_lang.detect_language` helper shipped in `src/premura/parsers/_lang/`.

## Intake parsers (nutrition / supplement)

When the source carries **intake** rather than (or in addition to) observations,
the parser emits an `IntakeBatch` instead of (or alongside) an `IngestBatch`.
The authoritative shape lives in `src/premura/parsers/CONTRACT.md`
(§"Two seams" and §"Parser runtime output: observation, intake, or both") and in
`src/premura/parsers/base.py` — read those; the summary below must match them
exactly.

**The return type.** A parser's `parse(path)` may return:

- a bare `IngestBatch` — observation-only, the existing path, **unchanged and
  still supported** (the runtime normalizes this case); or
- a `ParseOutput(observation=<IngestBatch | None>, intake=<IntakeBatch | None>)`
  — use this whenever you emit intake, setting `intake=` (and optionally
  `observation=` when one source carries both kinds).

`ParseOutput` is the smallest backward-compatible shape: an *optional* second
return type, not a swap of the first, so no existing parser is touched. The
union is `ParserOutput = IngestBatch | ParseOutput`, and the structural protocol
in `base.py` types `parse` as `def parse(self, path: Path) -> ParserOutput`.

**How it is persisted (the runtime load path).** Every entry point routes a
parser's return value through the single dispatch helper
`premura.parsers.base.normalize_parse_output(output)`, which maps any output to
`(observation_batch | None, intake_batch | None)`. The runtime then sends the
observation batch (if any) to the observation loader and the intake batch (if
any) to `premura.store.profile_intake.persist_intake_batch`. **You do not call
`normalize_parse_output` or `persist_intake_batch` yourself** — you only return
the right shape; the runtime does the rest. Intake never becomes an observation
row.

**What an `IntakeBatch` carries** (see `base.py` for exact dataclasses):

- `nutrition_events: list[NutritionIntakeInput]` — each an eating/drinking
  occurrence with `items` (`NutritionItemInput`) and `quantities`
  (`NutritionQuantityInput`, keyed by `quantity_key` such as `energy` /
  `protein`); event-level totals go on `event_quantities` with
  `subject="event"`, per-item amounts on each item, so a whole-meal kcal is not
  double-counted against item kcal.
- `supplement_events: list[SupplementIntakeInput]` — each a supplement-taking
  occurrence with `items` (`SupplementItemInput`, naming a `product_label`
  and/or `ingredient_label`) and `doses` (`SupplementDoseInput`, requiring at
  least one of `amount_num` or `amount_text` — a text-only "one scoop" dose is
  valid).
- `source_descriptors: dict[str, SourceDescriptor]` — provenance; every intake
  row's `source_id` must have a descriptor (same rule as `IngestBatch`).
- `unmapped_metrics: list[str]` and `skipped_rows: list[SkippedRow]` — the
  review surfaces, mirroring `IngestBatch` exactly (see "Declaring gaps" below).

Each input type has a `validate()` that enforces one-home separation (a quantity
needs a parent, a supplement item must name a product or ingredient, a dose must
carry an amount), and `IntakeBatch.validate()` also enforces source-descriptor
coverage and per-domain dedupe-key uniqueness.

**Declaring gaps (standards-first).** A source column with no canonical home is
**declared as a gap**, never silently dropped: surface it on
`IntakeBatch.unmapped_metrics` (a field the decision tree found no home for) or
`IntakeBatch.skipped_rows` (a row that had a home but produced no loadable
intake row). These ride on the batch for review and are **never loadable rows** —
`persist_intake_batch` does not write them, exactly as for
`IngestBatch.unmapped_metrics`.

**Build-and-use boundary (no review for own data).** A runtime agent may
**build-and-use** an intake parser on the operator's **own** data with **no
review** — write it, load the operator's data, use it immediately. Review gates
**only** a parser the operator later chooses to **contribute back as a public
PR**. (Per ADR 0010 / DOCTRINE; the same boundary as observation parsers.)

A minimal, end-to-end worked example of `parse → IntakeBatch → persist` lives at
`tests/fixtures/intake/reference_parser.py` (a synthetic proof anchor, not a
production vendor parser — do not copy real exports). For the domain-agnostic
rule on making a declared intake dimension *usable* by analysis (resolver →
signal → tool), see `docs/building/architecture/INTAKE_DIMENSIONS.md`.

## Workflow

1. Read `src/premura/parsers/CONTRACT.md` end-to-end.
2. Inspect the user's sample file (header sniff, JSON schema, SQLite schema).
3. Walk the contract's decision tree against the field names you see; record
   anything that does not produce a canonical `metric_id` so it can become an
   `unmapped_metrics` entry.
4. Draft the parser module, the `dim_metric.yaml` additions, and the test
   fixture.
5. Run `uv run pytest -q tests/test_parsers/` and `uv run ruff check
   src/premura/parsers/` before handing off.

If you are blocked because the contract is ambiguous for a specific field,
say so explicitly and surface the ambiguity to the user rather than
guessing — the contract is intentionally allowed to evolve when reviewers
agree.
