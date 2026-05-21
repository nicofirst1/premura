---
name: premura-parser-generator
description: Generate a new Premura `PluginParser` for an unmapped health-data vendor export. Use when the user asks to "add a parser for X", "ingest a new wearable", "support a new source", "write a parser plugin for <vendor>", or any variant of teaching Premura to read an unfamiliar CSV/JSON/SQLite/zip dump from a wearable, app, or clinical export. Walks the author through the federated parser contract and produces a parser module under `src/premura/parsers/` plus the matching `dim_metric.yaml` rows.
---

# Premura parser generator

You are helping the user add a new parser plugin to Premura — the personal
health-data warehouse. A "parser" reads a single vendor's GDPR export (CSV,
JSON, SQLite, zip-of-the-above, etc.) and produces normalized measurements
and intervals tagged with canonical `metric_id` values from the project's
ontology.

## Authoritative contract — read this first

**Do not embed the contract here.** The authoritative parser contract ships
with the package at:

> `src/premura/parsers/CONTRACT.md`

Read that file before you write any code. It defines:

- `PluginParser` (structural protocol) and `PluginParseResult` (dataclass
  — treat as write-once even though it is not declared `frozen=True`; see
  `CONTRACT.md` for the rationale) — the exact symbols your parser must
  satisfy.
- The decision tree mapping raw vendor field names onto canonical
  `metric_id` values.
- Rules for `unmapped_metrics`, `language_detected`, and `confidence`.
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
