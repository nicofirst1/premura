# Contract: Stage 3 Unavailable-Response

Defines what every signal-backed Stage 3 tool response must contain when the
answer is not fully available. Verified by `tests/test_mcp_signal_tools.py`.

## Status values (unchanged set, must stay distinct)

| status | meaning | numeric value present? | structured `missing_input` block? |
|---|---|---|---|
| `available` | answer produced | yes (honest) | no |
| `missing_input` | required input absent | no | yes — input in `missing_inputs` |
| `stale_input` | input present but too old | the stale value may be retained on the family envelope, flagged stale | yes — input in `stale_inputs` |
| `insufficient_data` | input fresh but too sparse to answer | no fabricated comparison/trend value | no (input is present and fresh) |

## Required fields per response

- `tool_name`: stable tool name.
- `status`: one of the four values above.
- `message`: a user-facing sentence. **When status is `missing_input`, this MUST
  be the signal's actionable `missing_input_hint`** (e.g. "Connect a wearable that
  records daily resting heart rate to answer this."), not a generic "no value"
  string.
- `result`: the family envelope `to_dict()`.
- `missing_input` (NEW, present for `missing_input` and `stale_input`): the
  `MissingInputReport.to_dict()` with:
  - `required_inputs`: non-empty list of the signal's declared inputs.
  - `missing_inputs`: inputs that are absent (populated for `missing_input`).
  - `stale_inputs`: inputs present but stale (populated for `stale_input`).
  - `message`: the same actionable hint.

## Honesty rules

1. No response with `status != available` may contain a fabricated numeric value
   (e.g. `latest_value`/`baseline_mean` must be `null`, not `0.0`, when unknown).
2. A `missing_input` response must let a caller learn *what data is needed* from
   `message` (prose) **and** `missing_input.required_inputs`/`missing_inputs`
   (structured) — without parsing free text.
3. The three raw tools (`query_warehouse`, `list_metrics`, `metric_summary`) are
   out of scope and unchanged.

## Test obligations

- Data-absent case for at least one signal asserts: `status == "missing_input"`,
  `message` contains the signal's specific hint text, and
  `missing_input.required_inputs`/`missing_inputs` name the input.
- Stale case asserts `status == "stale_input"` and `missing_input.stale_inputs`
  names the input.
- Baseline unavailable/unknown case asserts numeric fields are `null`.
- All six approved signals (incl. `weight_trend`) have an end-to-end Stage 3 call
  test.
