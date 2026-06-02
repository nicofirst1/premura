# Mission plan (DRAFT): session-scoped research trace + multiplicity audit

> Status: **pre-spec draft.** Not authoritative. Captures the design agreed so
> far for the next mission so we can resume without re-deriving it. All major
> decisions are settled; only small specify-time details remain (see end).
>
> Companion reading: design decision note
> [`0008`](../adr/0008-correlate-pre-registered-lagged-association.md) (which
> explicitly defers this), [`STAGES.md`](../architecture/STAGES.md),
> `src/premura/engine/analytical_contract.py`, and
> `src/premura/engine/CONTRACT.md` §"Extending or reviewing a Stage 3 analytical
> tool".

## Why this mission, why now

Phase 3 now ships three inference tools (`change_point`, `correlate`, and the
deferred-but-coming `paired_t_test`). An agent can run many hypotheses and
surface only the one that fits. Per-call honesty cannot see that — 0008 names it
a **stateful, session-layer** concern and pushes it to "the audit/trace mission
after" `correlate`. This is the unretired *surfacing* half of risk **R7**: the
honest response to search effort is **disclosure** ("1 notable result among N
examined"), never a fake multiplicity-corrected statistic (which we couldn't
compute honestly, having refused the p-value).

Chosen over the alternatives (`rolling_mean`/`paired_t_test`; intake resolvers)
because the multiplicity risk is **live now**, not hypothetical.

## Locked design decisions

1. **Home — MCP boundary, engine stays pure.** A new `premura.trace` module,
   driven by the MCP entrypoint. The engine keeps its invariant: no clock, no
   session state, no filesystem, no network. The MCP wrapper records every
   analytical call **before/after** dispatch, so counts are **measured, not
   self-reported** by the agent (same threat-model reasoning as ADR-0007).

2. **Store — `trace.*` in the warehouse DuckDB file, not `hp.*`.** Local,
   append-only tables in the same DuckDB file (so each record can carry exact
   warehouse context and stay queryable), under a `trace.*` schema. Kept out of
   `hp.*` because this is **tool-use provenance, not health data** — preserves
   the "health facts live in `hp.*`" meaning boundary. New migration
   `005_trace_audit.sql`.

3. **Canonical ledger is structured + append-only; Markdown/JSON is an export.**
   Human-readable audit artifacts are generated *from* the store on demand, never
   the source of truth (too easy to omit, edit, or format inconsistently).

4. **Proposed schema (to firm up at specify time):**
   - `trace.session` — session id, started_at, client label, warehouse
     fingerprint / schema version.
   - `trace.tool_call` — one row per analytical call: tool name, request hash,
     **normalized hypothesis identity**, timestamps, status / refusal reason.
   - `trace.tool_result` — optional compact result envelope or result hash.
   - a derived **disclosure view** — counts for the "N examined / M available /
     K surfaced" statement.

5. **Multiplicity denominator `N` = unique examined hypotheses** (after
   normalizing and deduplicating identical requests). Surface a **second** raw
   count alongside it, e.g. *"1 notable among 12 unique hypotheses examined; 17
   analytical calls including retries."*
   - **Counts toward N:** any valid analytical request that chooses something
     variable (metric / pair / lag / window / comparison / parameter / expected
     direction) and reaches the data or evidence/admissibility layer — **including
     refusals** for weak support, stale, inadmissible, no-overlap, or
     out-of-bounds evidence (a refusal is still a look at the data).
   - **Does not count:** exact retries of the same normalized request in-session;
     catalog/metadata calls (`list_metrics`, `metric_summary`); pure validation
     failures *before* a request becomes an analytical question (empty metric id,
     invalid enum); re-rendering/exporting a prior result; reading the trace.

6. **Hypothesis identity (the normalization key), per tool:**
   - `correlate` — left metric, right metric, lag, expected direction, declared params.
   - `change_point` — metric, analysis params (e.g. `min_side_observations`).
   - `smoothed_average` — metric, window, min coverage.
   - future `paired_t_test` — outcome metric, grouping/event definition, windows,
     direction/contrast, params.

7. **`K` ("surfaced") is an agent/presentation-layer mark, never an engine
   decision.** A result is *surfaced* when the agent uses it in the answer's
   claims, summary, recommendation, or next-step reasoning — i.e. **selected for
   presentation**, explicitly *not* "significant". The agent marks it through a
   session-layer step, e.g. `trace_mark_surfaced(call_id, role, rationale)`;
   `K` = count of marked calls. So the phrase is **"K user-facing findings among
   N unique hypotheses examined"**, never "K significant results among N tests".
   - *Counts as surfaced:* a result used in the final answer; a named "strongest
     pattern I found"; a refusal cited as evidence ("I checked X but there wasn't
     enough overlap"); a trace section marked as included in the user-facing answer.
   - *Not surfaced:* computed but never mentioned; used only internally to decide
     what to try next; an exact retry that replaces an identical call; an answer
     that gives only generic caveats without naming the result.
   - **Conservative fallback for weak/careless agents:** if a trace is exported
     with no explicit marks, the summary says *"surfaced count unavailable; agent
     did not mark included results"* rather than guessing. A later review skill
     *may* infer likely surfaced calls by matching final-answer result IDs against
     the trace, but that inference is **audit-derived, never canonical**.

8. **Design *for* the audit skill now; implement it later.** This mission ships
   the trace and an **audit-consumer contract** — stable fields, IDs, normalized
   hypothesis identity, surfaced markers, refusal reasons, result hashes/envelopes
   — so a follow-on audit skill has a trustworthy input. The trace layer records
   what happened, mechanically and deterministically; the audit skill (a separate
   mission) interprets whether it was good agent behavior. Building both together
   would mix those two concerns before the trace even exists.

## Scope

**In:** `premura.trace` module + `trace.*` schema and migration `005`; MCP
wrapper auto-recording around dispatch; session lifecycle; per-tool hypothesis
normalization/identity; the agent-layer `trace_mark_surfaced(...)` marking step;
the disclosure computation + a minimal MCP read/export tool ("K user-facing
findings among N unique hypotheses examined", plus raw call count and refusals);
the **audit-consumer contract** (stable fields, IDs, normalized hypothesis
identity, surfaced markers, refusal reasons, result hashes/envelopes) the
follow-on audit skill will read; tests (public-import, DuckDB-fixture, recording
+ dedup + disclosure + surfaced-mark + refusal paths); **live-doc sync** (STATUS
/ STAGES / ROADMAP / FULL_APP — explicitly not dropped, per the recurring
live-doc-sync miss).

**Out:** the **audit skill** that turns trace findings into issues / PRs /
suggestions (0008's per-session twin of issue #10); automated critique of the
agent's final answer against the trace; PubMed grounding; any change to engine
purity or existing tool math.

## Acceptance test (mission-level)

> Given a session with multiple analytical calls and two explicitly surfaced
> results, the trace export reports **raw call count**, **unique hypothesis
> count**, **surfaced count**, **refusals**, and **stable result references** —
> and, when no results were marked surfaced, reports surfaced count as
> *unavailable* rather than guessing.

The follow-on audit mission's test then reads: *given a trace export and a final
answer, the audit skill checks whether the answer disclosed search effort, hid
refused/contradictory results, overclaimed causality, or should open a repo
issue/suggestion.*

## Doctrine checks

- **Agent-first** — a ledger the agent reads/writes through MCP, not a
  human-operated dashboard.
- **Guide, don't enumerate** — define the *counting rule* and identity
  normalization, not an enumerated report format or a fixed list of "notable"
  findings.
- **Local-first** — stays inside the DuckDB file; no network at any layer.

## Recommended sequencing

1. **Design decision note `0009` first.** This introduces a new MCP-layer
   interface, a new `trace.*` schema, and new public types — the "note before the
   mission" trigger in the repo conventions. 0008 already anticipates it.
2. Then `/spec-kitty.specify` → plan → tasks → implement-review.

## Resolved since first draft

- **`K` ("surfaced")** — agent/presentation-layer mark via
  `trace_mark_surfaced(...)`, with a conservative "unavailable" fallback when
  unmarked (decision 7).
- **Audit skill** — out of scope; this mission ships the trace + audit-consumer
  contract, the skill is a follow-on (decision 8).

## To settle at specify time (smaller)

- **Session lifecycle** — explicit `open_session` tool vs. per-connection
  auto-create. Explicit favored, for reproducible session ids.
- **`request hash` / `result hash`** normalization details and the exact
  normalized-hypothesis-identity function per tool.
- Whether the disclosure/export tool returns all counts (raw, unique, surfaced,
  refusals) in one call.
- The exact `trace.*` table columns and the migration `005` shape.

## Next steps

1. Write design decision note `0009` locking the home, the `trace.*` boundary,
   the public types (session, trace records, surfaced mark), and the
   audit-consumer contract.
2. `/spec-kitty.specify` → plan → tasks → implement-review, against this brief.
