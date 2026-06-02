# Contract: Bootstrap CLI

## Command

Planned command:

```text
uv run hpipe bootstrap
```

The command is agent-facing setup. It may prepare the local project environment and project skills, then verify readiness. It must not ingest health data, query private warehouse rows, call analytical MCP tools, upload artifacts, or start runtime operating roles.

## Required Semantics

### Success path

When run from a supported fresh Premura checkout with installable local prerequisites available, the command must:

1. Prepare or verify the local project environment.
2. Install or verify bundled Premura skills through the repo-supported skill path.
3. Verify command availability/readiness needed before normal operation.
4. Print a concise final handoff summary.
5. Exit with code `0`.

The handoff summary must include:

- overall status (`ready`, `partial`, or equivalent plain language),
- local actions changed vs already current,
- remaining blockers, if any,
- optional warnings, if any,
- reload guidance (`reload required`, `reload recommended`, or `reload not required`),
- one safe next step.

### Blocked path

When a required prerequisite cannot be installed safely inside the checkout/environment, the command must:

1. Avoid uncontrolled system-wide mutation.
2. Report the prerequisite as a blocker.
3. Explain why it was not handled locally.
4. Provide an exact next action.
5. Exit non-zero if the checkout is not ready for normal operation.

### Idempotent path

When run twice on an already prepared checkout, the second run must:

1. Preserve the prepared state.
2. Report local actions as already current or no change.
3. Exit with code `0` if no required blockers remain.

## Output Requirements

- Success-path output must fit within 200 terminal lines.
- Each failed required check must be explained in no more than 5 lines.
- Optional capabilities must be visually or structurally distinct from blockers.
- Output must not include private health artifacts, source-data excerpts, warehouse rows, or secrets.

## Safety Boundaries

- The command must not run `hpipe ingest`, `hpipe run-monthly`, `hpipe upload`, default MCP analytical tools, or operator SQL tools.
- The command must not require `data/inbox/`, `data/raw/`, or a real warehouse to contain private health data.
- The command must not write to `hp.*` tables.
- The command must not silently install system-wide prerequisites; if a prerequisite is outside the safe local project scope, report it.

## Acceptance Test Hooks

Tests should verify observable behavior through the CLI:

- command registration under `hpipe`,
- clean-checkout success or controlled skip using a temporary project root,
- blocked prerequisite reporting,
- idempotent second run,
- skill install/reload guidance,
- no invocation of health-data operation commands.
