# Quickstart: Fresh Clone Bootstrap Agent

This quickstart describes the intended behavior after implementation. It uses synthetic or empty setup state only; do not use real health exports for bootstrap validation.

## 1. Fresh checkout setup

From the project root:

```bash
uv run hpipe bootstrap
```

Expected result:

- local project dependencies are installed or verified,
- bundled Premura skills are installed or verified,
- the command reports whether an agent-session reload is required,
- the final summary says whether the checkout is ready, partial, or blocked.

## 2. Idempotency check

Run the command again:

```bash
uv run hpipe bootstrap
```

Expected result:

- no unnecessary reinstall of already-current local dependencies,
- skill setup reports no change or equivalent,
- exit code remains `0` when no required blockers remain.

## 3. Missing prerequisite check

Simulate or use an environment where one required prerequisite cannot be handled locally.

Expected result:

- the command does not perform uncontrolled system-wide mutation,
- the blocker is named clearly,
- the output includes the exact next action,
- exit code is non-zero if the checkout is not ready.

## 4. Setup-only boundary check

During review, confirm bootstrap did not run any health-data operation:

```bash
uv run hpipe bootstrap
```

Expected result:

- no source artifact is ingested,
- no private warehouse rows are queried,
- no analytical MCP tool is called,
- no upload is attempted.

## 5. Suggested validation commands

**Invocation nuance discovered during implementation:** the project's `pytest`,
`ruff`, and `mypy` live in the `dev` optional-dependency group, so validation
runs through `uv run --extra dev …` (plain `uv run python -m pytest` will not see
them on a checkout that only synced the default groups).

Run the relevant changed-scope checks before review handoff:

```bash
uv run --extra dev python -m pytest -q tests/test_bootstrap_core.py tests/test_bootstrap_cli.py tests/test_bootstrap_docs.py --tb=short
uv run --extra dev ruff check src/premura tests
uv run --extra dev ruff format --check src/premura tests
uv run --extra dev mypy src/premura
```

If implementation touches existing CLI or skill installer behavior, also run the existing related tests:

```bash
uv run --extra dev python -m pytest -q tests/test_skeleton.py tests/test_install_skills_research_trace_audit.py --tb=short
```

## 6. Setup-only boundary checks for reviewers

The shipped command is `hpipe bootstrap` (the CLI app is `hpipe`). Confirm the
setup-only boundary holds — no real health data is required for any check below:

- README "Quick start" routes a fresh clone to `hpipe bootstrap` before normal
  operation, and still distinguishes setup from ingest, encrypt, and OPT-IN
  upload (the opt-in upload warning is preserved).
- README "CLI surface" lists `hpipe bootstrap` as setup-only.
- CONTRIBUTING names `hpipe bootstrap` as the fresh-clone path and still points
  to the development checks (`pytest` / `ruff` / `mypy`).
- `docs/operations/STATUS.md` records `hpipe bootstrap` as shipped setup-only
  behavior, not as ingest / upload / analysis, and does not overstate platform
  support beyond the charter (macOS local).
- `tests/test_bootstrap_docs.py` passes — it asserts the stable command name and
  boundary words above so the docs cannot silently drop the command or oversell
  it.
