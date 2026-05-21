# Premura parser plugin contract

> Audience: humans and AI agents authoring a new parser under `src/premura/parsers/`.
> Authority: this file ships with the package and is the source of truth for the
> federated parser contract. The mission-level planning document at
> `kitty-specs/v2-architectural-skeleton-01KS4SHA/contracts/plugin-parser.md`
> defines what this file must contain; this file is what implementers actually
> read at PR time.

## Symbols you implement against

Both symbols live in `src/premura/parsers/base.py`.

### `PluginParser(Parser, Protocol)`

A structural protocol — implementers do not subclass; any object that
matches the shape satisfies the protocol. Implementations must expose:

- `source_kind: str` — short stable identifier for the vendor / source
  (for example `"oura"`, `"withings"`, `"apple_health"`).
- `language_hint: str | None` — ISO 639-1 code if the source's field labels
  are known to be in a single language, else `None` to defer to
  `_lang.detect_language`.
- `def declares_metrics(self) -> list[str]` — every canonical `metric_id`
  that `parse()` may emit. Reviewers cross-check this against the
  `dim_metric.yaml` rows your PR adds.
- `def parse(self, path: Path) -> PluginParseResult` — actually parse the
  vendor file and return the result described below.

The structural-subtype relationship with the v1 `Parser` protocol is
deliberate: existing v1 parsers stay valid against the original `Parser`
contract with no migration required.

### `PluginParseResult(ParseResult)`

A dataclass that extends `ParseResult` with three additive fields. It is
intentionally **not** declared `frozen=True`: Python's dataclass machinery
forbids a frozen subclass of the non-frozen `ParseResult`, and this mission
requires `ParseResult` itself to stay unchanged. Treat the instance as
write-once at parse time even though the runtime does not enforce
immutability — see the matching note on `PluginParseResult` in
`src/premura/parsers/base.py`. Fields:

- `language_detected: str | None = None` — code returned by
  `_lang.detect_language()` (or `None` if not run). Local-only — no
  external API calls.
- `unmapped_metrics: list[str] = field(default_factory=list)` — raw vendor
  field names you deliberately skipped because the decision tree below
  produced no canonical `metric_id`. Surfacing them here is the contract
  for handing them to the human reviewer.
- `confidence: float = 1.0` — your self-rating in `[0.0, 1.0]` for the
  batch as a whole.

The existing `Measurement`, `Interval`, `ParseResult`, and `Parser` symbols
are unchanged.

## The decision tree (mandatory for every vendor field)

For each field `X` in a vendor's data dump, resolve it to a canonical
`metric_id` using this exact order. The ordering is non-negotiable:

1. **Existing alias.** Call `suggest_metric(X)`. If it returns a
   `metric_id`, use that and stop. This is the single most important
   guarantee — it keeps two parsers from coining different names for the
   same concept.
2. **`LOINC` for labs.** If `X` is a clinical laboratory marker, look it
   up in [LOINC](https://loinc.org/search/) and propose a new
   `dim_metric.yaml` row with:
   - `metric_id = "lab:<english_canonical_name>"`,
   - `loinc = "<LOINC code>"`,
   - `aliases` containing clinically standard names and abbreviations
     only.
3. **`IEEE 1752.1` for wearables.** If `X` is a wearable / physiological
   metric covered by the IEEE 1752.1 mobile-health schema, propose a new
   row with:
   - `metric_id = "<english_canonical_name>"` (no prefix),
   - `ieee1752 = "<IEEE code>"`,
   - `aliases` containing clinically standard names and abbreviations
     only.
4. **Bare English canonical name** for any reusable concept that neither
   LOINC nor IEEE 1752.1 covers but that is real and cross-vendor:
   - `metric_id = "<english_canonical_name>"` (no prefix),
   - `aliases` containing clinically standard names and abbreviations
     only.
5. **`vendor:*` fallback** for source-specific or non-standard concepts:
   - `metric_id = "vendor:<source>:<X>"`,
   - `aliases = {}`.

If for some reason no step applies (the field is structural metadata, or
its meaning is genuinely ambiguous), do NOT invent a `metric_id`. Skip the
field at parse time, append `X` to `PluginParseResult.unmapped_metrics`,
and let the human reviewer decide.

## Alias rule

Aliases recorded in `dim_metric.yaml` MUST be clinically standard names or
abbreviations only. They are not a free-text search index. A reviewer
should be able to read each alias and recognise it as something a
clinician, lab, or device vendor would use in writing. Marketing slogans,
loose user phrasing, and non-standard nicknames do not belong here.

## The `derived:` namespace is off-limits to parsers

The `derived:` `metric_id` namespace is reserved for outputs of the Stage 2
engine (signal computations such as `derived:ast_alt_ratio`). Parsers MUST
NOT emit any `metric_id` whose value starts with `derived:`. Future CI may
grep parser modules and emitted records for this prefix.

## Same-PR rule for ontology additions

Every new `metric_id` your parser emits MUST be added to
`src/premura/dim_metric.yaml` **in the same PR** as the parser code. This
is enforced by review, not by runtime; PR reviewers will reject parser
changes whose declared metrics do not appear in the ontology diff. The
goal is to keep the ontology and the parsing layer atomically in sync — a
parser emitting a `metric_id` that does not exist in `dim_metric.yaml` is
a bug.

## Reviewer checklist

When reviewing a parser PR, confirm:

- The decision tree was followed in order; the first applicable step won.
- No `metric_id` starts with `derived:`.
- `declares_metrics()` matches the set of `metric_id`s the parser actually
  emits and matches the ontology rows the PR adds.
- New aliases are clinically standard names or abbreviations only.
- LOINC codes are real (look them up) for any new `lab:*` rows.
- The parser passes at least one fixture-driven test.
- Any field surfaced in `unmapped_metrics` has a comment or PR note
  explaining why it was skipped.
