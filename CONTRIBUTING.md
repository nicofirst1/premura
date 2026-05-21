# Contributing

This is the main development guide for Premura contributors, whether you are a
human working locally or an agent editing the repo.

## Start here

- Read `README.md` for bootstrap and CLI usage.
- Read `docs/STAGES.md` before moving logic across package boundaries.
- Read `.kittify/charter/charter.md` for the current quality gates and risk
  boundaries.
- If you are adding a new parser, also read `docs/PARSER_CONTRIBUTING.md` and
  `src/premura/parsers/CONTRACT.md`.

## Setup

```bash
bash ops/bootstrap.sh
uv sync --extra dev
uv run hpipe doctor
```

## Daily commands

```bash
uv run python -m pytest -q
uv run ruff check .
uv run ruff format --check .
uv run mypy <changed-paths>
```

Before review handoff, the relevant `ruff`, `mypy`, and `pytest` checks must be
green for the changed scope.

## Architecture boundaries

Premura is split into four stages. Keep changes inside the right stage unless
the task explicitly spans them.

- `parsers`: ingest vendor artifacts into canonical warehouse rows. No
  derivation, no imputation, no analysis.
- `engine`: deterministic signal-processing logic. No network, no LLM.
- `mcp`: tool boundary for model-facing operations. This is the only stage that
  may make model or user-initiated network calls.
- `ui`: presentation, interview flow, and teaching. Do not read raw warehouse
  tables directly from here.

Authoritative stage guidance lives in `docs/STAGES.md`.

## Health-data and security rules

- No PHI in logs, tests, fixtures, or commits.
- No live API scraping for personal health data. Ingest official user-exported
  artifacts only.
- Keep the system local-first and offline by default.
- Cloud upload is opt-in. Encryption with `age` is mandatory before any upload.

## Change style

- Prefer the smallest correct change.
- Keep code modular. Do not let a small feature force unrelated layers to know
  about each other.
- Public functions should have type hints.
- Any change that touches health-data behavior should ship with at least one
  meaningful test.
- When behavior or workflow changes, update the relevant docs in the same
  change.

## Source of truth

- Product and data-contract intent: `docs/SPEC.md`
- Architecture and repo shape: `docs/ARCHITECTURE_HISTORY.md`
- Stage boundaries: `docs/STAGES.md`
- Warehouse update policy: `docs/UPDATE_STRATEGY.md`
- Parser plugin contract: `src/premura/parsers/CONTRACT.md`
- Parser-generation skill: `src/premura/skills/parser-generator/SKILL.md`

If a planning artifact in `kitty-specs/` disagrees with a shipped contract or
runtime doc, follow the shipped contract or runtime doc.
