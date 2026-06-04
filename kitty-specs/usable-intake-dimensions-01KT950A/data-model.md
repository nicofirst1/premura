# Phase 1 Data Model: Usable Intake Dimensions

This data model describes the planning-level entities and contracts the mission
adds or extends. It does not replace the authoritative meaning contract in
`docs/building/architecture/PROFILE_AND_INTAKE_CONTRACT.md`; it defines the
runtime/parser/resolver/signal shapes this mission needs to make intake usable.

## 1. Parser-side entities

### Parser output surface — exact returned shape intentionally provisional at planning time

Purpose: replace the observation-only `parse(path) -> IngestBatch` contract with
a runtime-supported parser output surface that can handle intake-first sources.

Planning requirement:
- the supported parser/runtime path must accept observation-only output
- the supported parser/runtime path must accept intake-only output
- the design should not structurally preclude mixed observation+intake output
  when a source genuinely carries both

Provisional design note:
- A wrapper object carrying observation and intake sub-batches is one plausible
  implementation, but it is **not** locked by this plan. `/spec-kitty.tasks` and
  implementation should choose the smallest viable shape that satisfies the
  runtime-path requirement above.

Relationship:
- Produced by one `PluginParser.parse(path)` call or equivalent parser runtime
  surface after the protocol adjustment.
- Consumed by runtime parser invocation in CLI/harness paths.

### `IntakeBatch` — existing intake persistence seam (reused, not redesigned)

Already shipped in `src/premura/parsers/base.py` and persisted by
`persist_intake_batch(...)`.

Important carried invariants:
- every row has provenance via `source_descriptors`
- dedupe keys stay the idempotency contract
- nutrition and supplement rows stay distinct
- event-level and item-level nutrition quantities remain distinguishable
- supplement doses may be numeric, textual, or both

## 2. Resolver-side entities

### `ResolvedInput` for `nutrition_intake`

Purpose: resolve one declared nutrition intake dependency through the existing
Stage 2 seam.

Core fields come from the existing `ResolvedInput` contract:
- `domain="nutrition_intake"`
- `required_key`
- `anchor_ts`
- `usable`
- `absence_reason`
- `message`

Planned payload fields:

| Field | Type | Notes |
| --- | --- | --- |
| `matched_key` | `str` | The nutrition quantity key actually resolved |
| `window_days` | `int` | The caller-selected or default window |
| `points` | `list[...]` | Ordered daily intake points over the window |
| `days_with_data` | `int` | Count of days with logged quantity |
| `window_day_count` | `int` | Total day count considered |
| `latest_logged_at` | `datetime | None` | Most recent matching intake event |
| `freshness_state` | `str` | Current/stale/unavailable basis for the signal layer |
| `day_basis` | `str` | `local_calendar_day` or fallback `naive_utc_day` |

The resolver remains generic: it does not compute trend direction itself.

### `ResolvedInput` for `supplement_intake`

Purpose: resolve one declared supplement intake dependency through the same seam.

Planned payload fields:

| Field | Type | Notes |
| --- | --- | --- |
| `matcher` | bounded supplement selector | Caller-declared selector over stored supplement identity fields (for example product label and/or ingredient label); exact field shape to be finalized in tasks/contracts, not improvised in implementation |
| `window_days` | `int` | Caller-selected or default window |
| `logged_days` | `list[date]` | Distinct local days with a matching supplement event |
| `logged_day_count` | `int` | K in "logged on K of N days" |
| `window_day_count` | `int` | N in "K of N days" |
| `latest_logged_at` | `datetime | None` | Most recent matching supplement event |
| `freshness_state` | `str` | Current/stale/unavailable basis for the signal layer |
| `day_basis` | `str` | `local_calendar_day` or fallback `naive_utc_day` |

Again, the resolver stays generic and non-answer-shaped.

## 3. Signal-side entities

### `supplement_intake_adherence` Stage 2 result

Family: a descriptive Stage 2 result using the existing result-family vocabulary.
The exact envelope should be finalized against `src/premura/engine/CONTRACT.md`
and the current signal patterns during implementation.

Inputs:
- caller-declared supplement matcher
- bounded `window_days` with repo default

Answer shape:

| Field | Type | Notes |
| --- | --- | --- |
| `logged_day_count` | `int` | K |
| `window_day_count` | `int` | N |
| `coverage_fraction` | `float` | K/N |
| `latest_logged_at` | `datetime | None` | Most recent matching intake |
| `caveats` | `list[str]` | Descriptive only; no recommendation language |

Availability semantics to preserve through the Stage 2 -> Stage 3 boundary:
- missing_input-like behavior: declared-but-empty domain / no matching rows
- stale-input-like behavior: matching history exists but latest usable data is
  outside the signal's freshness rule
- insufficient-data behavior: some rows exist but not enough to answer honestly
  under the declared policy

### `nutrition_intake_trend` Stage 2 result

Family: `trend`.

Inputs:
- caller-declared nutrition quantity key
- bounded `window_days` with repo default

Answer shape:

| Field | Type | Notes |
| --- | --- | --- |
| `trend_direction` | `up | down | flat | unknown` | Descriptive only |
| `points` | ordered visible points | Missing days remain gaps, never imputed |
| `days_with_data` | `int` | Observed days only |
| `window_day_count` | `int` | Window denominator |
| `latest_logged_at` | `datetime | None` | Most recent matching intake |
| `current_freshness_state` | `str` | Current/stale/unavailable |
| `caveats` | `list[str]` | Includes sparse/gap visibility |

Special rule:
- Missing days remain gaps and are visible; no carry-forward or imputation.

## 4. Tool-side entities

### Default MCP tool payloads

Each intake-backed tool follows the same Stage 3 wrapper shape already used by
the other signal-backed tools:

```json
{
  "tool_name": "...",
  "status": "available | missing_input | stale_input | insufficient_data",
  "message": "user-facing sentence",
  "result": { "... structured envelope ..." },
  "missing_input": { "... optional report for missing/stale ..." }
}
```

Provisional tool-name examples:
- `supplement_intake_adherence(...)`
- `nutrition_intake_trend(...)`

The exact public names should stay aligned with existing repo naming patterns
during task decomposition; these are examples, not locked API names.

## 5. Reference parser + synthetic fixture entities

### Synthetic intake fixture

Purpose: prove parse -> intake persistence -> resolver/signal use with no PHI.

Needed properties:
- one nutrition shape
- one supplement shape
- at least one event with `local_tz` such that local day != UTC date
- one text-only supplement dose
- one event-level nutrition quantity
- one item-level nutrition quantity
- one unmapped source field surfaced honestly

### Reference intake parser

Purpose: a minimal proof/parser-contract anchor, not a production vendor parser.

Expected behavior:
- parses the synthetic fixture only
- returns intake output through the first-class parser protocol
- persists through `persist_intake_batch(...)`
- surfaces unmapped fields honestly

## 6. State / availability transitions

### Domain resolution lifecycle

`declared domain` -> `resolver present?`

- no -> `usable=False, absence_reason="unsupported_domain"`
- yes, no matching rows -> `usable=False, absence_reason=missing/empty-domain-like reason`
- yes, rows present but outside freshness/sufficiency -> `usable=False` with
  `stale_input` or `insufficient_data` at the signal/tool layer
- yes, usable rows present -> `usable=True` with payload

### Parser runtime lifecycle

`source artifact` -> `parse()` -> supported parser output surface

- observation batch only -> observation loader path
- intake batch only -> intake persistence path
- both -> both paths, no seam mixing
- invalid batch -> fail before persistence

## 7. Validation rules to lock in tasks

- Parser protocol/runtime support for intake must be exercised through real
  runtime entrypoints, not only by type checks in `base.py`.
- Resolvers must never satisfy an intake dependency from observation rows.
- Positive-path fixtures are required for present data in both domains.
- At least one acceptance fixture must cross local midnight so compute basis and
  reported metadata basis cannot drift apart.
- New tools must remain descriptive only and inherit the standard Stage 3
  availability-status surface.
