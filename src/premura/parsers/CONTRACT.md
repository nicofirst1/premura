# Premura parser plugin contract

> Audience: humans and AI agents authoring a new parser under `src/premura/parsers/`.
> Authority: this file ships with the package and is the source of truth for the
> federated parser contract.

## Two seams: observations vs. normalized intake

A parser produces data for one of **two** persistence seams. Pick by meaning, not by which path already exists:

| What the source row means | Emit | Lands in |
| --- | --- | --- |
| A body/physiological observation, reading, or aggregate (weight, heart rate, sleep stage, daily step total, expended kcal) | `Measurement` / `Interval` in an `IngestBatch` | `hp.fact_measurement` / `hp.fact_interval` |
| Narrative commentary or diagnosis text | `ClinicalNote` in an `IngestBatch` | `hp.fact_clinical_note` |
| An eating or drinking occurrence and its nutrient/energy amounts | `NutritionIntakeInput` in an `IntakeBatch` | `hp.nutrition_intake_event` / `_item` / `hp.nutrition_quantity` |
| A supplement-taking occurrence and its doses | `SupplementIntakeInput` in an `IntakeBatch` | `hp.supplement_intake_event` / `hp.supplement_item` / `hp.supplement_dose` |

**Nutrition and supplement intake are not observations.** Do not push a meal's
calories or a supplement dose into `Measurement`, `Interval`, or `ClinicalNote`
just because those paths are already wired. Intake has its own home and its own
seam; the `IntakeBatch` you emit is persisted by
`premura.store.profile_intake.persist_intake_batch`, never by the observation
loader. A wearable's *expended* kcal is an observation (`Interval`); a meal's
*consumed* kcal is `nutrition_intake`. Same unit, different meaning, different
home.

A single parser may emit **both** an `IngestBatch` (observations) and an
`IntakeBatch` (intake) from one source artifact when the artifact genuinely
carries both kinds of data. It must not fold one into the other. See
"Parser runtime output: observation, intake, or both" below for how `parse()`
returns each and how the runtime routes them.

One source class has its own interchange contract layered on top of this one:
AI-chat recalled supplement/medication intake
(`source_kind = "ai_chat_recall"`) is defined by
`docs/building/architecture/AI_CHAT_RECALL_CONTRACT.md` — a documented JSON
format any assistant's paste-prompt can target, consumed by
`parsers/ai_chat_recall.py` through this same intake seam.

Baseline profile facts (birth date, biological sex, declared height) are **not**
a parser concern at all: they are captured through the bounded agent-mediated
path `premura.store.profile_intake.record_profile_context`, which validates
against the closed allowlist in `premura.profile_fields`. Parsers never emit
profile assertions.

## Symbols you implement against

Both symbols live in `src/premura/parsers/base.py`.

### `PluginParser(Parser, Protocol)`

A structural protocol. Implementations must expose:

- `source_kind: str` — short stable identifier for the vendor or source.
- `language_hint: str | None` — ISO 639-1 code if the source labels are known to be in one language, else `None`.
- `def declares_metrics(self) -> list[str]` — every canonical `metric_id` the parser may emit.
- `def parse(self, path: Path) -> IngestBatch | ParseOutput` — parse the vendor
  file and return its output (see the next section). Returning a bare
  `IngestBatch` is observation-only and is the unchanged path every existing
  parser uses.

First-party parsers and plugin parsers now target the same seam.

## Parser runtime output: observation, intake, or both

`parse()` returns one of two shapes; the runtime normalizes either before
routing it to a persistence seam:

- **Observation-only (unchanged).** Return a bare `IngestBatch`. This is exactly
  the historical contract — **existing observation-only parsers are unchanged
  and stay supported**; intake support is purely additive and did **not** swap
  the return type out from under them.
- **Intake, or both.** Return a `ParseOutput(observation=..., intake=...)`
  carrying an optional `IngestBatch` and/or an optional `IntakeBatch`. Use this
  when the source carries intake (set `intake`), or carries both kinds of data
  from one artifact (set both fields).

The runtime calls the single dispatch helper
`premura.parsers.base.normalize_parse_output(output)`, which maps any parser
output to `(observation_batch | None, intake_batch | None)`. A bare `IngestBatch`
normalizes to `(batch, None)`. The runtime then sends the observation batch (if
any) to the observation loader and the intake batch (if any) to
`premura.store.profile_intake.persist_intake_batch`. **Intake never becomes a
`Measurement`, `Interval`, or `ClinicalNote`** — the two-seam / one-home rule
holds at the runtime boundary, not just in prose.

Every runtime call site (CLI ingest, the in-sandbox ingest runner, and the
live-trial harness) routes through `normalize_parse_output`; a new entry point
must do the same rather than re-implement the union handling.

### `IngestBatch`

The parser-to-loader seam for one source artifact. `IngestBatch` contains only loadable rows plus the provenance and review metadata needed to validate them at the warehouse seam. Relevant fields:

- `measurements` / `intervals` — loadable rows only.
- `clinical_notes` — optional narrative commentary / diagnosis text that belongs in the report but not in the numeric fact tables.
- `declared_metrics` — the canonical `metric_id` values this parser is allowed to emit.
- `source_descriptors` — provenance used to upsert `hp.dim_source` without out-of-band parser state.
- `unmapped_metrics` — raw vendor fields deliberately skipped because the decision tree produced no canonical `metric_id`.
- `skipped_rows` — source rows that resolved to a canonical metric but still produced no loadable row (for example unit mismatch, unsupported qualitative value, or a deferred follow-up marker).
- `language_detected` — code returned by `_lang.detect_language()` when used.
- `confidence` — parser self-rating for the batch.

The parser validates the batch before returning it. The loader validates it again before persistence. If any emitted row violates the contract, the whole batch fails.

### `IntakeBatch`

The parser-to-store seam for normalized **nutrition and supplement intake**. Distinct from `IngestBatch`: it carries intake occurrences, not observations, and is persisted by `premura.store.profile_intake.persist_intake_batch` rather than the observation loader. Fields:

- `nutrition_events` — `NutritionIntakeInput` rows. Each anchors one eating/drinking occurrence and may hold `items` (`NutritionItemInput`) and event-level or item-level `quantities` (`NutritionQuantityInput`, e.g. `energy`/`protein` in their source unit).
- `supplement_events` — `SupplementIntakeInput` rows. Each anchors one supplement-taking occurrence and may hold `items` (`SupplementItemInput`, naming a product and/or ingredient) with `doses` (`SupplementDoseInput`).
- `source_descriptors` — provenance used to upsert `hp.dim_source`, exactly as for `IngestBatch`. Every intake row's `source_id` must have a descriptor.
- `unmapped_metrics` — raw vendor fields an intake parser deliberately skipped because the decision tree produced no home for them. Same role as `IngestBatch.unmapped_metrics`: an intake parser declares an unmapped field here rather than dropping it silently or inventing a row.
- `skipped_rows` — source rows that had a home but still produced no loadable intake row (for example a malformed quantity), surfaced with a reason. Same role as `IngestBatch.skipped_rows`.
- `ingest_batch` — optional batch id recorded on each event for source-artifact loads.

`unmapped_metrics` and `skipped_rows` are **review metadata carried on the
batch, never loadable rows** — `persist_intake_batch` does not write them, the
same posture as `IngestBatch.unmapped_metrics`. An intake parser declares its
gaps exactly the way an observation parser does.

Validation that the store boundary enforces (also runnable on the batch via `validate()`):

- Each event carries a non-empty `dedupe_key`; the `dedupe_key` UNIQUE constraint makes re-loading the same source artifact idempotent (a duplicate event is skipped wholesale).
- A `NutritionQuantityInput` is attributed to either its item or the whole event (`subject`), never floating free.
- A `SupplementItemInput` names at least one of `product_label` / `ingredient_label`; an unknown brand-vs-ingredient situation stays representable rather than invented.
- A `SupplementDoseInput` carries at least one of `amount_num` / `amount_text`; partial knowledge is preserved, never fabricated as zero.

## The decision tree (mandatory for every vendor field)

For each field `X` in a vendor dump, resolve it to a canonical `metric_id` using this exact order:

1. **Existing alias.** Call `suggest_metric(X)`. If it returns a `metric_id`, use that and stop.
2. **`LOINC` for labs.** If `X` is a clinical laboratory marker, propose a new `dim_metric.yaml` row with `metric_id = "lab:<english_canonical_name>"` and the matching `loinc`.
3. **`IEEE 1752.1` for wearables.** If `X` is a wearable or physiological metric covered by IEEE 1752.1, propose a new row with `metric_id = "<english_canonical_name>"` and the matching `ieee1752`.
4. **Bare English canonical name.** For a reusable concept not covered by the above standards, propose a new row with `metric_id = "<english_canonical_name>"`.
5. **`vendor:*` fallback.** For source-specific or non-standard concepts, propose `metric_id = "vendor:<source>:<X>"`.

If no step applies because the field is structural metadata or genuinely ambiguous, do **not** invent a `metric_id`. Skip the field at parse time, append `X` to `IngestBatch.unmapped_metrics`, and let the reviewer decide whether it should become a canonical metric in a future PR. If the field *does* resolve to a canonical metric but the row still cannot become a measurement or interval, surface it via `IngestBatch.skipped_rows` with a reason instead.

## Alias rule

Aliases recorded in `dim_metric.yaml` must be clinically standard names or abbreviations only. They are not a free-text search index.

## The `derived:` namespace is off-limits to parsers

The `derived:` namespace is reserved for outputs of the Stage 2 engine. Parsers must not emit any `metric_id` that starts with `derived:`.

The Stage 2 engine has its own contributor contract at
`src/premura/engine/CONTRACT.md`. Read it before adding a Stage 2 signal that
answers a user-facing question (status / trend / baseline / change); it covers
the result envelopes, required caveats, and what Stage 2 must not claim.

## Same-PR rule for ontology additions

Every new `metric_id` a parser emits must be added to `src/premura/dim_metric.yaml` in the same PR as the parser code. This is enforced by both review and runtime: reviewers reject parser changes whose declared metrics do not appear in the ontology diff, and the loader rejects any `IngestBatch` whose declared metrics are missing from `dim_metric.yaml`.

## Reviewer checklist

When reviewing a parser PR, confirm:

- The decision tree was followed in order.
- No emitted `metric_id` starts with `derived:`.
- `declares_metrics()` matches the set of emitted `metric_id` values.
- The ontology diff includes every newly emitted canonical metric.
- New aliases are clinically standard names or abbreviations only.
- The parser ships at least one fixture-driven test.
- Any field surfaced in `unmapped_metrics` or `skipped_rows` includes a PR note explaining why it was skipped.
