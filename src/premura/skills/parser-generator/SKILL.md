---
name: premura-parser-generator
description: Generate a new Premura `PluginParser` (observation and/or intake) for an unmapped vendor health-data export. Use when the user wants Premura to read a new source — a vendor/app/wearable/clinical CSV, JSON, SQLite, or zip no existing parser handles. Not for debugging an existing parser.
---

# Premura parser generator

You are helping the user add a new parser plugin to Premura — the personal health-data warehouse. A "parser" reads a single vendor's GDPR export (CSV, JSON, SQLite, zip-of-the-above, etc.) and produces normalized data tagged with canonical `metric_id` values from the project's ontology.

A source can carry two **separate seams** of data, and a parser may emit either or both:

- **Observations** — point-in-time measurements and bounded intervals carried in an `IngestBatch` (the original, default path).
- **Normalized intake** — nutrition (eating/drinking occurrences) and supplement (supplement-taking occurrences) carried in an `IntakeBatch`. Intake is **not** an observation and never becomes a `fact_measurement` / `fact_interval` / note row.

The two seams are intentionally separate so a parser cannot back-fill intake into the fact tables just because that path exists (a meal's _consumed_ kcal is `nutrition_intake`; a wearable's _expended_ kcal is an observation — same unit, different meaning, different home).

## Authoritative contract — read this first

**Do not embed the contract here.** The authoritative parser contract ships with the package at:

> `src/premura/parsers/CONTRACT.md`

Read that file before you write any code. It defines:

- `PluginParser` (structural protocol) and `IngestBatch` (the parser-to-loader seam) — the exact symbols your parser must satisfy.
- The decision tree mapping raw vendor field names onto canonical `metric_id` values.
- Rules for `unmapped_metrics`, `language_detected`, `confidence`, and strict batch validation.
- How `dim_metric.yaml` extensions interact with the parser.

If `CONTRACT.md` ever disagrees with this skill, `CONTRACT.md` wins.

## Workflow

1. Read `src/premura/parsers/CONTRACT.md` end-to-end.
2. Inspect the user's sample file (header sniff, JSON schema, SQLite schema).
3. Walk the contract's decision tree against the field names you see; record anything that does not produce a canonical `metric_id` so it can become an `unmapped_metrics` entry.
4. Draft the parser module, the `dim_metric.yaml` additions, and the test fixture. Done when the parser passes every item in CONTRACT.md's "Reviewer checklist".
5. Run `uv run pytest -q tests/test_parsers/` and `uv run ruff check src/premura/parsers/` before handing off.

If you are blocked because the contract is ambiguous for a specific field, say so explicitly and surface the ambiguity to the user rather than guessing — the contract is intentionally allowed to evolve when reviewers agree.

## What you produce

A typical run of this skill yields, all under `src/premura/parsers/<source>/` (or a single module if the parser is small):

1. A parser module exposing the `PluginParser` protocol from `src/premura/parsers/base.py`.
2. Any new canonical `metric_id` rows appended to `src/premura/dim_metric.yaml`, one per metric the parser declares via `declares_metrics()`.
3. A short test fixture under `tests/test_parsers/` exercising at least one sample row per declared metric, plus the `unmapped_metrics` surface for any field the contract's decision tree skipped.

Keep the parser local: no network calls, no API keys, no language detection beyond the `_lang.detect_language` helper shipped in `src/premura/parsers/_lang/`.

## Intake parsers (nutrition / supplement)

Emit intake, not an observation, when the source row is an eating/drinking or supplement-taking **occurrence** rather than a physiological reading (a meal's consumed kcal is intake; a wearable's expended kcal is an observation — same unit, different meaning).

Return `ParseOutput(intake=<IntakeBatch>, observation=<IngestBatch | None>)` — part of the `ParserOutput = IngestBatch | ParseOutput` union — instead of a bare `IngestBatch` whenever you emit intake. Every entry point normalizes either shape via `normalize_parse_output` and persists the intake half through `premura.store.profile_intake.persist_intake_batch`; you never call either yourself.

An `IntakeBatch` carries `nutrition_events` (`NutritionIntakeInput` with `NutritionItemInput` / `NutritionQuantityInput`), `supplement_events` (`SupplementIntakeInput` with `SupplementItemInput` / `SupplementDoseInput`), `source_descriptors` (`SourceDescriptor`), and the review surfaces `unmapped_metrics` / `skipped_rows` (`SkippedRow`) — see `base.py` for exact shapes.

**Build-and-use boundary (no review for own data).** A runtime agent may build-and-use an intake parser on the operator's own data with no review; review gates only a parser later contributed back as a public PR.

Read `src/premura/parsers/CONTRACT.md` §"Two seams" for the full validation rules. A worked example lives at `tests/fixtures/intake/reference_parser.py`.
