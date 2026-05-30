# Quickstart: Correlate Lagged Association

## Goal

Validate the planned `correlate` behavior locally before review handoff. The
tool must answer only pre-registered association questions, never significance or
causation questions.

## Expected Local Flow

1. Start with a failing acceptance test for one visible behavior.
2. Implement the smallest engine change needed for that test.
3. Add the matching refusal or edge-case test before widening behavior.
4. Keep MCP exposure thin: it delegates to the engine and serializes the
   analytical envelope.
5. Run changed-scope tests and static checks before handoff.

## Acceptance Fixtures

Create or reuse synthetic daily series fixtures that cover:

- available association with lag 1 and expected negative direction;
- opposite observed direction versus expected direction;
- lag 4 without justification;
- lag beyond 14 days;
- fewer than 20 paired days;
- effective sample size below 12 despite at least 20 raw pairs;
- constant or rank-deficient series;
- imputed-pair share at or above 20%;
- pre-declared common-cause candidate.

Fixtures must be synthetic and contain no PHI.

## Validation Commands

Run focused tests first while developing:

```bash
uv run python -m pytest tests/test_engine_analytical_inputs.py -q
uv run python -m pytest tests/test_engine_analytical_tools.py -q
uv run python -m pytest tests/test_engine_analytical_public_surface.py -q
```

Run policy/admissibility tests when adding the lagged-association question type:

```bash
uv run python -m pytest tests/test_engine_policy_defaults.py tests/test_engine_policy_evaluator.py -q
```

Before review handoff, run the changed-scope static checks:

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src/premura/engine src/premura/mcp
```

If pre-existing unrelated failures remain, name them in the work package review
handoff rather than hiding them.

## Review Checklist

- `correlate` refuses before computation when inputs or hypothesis are invalid.
- Available results include Spearman's rho, association band, raw/effective
  sample counts, overlap, lag, imputation, validity, and confounds.
- Serialized results contain no p-value or significance field.
- Caveats contain no causal, diagnostic, treatment, dosing, emergency, or
  population-norm claim.
- The MCP wrapper contains no statistical computation.
- Runtime code contains no network or PubMed call.
- The tool does not scan lags or metric pairs.
