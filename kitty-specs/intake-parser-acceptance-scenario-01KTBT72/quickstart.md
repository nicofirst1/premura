# Quickstart — Intake Parser Acceptance Scenario

How to run the two layers once this mission lands. All commands run from the repo root.

## Layer 1 — deterministic floor (default suite, no model server)

The reference intake parser is graded against the alien source by the three rules. These
run in the normal suite — offline, deterministic, never flaky.

```bash
uv run pytest tests/test_intake_scenario_grading.py \
              tests/test_intake_scenario_drawer.py \
              tests/test_intake_runtime_contract.py -q
```

Expected: full pass (SC-001); a mis-filed intake row fails `loaded` (SC-002); an
unmappable column is reported as a declared gap (SC-004); the intake `runtime_valid`
clause set matches the contract (SC-008).

## Failure path (default suite, stub operator)

Proves a broken parser still yields a completed, persisted, failing record (FR-009).

```bash
uv run pytest tests/test_failure_path_record.py -q
```

Expected: a session-log run record exists with `passed=False` and a captured parser
error; the harness does not raise (SC-007).

## No-fork + observation regression (default suite)

```bash
uv run pytest tests/test_scenario_no_fork.py \
              tests/test_observation_scenario_golden.py -q
```

Expected: ≥ 2 scenarios run through one shared grade path with no per-source branch
(SC-003); the observation verdict is byte-identical to the pre-refactor golden (SC-006 /
C-004).

## Whole default suite stays green

```bash
uv run pytest -q -m "not live_trial"
```

Expected: green, no network, no model server (NFR-001/002).

## Layer 2 — live cheap model (opt-in, local Ollama)

The local cheap model authors the intake parser itself for the alien source and is
graded by the same rules. Opt-in, local-only, never blocks CI.

```bash
# Requires a local Ollama; inherits the local-only OLLAMA_URL guard.
uv run pytest -m live_trial tests/test_live_trial_intake.py -s
```

Expected: a well-formed verdict is printed for inspection with `run_kind=live_trial`,
`operator_model`, `driver_model` recorded. The model's score is **printed, never
asserted as a pass** (SC-005). A non-local `OLLAMA_URL` is rejected before any request
(NFR-003).
