# Contract: Intake Tool Surface

Purpose: define how the new intake-backed Stage 2 answers reach the default MCP
surface.

## Tool-surface rules

1. Both new intake-backed tools are exposed on the default MCP surface alongside
   the existing signal-backed tools.
2. Each tool is a thin Stage 3 wrapper around the grounded Stage 2 signal path.
3. Tool payloads follow the existing signal-wrapper contract:

```json
{
  "tool_name": "...",
  "status": "available | missing_input | stale_input | insufficient_data",
  "message": "...",
  "result": { "..." },
  "missing_input": { "... optional ..." }
}
```

4. The wrapper layer does not re-derive intake semantics from raw tables.
5. Missing/stale/insufficient states remain structurally distinct, not generic
   string errors.

## Behavioral promises

- supplement tool: descriptive logged-on-K-of-N-days style answer only
- nutrition tool: descriptive up/down/flat answer only
- no fallback into another domain's value
- no diagnosis / recommendation / causal language

## Evidence expectation

- MCP registration test proving both tools are published
- one successful call per tool
- missing/stale/insufficient tool-path tests
