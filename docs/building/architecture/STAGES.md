# premura — Stages

> Status: authoritative. Source of truth for cross-stage architecture boundaries.
>
> Companion to [DOCTRINE.md](../../shared/DOCTRINE.md) and [SPEC.md](../../shared/SPEC.md). The stages are the _data-flow shape_: a feature is located by where it sits in the pipeline.

## The four stages

Data moves through the system in a strict order. Each stage has a different contract and a different reason to change.

```
[ Sources ]
    │
    ▼
┌──────────────────────────────────────────┐
│ 1. Ingest                                │  parsers → DuckDB
│    Vendor artifact → fact_* rows         │
├──────────────────────────────────────────┤
│ 2. Signal processing                     │  deterministic Python
│    Raw rows → validity-checked,          │
│    imputed, derived signals              │
├──────────────────────────────────────────┤
│ 3. MCP                                   │  tools an LLM can call
│    Signal ops + PubMed, exposed as       │
│    MCP tools that return typed results   │
├──────────────────────────────────────────┤
│ 4. User interface                        │  agent text today, UI later
│    Interview, teaching, conversation,    │
│    presentation                          │
└──────────────────────────────────────────┘
```

### 1. Ingest

Parsers turn a vendor artifact into rows in `hp.fact_measurement` / `hp.fact_interval` per the long-format star schema. The registered parsers define what is supported; adding a source is parser work, not a change to this stage.

- No derivation, no imputation, no analysis. Ingest stores **what was observed, in canonical units, with provenance**.
- Idempotent (sha256 + `dedupe_key UNIQUE`), append-only.

### 2. Signal processing

Deterministic Python functions that turn raw rows into _answerable_ signals ("compound and creating new signals"; "two blood samples separated by 10 years probably can't be used"). They read only the user's own warehouse data and return shared result envelopes (`status`, `trend`, `baseline`, `change`) defined in `src/premura/engine/_results.py`; contributor rules live in `src/premura/engine/CONTRACT.md`.

Signal answers are **descriptive and comparative only**: no reference ranges, no diagnosis, no statistical significance, no causation. A `change` answer never reports a p-value or implies the named date caused anything; a `baseline` is the user's own history, never a population norm. A signal refuses (stale / unavailable / insufficient data) rather than present a misleading result.

**Input-resolution seam.** A Stage 2 consumer that needs data from another semantic domain declares one dependency per `DependencyDeclaration(consumer_name, depends_on_domain, required_key, failure_mode)` and asks for its value via `resolve_dependency(conn, ResolutionRequest(...))` (both re-exported from `premura.engine`). Dispatch is registry-driven through `RESOLVERS`, populated by the `@resolver(domain=...)` decorator. A declared dependency with no matching, fresh row resolves to an explicit missing / stale outcome and never substitutes a value from another domain. Adding a supported domain means landing one module under `premura/engine/views/` and appending its dotted name to `_BUILTIN_RESOLVER_MODULES`, without touching existing dispatch — the domain-agnostic steps are in [INTAKE_DIMENSIONS.md](../../../src/premura/engine/INTAKE_DIMENSIONS.md). (A BMI signal is a worked example: it declares height from profile context plus weight from observation history.)

**Answer-family closure.** The `RESULT_FAMILIES` set (`status`, `trend`, `baseline`, `change`) is **closed**. A new family is added only when a desired answer cannot be honestly mapped onto one of the four AND the question shape itself is approved through a dedicated planning mission. Resolver dispatch is open; answer families are not.

Four families of function:

- **Time-validity** — per-metric freshness window declared in `dim_metric`. HRV stales in hours; weight in weeks; blood lipids in months; a DXA scan effectively forever. The processor refuses to treat values past their window as "current" without an explicit override.
- **Missing-data policy** — per-metric: `none` (never impute; lab markers, exercise sessions), `last_observation_carried_forward` (weight, height, within window), `linear_interp` (dense continuous, short gaps), `seasonal_naive` (cyclic, opt-in). Returns the series **and** a parallel `is_imputed` mask.
- **Derived signals** — compound metrics computed from raw inputs and persisted with `metric_id` prefix `derived:` (e.g. `derived:hrv_7d_mean`, `derived:ldl_hdl_ratio`, `derived:ast_alt_ratio`). Recomputed on ingest of any input.
- **Signal selector** — given a question or interest, ranks signals that can answer it given _this_ warehouse's actual contents and current validity.

Signal processing has no external dependencies. No network, no LLM. It must be inspectable and reproducible from the warehouse alone.

### 3. MCP

The MCP server exposes Stage 2 signal functions as tools an LLM can call. Per [DOCTRINE.md](../../shared/DOCTRINE.md) this is the **primary operational interface**: the human brings artifacts, goals, and approvals; the agent works mainly through this tool surface. Two entrypoints exist (`src/premura/mcp/server.py`, `entrypoint.py`).

**Default agent surface (`premura-mcp`)** — the live tool inventory lives in the test suite (`tests/mcp/test_mcp_server.py`); the tool groups and their contracts:

- **Catalog / summary** — list metrics and per-metric summaries. Delegate entirely to the Stage 2 engine (no direct `hp.*` SQL) and return structured validity/imputation envelopes with machine-branchable fields.
- **Signal-backed** — one tool per grounded signal (resting HR status and trend, steps trend, weight trend, deep-sleep baseline, HRV change, supplement adherence, nutrition-intake trend, …). Each opens the warehouse read-only and delegates to the Stage 2 engine; the `status` field (`available` / `missing_input` / `stale_input` / `insufficient_data`) keeps each refusal reason distinct.
- **Agent-mediated profile capture** — a bounded _write_ path recording one baseline profile fact at a time, validated against the closed allowlist (`premura.profile_fields`) at the store boundary, stamping provenance and superseding the prior assertion while keeping history. An unsupported or derived key (such as `age`) comes back as a structured `rejected` response. These live on the default surface because bounded capture is the supported agent workflow.
- **Analytical** — a closed set returned by `engine.list_analytical_tools()`: change-point, smoothed average, correlation (a pre-registered, caller-declared association — no p-value, names no cause), rolling mean, and paired / condition-paired comparisons (a declared before/after paired difference with a descriptive uncertainty band — **not** a significance test). Each delegates to the engine over the bounded analytical contract, returns the mandatory result envelope (estimate + validity metadata + closed confound checklist) or a first-class refusal, and takes an optional `session_id` recording the call in a research trace.
- **Session research trace** — an explicit, append-only ledger of the analytical calls dispatched in a session, from which a _measured_ multiplicity disclosure ("K user-facing findings among N unique hypotheses examined") is derived. This is MCP-boundary provenance, not engine state: it lives in the pure `premura.trace` service over `trace.*` tables, reads no `hp.*` rows, computes no statistic, and the engine produces byte-identical envelopes whether or not a trace is active. See [ADR 0009](../adr/0009-session-research-trace-and-multiplicity-disclosure.md).
- **PubMed grounding** — search returns **candidates only** (`citation_status = candidate_only`, never citeable even when a hit carries a PMID); fetch takes one exact PMID and returns a **citeable** record (`citation_status = citeable_fetched_record`) with the `pubmed_url` + `provider` provenance an honest citation needs. A final answer may cite **only** a fetched record. The provider is a Premura-owned adapter over NCBI E-utilities (label `ncbi-eutils`) called through the Python standard library, so no HTTP dependency is added; provider/network failures return a structured `provider_error`, not an exception. These tools reach the literature, never the operator's `hp.*` data.

**Operator surface (`premura-mcp-operator`)** — all default tools plus `query_warehouse`, the raw-SQL escape hatch, which returns raw rows without any Stage 2 validity guarantees. Requires explicit user approval before agent use. See [ADR 0004](../adr/0004-stage3-operator-entrypoint.md).

Principles:

- The LLM never returns effect sizes from its priors — it calls a tool, receives a structured result, and narrates.
- Every PubMed citation must round-trip through `pubmed_fetch(pmid=…)`: search candidates are discovery hints only and are never citeable.
- MCP is the only stage that talks to a model and the only stage that may make a network call. Network calls are user-initiated, never background, and reach the literature, never the operator's health data.

### 4. User interface

Everything the human encounters: the agent's text today, MCP-backed chat, an eventual custom UI. This stage is human-critical in purpose even though it is not the main execution surface.

- **Interview** — first contact asks the user _what direction_ (sleep, cardio, metabolic, stress, mental, gut, lab/cardiometabolic, overview). Output is a routing decision that calls the signal selector; no "analyse everything at once" by default. The same agent-mediated interview shape captures baseline profile facts: the agent records one allowlisted attribute at a time through the profile-capture tools (mirrored as the expert CLI verbs `premura profile-fields` / `premura profile-record`), never via a human-filled form.
- **Teaching** — a content + interaction _style_ (plain-language metric introductions, progressive disclosure, dual coding of insight + number), not a screen. It lands first in the agent's **text narration** through a coding-agent client and transfers to a **custom UI when one is built later**. The narration-level half (the caption that names the insight, the plain-English gloss) applies now; _dual-coded charts_ specifically are a later-UI affordance. Applies to every metric surfaced, blood markers especially.
- The UI stage is the only stage that does presentation, unit display, and prose. It is where the human receives help, teaching, and guided interpretation from the agent-mediated workflow — today that surface is the agent's text through a coding-agent client; a custom UI is a deliberate later destination, not UI-free.

## Why this matters

A feature with no stage assignment slides into "everything is everything." Sample placements:

| Feature shape                   | Stage                                |
| ------------------------------- | ------------------------------------ |
| "Ingest Withings export"        | Ingest                               |
| "Fill gaps in weight series"    | Signal processing                    |
| "Compute LDL/HDL ratio"         | Signal processing                    |
| "Decide which signal answers Q" | Signal processing (selector)         |
| "Run a paired t-test"           | MCP (tool calling signal processing) |
| "Onboard a new user"            | UI (interview)                       |
| "Explain rMSSD"                 | UI (teaching)                        |
| "Cite a PubMed paper"           | MCP                                  |

## Semantic domains (not a fifth stage)

The four stages are an _execution_ model — they describe how data flows through the pipeline. Premura also has _semantic_ domains that describe what a piece of data **means**. The two axes are orthogonal: a stage is _where_ work happens; a domain is _what kind of thing_ the data is. The domains — observation history, note history, baseline profile context, nutrition intake, supplement intake — and the boundary rules between them (the hard cases are where the same real-world subject appears in more than one domain) are defined in [PROFILE_AND_INTAKE_CONTRACT.md](../../../src/premura/store/PROFILE_AND_INTAKE_CONTRACT.md).

There is **no fifth stage**. Profile context and intake are data domains that later stages read; they do not add a step to the ingest → signal → MCP → UI pipeline:

- **Stage 1 (Ingest)** stores observations. Profile assertions and intake records have their own domain homes under `hp.` (migration `004_profile_intake.sql`) — they are **never** written as extra `fact_measurement` rows, because a declaration and a consumption event are not measurement events.
- **Stage 2 (Signal processing)** may _read_ profile/intake context to answer a question, but only by **declaring** that dependency through the input-resolution seam above; a no-matching-row case resolves to an explicit missing/stale outcome and is never coerced into an observation.
- **Stages 3–4 (MCP, UI)** surface whatever Stage 2 produces and host the agent-mediated profile-capture write path (bounded capture against the closed allowlist). This does not let an agent read `fact_measurement` directly any more than the signal tools do.

**Anti-pattern — do not smuggle profile/intake into observation paths.** A declared height is not a measurement; a meal's calories are not a body observation; a structured supplement dose is not a free-text note. Reusing an observation path for a declaration (or a note for structured intake) collapses two distinct meanings; keep them apart. If something seems to need two homes, that is a sign two meanings are being conflated.

## Boundary contracts

- **Default agent surface (`premura-mcp`):** reaches `fact_measurement` only through a signal-processing function that has already applied validity + imputation policy. Catalog/summary/signal helpers delegate entirely to the Stage 2 engine (no raw `hp.*` SQL); profile-capture writes only through the bounded store boundary; trace tools read/write only derived `trace.*` rows (never `hp.*` facts); PubMed tools reach only external literature. The `query_warehouse` escape hatch is **not present** on this surface.
- **Operator surface (`premura-mcp-operator`):** a separate, explicitly opt-in entrypoint adds `query_warehouse` on top of the full default set, returning raw rows without Stage 2 validity, freshness, or imputation guarantees. The approval rule is enforced two ways: the raw-SQL tool is absent from the default surface (an agent connected there cannot reach it), and the operator entrypoint refuses to start unless the launcher acknowledges lower-guarantee mode via `--ack` or `PREMURA_OPERATOR_ACK`. See [ADR 0004](../adr/0004-stage3-operator-entrypoint.md).
- UI never reads `fact_measurement` directly — always through MCP tools (even when invoked locally without a remote LLM, the MCP boundary is the API).
- Ingest never calls signal processing. The warehouse must be reconstructible from raws alone.

## Where each contract lives

STAGES is the map; each stage's detailed contract lives next to its code in `src/premura/` (one source of truth, docs link to it — [ADR 0017](../adr/0017-contracts-live-in-src-docs-link.md)):

- **Ingest (parsers)** — [`parsers/CONTRACT.md`](../../../src/premura/parsers/CONTRACT.md) (plugin contract), [`parsers/PARSER_CONTRIBUTING.md`](../../../src/premura/parsers/PARSER_CONTRIBUTING.md) (contributor guide), [`parsers/AI_CHAT_RECALL_CONTRACT.md`](../../../src/premura/parsers/AI_CHAT_RECALL_CONTRACT.md).
- **Signal processing (engine)** — [`engine/CONTRACT.md`](../../../src/premura/engine/CONTRACT.md) (what a signal may claim), [`engine/INTAKE_DIMENSIONS.md`](../../../src/premura/engine/INTAKE_DIMENSIONS.md) (the add-a-resolver rule).
- **Storage (store)** — [`store/UPDATE_STRATEGY.md`](../../../src/premura/store/UPDATE_STRATEGY.md) (warehouse update kinds), [`store/PROFILE_AND_INTAKE_CONTRACT.md`](../../../src/premura/store/PROFILE_AND_INTAKE_CONTRACT.md) (profile/intake meaning contract, with its `profile_intake_contracts/*.yaml`).
- **MCP / trace** — [`AUDIT_CONSUMER_CONTRACT.md`](../../../src/premura/AUDIT_CONSUMER_CONTRACT.md) (the Session Disclosure shape `trace.py` produces).
- **UI (Stage 4)** — [`ui/OPERATING_ROLES.md`](../../../src/premura/ui/OPERATING_ROLES.md) (runtime orchestrator + operating roles), [`ui/HUMAN_FACING.md`](../../../src/premura/ui/HUMAN_FACING.md) (human-facing role + interview flow), and the disclosure rubric [`skills/human-facing-teaching/DISCLOSURE_RUBRIC.md`](../../../src/premura/skills/human-facing-teaching/DISCLOSURE_RUBRIC.md).
