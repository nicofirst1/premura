# Contract: `PluginParser` Protocol

> Mission: `v2-architectural-skeleton-01KS4SHA`
> Phase 1 contract document
> Authoritative agent-facing version: `src/premura/parsers/CONTRACT.md` (shipped with the package; this document defines what that file must contain).

## Purpose

Define the parser-side federated contract: what a community-PR'd (or AI-agent-generated) parser must provide, how it must map vendor-specific fields to canonical metric_ids, and how it surfaces mapping gaps for human review.

## Symbols

### `PluginParser(Parser, Protocol)` — defined in `src/premura/parsers/base.py`

```python
class PluginParser(Parser, Protocol):
    source_kind: str
    language_hint: str | None

    def parse(self, path: Path) -> PluginParseResult: ...
    def declares_metrics(self) -> list[str]: ...
```

### `PluginParseResult(ParseResult)` — defined in `src/premura/parsers/base.py`

```python
@dataclass(frozen=True)
class PluginParseResult(ParseResult):
    language_detected: str | None = None
    unmapped_metrics: list[str] = field(default_factory=list)
    confidence: float = 1.0
```

See [data-model.md](../data-model.md) §4 for full field semantics.

## Decision tree (mandatory for every vendor field)

For each field `X` in a vendor's data dump, the parser MUST resolve it to a canonical `metric_id` using this exact order:

```
Step 1: Existing-alias lookup
   suggest_metric(X)  →  hit?
     YES → use the returned metric_id. Done.
     NO  → continue to Step 2.

Step 2: Domain-aware standards lookup
   2a. Is X a clinical lab marker?
       YES → consult LOINC at https://loinc.org/search/
             Propose: metric_id = "lab:<english_canonical_name>"
                      loinc = "<LOINC code>"
                      aliases.en = [..., X]   (back-fill so future parsers find it)
             Add the new row to dim_metric.yaml in the SAME PR.

   2b. Is X a wearable/physiological metric?
       YES → consult IEEE 1752.1 schema.
             Propose: metric_id = "<english_canonical_name>"   (no prefix)
                      ieee1752 = "<IEEE code>"
                      aliases.en = [..., X]
             Add the new row to dim_metric.yaml in the SAME PR.

   2c. Neither standard covers it:
       Propose: metric_id = "vendor:<source>:<X>"
                aliases = {}
       Add the new row to dim_metric.yaml in the SAME PR.
       The vendor: namespace makes "we coined this" explicit.

Step 3: Genuinely irresolvable
   If for some reason the parser cannot decide (e.g., the field is structural
   metadata not a measurement, or the field's meaning is ambiguous and
   needs human inspection):
   - Skip the field at parse time.
   - Add X to PluginParseResult.unmapped_metrics.
   - The reviewer (human PR reviewer) decides what to do.
```

## The federated workflow

```
User drops vendor_x.zip in data/inbox/
       │
       ▼
User invokes parser-generator skill in Claude Code (or equivalent agent)
       │
       ▼
Agent reads src/premura/parsers/CONTRACT.md (this contract)
Agent reads vendor_x.zip contents (sample files)
Agent reads dim_metric.yaml (current ontology)
       │
       ▼
For each vendor field, agent follows the decision tree above.
       │
       ▼
Agent writes src/premura/parsers/vendor_x.py implementing PluginParser.
   - parse() returns PluginParseResult with:
       measurements, intervals: standard records
       language_detected: from _lang.detect_language(sample_text) or None
       unmapped_metrics: fields the parser gave up on
       confidence: parser's self-rating
   - declares_metrics() returns the canonical metric_ids parse() may emit
   - source_kind: vendor identifier
   - language_hint: known source language or None
       │
       ▼
Agent proposes any new dim_metric.yaml rows + aliases additions
in the same commit. Standards-first: LOINC for labs, IEEE 1752.1
for wearables, vendor:* fallback.
       │
       ▼
User runs locally: hpipe ingest data/inbox/vendor_x.zip
   Verifies rows land in hp.fact_measurement / hp.fact_interval.
   Spot-checks values and unmapped_metrics report.
       │
       ▼
If happy → user (or agent) opens PR.
PR reviewer cross-checks:
   - parser.declares_metrics() matches dim_metric.yaml additions
   - No derived:* metric_id emitted (C-011)
   - aliases.en includes the vendor's exact field names
   - Tests added (at minimum a parse-a-fixture test)
       │
       ▼
PR merges → vendor_x is now first-class.
```

## Rules enforced by review (not at runtime)

| Rule | Source | Enforcement |
|---|---|---|
| Parser MUST NOT emit `metric_id` starting with `derived:` | C-011 in [spec.md](../spec.md) | PR review; future CI grep on `parsers/*.py` and emitted records. |
| Parser MUST declare every emitted `metric_id` in `declares_metrics()` | This contract | PR review; runtime sanity check possible later via a wrapper. |
| New `dim_metric.yaml` rows MUST follow the row schema (see [data-model.md](../data-model.md) §2) | FR-017 | YAML smoke test; PR review. |
| Aliases additions MUST be in the same PR as the parser | This contract | PR review. |
| Lab markers MUST carry a real LOINC code or the `"[unmapped]"` placeholder | FR-017 | YAML smoke test. |
| Language detection MUST be local-only (no external API) | C-001 | Implementation review when `_lang/` actually ships. |

## What the skeleton ships vs. what implementation missions add

| Surface | Skeleton (this mission) | Future implementation mission |
|---|---|---|
| `PluginParser` Protocol | ✅ Defined in `parsers/base.py` | (no change needed) |
| `PluginParseResult` dataclass | ✅ Defined in `parsers/base.py` | (no change needed) |
| `suggest_metric()` | Stub raises `NotImplementedError` | Real reverse-index implementation |
| `detect_language()` | Stub raises `NotImplementedError` | Local detection (langdetect/pycld3) + optional local translation |
| `parsers/CONTRACT.md` | Full content shipped (this document materialised) | Updates as the contract evolves |
| Reference parsers using the new Protocol | None | One or more reference implementations (Oura, Withings, Apple Health, etc.) |
| `parser-generator` Claude Code skill | Stub manifest pointing to CONTRACT.md | Full generation playbook |
| CI grep enforcement for `derived:*` rule | Not in scope | Optional follow-up |

## Acceptance tests this contract implies (covered by `tests/test_skeleton.py`)

- `PluginParser` and `PluginParseResult` importable from `premura.parsers.base`.
- `PluginParseResult` is a dataclass subclass of `ParseResult`.
- `PluginParser` is a structural subtype of `Parser` (typing-only check).
- Existing 17 tests pass — proves `Parser` Protocol was not mutated.
- `parsers/CONTRACT.md` contains the strings `"LOINC"`, `"IEEE 1752.1"`, `"derived:"` (FR-009 verification).
- `AGENTS.md` at repo root references both the skill and `parsers/CONTRACT.md` (FR-010 verification).

## Open questions deferred to implementation missions

1. **`suggest_metric()` performance**: does the reverse-index need to be lazy-built, cached on disk, or rebuilt-per-call? Decision deferred to the mission that implements it. The skeleton commits no performance contract.

2. **Vendor-namespace canonicalization**: when two community parsers both add `vendor:withings:body_temp`, do they conflict? The skeleton's policy via C-005 (no row removal) means the first writer wins; reviewers must catch this at PR time. A future mission may add per-vendor name-scoping inside vendor namespaces.

3. **Translation fallback**: when `suggest_metric` misses and `detect_language` returns a non-English language, does the system attempt translation before standards lookup? The skeleton's docstring says local-only translation is on the TODO list; the decision tree above explicitly does NOT include a translation step (translation is fallback to the *human* reviewer, not to LOINC lookup).
