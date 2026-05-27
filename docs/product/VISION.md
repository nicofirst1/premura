# premura — Vision

> Status: proposal/archive. Long-term trajectory, not a build contract.
>
> Companion to [DOCTRINE.md](DOCTRINE.md), [SPEC.md](SPEC.md), [ARCHITECTURE_HISTORY.md](../architecture/ARCHITECTURE_HISTORY.md), [USERJOURNEY.md](USERJOURNEY.md), [STATUS.md](../operations/STATUS.md), [ROADMAP.md](ROADMAP.md), [STAGES.md](../architecture/STAGES.md), [PROPOSAL_LABS.md](../research/PROPOSAL_LABS.md).
>
> The **pillars below describe the trajectory**. For the orthogonal *data-flow shape* (Ingest → Signal processing → MCP → UI), see [STAGES.md](../architecture/STAGES.md). Pillars and stages compose: a feature is located in pillars by intent and in stages by where it sits in the pipeline.
>
> Captured 2026-05-20 as the project's scope expands from "personal pipeline for Nicolò" toward an agent-operable health reasoning system. See [DOCTRINE.md](DOCTRINE.md) for the product stance this trajectory now serves: agent-primary execution, human-primary purpose. The bare-bone v1 (the work tracked in [STATUS.md](../operations/STATUS.md)) is the foundation. Everything below is the trajectory we are deliberately *not* building yet.

## What this is becoming

Three sentences:

1. **A common warehouse** for health dumps from as many vendors as possible — not a Garmin tool, not a Health-Connect tool. The DuckDB long-format star schema already in v1 is built to accept arbitrary `(metric_id, ts_utc, value, source)` tuples; what's missing is the **community of parsers** to fill it.
2. **An agent-operable analytical surface** that reads the warehouse, spots patterns, proposes the next question, and does most of the operational work for the human — backed by deterministic statistical tools (so the LLM cannot confabulate effect sizes) and PubMed-backed evidence (so the LLM cannot invent citations).
3. **A human-helping tutor, not a dashboard.** Every metric introduced is *taught*. Every chart answers a question. The human finishes a session knowing *more* about their physiology than when they started — not just "what their HRV was last Tuesday."

## Pillars

### Pillar 1 — Extensible by users, not just maintainers

The hard truth: there are dozens of health vendors, and we are not going to write a parser for each of them ourselves. The system must let users add a parser the way a CMS lets users add a plugin.

The mechanism we're betting on: **Claude Code skills**. A skill can carry a parser implementation, a description of which file shape it handles, and the prompt scaffolding needed for an AI to *generate* a new parser from a sample dump.

Two skill types we'll need:

- **Parser skills** — one per vendor (Withings, Oura, Apple Health, Whoop, MyFitnessPal, Cronometer, Fitbit, Polar Flow, Suunto, …). Each emits `Measurement` / `Interval` records into our existing `parsers.base` contract. Users can install community ones or generate their own.
- **Setup skills** — for the operational layer: install `age` / `rclone` / `bw`, configure remote storage, bootstrap a Bitwarden secure note for the key, generate a launchd plist, set up notifications. Right now `ops/bootstrap.sh` is a single bash script; in the skill world, each setup step becomes a discoverable skill the user can invoke as needed.

**Open question to revisit when more requirements arrive:** what's the contract between a skill and the loader? Probably (a) skill exposes a `parse(path) -> ParseResult` callable matching `parsers.base.Parser`, (b) skill declares a filename / header / magic-byte signature so autodiscovery can route, (c) skill declares any `dim_metric` rows it adds.

### Pillar 2 — A common DB, regardless of source

The `hp.fact_measurement` + `hp.fact_interval` + `hp.dim_metric` + `hp.dim_source` schema (PLAN §"DuckDB schema — long-format star") already handles this. What it does *not* handle yet and will need:

- **A canonical-vocabulary expansion process.** When Oura emits "readiness_score", do we map to a new `metric_id="readiness"` or alias to Garmin's `training_readiness`? Needs a documented decision rubric, not ad-hoc choices.
- **Cross-source priority extended** as we add vendors. Currently 4 sources. With ~10, we need declarative rules in `dim_metric` (e.g. "for `weight`, prefer scales with sub-100g precision over phone-entered values").
- **Provenance preservation.** When two sources disagree, we should be able to ask the warehouse "show me the raw rows behind the daily average HRV on 2026-04-15." The `raw_payload` JSON already supports this; needs an indexed accessor.

### Pillar 3 — AI tools that don't lie

The MCP-server idea from [ROADMAP.md](ROADMAP.md) is the operational form. The principles:

- **Deterministic tools, narrating LLM.** The LLM calls `correlate(metric_a, metric_b, window_days)`, receives `{r, n, p, ci}`, and explains it. The LLM never produces effect sizes from training.
- **Pattern-spotting tools, not pattern-claiming LLM.** `changepoint_detect(metric_id, since)`, `seasonal_decompose(metric_id)`, `anomaly_score(metric_id, lookback)`. The output is structured; the LLM contextualizes.
- **PubMed citations must round-trip.** Every reference is fetched by PMID and echoed back. Hallucinated DOIs are rejected at the tool boundary.
- **Eventually: OpenRouter integration** so the user picks which model runs the analysis (cheap for routine, expensive for synthesis). Not v1.

### Pillar 4 — Interview, then teach

A first-time user shouldn't see "here are 43 metrics." They should be asked:

> Which direction of your health do you want to understand right now?
> - [ ] Sleep & recovery
> - [ ] Cardiovascular fitness & training load
> - [ ] Metabolic health & body composition
> - [ ] Stress & autonomic balance
> - [ ] Mental / cognitive
> - [ ] General overview

Each choice routes them into a curated **learning track** — a sequence of (a) a metric explained in plain language, (b) their own data charted, (c) a guided counterfactual ("what happens to your HRV trend if we exclude alcohol nights?"), (d) a PubMed-cited finding to compare against, (e) the next question.

This is the "interview" the user described. The default assumption is that an agent conducts most of this flow on the human's behalf, then presents and teaches. Implementation could be:

- CLI: `hpipe learn` walks the user through a track in the terminal with Rich prompts.
- MCP: the AI agent runs the interview conversationally.
- Future UI: a Streamlit / web front-end built from the same routing logic.

### Pillar 5 — Teach, don't just inform

This is the single hardest pillar. The reference framework is the audit research from a sibling project: `~/repos/personal/immokalkul/docs/audits/UI/research.md`. The same 8 frameworks apply almost verbatim here, because we have the same dual goal: **don't overwhelm + teach transparently.**

| Framework | What it gives premura |
|---|---|
| **Nielsen 10 Usability Heuristics** | Standard heuristic spine. H2 (Match real world) tells us to gloss "rMSSD" → "heart-rate variability". H6 (Recognition vs recall) tells us not to assume the user remembers what stress 0-100 means between screens. H8 (Minimalist) tells us the first screen shows one number, not forty. |
| **Cognitive Load Theory** (Sweller 1988) | Health data has **high intrinsic complexity** — we cannot dumb it down, only chunk it. Eliminate extraneous load (redundant labels, split-attention). Use worked examples (pre-loaded sample analyses) — the user's own data acts as the worked example once ingested. |
| **Progressive Disclosure** (Nielsen 1995) | Show one headline metric first; advanced metrics on demand. Max 2 disclosure levels. The interview flow (Pillar 4) is progressive disclosure formalized. |
| **"Don't Make Me Think"** (Krug 2014) | The 5-second test: on landing, can the user state (a) what this is, (b) the headline finding about their data, (c) what to explore next? Today they can't — they see SQL row counts. |
| **Explorable Explanations** (Bret Victor 2011, Nicky Case) | The warehouse *is* a simulation; we just don't expose it. Patterns we'll borrow: reactive documents (changing the date window updates everything immediately), parameterizable diagrams ("drag this to see what an HRV of 60 would look like in your distribution"), guided tours, question-prompt mode. |
| **Plain Language + Microcopy** | Every metric introduced with a plain-English one-liner. Every tooltip explains *why it matters*, not just *what it is*. No "rMSSD" without "(heart-rate variability — root mean square of beat-to-beat differences. Higher generally = better autonomic recovery)" on first appearance. |
| **Dual Coding Theory** (Paivio 1971) | Every chart has a caption that names the insight. Every number has a visual analog. We use **both** verbal and visual channels at every step. |
| **Jobs-to-be-Done** | The job is **"when I sense something about my body changed (worse sleep, lower mood, less endurance), I want to know what my data says is correlated, so I can decide whether to talk to a doctor / adjust training / wait."** Every surface either serves this job or is labeled as exploratory/advanced. |

The teaching layer is **not the final UI**. It is a content + interaction style that propagates from an agent-mediated MCP flow first, then through CLI and any web UI that comes later.

### Pillar 6 — Privacy is non-negotiable

Health is GDPR Article 9 special-category data. The v1 contract holds at every future stage:

- Cleartext never leaves the local machine without `age` encryption.
- The `age` private key has two storage paths: local file (default) or Bitwarden secure note. We do not build a key-escrow service. **The user owns recovery.**
- No telemetry, no analytics, no crash reporting in the pipeline. If we ever add a hosted component (we don't plan to), it gets a separate threat model and explicit consent.
- AI analysis runs locally or against a model the user chose (OpenRouter, Anthropic, etc.). The warehouse contents are sent only with explicit user invocation of an AI tool — never in the background.

## Deliberately deferred

- **GUI.** The user signalled "open to it eventually" — not blocking on it. Everything in the interview / teaching layer will land first in CLI + MCP, where it's reusable by whatever front-end comes later.
- **Drive auto-upload.** Now opt-in (see [STATUS.md](../operations/STATUS.md)). The encrypted artifact is returned to the user; they choose where it goes.
- **Hosted / multi-user.** Single-user, single-machine, by design. Could change *after* the extensibility + teaching layers are mature, never before.

## How this changes near-term work

It mostly doesn't. The barebone v1 [STATUS.md](../operations/STATUS.md) work — close the launchd loop, verify age round-trip, dust off the wiki page — is unchanged. The vision above sets the *shape* of v2; concrete v2 work items are captured in [ROADMAP.md](ROADMAP.md).

The first steps along Pillar 3 are now on the ground rather than only on paper: the warehouse can answer a small handful of grounded, freshness-aware questions about the user's own data (current and trending resting HR, steps and weight trends, deep sleep against one's own normal, an overnight-HRV before/after around a named date). They are deliberately descriptive and comparative — they describe and compare the user's own history, never diagnose, never claim significance or causation — and they live behind the same CLI/MCP boundary the rest of this trajectory will build on. The "AI tools that don't lie" promise here is modest by design: honest about freshness and gaps, and silent when the data can't support an answer. The statistical depth, literature grounding, and the teaching surface that turn these into a tutor are still ahead.

Profile- and intake-aware reasoning also has a clearer semantic path now: the meaning contract for baseline profile context, nutrition intake, and supplement intake is fixed (`docs/architecture/PROFILE_AND_INTAKE_CONTRACT.md`), so a future function knows where a declared height or a meal's energy lives and how to declare that it needs them. This is a settled boundary, **not** a shipped capability — there is still no intake capture, no profile-aware analysis, and no storage for these domains; that work stays deferred (issue `#6`).
