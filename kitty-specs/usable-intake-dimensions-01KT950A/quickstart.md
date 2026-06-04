# Quickstart: Usable Intake Dimensions

Audience: a reviewer validating the planning outputs and, later, the completed
implementation from a clean local checkout.

## Branch contract

Current branch at planning start: `master`.
Planning/base branch: `master`.
Final merge target for completed changes: `master`.

## 1. Validate the parser runtime path now supports intake as a first-class output

Expected review path after implementation:

```bash
uv run pytest -q tests/test_profile_intake_parser_contract.py
uv run pytest -q tests/test_profile_intake_persistence.py
```

What this should prove:
- the authoritative parser contract and parser protocol are aligned
- a runtime parser can emit intake through the supported parser surface
- runtime invocation routes intake output to `persist_intake_batch(...)`
- the one-home rule still holds: intake does not go through the observation
  loader path

## 2. Validate both intake domains now resolve through the existing Stage 2 seam

Expected review path after implementation:

```bash
uv run pytest -q tests/test_engine_input_resolution_surface.py
uv run pytest -q tests/test_intake_resolvers.py
```

What this should prove:
- `nutrition_intake` and `supplement_intake` no longer fall through to
  `unsupported_domain` when matching rows exist
- no same-named observation row can satisfy an intake dependency
- declared-but-empty / stale / insufficient cases stay explicit

## 3. Validate the two descriptive intake signals

Expected review path after implementation:

```bash
uv run pytest -q tests/test_intake_signals.py
```

What this should prove:
- supplement adherence returns a descriptive K-of-N style answer when data is
  present
- nutrition trend returns descriptive up/down/flat over logged days only
- neither signal diagnoses, recommends, imputes missing days, or hides gaps
- a local-midnight divergence fixture proves compute and reported metadata use
  the same local-day basis when `local_tz` is present

## 4. Validate default MCP tool exposure

Expected review path after implementation:

```bash
uv run pytest -q tests/test_mcp_signal_tools.py
uv run pytest -q tests/test_mcp_intake_tools.py
```

What this should prove:
- both intake-backed tools appear on the default MCP surface
- wrappers return the standard signal-tool payload shape
- `available`, `missing_input`, `stale_input`, and `insufficient_data` remain
  structurally distinct

## 5. Run changed-scope gates before review handoff

```bash
uv run ruff check src/premura tests
uv run ruff format --check src/premura tests
uv run mypy src/premura
uv run pytest -q
```

## 6. Example reviewer stories to re-run end-to-end

1. Synthetic supplement rows present:
   ask the supplement-adherence tool about a named supplement over a bounded
   window and confirm it returns a descriptive coverage answer.
2. Synthetic nutrition rows present:
   ask the nutrition-trend tool about a caller-declared nutrition quantity key
   and confirm missing days stay gaps.
3. No matching intake rows:
   confirm both tools return explicit honest non-usable outcomes, never another
   domain's data.
4. Runtime intake parser proof:
   run the synthetic reference parser path and confirm the resulting data becomes
   resolvable and tool-usable without any review-only shim.
