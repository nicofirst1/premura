# Data Model: Harden Grounded Stage 2 Contract

Two envelope/shape changes; no warehouse schema changes.

## 1. `BaselineComparisonResult` (src/premura/engine/_results.py)

Make the numeric fields honestly optional and enforce absence when there is no
trustworthy comparison.

**Before**
```
latest_value: float
baseline_mean: float
```

**After**
```
latest_value: float | None = None
baseline_mean: float | None = None
```

**New `validate()` rule** (mirrors `StatusResult.validate`):
- If `freshness_state is UNAVAILABLE` → `latest_value` MUST be `None`.
- If `comparison_state is UNKNOWN` → `baseline_mean` MUST be `None`
  (no trustworthy baseline was formed).
- Otherwise values may be present.

`to_dict()` is unchanged in keys; it now serializes `None` for the numeric
fields in unavailable/unknown cases instead of a fabricated `0.0`.

**Caller change** (`comparative_signals.py`, `_baseline_comparison`): stop the
`... if x is not None else 0.0` coercion — pass `computed.latest_value` /
`computed.baseline_mean` straight through (which may be `None`), then call
`.validate()`.

## 2. `MissingInputReport` as serialized in a Stage 3 response

Already defined in `_results.py`; this mission makes Stage 3 actually emit it.
Shape (via `to_dict()`):

```
{
  "family": "missing_input",
  "tool_name": "<tool>",
  "required_inputs": ["resting_hr"],
  "missing_inputs": ["resting_hr"],   # present when the input is absent
  "stale_inputs": [],                  # present when the input exists but is stale
  "message": "<the signal's missing_input_hint>"
}
```

### Stage 3 response envelope (unavailable case)

The server's `_serialize_signal_result` output for an unavailable answer:

```
{
  "tool_name": "resting_hr_status",
  "status": "missing_input" | "stale_input" | "insufficient_data",
  "message": "<actionable missing_input_hint text>",
  "result": { ...family to_dict()... },
  "missing_input": { ...MissingInputReport.to_dict()... }   # NEW: structured detail
}
```

- `message` for an unavailable answer is the signal's `missing_input_hint`
  (actionable), not a generic sentence.
- `missing_input` (the structured report) is attached for `missing_input` and
  `stale_input` statuses; `required_inputs` always lists the signal's declared
  inputs, `missing_inputs`/`stale_inputs` reflect which are absent vs. stale.
- The `available` and pure `insufficient_data`-with-fresh-input paths keep their
  current shape (no structured missing-input block where it does not apply).

## Invariants

- A response never carries a fabricated numeric value when its status is not
  `available`.
- `required_inputs` is non-empty whenever a `missing_input` block is present.
- The three unavailable statuses remain structurally distinct (FR-003).
