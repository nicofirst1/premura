# Quickstart: Fresh Clone Bootstrap Agent

This quickstart describes the intended behavior after implementation. It uses synthetic or empty setup state only; do not use real health exports for bootstrap validation.

## 1. Fresh checkout setup

From the project root:

```bash
hpipe bootstrap
```

Expected result:

- local project dependencies are installed or verified,
- bundled Premura skills are installed or verified,
- the command reports whether an agent-session reload is required,
- the final summary says whether the checkout is ready, partial, or blocked.

## 2. Idempotency check

Run the command again:

```bash
hpipe bootstrap
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
hpipe bootstrap
```

Expected result:

- no source artifact is ingested,
- no private warehouse rows are queried,
- no analytical MCP tool is called,
- no upload is attempted.

## 5. Suggested validation commands

Run the relevant changed-scope checks before review handoff:

```bash
uv run python -m pytest -q tests/test_bootstrap_cli.py --tb=short
uv run ruff check src/premura tests
uv run ruff format --check src/premura tests
uv run mypy src/premura
```

If implementation touches existing CLI or skill installer behavior, also run the existing related tests:

```bash
uv run python -m pytest -q tests/test_skeleton.py tests/test_install_skills_research_trace_audit.py --tb=short
```
