# Contributing

This is the main development guide for Premura contributors, whether you are a
human working locally or an agent editing the repo.

## Start here

- Read `README.md` for bootstrap and CLI usage.
- Read `docs/architecture/STAGES.md` before moving logic across package boundaries.
- Read `.kittify/charter/charter.md` for the current quality gates and risk
  boundaries.
- If you are adding a new parser, also read `docs/architecture/PARSER_CONTRIBUTING.md` and
  `src/premura/parsers/CONTRACT.md`.

## Setup

On a fresh clone, the agent-friendly path is one command — `uv run hpipe bootstrap`
prepares and verifies the local checkout (environment + bundled skills) and
reports whether an agent-session reload is needed. It is setup-only. (`uv run` is
required because `hpipe` is a console script that does not exist until the package
is installed; `uv run` provisions the environment first, so it works on a brand-new
clone.) The underlying steps, if you prefer running them yourself:

```bash
bash ops/bootstrap.sh
uv sync --extra dev
uv run pre-commit install
uv run hpipe doctor
```

## Daily commands

```bash
uv run python -m pytest -q -x --tb=short
uv run python -m pytest -q --lf --tb=short
uv run python -m pytest -q -m regression    # explicit real-export regressions
uv run ruff check .
uv run ruff format --check .
uv run pre-commit run --files <changed-python-files>
uv run mypy <changed-paths>
```

The default pytest loop excludes tests marked `regression` so local agent
feedback stays fast even when private real-export files exist. Objective: the
default `uv run python -m pytest -q -x --tb=short` feedback command should stay
under 90 seconds on the maintainer's M-series Mac; if it exceeds that, profile
the slow tests before merging more work.

Before review handoff, the relevant `ruff`, `mypy`, and `pytest` checks must be
green for the changed scope. Run `-m regression` explicitly when changing parser
schemas, real-export handling, or release validation.

The pre-commit hook runs the fast linting phase (`ruff check` and
`ruff format --check`) on staged Python files before each commit. It is a local
guardrail, not a replacement for the changed-scope `mypy` and `pytest` checks
above.

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

Authoritative stage guidance lives in `docs/architecture/STAGES.md`.

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

## Pull requests and review handoff

This guide owns the contribution path for both humans and coding agents. Before
opening a pull request:

1. Keep the change scoped to one coherent unit of work (see §"Change style").
2. Run the changed-scope checks above and make them green: `uv run ruff check .`,
   `uv run ruff format --check .`, `uv run mypy <changed-paths>`, and the fast
   `uv run python -m pytest -q -x --tb=short` loop. Run `-m regression` when you
   touch parser schemas, real-export handling, or release validation.
3. Update the docs touched by the behavior change in the same PR.
4. Open the pull request with a summary of intent, the checks you ran, and any
   follow-up left out of scope. A reviewer (human or agent) should be able to
   verify the change against the relevant contract without reconstructing it.

Coding agents working inside the repo reach this section through
[`AGENTS.md`](AGENTS.md); runtime agents proposing changes from a live session
do so through a reviewed share packet — see
[`docs/operations/RUNTIME_AGENT.md`](docs/operations/RUNTIME_AGENT.md).

## Source of truth

- Product and data-contract intent: `docs/product/SPEC.md`
- Architecture and repo shape: `docs/history/architecture/ARCHITECTURE_HISTORY.md`
- Stage boundaries: `docs/architecture/STAGES.md`
- Warehouse update policy: `docs/architecture/UPDATE_STRATEGY.md`
- Parser plugin contract: `src/premura/parsers/CONTRACT.md`
- Parser-generation skill: `src/premura/skills/parser-generator/SKILL.md`

If a planning artifact in `kitty-specs/` disagrees with a shipped contract or
runtime doc, follow the shipped contract or runtime doc.
