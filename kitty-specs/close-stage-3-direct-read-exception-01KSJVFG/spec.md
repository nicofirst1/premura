# Feature Specification: Close the Stage 3 Direct-Read Exception

**Mission**: close-stage-3-direct-read-exception-01KSJVFG
**Created**: 2026-05-26
**Mission type**: software-dev
**Status**: Draft

## 1. Summary

Premura's architecture requires the AI-facing Stage 3 (MCP) surface to reach the
warehouse fact tables only through a Stage 2 engine function that has already
applied validity-window and imputation policy. The six signal-backed tools honor
that contract today, but three raw tools — `query_warehouse`, `list_metrics`,
`metric_summary` — read the fact tables directly and surface row counts and
all-time extrema with no freshness or imputation gating. The architecture doc
records this as a "Known exception (temporary)".

The exception's only stated precondition — a built-out Stage 2 — is now met. Under
the product doctrine, the agent-facing MCP surface is the **primary product
interface**, so an un-gated agent read on that surface is a product-integrity
problem, not just documentation debt. This mission closes the exception:

1. **Catalog and summary go through Stage 2.** `list_metrics` and `metric_summary`
   are re-backed by validity-gated engine functions, so the agent receives values
   already gated for freshness and annotated for imputation, with a machine-readable
   validity envelope instead of raw fact-table rows.
2. **The raw SQL escape hatch becomes operator-only.** `query_warehouse` is removed
   from the default agent-facing surface and exposed only when the server is launched
   in an explicit operator mode — keeping ad-hoc SQL available to the human while
   matching the doctrine's "direct SQL is an expert-fallback path" stance.
3. **The boundary contract reads clean.** The architecture doc's "Known exception
   (temporary)" note is removed, and the decision is recorded in a new ADR.

No new Stage 2 question signals, statistics, or profile-dependent behavior are added.

## 2. User Scenarios & Testing

### Primary actors

- **Agent (primary operational client)** calling the default Stage 3 (MCP) tool
  surface to inspect what data exists and how trustworthy it is.
- **Downstream caller / UI** that branches on tool responses programmatically.
- **Operator (human)** who occasionally needs ad-hoc SQL over the warehouse.

### Acceptance scenarios

1. **No un-gated agent read.** Given the server started in its default (agent-facing)
   mode, when the agent lists the available tools, then the arbitrary-SQL tool is
   absent and every remaining tool that reports warehouse data applies validity and
   imputation policy.
2. **Catalog carries freshness, not raw counts.** Given a warehouse with fresh,
   stale, and empty metrics, when the agent requests the metric catalog, then each
   metric entry carries a validity status (current / stale / unavailable) derived
   from the metric's validity window, plus its declared validity window and
   missing-data policy — not a raw fact-table row count.
3. **Summary carries a validity/imputation envelope.** Given a metric with recent
   data, when the agent requests its summary, then the response reports the latest
   value with its validity status and observation time, the declared policy, the
   sample size, the imputed proportion, and the gap count over a recent window —
   and reports no all-time aggregate extrema.
4. **Honest absence.** Given a metric with no usable data, or an unknown metric id,
   when the agent requests its catalog entry or summary, then the response presents
   an explicit unavailable state with no fabricated numeric values.
5. **Operator keeps the escape hatch.** Given the server started in operator mode,
   when the operator lists tools, then the arbitrary-SQL tool is present and usable.
6. **Boundary doc reads clean.** Given the architecture boundary documentation,
   when a reader reviews the Stage 2 → Stage 3 contract, then it states the contract
   holds with no exception and contains no "known exception (temporary)" note.

### Edge cases

- A metric that is present-but-stale must surface as `stale`, distinct from an
  empty metric surfacing as `unavailable`.
- Re-backing the catalog tools must not regress the six signal-backed tools or the
  lazy-load guarantee (importing the engine must not eagerly load signal modules).
- A metric whose missing-data policy forbids imputation must report a zero imputed
  proportion, never carried-forward values.
- Listing tools in default vs. operator mode must differ only by the presence of
  the arbitrary-SQL tool.

## 3. Functional Requirements

| ID | Requirement | Verification | Status |
|---|---|---|---|
| FR-001 | No tool on the default agent-facing surface SHALL read the warehouse fact tables without first applying the metric's validity-window and imputation policy. | Test asserts the default tool surface excludes the arbitrary-SQL tool and that the catalog/summary tools route through the validity-gated engine, not direct fact-table reads. | Draft |
| FR-002 | The metric catalog tool SHALL report, per metric, a validity status (current / stale / unavailable) computed from the metric's validity window, together with the declared validity window and missing-data policy, in place of raw fact-table row counts. | Test seeds fresh, stale, and empty metrics and asserts each catalog entry carries the correct validity status and declared policy, with no raw-count field. | Draft |
| FR-003 | The metric summary tool SHALL return a validity/imputation envelope — latest value, validity status, observation time, declared policy, sample size, imputed proportion, and gap count over a recent window — and SHALL NOT return all-time aggregate extrema. | Test asserts the summary response carries the validity-envelope fields and that all-time min/max/avg are absent. | Draft |
| FR-004 | When a metric has no usable data or its id is unknown, the catalog and summary tools SHALL return an explicit unavailable result with no fabricated numeric values. | Test asserts that for an empty and an unknown metric the numeric fields are absent/empty while a validity status and explanation are present. | Draft |
| FR-005 | The arbitrary-SQL tool SHALL be absent from the default agent-facing tool surface and exposed only when the server is explicitly launched in operator mode. | Test asserts the default-mode tool list omits the SQL tool and the operator-mode tool list includes it. | Draft |
| FR-006 | The Stage 2 → Stage 3 boundary documentation SHALL state a clean contract with no exception, and the "Known exception (temporary)" note SHALL be removed. | Review/grep confirms the boundary section contains no temporary-exception note and describes the agent surface as fully validity-gated. | Draft |

## 4. Non-Functional Requirements

| ID | Requirement | Threshold / Verification | Status |
|---|---|---|---|
| NFR-001 | The change SHALL preserve the behavior of the six signal-backed tools and the engine lazy-load boundary. | Full existing test suite passes with no regressions, and importing the engine still does not eagerly load signal modules. | Draft |
| NFR-002 | The catalog and summary outputs SHALL remain non-diagnostic. | Review and tests confirm no clinical thresholds, statistical significance, or causal language is introduced; outputs report only freshness, availability, and coverage. | Draft |
| NFR-003 | The validity/imputation envelope SHALL be machine-branchable from explicit fields. | Tests branch on `validity_status`, sample size, imputed proportion, and gap count as discrete fields without parsing free text. | Draft |
| NFR-004 | Operator mode SHALL be opt-in and explicit; the default server start SHALL expose exactly the agent-facing tool set and never the arbitrary-SQL tool. | Test asserts the default build registers the agent-facing set (the six signal tools plus the two validity-gated catalog tools) with no SQL tool, and the operator build adds exactly the SQL tool. | Draft |

## 5. Constraints

| ID | Constraint | Status |
|---|---|---|
| C-001 | The change SHALL reuse the existing Stage 2 validity primitives and freshness vocabulary (the current/stale/unavailable freshness model and the existing latest-value / windowing helpers); it SHALL NOT introduce a parallel freshness model. | Active |
| C-002 | No new Stage 2 question signals, no statistics/PubMed tools, and no profile-dependent behavior (profile attributes stay deferred to issue `#6`); the encryption boundary (ADR 0002) is unchanged. | Active |
| C-003 | Changes are confined to the engine catalog functions and their result types, the Stage 3 server and entrypoint, the affected tests, and the relevant docs plus a new ADR. No unrelated refactors. | Active |

## 6. Success Criteria

- SC-001: Zero tools on the default agent-facing surface read the warehouse fact
  tables without validity and imputation policy applied.
- SC-002: Every default agent-facing catalog entry carries an explicit validity
  status, and every summary response additionally carries sample size and imputed
  proportion — all determinable from structured fields alone.
- SC-003: The arbitrary-SQL tool is absent from the default agent surface and
  present only under operator mode, verifiable by listing tools in each mode.
- SC-004: No catalog or summary response presents a fabricated numeric value when a
  metric has no usable data or is unknown.
- SC-005: The architecture boundary documentation reads clean (no "known exception
  (temporary)" note remains), and the full test suite passes with no regressions.

## 7. Key Entities

- **Metric catalog entry**: a per-metric record carrying the metric's identity and
  declared policy plus a freshness-derived validity status.
- **Metric validity summary**: a per-metric envelope carrying the latest value with
  its validity status and observation time, sample size, imputed proportion, and gap
  count over a recent window.
- **Validity status**: the current / stale / unavailable freshness verdict already
  used by the engine's signal results, reused here as the catalog/summary trust signal.
- **Operator mode**: an explicit server launch mode that additionally exposes the
  arbitrary-SQL escape hatch for human/expert use.

## 8. Assumptions

- The engine's existing freshness vocabulary (current / stale / unavailable) is the
  validity status to surface; no new status vocabulary is invented.
- "Honest absence" means an explicit empty/null numeric value in the serialized
  response, consistent with how the status-family signal result already omits its
  value when unavailable.
- A fixed recent window (set during planning, e.g. a 30-day daily window) is an
  acceptable basis for the summary's sample size, imputed proportion, and gap count;
  the exact span is an implementation detail.
- Removing the arbitrary-SQL tool from the default agent surface does not remove the
  capability: the operator retains it via operator mode and via direct access to the
  local warehouse file.

## 9. Scope

**In scope**: re-backing `list_metrics` and `metric_summary` through new
validity-gated engine functions that return a validity/imputation envelope; gating
`query_warehouse` behind an explicit operator mode; removing the architecture
boundary exception and recording the decision in a new ADR; and rewriting the
affected tests to assert validity gating and operator-mode behavior instead of
direct-read passthrough.

**Out of scope**: new signals or question shapes; statistical tooling, external
references, or teaching behavior; profile-dependent answers (deferred to `#6`); any
change to the encryption boundary (ADR 0002); unrelated refactors.
