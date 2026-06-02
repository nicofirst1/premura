# A session-scoped research trace lives at the MCP boundary, in its own non-`hp.*` schema, and reports a *measured* multiplicity disclosure — never a corrected statistic

The session-scoped research trace is the stateful counterpart that design
decision note [0008](0008-correlate-pre-registered-lagged-association.md)
explicitly pushed out of the stateless analytical engine. With three inference
tools now shipped (`change_point`, `correlate`, and `paired_t_test` coming), an
agent can examine many hypotheses against one person's data and present only the
one that fit — a per-session property that per-call honesty cannot see. This note
records the shape the trace is taking so the implementing mission, and the audit
skill after it, extend it consistently instead of re-deciding. The mission spec
is `kitty-specs/session-research-trace-01KSYT4A/spec.md`; the fuller planning
brief is `docs/building/planning/research-trace-multiplicity-audit.md`.

The decisions:

- **The trace lives at the MCP boundary, not in the engine.** A new
  `premura.trace` surface driven by the MCP entrypoint records every analytical
  call before/after dispatch. The analytical engine keeps its invariant from
  0007/0008 — stateless, deterministic, no clock, no filesystem, no network — and
  its tool outputs are byte-identical whether or not a session is active. The MCP
  layer is the only place that actually *observes* tool calls, which is precisely
  why the count can be **measured rather than self-reported**.

- **The count must be measured, not trusted.** The same threat model as ADR-0007
  applies: any agent, including a weak or careless one, may operate Premura, so
  safety cannot rest on the agent honestly reporting how many hypotheses it tried.
  The boundary records each dispatched analytical call mechanically; a false
  self-reported count cannot change the disclosure.

- **Provenance is stored in a dedicated `trace.*` schema in the same DuckDB file,
  never in `hp.*`.** Keeping it in the warehouse file lets each record carry exact
  warehouse context (fingerprint / schema version) and stay queryable; keeping it
  out of `hp.*` preserves the "health facts live in `hp.*`" meaning boundary,
  because tool-use provenance is *not* health data. It is therefore also outside
  the encrypted health-export/backup semantics that apply to `hp.*`. The
  canonical ledger is structured and **append-only**; Markdown/JSON is an export
  generated on demand, never the source of truth (too easy to omit, edit, or
  format inconsistently).

- **The disclosure is *disclosure of search effort*, never a corrected
  statistic.** Having refused the p-value in 0008, we cannot honestly compute a
  multiplicity-corrected significance, and one would be meaningless on
  non-independent n-of-1 tests anyway. The honest artifact is a count: **"K
  user-facing findings among N unique hypotheses examined,"** with the raw
  analytical-call count shown alongside. The denominator **N is unique examined
  hypotheses** (normalized and deduplicated), not raw calls — a second raw number
  is surfaced separately so retries are visible without inflating N.

- **What counts as an examined hypothesis is a rule, not a list.** A call counts
  toward N when it is a valid analytical request that varies something (metric,
  pair, lag, window, comparison, parameter, expected direction) and reaches the
  data or the evidence/admissibility layer — **including refusals** for weak
  support, stale, inadmissible, no-overlap, or out-of-bounds evidence, because a
  refusal is still a look at the data. Excluded: exact in-session retries,
  catalog/metadata calls (`list_metrics`, `metric_summary`), validation failures
  *before* a request becomes an analytical question, re-rendering/exporting a
  prior result, and reading the trace. Each analytical tool declares its
  **normalized hypothesis identity** (correlate: left, right, lag, expected
  direction, params; change_point: metric, params; smoothed_average: metric,
  window, min coverage; future paired_t_test: outcome, grouping/event, windows,
  contrast, params). Adding a tool means declaring its identity, per "guide,
  don't enumerate" — never editing a counting switch.

- **"Surfaced" (K) is an agent/presentation-layer mark, never an engine
  judgment.** A result is *surfaced* when the agent uses it in the answer's
  claims, summary, recommendation, or next-step reasoning — *selected for
  presentation*, explicitly **not** "significant." The agent marks it through a
  session-layer step (e.g. `trace_mark_surfaced(call_id, role, rationale)`); K is
  the count of marks. When a trace has analytical calls but no marks, the
  disclosure reports surfaced as **unavailable** ("agent did not mark included
  results") rather than guessing. A later review skill *may* infer likely surfaced
  calls by matching final-answer result references against the trace, but that
  inference is **audit-derived, never canonical**.

- **Design *for* the audit skill now; build it later.** This mission ships the
  trace plus a stable **audit-consumer contract** — documented fields, IDs,
  normalized hypothesis identity, surfaced markers, refusal reasons, result
  hashes/envelopes — so a follow-on audit skill (0008's per-session twin of issue
  #10) has a trustworthy input. The trace layer records what happened,
  mechanically and deterministically; the audit skill interprets whether it was
  good agent behavior and may turn findings into issues/PRs/suggestions. Building
  both together would couple recording to interpretation before the trace exists.

This combination won because each alternative reopens a problem the project is
explicitly trying to avoid:

- **A stateful engine** would break the determinism invariant the whole
  analytical layer depends on (0007/0008); pushing state to the MCP boundary
  keeps the engine pure while still measuring the session.
- **Self-reported counts** would rest safety on the operating agent's honesty,
  which the threat model refuses — the same reason 0007 does not trust the agent's
  judgment about admissibility.
- **A multiplicity-corrected statistic** would be either uncomputable (we refused
  the p-value) or numerically meaningless on non-independent n-of-1 tests;
  disclosure of search effort is the honest artifact.
- **Inferring "surfaced" from an effect-size threshold** would smuggle back the
  "significant" call the project forbids; an explicit agent mark, with a
  conservative "unavailable" fallback, keeps the meaning honest and measured.
- **Storing provenance in `hp.*`** would collapse the health-fact meaning boundary
  and drag tool-use logs into the encrypted health export; a separate `trace.*`
  schema keeps the two meanings apart.

Consequences and forward-compatibility: the trace is additive — it introduces a
new `trace.*` schema (a new migration), a `premura.trace` surface, and new MCP
verbs (open session, mark surfaced, read/export disclosure) without changing any
analytical tool's signature or math. The per-tool normalized hypothesis identity
is the seam a future tool (`rolling_mean`, `paired_t_test`) plugs into by
declaration. The audit-consumer contract is the stable surface the deferred audit
skill builds on without a breaking change.
