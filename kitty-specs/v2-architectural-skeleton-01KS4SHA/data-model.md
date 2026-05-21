# Phase 1 — Data Model: v2 Architectural Skeleton

> Mission: `v2-architectural-skeleton-01KS4SHA`
> Date: 2026-05-21
> Purpose: Document the concrete data shapes the skeleton commits to. Implementation work in subsequent missions must honor these exactly.

## Overview

This skeleton mission commits four data shapes:

1. **Extended `hp.dim_metric` table** — six new nullable columns on the existing DuckDB table.
2. **Extended `dim_metric.yaml` row** — six new optional fields per row in the seed YAML.
3. **`SignalSpec` dataclass** — new Python type in `src/premura/engine/_registry.py`.
4. **`PluginParseResult` dataclass** — new Python type in `src/premura/parsers/base.py`, extending the existing `ParseResult`.

The existing `Measurement`, `Interval`, `ParseResult`, and `Parser` symbols in `parsers/base.py` are **untouched** (C-006).

---

## 1. `hp.dim_metric` — extended schema

### Existing columns (from `001_init.sql`, unchanged by this mission)

| Column | Type | Constraint | Source |
|---|---|---|---|
| `metric_id` | `VARCHAR` | `PRIMARY KEY` | Canonical English name, may be prefixed (`lab:*`, `derived:*`, `vendor:<src>:*`, `bmt_custom:*`). Broad invented domain prefixes are intentionally avoided in this mission. |
| `display_name` | `VARCHAR` | `NOT NULL` | Human-readable label. |
| `canonical_unit` | `VARCHAR` | `NOT NULL` | The unit every `Measurement` for this metric carries (e.g., `kg`, `bpm`, `mmol/L`). |
| `value_kind` | `VARCHAR` | `NOT NULL` | One of: `instantaneous`, `aggregate`, `interval`. |
| `description` | `VARCHAR` | nullable | Free-text. |

### New columns (added in `002_dim_metric_ontology.sql`)

All six are nullable to preserve backward compatibility for the existing 43 rows.

| Column | Type | Purpose | Example |
|---|---|---|---|
| `category` | `VARCHAR` | Coarse domain grouping. Used by engine `list_by_domain` (Stage 2) once implemented. | `"cardiovascular"`, `"blood:cbc"`, `"blood:lipids"`, `"sleep"`, `"body_composition"`, `"urine"`, `"stool"`, `"derived"`. |
| `validity_window` | `VARCHAR` | ISO 8601 duration after which a value should not be treated as "current" without override. Read by Stage 2's `validate_window` and `check_inputs_available` functions. | `"PT1H"` (HRV: 1 hour), `"P1W"` (weight: 1 week), `"P3M"` (HbA1c: 3 months), `"P0D"` (no decay) where applicable. |
| `missing_data_policy` | `VARCHAR` | How Stage 2 should treat gaps for this metric. | `"none"`, `"last_observation_carried_forward"`, `"linear_interp"`, `"seasonal_naive"`. Default `"none"` for lab markers; `"last_observation_carried_forward"` for slowly-changing physical state (weight, height). |
| `aliases` | `JSON` | Multilingual + vendor synonyms. Flat per-language buckets. Used by `parsers/lookup.suggest_metric()` for vendor-field-to-canonical mapping. | `{"en":["Hb","Hgb"],"it":["emoglobina","HB"],"de":["Hämoglobin","Hb"]}` |
| `loinc` | `VARCHAR` | LOINC code (Regenstrief) where one exists. Required for `lab:*` rows (use `"[unmapped]"` placeholder if no LOINC code applies). | `"718-7"` (hemoglobin), `"2093-3"` (total cholesterol). |
| `ieee1752` | `VARCHAR` | IEEE 1752.1 code for wearable/physiological metrics where one exists. | (Codes per IEEE 1752.1 schema; null where the standard doesn't cover the metric.) |

### Constraints on the new columns

- All nullable (NFR-007).
- `category` MUST be non-null for every row after this mission ships (FR-017) — even pre-existing rows get a category assignment in the YAML seed.
- `lab:*` `metric_id` rows MUST have `loinc` set to either a real LOINC code or the literal placeholder string `"[unmapped]"` (FR-017).
- `aliases` JSON shape:
  ```typescript
  {
    "<lang_code>": ["<alias_string>", ...],   // lang_code is ISO 639-1 ("en", "it", "de", ...)
    ...
  }
  ```
  Only clinically standard names and abbreviations belong in these buckets. Raw vendor-local labels (for example `"body_battery_score"`) stay out unless they are themselves standard.

### Migration

`src/premura/store/migrations/002_dim_metric_ontology.sql`:

```sql
-- v2 architectural skeleton — ontology schema extension.
-- Adds nullable columns to hp.dim_metric for: category, validity_window,
-- missing_data_policy, aliases (JSON), loinc, ieee1752.
--
-- Idempotent: uses ADD COLUMN IF NOT EXISTS (DuckDB >= 0.8; project pin >=1.1).
-- Backward-compatible: all new columns are nullable, so pre-existing rows
-- continue to work without backfill.

ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS category VARCHAR;
ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS validity_window VARCHAR;
ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS missing_data_policy VARCHAR;
ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS aliases JSON;
ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS loinc VARCHAR;
ALTER TABLE hp.dim_metric ADD COLUMN IF NOT EXISTS ieee1752 VARCHAR;
```

### Loader update

`src/premura/store/duck.py:seed_dim_metric` (modified) reads the six new fields via `row.get(...)` (returns None for missing keys) and includes them in the INSERT...ON CONFLICT UPDATE:

```python
def seed_dim_metric(conn: duckdb.DuckDBPyConnection) -> int:
    yaml_text = resources.files("premura").joinpath(DIM_METRIC_YAML).read_text(encoding="utf-8")
    data = yaml.safe_load(yaml_text) or []
    for row in data:
        conn.execute(
            """
            INSERT INTO hp.dim_metric (
                metric_id, display_name, canonical_unit, value_kind, description,
                category, validity_window, missing_data_policy, aliases, loinc, ieee1752
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT (metric_id) DO UPDATE SET
                display_name = EXCLUDED.display_name,
                canonical_unit = EXCLUDED.canonical_unit,
                value_kind = EXCLUDED.value_kind,
                description = EXCLUDED.description,
                category = EXCLUDED.category,
                validity_window = EXCLUDED.validity_window,
                missing_data_policy = EXCLUDED.missing_data_policy,
                aliases = EXCLUDED.aliases,
                loinc = EXCLUDED.loinc,
                ieee1752 = EXCLUDED.ieee1752
            """,
            [
                row["metric_id"],
                row["display_name"],
                row["canonical_unit"],
                row["value_kind"],
                row.get("description"),
                row.get("category"),
                row.get("validity_window"),
                row.get("missing_data_policy"),
                json.dumps(row.get("aliases")) if row.get("aliases") else None,
                row.get("loinc"),
                row.get("ieee1752"),
            ],
        )
    return conn.execute("SELECT COUNT(*) FROM hp.dim_metric").fetchone()[0]
```

---

## 2. `dim_metric.yaml` — row shape

### Existing 5-field shape (still valid for legacy rows in this mission)

```yaml
- metric_id: heart_rate
  display_name: Heart rate
  canonical_unit: bpm
  value_kind: instantaneous
  description: Instantaneous heart rate sample.
```

### Extended shape (all new rows in this mission MUST use this form; existing rows get `category` added)

```yaml
- metric_id: lab:hemoglobin
  display_name: Hemoglobin
  canonical_unit: g/dL
  value_kind: instantaneous
  description: Total haemoglobin in blood, principal oxygen carrier.
  category: blood:cbc
  validity_window: P3M
  missing_data_policy: none
  aliases:
    en: [Hb, Hgb, hemoglobin_total]
    it: [emoglobina, HB]
    de: [Hämoglobin, Hb]
  loinc: "718-7"
  ieee1752: null
```

### Field-by-field expectations for new rows

| Field | Required? | Notes |
|---|---|---|
| `metric_id` | yes | Canonical English name. `lab:*` for clinical labs, `derived:*` reserved for Stage 2 outputs (C-011), `vendor:<src>:*` for vendor-namespaced fallbacks, no prefix for general wearable/physiological metrics. |
| `display_name` | yes | Human-readable. |
| `canonical_unit` | yes | Match existing `unit` conventions in spec.md §5 (e.g., `kg`, `mmol/L`, `bpm`, `%`). |
| `value_kind` | yes | `instantaneous` / `aggregate` / `interval`. |
| `description` | recommended | One-line natural-language description. Important for Stage 4 (teaching layer). |
| `category` | **required (FR-017)** | Coarse domain grouping. New for this mission. |
| `validity_window` | recommended | ISO 8601 duration. Defaults to null = "no policy declared". |
| `missing_data_policy` | recommended | One of the four documented values. Defaults to null = "treated as `none` at runtime". |
| `aliases` | recommended | Multilingual clinically standard names / abbreviations. Empty / missing means lookup falls through to standards. |
| `loinc` | **required for `lab:*` rows** | Real LOINC code or `"[unmapped]"` placeholder. Quote the value if it starts with a digit (YAML safety). |
| `ieee1752` | optional | Null where the standard doesn't cover the metric. |

### Row count target

- Starting: 43 rows.
- Floor: 140 rows after this mission (per FR-017).
- Target: ~150 (±10).
- Composition:
  - Wearable expansion: ~40 new rows (HRV variants, HR variants, respiratory, SpO2, sleep stages, training metrics).
  - CBC + chemistry + lipids + liver/kidney + electrolytes + thyroid + iron + vitamins + inflammation + endocrine: ~80 lab rows.
  - Urine starter: ~15 rows.
  - Stool starter: ~15 rows.

### Canonical-vocabulary note

- The current 43 legacy v1 rows keep their existing `metric_id`s in this mission.
- This mission defines the future canonical-vocabulary policy but does **not** perform the legacy-ID rewrite.
- The eventual rewrite will happen via a later **full rebuild from raw inputs**, not an in-place migration.

---

## 3. `SignalSpec` — engine registry record

`src/premura/engine/_registry.py`:

```python
"""Engine signal registry — the open boundary of Stage 2.

This module defines the data shape that signal functions register against.
Importing this module never imports any actual signal implementation.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, Optional


@dataclass(frozen=True)
class SignalSpec:
    """One signal function's registration record.

    See parsers/CONTRACT.md for the parsers-side companion contract.
    See STAGES.md for the four-stage architecture this slots into.
    """
    name: str
    """Unique short identifier within the registry. Snake_case. Example: "ast_alt_ratio"."""

    domain: list[str]
    """One or more domain tags the signal serves. Used by MCP's list_by_domain
    discovery. Example: ["liver", "metabolic"]."""

    inputs: list[str]
    """Canonical metric_ids this signal needs as input. Example: ["lab:ast", "lab:alt"]."""

    output: Optional[str] = None
    """Canonical metric_id this signal produces, or None for transient outputs.
    If set, MUST start with "derived:" per C-011. Example: "derived:ast_alt_ratio"."""

    priority: str = "normal"
    """One of "high" / "normal" / "low". MCP surfaces missing-input gaps to the
    user only for high-priority signals (per Scenario D in spec.md §6)."""

    auto_safe: bool = False
    """If True, the ingest loader may auto-precompute this signal after parsing
    when its inputs land in the new batch. Conservative default False — only
    derivations with super-low noise-introduction probability should opt in."""

    revision: str = "1"
    """Bump when the function's derivation logic materially changes. Stored in
    raw_payload of any persisted derived:* row, so a future `hpipe revalidate`
    command can identify stale outputs. See docs/UPDATE_STRATEGY.md."""

    fn: Optional[Callable] = None
    """The actual function. Set by the @signal(...) decorator. None at definition
    time means the spec was declared without a function body (test-only)."""


REGISTRY: dict[str, SignalSpec] = {}
"""Module-level registry. Empty at import time; populated by @signal(...) decorators
when signal implementation modules are imported. Stage 2 implementation missions
will define those modules; this skeleton mission ships an empty registry."""


def signal(
    *,
    name: str,
    domain: list[str],
    inputs: list[str],
    output: Optional[str] = None,
    priority: str = "normal",
    auto_safe: bool = False,
    revision: str = "1",
) -> Callable:
    """Register a signal function into REGISTRY.

    Usage:

        from premura.engine import signal

        @signal(name="ast_alt_ratio", domain=["liver", "metabolic"],
                inputs=["lab:ast", "lab:alt"], output="derived:ast_alt_ratio",
                priority="high", auto_safe=True, revision="1")
        def compute_ast_alt_ratio(conn):
            ...
    """
    def deco(fn: Callable) -> Callable:
        REGISTRY[name] = SignalSpec(
            name=name, domain=domain, inputs=inputs, output=output,
            priority=priority, auto_safe=auto_safe, revision=revision, fn=fn,
        )
        return fn
    return deco
```

### Engine module API (5 stub functions)

`src/premura/engine/__init__.py` re-exports the registry symbols and adds five stub API functions. All five raise `NotImplementedError`:

```python
def compute(spec_name: str, conn) -> object: ...
def list_by_domain(domain: str) -> list[SignalSpec]: ...
def list_auto_safe() -> list[SignalSpec]: ...
def check_inputs_available(inputs: list[str], conn, within=None) -> bool: ...
def list_unavailable(domain: str, conn) -> list[SignalSpec]: ...
```

See [contracts/signal-registry.md](contracts/signal-registry.md) for the full semantic contract of each function.

---

## 4. `PluginParseResult` — federated parser return type

`src/premura/parsers/base.py` (append-only addition):

```python
from dataclasses import dataclass, field
from typing import Protocol


@dataclass(frozen=True)
class PluginParseResult(ParseResult):
    """ParseResult extended for federated (community-PR'd) parsers.

    Adds three fields that capture information the federated workflow needs:
    language detection, ontology-mapping misses, and parser confidence.
    """
    language_detected: str | None = None
    """ISO 639-1 code (e.g., 'en', 'it', 'de') if the parser's _lang detector
    ran on the source text. None if detection was skipped or N/A."""

    unmapped_metrics: list[str] = field(default_factory=list)
    """Vendor field names the parser could NOT map to any canonical metric_id
    (existing alias, LOINC, IEEE 1752.1, bare English canonical name, or
    vendor:* fallback). Surfaced for
    human review per parsers/CONTRACT.md. Empty list = full ontology coverage."""

    confidence: float = 1.0
    """Parser's self-reported confidence in its mappings, in [0.0, 1.0].
    Convention: 1.0 for v1 hand-written parsers; LLM-generated parsers may
    set lower values when they had to guess. Used by reviewers as a hint, not
    enforced at runtime."""


class PluginParser(Parser, Protocol):
    """Protocol for federated parsers. Extends Parser with extra metadata
    and a richer return type.

    See parsers/CONTRACT.md for the full agent-facing contract including
    the decision tree for canonical-metric mapping.
    """
    source_kind: str
    language_hint: str | None
    """Optional hint about the expected language of the source. Used by
    _lang.detect_language to skip detection when the parser already knows."""

    def parse(self, path: Path) -> PluginParseResult: ...

    def declares_metrics(self) -> list[str]:
        """Return the canonical metric_ids this parser may emit. Used by
        reviewers to cross-check against dim_metric.yaml before merging the
        parser's PR. Must NOT include any `derived:*` metric_id (C-011)."""
        ...
```

Existing `Measurement`, `Interval`, `ParseResult`, `Parser` are unchanged. Only the two new symbols above are added (append-only).

---

## Cross-reference table

| Symbol | Defined in | First user | Used by |
|---|---|---|---|
| `hp.dim_metric.category` | `store/migrations/002_dim_metric_ontology.sql` | `seed_dim_metric` (loader) | engine's `list_by_domain`, MCP discovery |
| `hp.dim_metric.validity_window` | same | same | engine's `check_inputs_available` |
| `hp.dim_metric.missing_data_policy` | same | same | engine's `apply_missing_data_policy` (future) |
| `hp.dim_metric.aliases` | same | same | `parsers/lookup.suggest_metric` |
| `hp.dim_metric.loinc` / `ieee1752` | same | same | `parsers/CONTRACT.md` decision-tree |
| `SignalSpec` | `engine/_registry.py` | engine implementation missions | MCP, ingest auto-run path |
| `REGISTRY` | same | same | engine + MCP + ingest auto-run |
| `signal` decorator | same | engine implementation missions | engine functions only |
| `PluginParseResult` | `parsers/base.py` (append) | community parsers (future) | parser PR reviewers, alias-PR-feedback loop |
| `PluginParser` | same | community parsers (future) | parsers/CONTRACT.md, `lookup.suggest_metric` flow |
