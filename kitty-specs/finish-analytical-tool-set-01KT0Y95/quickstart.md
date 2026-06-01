# Quickstart: Finish Analytical Tool Set

## Goal

Validate the planned `rolling_mean` and simple anchor-date `paired_t_test`
behavior locally before review handoff. Both tools must produce deterministic
analytical envelopes or structured refusals and must not expand into PubMed,
teaching UI, diagnosis, causation, or hidden search.

## Expected Local Flow

1. Start each work package with one failing public-behavior test.
2. Implement the smallest engine change needed for that test.
3. Add refusal and edge-case tests before widening behavior.
4. Keep MCP exposure thin: wrappers delegate to engine preparation/dispatch and
   serialize the analytical envelope.
5. Add trace identity/recording tests through the trace and MCP public surfaces.
6. Run focused tests and static checks before handoff.

## Acceptance Fixtures

Create or reuse synthetic fixtures only. No real health rows or PHI.

`rolling_mean` fixtures should cover:

- available result with a 7-observation window;
- custom supported window;
- insufficient coverage;
- zero or negative window;
- window beyond supported maximum;
- imputed points visible in coverage/imputation metadata;
- request to scan/select the best window refused.

`paired_t_test` fixtures should cover:

- available before/after result around a declared anchor date;
- expected increase but observed decrease, and vice versa;
- missing anchor date;
- unsupported before/after window;
- too few valid pairs;
- constant paired differences;
- imputed pairs visible in metadata;
- request for condition-label pairing refused as out of scope;
- request to scan anchor dates or windows refused.

Trace fixtures should cover:

- one recorded call for each new tool;
- exact retry collapse in unique hypothesis count;
- different window or anchor values counted as distinct hypotheses;
- refused calls included in the refusal breakdown;
- surfaced marks working for the new tools.

## Focused Validation Commands

Run focused tests first while developing:

```bash
uv run python -m pytest tests/test_engine_analytical_tools.py -q
uv run python -m pytest tests/test_engine_analytical_inputs.py -q
uv run python -m pytest tests/test_engine_analytical_public_surface.py -q
```

Run policy/admissibility tests when adding question types:

```bash
uv run python -m pytest tests/test_engine_policy_defaults.py tests/test_engine_policy_evaluator.py -q
```

Run MCP and trace tests when adding wrappers and session recording:

```bash
uv run python -m pytest tests/test_mcp_analytical_tools.py tests/test_mcp_trace_recording.py tests/test_trace_store.py -q
```

Before review handoff, run changed-scope static checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/premura/engine src/premura/mcp src/premura/trace.py
```

If pre-existing unrelated failures remain, name them in the work package review
handoff rather than hiding them.

## Review Checklist

- `rolling_mean` refuses before computation when input or window parameters are
  unsupported.
- `rolling_mean` available results include window, coverage, imputation,
  emitted-point, validity, and confound metadata.
- `paired_t_test` only supports before/after anchor-date pairing in this mission.
- `paired_t_test` refuses condition-label pairing, arbitrary pair maps, and anchor
  or window scans.
- `paired_t_test` available results include pair count, mean paired difference,
  uncertainty metadata, direction metadata, validity, and confounds.
- Serialized results contain no diagnosis, causation, treatment, dosing,
  emergency, population-norm, hidden-search, or network/PubMed behavior.
- MCP wrappers contain no analytical computation.
- Trace disclosure counts the new tools by normalized identities.
