# The session log adopts the OpenTelemetry GenAI *shape* but takes no library and runs no server — plain rows in its own local DuckDB file

Premura needs a general **session log**: the record of every step of one operating
session (agent turns, model calls, tool executions, and Premura-internal ingest
provenance), so a run can be tested end-to-end in a sandbox, audited for honesty,
and mined for improvement candidates. The fuller framing — including the thin
first slice (the parser-build loop), the two-layer testing model, and the
relationship to the orchestrator and the research trace — is in
[`docs/building/planning/agent-interaction-audit-substrate.md`](../planning/agent-interaction-audit-substrate.md).
This note records the storage decision so the implementing mission does not
re-litigate it.

The decisions:

- **Adopt the OpenTelemetry GenAI *vocabulary and tree shape*, not a backend.**
  Steps are modelled as a tree (agent turn → model call → tool call) using the
  GenAI attribute names, so the log is a recognized shape any observability tool
  could read later — but the names are hardcoded as plain strings, not imported
  from the still-"Development"-status conventions package whose attribute names
  churn.

- **Take no OTel library and run no server.** We write plain rows by hand, exactly
  the idiom `premura.trace` already uses. Researched June 2026: the auto-capturing
  instrumentation libraries only hook the OpenAI/Anthropic *client SDKs* — they
  would not see Premura's own MCP tools, the agent editing files during a parser
  build, or ingest provenance — so we instrument our own events by hand *either
  way*. The SDK's one real benefit (async parent/child context propagation) is not
  needed where events are recorded at single known points. Every off-the-shelf
  alternative surveyed (MLflow tracing, Logfire, Phoenix, Langfuse, AgentOps,
  Braintrust, Helicone, Lunary, Laminar, Lilypad) requires a running server, a
  cloud account, or a heavy multi-service stack; the one lighter option
  (`otel-file-exporter`) forces a clunky JSON format and loses DuckDB querying.
  Hand-rolling adds zero dependencies and works offline inside a sandbox.

- **The session log is its own local file, separate from the warehouse.** It is
  PHI-bearing (it can hold the human's actual questions), so a separate file makes
  "never sync, never export" one physical rule; it is trivial to point at a temp
  location and discard for a sandbox run; and it removes the *warehouse-vs-log*
  contention behind the open/close connection dance `entrypoint.py` performs
  because DuckDB refuses two *concurrent* connections to one file. (The log itself
  stays single-writer / serialized — see the planning note — so the contention is
  not merely moved onto the log file.)

- **The research trace is left untouched.** The `trace.*` honesty ledger
  (ADR-0009) is engine-pure, measured, and contract-protected. The session log is
  a broader, looser-semantics layer and is kept in a **separate file**, never
  folded into the research-trace tables. Unifying them is an optional, much-later
  optimization, explicitly out of scope.

Consequence: nothing is foreclosed. If a future orchestrator's heavily-async agent
loop ever makes the OTel SDK worth it, a small custom exporter writes into the
*same* tables; an "export to standard format" path can be added without touching
how steps are recorded.
