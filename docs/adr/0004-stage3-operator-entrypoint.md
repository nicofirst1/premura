# Split a separate operator entrypoint for raw SQL; gate agent use behind explicit approval

The Stage 2 → Stage 3 boundary contract requires that the default agent-facing MCP surface
reaches `hp.fact_measurement` only through Stage 2 engine functions that have already applied
validity and imputation policy.  Raw SQL access (`query_warehouse`) is a necessary expert
escape hatch — it provides open-ended warehouse exploration that the signal-backed tools do
not cover — but it carries no Stage 2 validity, freshness, or imputation guarantees, so it
must not appear on the surface an autonomous agent consumes by default.

The decision is to ship two separate console-script entrypoints: `premura-mcp` (default,
eight fully validity-gated tools) and `premura-mcp-operator` (lower-guarantee, adds
`query_warehouse`).  This keeps the agent default clean — the eight-tool surface honors the
Stage 2 boundary contract end-to-end — while preserving the raw SQL path behind an explicit
operator gate.  The explicit-approval rule is enforced two ways rather than by prose alone:
(1) surface separation — `query_warehouse` is absent from the default `premura-mcp` surface, so
an agent connected there cannot reach it; and (2) an explicit launch acknowledgment — the
`premura-mcp-operator` console entry refuses to start, and therefore never exposes
`query_warehouse`, unless the launcher opts in via `--ack` or the `PREMURA_OPERATOR_ACK`
environment variable.  The lower-guarantee disclosure to the end user remains a client/agent-layer
responsibility the server cannot enforce.  The split builds on ADR 0002, which established
that MCP uses the local warehouse directly; this ADR closes the final Stage 3 direct-read
exception that ADR 0002 left open.
