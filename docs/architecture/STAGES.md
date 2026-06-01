# premura — Stages

> Status: authoritative. Source of truth for cross-stage architecture boundaries.
>
> Companion to [DOCTRINE.md](../product/DOCTRINE.md), [../history/product/VISION.md](../history/product/VISION.md), [SPEC.md](../product/SPEC.md), [ROADMAP.md](../product/ROADMAP.md), [../history/research/PROPOSAL_LABS.md](../history/research/PROPOSAL_LABS.md).
> Captured 2026-05-21. Complements `docs/history/product/VISION.md` — does **not** replace the pillar framing. The pillars are the *trajectory*; the stages below are the *data-flow shape*. A feature is located in pillars by intent and in stages by where it sits in the pipeline.

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
│ 4. User interface                        │  CLI today, UI later
│    Interview, teaching, conversation,    │
│    presentation                          │
└──────────────────────────────────────────┘
```

### 1. Ingest

Parsers turn a vendor artifact into rows in `hp.fact_measurement` / `hp.fact_interval` per the long-format star schema documented in [../history/architecture/ARCHITECTURE_HISTORY.md](../history/architecture/ARCHITECTURE_HISTORY.md).

- Today: HC `.db`, Garmin GDPR `.zip`, Sleep as Android CSV, BMT CSV.
- Coming: blood / urine / stool lab PDFs (see [../history/research/PROPOSAL_LABS.md](../history/research/PROPOSAL_LABS.md)), continuous glucose, additional wearables.
- No derivation, no imputation, no analysis. Ingest stores **what was observed, in canonical units, with provenance**.
- Idempotent (sha256 + `dedupe_key UNIQUE`), append-only.

### 2. Signal processing

Deterministic Python functions that turn raw rows into *answerable* signals. This is the stage the user named when describing "compound and creating new signals" and "two blood samples separated by 10 years probably can't be used."

**Shipped today (first grounded answers).** Stage 2 now hosts six grounded, freshness-aware answers in addition to the derived lab ratios. They read only the user's own warehouse data and return shared result envelopes (`status`, `trend`, `baseline`, `change`) defined in `src/premura/engine/_results.py`; the contributor rules live in `src/premura/engine/CONTRACT.md`. The six:

- `resting_hr_status` — current resting HR with an honest freshness verdict (status).
- `resting_hr_trend` — direction of resting HR over recent weeks, gaps and carried-forward points made visible (trend).
- `steps_trend` — direction of daily steps; missing days stay gaps and are never imputed (trend).
- `weight_trend` — direction of body weight over the last month, carry-forward within the freshness window flagged (trend).
- `sleep_deep_pct_baseline` — latest deep-sleep percentage versus the user's **own** recent normal (baseline).
- `hrv_change_around_date` — plain before/after average of overnight HRV around a user-named date (change).

These are **descriptive and comparative only**: no reference ranges, no diagnosis, no statistical significance, no causation. A `change` answer never reports a p-value or implies the named date caused anything; a `baseline` is the user's own history, never a population norm. They refuse to answer (stale / unavailable / insufficient data) rather than present a misleading result. **BMI now ships as the first cross-domain Stage 2 proof consumer** using the input-resolution seam (see "Input-resolution seam" below); age-adjusted interpretation remains deferred as future implementation over the profile/intake contract, whose semantic boundary is now settled (see [PROFILE_AND_INTAKE_CONTRACT.md](PROFILE_AND_INTAKE_CONTRACT.md)).

**Input-resolution seam.** Stage 2's next foundation is **domain-aware input resolution**, not a universal prepared-series layer. A Stage 2 consumer declares one dependency per `DependencyDeclaration(consumer_name, depends_on_domain, required_key, failure_mode)` and asks for its value via `resolve_dependency(conn, ResolutionRequest(...))` (both re-exported from `premura.engine`). Dispatch is registry-driven through `RESOLVERS`, populated by the `@resolver(domain=...)` decorator. Four `SEMANTIC_DOMAINS` are valid in declarations — `observation_history`, `profile_context`, `nutrition_intake`, `supplement_intake` — but only the first two have concrete resolvers shipped in this mission; the other two return an explicit `usable=False, absence_reason="unsupported_domain"` outcome until a future mission ships their resolvers. Adding a new supported domain means landing one new module under `premura/engine/views/` and appending its dotted name to `_BUILTIN_RESOLVER_MODULES`, without touching existing dispatch.

**Answer-family closure.** The Stage 2 `RESULT_FAMILIES` set (`status`, `trend`, `baseline`, `change`) stays **closed** in this mission. A new family is added only when a desired answer cannot be honestly mapped onto one of the four AND the question shape itself is approved through a dedicated planning mission. Resolver dispatch is open; answer families are not.

Four families of function:

- **Time-validity** — per-metric freshness window declared in `dim_metric` (new column). HRV stales in hours; weight in weeks; blood lipids in months; DXA scan effectively forever. The processor refuses to treat values past their window as "current" without an explicit override.
- **Missing-data policy** — per-metric: `none` (never impute; lab markers, exercise sessions), `last_observation_carried_forward` (weight, height, within window), `linear_interp` (dense continuous, short gaps), `seasonal_naive` (cyclic, opt-in). Returns the series **and** a parallel `is_imputed` mask.
- **Derived signals** — compound metrics computed from raw inputs and persisted with `metric_id` prefix `derived:` (e.g. `derived:hrv_7d_mean`, `derived:ldl_hdl_ratio`, `derived:ast_alt_ratio`). Recomputed on ingest of any input.
- **Signal selector** — given a question or interest, ranks signals that can answer it given *this* warehouse's actual contents and current validity.

Signal processing has no external dependencies. No network, no LLM. It must be inspectable and reproducible from the warehouse alone.

### 3. MCP

The MCP server exposes Stage 2 signal functions as tools an LLM can call. Per [DOCTRINE.md](../product/DOCTRINE.md), this is the **primary operational interface** of the product: the human brings artifacts, goals, and approvals; the agent works mainly through this tool surface. The first bounded analytical tool set is now complete — `change_point`, `smoothed_average`, `correlate`, `rolling_mean`, `paired_t_test`, and the three session research trace tools have shipped. The long-term surface still adds PubMed search/fetch and a signal selector — those remain future work. Today two entrypoints exist (`src/premura/mcp/server.py`, `entrypoint.py`):

**Default agent surface (`premura-mcp`) — eighteen tools:**

- **Two catalog/summary tools** — `list_metrics`, `metric_summary`. These delegate entirely to the Stage 2 engine (no direct `hp.*` SQL) and return structured validity/imputation envelopes with machine-branchable fields.
- **Six signal-backed tools** — `resting_hr_status`, `resting_hr_trend`, `steps_trend`, `weight_trend`, `sleep_deep_pct_baseline`, `hrv_change_around_date`. Each opens the warehouse read-only and **delegates to the Stage 2 engine** instead of running its own SQL against the fact tables. They return a structured payload whose `status` field (`available` / `missing_input` / `stale_input` / `insufficient_data`) keeps each refusal reason distinct.
- **Two agent-mediated profile-capture tools** — `profile_context_supported_fields` (list the bounded allowlist) and `profile_context_record` (record one baseline profile fact). These are a bounded *write* path: `profile_context_record` validates against the closed allowlist (`premura.profile_fields`) at the store boundary, stamps provenance `agent_profile_capture`, and supersedes the prior open assertion while keeping history. An unsupported or derived key (such as `age`) comes back as a structured `rejected` response rather than being written. They live on the **default** surface because bounded capture is the supported agent workflow.
- **Five analytical tools** — `change_point` (level-shift detection), `smoothed_average` (conservative trailing smoothed pattern), `correlate` (a pre-registered, caller-declared whole-day-lagged Spearman *association* — no p-value, no "significant," names no cause), `rolling_mean` (a declared moving-window summary with visible coverage/imputation, distinct from `smoothed_average`), and `paired_t_test` (a declared before/after anchor-date paired comparison reporting a paired difference and a descriptive uncertainty band — **not** a significance test, no p-value, names no cause). This is the completed first bounded analytical tool set; `engine.list_analytical_tools()` returns exactly these five. Each delegates to the Stage 2 engine over the bounded analytical contract, routes to its own first-class analytical `QuestionType`, and returns the mandatory result envelope (estimate + validity metadata + closed confound checklist) or a first-class refusal. Each also takes an optional `session_id` that records the call in a session research trace (see below).
- **Three session research trace tools** — `research_trace_open`, `research_trace_mark_surfaced`, and `research_trace_disclosure`. These expose the **session research trace**: an explicit, append-only ledger of the analytical calls dispatched in a research session, from which a *measured* multiplicity disclosure ("K user-facing findings among N unique hypotheses examined") is derived. This is **MCP-boundary provenance, not engine state**: the trace lives in the pure `premura.trace` service over `trace.*` tables, recording happens *around* analytical dispatch, and the analytical engine stays stateless and produces byte-identical envelopes whether or not a trace session is active. The trace reads no `hp.*` health rows and computes no statistic. See design decision note [0009](../adr/0009-session-research-trace-and-multiplicity-disclosure.md).

**Operator surface (`premura-mcp-operator`) — nineteen tools:**

All eighteen default tools plus `query_warehouse`, the raw SQL escape hatch. This surface is lower-guarantee: `query_warehouse` returns raw rows without any Stage 2 validity guarantees. Requires explicit user approval before agent use. See [ADR 0004](../adr/0004-stage3-operator-entrypoint.md).

Other principles, still the target shape:

- The LLM never returns effect sizes from its priors — it calls a tool, receives a structured result, and narrates.
- Every PubMed citation must round-trip through `pubmed_fetch(pmid=…)` (PubMed tooling is not built yet).
- MCP is the only stage that talks to a model and the only stage that may make a network call. Network calls are user-initiated, never background.

### 4. User interface

Everything the human encounters: CLI today, MCP-backed chat, eventual UI. This stage is human-critical in purpose even though it is not the main execution surface.

- **Interview** (VISION Pillar 4) — first contact asks the user *what direction* (sleep, cardio, metabolic, stress, mental, gut, lab/cardiometabolic, overview). Output is a routing decision that calls the signal selector. No "analyse everything at once" by default. The same agent-mediated interview shape is how baseline profile facts are captured: the agent records one allowlisted attribute at a time through the profile-capture tools (mirrored as the expert CLI verbs `hpipe profile-fields` / `hpipe profile-record`), never via a human-filled form.
- **Teaching** (VISION Pillar 5) — plain-language metric introductions, dual-coded charts, progressive disclosure. Applies to every metric the UI surfaces, blood markers especially.
- The UI is the only stage that does presentation, unit display preferences, and prose. It is the layer where the human receives help, teaching, and guided interpretation from the agent-mediated workflow.

## Why this matters

A feature with no stage assignment tends to slide into "everything is everything." Sample placements:

| Feature shape | Stage |
|---|---|
| "Ingest Withings export" | Ingest |
| "Fill gaps in weight series" | Signal processing |
| "Compute LDL/HDL ratio" | Signal processing |
| "Decide which signal answers Q" | Signal processing (selector) |
| "Run a paired t-test" | MCP (tool calling signal processing) |
| "Onboard a new user" | UI (interview) |
| "Explain rMSSD" | UI (teaching) |
| "Cite a PubMed paper" | MCP |

## Semantic domains the stages work with (not a fifth stage)

The four stages above are an *execution* model — they describe how data flows
through the pipeline. Premura also has *semantic* domains that describe what a
piece of data **means**. The two axes are orthogonal: a stage is *where* work
happens; a domain is *what kind of thing* the data is.

Alongside the long-standing **observation history** (device/lab measurements in
`hp.fact_measurement` / `hp.fact_interval`) and **note history** (narrative free
text that cannot be normalized), the model now recognises three additional
semantic domains, fixed in
[PROFILE_AND_INTAKE_CONTRACT.md](PROFILE_AND_INTAKE_CONTRACT.md):

- **Baseline profile context** — stable or slowly-changing personal attributes
  the operator *states about themselves* (birth date, biological sex, a declared
  standing height). These are the operator's account of themselves, not an
  instrument reading.
- **Nutrition intake** — food/drink/energy/nutrient consumption: what was eaten
  or drunk, when, and what it contained (e.g. a meal's `energy_kcal`,
  `protein_g`).
- **Supplement intake** — supplement products, ingredients, and the doses taken.

> **These are semantic categories, not new runtime layers.** There is still no
> fifth stage. Profile context and intake are *data domains that later stages may
> read*; they do not add a step to the ingest → signal → MCP → UI pipeline. The
> contract fixes their meaning; the
> `implement-profile-and-intake-storage-01KSMWV1` mission then added concrete
> storage (migration `004_profile_intake.sql`, dedicated `hp.*` tables) and an
> **agent-mediated profile-capture** path, without adding a stage. What ships:
> bounded profile capture through MCP/CLI tools, and storage + a normalized load
> path for nutrition/supplement intake. **BMI now ships** as the first
> cross-domain Stage 2 proof consumer using the input-resolution seam. What
> does **not** ship: any built-in importer for a specific nutrition/supplement
> source (that stays parser/plugin follow-on work), concrete resolvers for the
> intake domains (declarations against `nutrition_intake` or
> `supplement_intake` remain valid but currently resolve to an explicit
> `unsupported_domain` outcome — they are not silently coerced into
> observations), and further profile-dependent Stage 2 answers beyond BMI
> (age-adjusted interpretation is the next deferred candidate). Do not infer a
> built-in nutrition importer from the existence of the intake tables.

### Where the new domains sit relative to observations and notes

Future stages relate to the new domains the same way they relate to observations
today, but the data is *meant* differently:

- **Stage 1 (Ingest)** stores observations (what a device/lab measured). Profile
  assertions and intake records now have their own domain homes under `hp.`
  (migration `004_profile_intake.sql`) — they are **never** written as extra
  `fact_measurement` rows, because those are declarations and consumption, not
  measurement events. Nutrition/supplement intake has a normalized load path
  (`persist_intake_batch`), but a parser that adapts a *specific* source into it
  is still follow-on work; no built-in importer ships.
- **Stage 2 (Signal processing)** may *read* profile/intake context to answer a
  question, but only by **declaring** that dependency explicitly through the
  input-resolution seam (see
  [PROFILE_AND_INTAKE_CONTRACT.md](PROFILE_AND_INTAKE_CONTRACT.md), "How future
  functions declare what they need", and `src/premura/engine/CONTRACT.md`).
  BMI is the first Stage 2 consumer that uses this seam (declared height from
  profile context plus weight from observation history); age-adjusted
  interpretation remains deferred, and `age` stays derived, never stored.
  `nutrition_intake` and `supplement_intake` remain **valid declaration
  targets** but currently resolve to an explicit `unsupported_domain` outcome
  — they are not silently coerced into observations.
- **Stages 3–4 (MCP, UI)** surface whatever Stage 2 produces and **also host the
  agent-mediated profile-capture write path**: the default MCP surface exposes
  `profile_context_supported_fields` / `profile_context_record`, mirrored by the
  expert CLI `hpipe profile-fields` / `hpipe profile-record`. This is the bounded
  *capture* path (writing declared baseline facts against the closed allowlist),
  not a reach into observation data — it does not let an agent read
  `fact_measurement` directly any more than the signal tools do.

### Boundary examples and anti-patterns

The hard cases are where the *same real-world subject* appears in more than one
domain. The model resolves them by meaning, with exactly one canonical home per
normalized value (`profile_context`, `nutrition_intake`, `supplement_intake`,
`observation_history`, or `note_history` — there is no `misc` bucket):

| Subject | Profile / intake domain | Observation domain | Why they stay apart |
|---|---|---|---|
| **Height** | A height the operator *declares* is baseline profile context (`standing_height_declared`). | A height a *smart scale emits* is an observation in `fact_measurement`. | One is the operator's account of themselves; the other is an instrument reading. Both may exist; a function that needs "height" must say **which**. |
| **Calories** | A meal's energy is a nutrition fact (`energy_kcal`) on an intake event. | A wearable's daily `total_kcal` is an observation (energy expenditure the device reported). | One is a quantity attributed to something consumed; the other is a body-state reading. They never merge into one number. |
| **Supplements** | A supplement dose (amount + unit taken) is supplement intake. | A blood/urine marker that reflects the body's state is an observation. | A dose is what the operator took; a marker is a reading about the body. The dose is preserved even when ingredients are unknown. |
| **Age vs birth date** | Birth date is a permanent profile attribute. | — | Age is **derived** at evaluation time from birth date; it is never stored or asserted on its own, so the two cannot drift apart. |

**Anti-pattern — do not smuggle profile/intake into existing paths.** Profile
and intake semantics must **not** be written into `fact_measurement`,
`fact_interval`, or generic note storage merely because those paths already
exist and would technically accept a row. A declared height is not a measurement;
a meal's calories are not a body observation; a structured supplement dose is not
a free-text note. Reusing an observation path for a declaration (or a note for
structured intake) collapses two distinct meanings and is exactly the back-door
the contract forbids. If something seems to need two homes, that is a sign two
meanings are being conflated — keep them apart.

## Boundary contracts

- **Default agent surface (`premura-mcp`):** MCP reaches `fact_measurement` only through a signal-processing function that has already applied validity + imputation policy.  The default surface exposes `list_metrics`, `metric_summary`, the six signal-backed tools, the two agent-mediated profile-capture tools (`profile_context_supported_fields`, `profile_context_record`), the five analytical tools (`change_point`, `smoothed_average`, `correlate`, `rolling_mean`, `paired_t_test`), and the three session research trace tools (`research_trace_open`, `research_trace_mark_surfaced`, `research_trace_disclosure`).  All catalog/summary/signal helpers delegate entirely to the Stage 2 engine — no raw `hp.*` SQL from the agent surface — the profile-capture tools write only through the bounded `record_profile_context` store boundary, and the trace tools read/write only derived `trace.*` provenance rows (never `hp.*` health facts), never via raw SQL.  The `query_warehouse` escape hatch is **not present** on this surface.
- **Operator surface (`premura-mcp-operator`):** A separate, explicitly opt-in entrypoint adds `query_warehouse` on top of the full default tool set.  This surface is lower-guarantee: `query_warehouse` returns raw rows without any Stage 2 validity, freshness, or imputation guarantees, and callers must interpret results themselves.  The explicit-approval rule is enforced two ways: `query_warehouse` is simply absent from the default surface (an agent connected there cannot reach it), and the operator entrypoint refuses to start unless the launcher acknowledges lower-guarantee mode via `--ack` or `PREMURA_OPERATOR_ACK`.  The lower-guarantee disclosure to the end user remains a client/agent-layer responsibility.  See [ADR 0004](../adr/0004-stage3-operator-entrypoint.md).
- UI never reads `fact_measurement` directly — always through MCP tools (even when invoked locally without a remote LLM, the MCP boundary is the API).
- Ingest never calls signal processing. The warehouse must be reconstructible from raws alone.

Pillars and stages compose: a single feature can sit in (say) Pillar 1 (extensibility) + Stage 1 (ingest). Use both axes when describing scope.
