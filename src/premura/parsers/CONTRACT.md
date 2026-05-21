# Premura parser plugin contract

> Audience: humans and AI agents authoring a new parser under `src/premura/parsers/`.
> Authority: this file ships with the package and is the source of truth for the
> federated parser contract.

## Symbols you implement against

Both symbols live in `src/premura/parsers/base.py`.

### `PluginParser(Parser, Protocol)`

A structural protocol. Implementations must expose:

- `source_kind: str` — short stable identifier for the vendor or source.
- `language_hint: str | None` — ISO 639-1 code if the source labels are known to be in one language, else `None`.
- `def declares_metrics(self) -> list[str]` — every canonical `metric_id` the parser may emit.
- `def parse(self, path: Path) -> IngestBatch` — parse the vendor file and return one ingest batch.

First-party parsers and plugin parsers now target the same seam.

### `IngestBatch`

The parser-to-loader seam for one source artifact. `IngestBatch` contains only loadable rows plus the provenance and review metadata needed to validate them at the warehouse seam. Relevant fields:

- `measurements` / `intervals` — loadable rows only.
- `declared_metrics` — the canonical `metric_id` values this parser is allowed to emit.
- `source_descriptors` — provenance used to upsert `hp.dim_source` without out-of-band parser state.
- `unmapped_metrics` — raw vendor fields deliberately skipped because the decision tree produced no canonical `metric_id`.
- `language_detected` — code returned by `_lang.detect_language()` when used.
- `confidence` — parser self-rating for the batch.

The parser validates the batch before returning it. The loader validates it again before persistence. If any emitted row violates the contract, the whole batch fails.

## The decision tree (mandatory for every vendor field)

For each field `X` in a vendor dump, resolve it to a canonical `metric_id` using this exact order:

1. **Existing alias.** Call `suggest_metric(X)`. If it returns a `metric_id`, use that and stop.
2. **`LOINC` for labs.** If `X` is a clinical laboratory marker, propose a new `dim_metric.yaml` row with `metric_id = "lab:<english_canonical_name>"` and the matching `loinc`.
3. **`IEEE 1752.1` for wearables.** If `X` is a wearable or physiological metric covered by IEEE 1752.1, propose a new row with `metric_id = "<english_canonical_name>"` and the matching `ieee1752`.
4. **Bare English canonical name.** For a reusable concept not covered by the above standards, propose a new row with `metric_id = "<english_canonical_name>"`.
5. **`vendor:*` fallback.** For source-specific or non-standard concepts, propose `metric_id = "vendor:<source>:<X>"`.

If no step applies because the field is structural metadata or genuinely ambiguous, do **not** invent a `metric_id`. Skip the field at parse time, append `X` to `IngestBatch.unmapped_metrics`, and let the reviewer decide whether it should become a canonical metric in a future PR.

## Alias rule

Aliases recorded in `dim_metric.yaml` must be clinically standard names or abbreviations only. They are not a free-text search index.

## The `derived:` namespace is off-limits to parsers

The `derived:` namespace is reserved for outputs of the Stage 2 engine. Parsers must not emit any `metric_id` that starts with `derived:`.

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
- Any field surfaced in `unmapped_metrics` includes a PR note explaining why it was skipped.
