# Tasks: Harden Grounded Stage 2 Contract

**Mission**: harden-grounded-stage-2-contract-01KSJ654
**Planning base**: `master` | **Merge target**: `master`
**Spec**: [spec.md](spec.md) | **Plan**: [plan.md](plan.md)

Three focused work packages, each owning a disjoint set of files. The mission is
small and surgical; no new signals, no new analysis.

## Subtask Index

| ID | Description | WP | Parallel |
|----|-------------|----|----------|
| T001 | Replace registry-truthiness loader guard with explicit `_BUILTINS_LOADED` flag | WP01 | | [D] |
| T002 | Regression test: pre-registered custom signal does not suppress built-ins | WP01 | | [D] |
| T003 | Make `BaselineComparisonResult` numeric fields `float \| None` + add `validate()` | WP02 | | [D] |
| T004 | Stop the `0.0` coercion in `sleep_deep_pct_baseline` and validate the envelope | WP02 | | [D] |
| T005 | Test: baseline reports no fabricated numbers when unavailable/unknown | WP02 | | [D] |
| T006 | Build a `MissingInputReport` from the signal's `inputs` + result freshness at the Stage 3 boundary | WP03 | | [D] |
| T007 | Use the signal's `missing_input_hint` as the user-facing message for unavailable answers | WP03 | | [D] |
| T008 | Attach the structured missing-input block for `missing_input`/`stale_input`; keep the four statuses distinct | WP03 | | [D] |
| T009 | Strengthen MCP tests to assert actionable guidance + structured input fields (not "some message") | WP03 | | [D] |
| T010 | Add the missing `weight_trend` end-to-end Stage 3 call test | WP03 | | [D] |

## Work Packages

### WP01 — Built-in Loader Honesty

**Goal**: Registering a custom signal before built-ins load must not suppress
built-in signal loading (FR-004).
**Requirements**: FR-004, NFR-001
**Independent test**: Pre-register a custom signal, then assert all built-in
signal names (`ast_alt_ratio`, `resting_hr_status`, …) are present and callable;
import-time laziness still holds.
**Dependencies**: none.

- [x] T001 Replace `if REGISTRY: return` with an explicit module-level `_BUILTINS_LOADED` sentinel in `src/premura/engine/__init__.py`; set it only after the static built-in modules import; keep `import premura.engine` from eagerly loading. (WP01)
- [x] T002 Add a regression test in `tests/test_engine_contract.py` that registers a custom signal first, calls the loader, and asserts built-ins still load. (WP01)

Prompt: [tasks/WP01-builtin-loader-honesty.md](tasks/WP01-builtin-loader-honesty.md)

### WP02 — Baseline Result-Shape Honesty

**Goal**: The deep-sleep own-baseline result must not fabricate `0.0` when there
is no trustworthy comparison (FR-005).
**Requirements**: FR-005, NFR-001, NFR-003
**Independent test**: With no deep-sleep value (and with too-few prior nights),
the result's `latest_value`/`baseline_mean` are absent (`None`), while status and
caveats explain why.
**Dependencies**: none.

- [x] T003 In `src/premura/engine/_results.py`, change `BaselineComparisonResult.latest_value` and `baseline_mean` to `float | None = None` and add a `validate()` that forbids a numeric value when `freshness_state is UNAVAILABLE` (latest_value) or `comparison_state is UNKNOWN` (baseline_mean), mirroring `StatusResult.validate`. (WP02)
- [x] T004 In `src/premura/engine/comparative_signals.py`, remove the `... else 0.0` coercion in the baseline path; pass through real `None` values and call `.validate()`. (WP02)
- [x] T005 In `tests/test_engine_comparative_signals.py`, assert that unavailable/unknown baseline results serialize `latest_value`/`baseline_mean` as `None`, not `0.0`, with honest status/caveats. (WP02)

Prompt: [tasks/WP02-baseline-result-shape-honesty.md](tasks/WP02-baseline-result-shape-honesty.md)

### WP03 — Stage 3 Actionable Missing-Input + Coverage

**Goal**: Deliver FR-008 fully — Stage 3 tells the user *what data is needed*,
both as actionable prose and structured fields — and close the `weight_trend`
coverage gap (FR-001/002/003/006).
**Requirements**: FR-001, FR-002, FR-003, FR-006, NFR-002, NFR-003
**Independent test**: A data-absent approved question returns
`status == "missing_input"`, a `message` containing the signal's specific hint,
and a `missing_input` block with `required_inputs`/`missing_inputs`; a stale case
populates `stale_inputs`; all six approved questions have a Stage 3 call test.
**Dependencies**: WP02 (consumes the honest baseline shape; the baseline
unavailable test asserts `None` numerics).

- [x] T006 In `src/premura/mcp/server.py`, build a `MissingInputReport` at the serialization boundary from the signal's declared `inputs` (registry) + the result's freshness/availability (required → missing when absent, → stale when stale). (WP03)
- [x] T007 Use the signal's registered `missing_input_hint` as the user-facing `message` for unavailable answers, instead of the generic value-absent sentence. (WP03)
- [x] T008 Attach the structured `missing_input` block to the response for `missing_input` and `stale_input` statuses; keep `available`/`insufficient_data` shapes unchanged and the four statuses structurally distinct. (WP03)
- [x] T009 Strengthen `tests/test_mcp_signal_tools.py` so the missing-input and stale-input cases assert the actionable hint text AND the structured `required_inputs`/`missing_inputs`/`stale_inputs` fields (not merely a non-empty message). (WP03)
- [x] T010 Add a `weight_trend` end-to-end Stage 3 call test in `tests/test_mcp_signal_tools.py`. (WP03)

Prompt: [tasks/WP03-stage3-actionable-missing-input.md](tasks/WP03-stage3-actionable-missing-input.md)

## Dependencies

```
WP01 (loader)        — independent
WP02 (baseline)      — independent
WP03 (Stage 3)       — depends on WP02
```

## MVP / sequencing

All three are required to close the review's blocker (FR-008 = WP03) and the two
RISKs (WP01, WP02). Suggested order: WP01, WP02, then WP03.
