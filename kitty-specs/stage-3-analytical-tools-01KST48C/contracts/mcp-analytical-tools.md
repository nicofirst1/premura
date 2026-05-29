# Contract: MCP Analytical Tools

## Purpose

Expose the proof analytical tools on the default MCP surface while preserving the
existing agent-safe boundary.

## Tools

### `change_point`

User intent:

- Ask whether and when one metric shifted to a new level.

Required behavior:

- Delegates to the engine analytical path.
- Returns a serialized analytical envelope.
- Refuses with a distinct reason for stale, inadmissible, insufficient, or
  out-of-bounds requests.
- Does not name a cause.

### `smoothed_average`

User intent:

- Ask for a conservative smoothed pattern for one metric.

Required behavior:

- Delegates to the engine analytical path.
- Returns smoothed output with smoothing/window metadata.
- Refuses with a distinct reason for stale, inadmissible, insufficient, or
  out-of-bounds requests.
- Does not imply prediction or statistical significance.

## Wrapper Rules

- MCP wrappers do not query raw fact tables directly.
- MCP wrappers do not implement statistical computation.
- MCP wrappers only validate caller-facing parameter shape, call the engine, and
  serialize the engine outcome.
- The default MCP surface includes these tools explicitly; raw SQL remains only
  on the separate operator surface.

## Response Rules

Every response includes:

- `tool_name`
- `status`
- `message`
- `result` or refusal details

Every non-refusal `result` includes the analytical result envelope fields named
in `data-model.md`.
