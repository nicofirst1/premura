# premura — Stages

> Status: authoritative. Source of truth for cross-stage architecture boundaries.
>
> Companion to [VISION.md](../product/VISION.md), [SPEC.md](../product/SPEC.md), [ROADMAP.md](../product/ROADMAP.md), [PROPOSAL_LABS.md](../research/PROPOSAL_LABS.md).
> Captured 2026-05-21. Complements VISION.md — does **not** replace the pillar framing. The pillars are the *trajectory*; the stages below are the *data-flow shape*. A feature is located in pillars by intent and in stages by where it sits in the pipeline.

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

Parsers turn a vendor artifact into rows in `hp.fact_measurement` / `hp.fact_interval` per the long-format star schema documented in [ARCHITECTURE_HISTORY.md](ARCHITECTURE_HISTORY.md).

- Today: HC `.db`, Garmin GDPR `.zip`, Sleep as Android CSV, BMT CSV.
- Coming: blood / urine / stool lab PDFs (see [PROPOSAL_LABS.md](../research/PROPOSAL_LABS.md)), continuous glucose, additional wearables.
- No derivation, no imputation, no analysis. Ingest stores **what was observed, in canonical units, with provenance**.
- Idempotent (sha256 + `dedupe_key UNIQUE`), append-only.

### 2. Signal processing

Deterministic Python functions that turn raw rows into *answerable* signals. This is the stage the user named when describing "compound and creating new signals" and "two blood samples separated by 10 years probably can't be used."

Four families of function:

- **Time-validity** — per-metric freshness window declared in `dim_metric` (new column). HRV stales in hours; weight in weeks; blood lipids in months; DXA scan effectively forever. The processor refuses to treat values past their window as "current" without an explicit override.
- **Missing-data policy** — per-metric: `none` (never impute; lab markers, exercise sessions), `last_observation_carried_forward` (weight, height, within window), `linear_interp` (dense continuous, short gaps), `seasonal_naive` (cyclic, opt-in). Returns the series **and** a parallel `is_imputed` mask.
- **Derived signals** — compound metrics computed from raw inputs and persisted with `metric_id` prefix `derived:` (e.g. `derived:hrv_7d_mean`, `derived:ldl_hdl_ratio`, `derived:ast_alt_ratio`). Recomputed on ingest of any input.
- **Signal selector** — given a question or interest, ranks signals that can answer it given *this* warehouse's actual contents and current validity.

Signal processing has no external dependencies. No network, no LLM. It must be inspectable and reproducible from the warehouse alone.

### 3. MCP

The MCP server exposes signal-processing functions as tools an LLM can call: `correlate`, `paired_t_test`, `rolling_mean`, `change_point`, plus PubMed search/fetch and the signal selector.

- The LLM never returns effect sizes from its priors — it calls a tool, receives `{effect, n, p, ci, is_imputed_pct, validity_status}`, and narrates.
- Every PubMed citation must round-trip through `pubmed_fetch(pmid=…)`.
- MCP is the only stage that talks to a model and the only stage that may make a network call. Network calls are user-initiated, never background.

### 4. User interface

Everything the human encounters: CLI today, MCP-backed chat, eventual UI.

- **Interview** (VISION Pillar 4) — first contact asks the user *what direction* (sleep, cardio, metabolic, stress, mental, gut, lab/cardiometabolic, overview). Output is a routing decision that calls the signal selector. No "analyse everything at once" by default.
- **Teaching** (VISION Pillar 5) — plain-language metric introductions, dual-coded charts, progressive disclosure. Applies to every metric the UI surfaces, blood markers especially.
- The UI is the only stage that does presentation, unit display preferences, and prose.

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

## Boundary contracts

- MCP never reads `fact_measurement` directly — always through a signal-processing function that has already applied validity + imputation policy.
- UI never reads `fact_measurement` directly — always through MCP tools (even when invoked locally without a remote LLM, the MCP boundary is the API).
- Ingest never calls signal processing. The warehouse must be reconstructible from raws alone.

Pillars and stages compose: a single feature can sit in (say) Pillar 1 (extensibility) + Stage 1 (ingest). Use both axes when describing scope.
