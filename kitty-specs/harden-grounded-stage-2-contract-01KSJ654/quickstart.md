# Quickstart / Validation: Harden Grounded Stage 2 Contract

Run from the lane worktree.

## Targeted checks

```bash
# FR-001/002/003 — actionable missing-input guidance + structured report
uv run python -m pytest tests/test_mcp_signal_tools.py -q

# FR-004 — loader no longer suppressed by pre-registration
uv run python -m pytest tests/test_engine_contract.py -q

# FR-005 — baseline no longer fabricates 0.0
uv run python -m pytest tests/test_engine_comparative_signals.py -q
```

## Manual spot-checks

```bash
# Missing-input response carries the actionable hint + structured inputs
uv run python -c "
from premura.mcp import server
import tempfile, os
# (use the test helpers' empty-warehouse pattern in real runs)
print('see tests/test_mcp_signal_tools.py for the seeded fixtures')
"

# Lazy boundary still holds (no eager signal load on import)
uv run python -c "import sys, premura.engine as e; print('lazy:', len(e.REGISTRY)==0 and 'premura.engine.descriptive_signals' not in sys.modules)"

# Built-ins survive a pre-registered custom signal
uv run python -c "
import premura.engine as e
from premura.engine._registry import REGISTRY
REGISTRY['custom_demo'] = object()      # simulate a custom pre-registration
e._ensure_builtin_signals_loaded()
assert 'resting_hr_status' in REGISTRY and 'ast_alt_ratio' in REGISTRY, 'built-ins suppressed!'
print('built-ins present after custom pre-registration: OK')
"
```

## Full regression (post-merge, on master)

```bash
uv run python -m pytest -q   # expect all green, no regressions vs. 131 baseline
```

## Expected outcomes

- A data-absent approved question returns `status == "missing_input"`, a
  `message` containing the signal's actionable hint, and a `missing_input` block
  with `required_inputs`/`missing_inputs`.
- `sleep_deep_pct_baseline` returns `latest_value: null` / `baseline_mean: null`
  (not `0.0`) when unavailable/unknown.
- Pre-registering a custom signal does not hide built-in signals.
- All six approved questions have an end-to-end Stage 3 test.
