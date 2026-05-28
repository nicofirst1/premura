# Findings — Grounding And Extending Premura's Stage 2 Engine

> Mission: `grounded-extensible-engine-research-01KSD0D1` · final deliverable (WP06)
> This is the single decision-ready package. It integrates the five research artifacts (`research/01`–`research/05`, all approved) into one argument a maintainer can read once and act on. The detailed artifacts remain available for evidence; this document is the answer.
>
> **Vocabulary, in plain English (used throughout):**
> - **Stage 2 engine** — Premura's deterministic, offline signal-processing layer that turns raw warehouse rows into question-ready *signals*. No network, no AI model.
> - **Signal** — a validity-checked, question-ready value or series, shaped to answer something (not raw data).
> - **Derived signal** — a signal computed from one or more metrics and saved back into the warehouse under a `derived:` name (the three shipped lab ratios are the examples).
> - **Engine function** — one registered Stage 2 signal function (one `SignalSpec` registration plus its code body).
> - **Health direction** — the user-facing area a person enters through (sleep, cardio, etc.), a routing choice, kept distinct from a signal's internal `domain` tag.
> - **Contribution contract** — the package a contributor must hand in to add a new engine function: its rationale, inputs, outputs, caveats, tests, and review notes.

---

## 1. Executive summary (read this first)

Plain-English summary of what Stage 2 should try to do, what it should avoid, and why (at most 10 bullets, per NFR-006):

1. **Why this mission exists:** Stage 2 is currently thin — it ships only three lab ratios — so Stage 3 (the AI-facing layer) reaches *past* it and reads the warehouse directly. That direct-read is documented, temporary debt. The fix is to make Stage 2 thicker with grounded, common-data functions so Stage 3 has something safe to call.
2. **The two halves are coupled, not separate:** "scientifically grounded" and "contributor-extensible" must move together. A function only belongs in Premura if it is both evidence-backed *and* arrives through a clear, reviewable seam.
3. **There is now a shared map** (Section 3): five first-wave **health directions** (sleep, cardiovascular, metabolic, stress, overview), five recurring **question shapes** (current status, trend, own-baseline, change-after-event, compound), and six **engine function families** that answer them — all kept strictly inside Stage 2's deterministic boundary.
4. **There is now an admission rule** (Section 4): a grounding rubric with ACCEPT / DEFER / REJECT verdicts, a compact contributor submission package (7 items), and a **reviewer gate of exactly 10 pass/fail checks** — small enough for routine use.
5. **The existing code seam mostly survives** (Section 5): the registry, decorator, discovery, validity-gated availability, revision metadata, and persistence mechanics are all **keep**. Two things must **change** — the contributor surface must grow beyond a bare registration record, and the engine must learn to *declare* a need for stable profile context (height/sex/age).
6. **One dependency is parked, not solved** (Section 6): some obvious functions (BMI, age-adjusted norms) need stable personal context — height, sex, birth date — that the timestamped measurement model cannot hold cleanly. This is tracked as **GitHub issue #6** and is deliberately kept out of the first wave.
7. **There is a decision-ready shortlist** (Section 7): six quick-win functions, ranked, each pre-graded ACCEPT. Five of six run purely on commonly-available wearable/phone data (resting heart rate, steps, weight, sleep). None needs the network, none shares data, none is blocked on issue #6.
8. **Confidence is stated honestly:** four candidates are **strong**, one **moderate**, one **exploratory** — Premura should not pretend every idea is equally solid.
9. **There is a next-mission order** (Section 8): build the four easiest descriptive functions first (Mission A), the two caveat-heavier ones second (Mission B), keep the signal selector as a research question, keep Stage 3 statistics tooling separate, and keep profile-dependent functions deferred to issue #6.
10. **There is a doc-alignment list** (Section 9): after acceptance, update `STAGES.md`, `STATUS.md`, `ROADMAP.md`, `FULL_APP_DEVELOPMENT_PLAN.md`, `VISION.md`, route an engine-side contributor pointer alongside the parser contract, and comment the deferred set on issue #6.

**The one-sentence answer to the mission question:** Stage 2 should grow first through grounded, descriptive, common-data engine functions admitted by a 10-check gate, reusing nearly all of the existing seam, while the profile-data gap stays explicitly parked in issue #6.

---

## Section order and what each covers

This document is ordered so a reader can follow one argument from baseline to action, and so the mission's functional requirements are visibly covered in sequence:

1. Executive summary
2. *(this map)*
3. **Where Stage 2 stands today** — baseline: committed intent, known debt, open questions (FR-001)
4. **A shared map for Stage 2** — directions, question shapes, function families (FR-002)
5. **The admission rule** — grounding rubric, contributor contract, reviewer gate (FR-003, FR-004, FR-005); plus the seam disposition (FR-006)
6. **The parked dependency** — baseline profile data and issue #6 (FR-007)
7. **The quick-win shortlist** (FR-008)
8. **What to build next** — follow-on mission sequence (FR-009)
9. **Docs to realign after acceptance** (FR-010)
10. **Requirement traceability table** (FR / NFR / SC coverage)

---

## 3. Where Stage 2 stands today (FR-001)

Premura has already committed to Stage 2 as the place where raw warehouse rows become answerable signals, but only a thin slice is built. This baseline separates what is **settled**, what is **accepted debt**, and what is **still open** — so the rest of this document does not re-litigate the settled parts.

### Settled (build on these without re-arguing)

- **Stage 2 is the deterministic signal layer:** it has no network and no AI model, and it must be reproducible from the warehouse alone (`docs/architecture/STAGES.md` §2).
- **Stage boundaries are fixed and ordered:** Ingest → Stage 2 signal processing → Stage 3 MCP (the only AI-facing and only network-touching stage) → Stage 4 user interface (presentation/teaching) (`docs/architecture/STAGES.md` "The four stages").
- **Stage 2 owns four responsibilities:** time-validity (per-metric freshness windows), missing-data policy (imputation rules plus an `is_imputed` mask), derived signals (compound metrics saved under a `derived:` prefix), and a signal selector (ranking which signals can answer a question) (`docs/architecture/STAGES.md` §2).
- **The seam is shipped as an open boundary:** registration is via the `SignalSpec` frozen record and the `@signal(...)` decorator into a module-level `REGISTRY`; importing `premura.engine` loads no signal implementation, so the boundary could even be reimplemented by a proprietary package without breaking callers (`src/premura/engine/_registry.py`; `src/premura/engine/__init__.py`).
- **The public API is concrete and tested** (82/82 tests green per `docs/operations/STATUS.md`): `compute`, `list_by_domain`, `list_auto_safe`, `check_inputs_available`, `list_unavailable`, plus `derived:` persistence (`src/premura/engine/__init__.py`).
- **Input availability is validity-gated, not just presence-gated:** `check_inputs_available` reads each metric's `validity_window` from `dim_metric.yaml` and treats stale-past-window data as unavailable (`src/premura/engine/__init__.py`; `src/premura/dim_metric.yaml`).
- **Local-first privacy is non-negotiable** at every stage: cleartext never leaves the machine, no telemetry, network only on explicit user action at Stage 3 (`docs/history/product/VISION.md` Pillar 6; `docs/architecture/STAGES.md` §3).

### Accepted debt (documented, temporary, expected to close)

- **The headline debt — Stage 3 reads the warehouse directly.** The shipped MCP tools (`query_warehouse`, `list_metrics`, `metric_summary`) read the fact tables directly, breaching the "MCP never reads `fact_measurement` directly" rule. This is a deliberate transitional slice, accepted *while Stage 2 is still thin*. The tools warn that their output bypasses validity and imputation policy. The exception closes when AI-facing analysis routes through validity-gated, engine-backed signal functions (`docs/architecture/STAGES.md` "Known exception"; `docs/adr/0002-mcp-local-warehouse-boundary.md`). **This is the central reason the mission exists, and the gap every quick win helps close.**
- **The signal selector is named but not shipped** — only `list_by_domain` / `list_unavailable` discovery exists, no ranking (`docs/architecture/STAGES.md` §2).
- **Derived-signal invalidation is metadata-only** — `revision` is stamped into rows but there is no `revalidate` command yet (`docs/architecture/UPDATE_STRATEGY.md` §(d)).
- **`auto_safe` is metadata only** — the auto-precompute flow it describes is not wired up (`src/premura/engine/__init__.py`).
- **Imputation is declared, not executed** — `dim_metric.yaml` carries per-metric policies and `STAGES.md` describes the `is_imputed` mask, but no shipped engine path applies imputation yet.
- **Only one signal family ships** — the three lab ratios; everything else is boundary-and-metadata (`src/premura/engine/lab_ratios.py`).

### Open questions (this mission's charter — now answered or scoped below)

The baseline left seven questions open. This document closes or scopes each: the contribution contract and grounding rules and reviewer gate (Section 5), the seam disposition (Section 5), the profile-data dependency (Section 6), the taxonomy (Section 4), the quick-win shortlist (Section 7), and — explicitly *not solved here, by design* — whether the engine becomes a third-party plugin system (out of scope; see Section 5).

*(Baseline detail: `research/01-repo-baseline.md`.)*

---

## 4. A shared map for Stage 2 (FR-002)

The mission needs one map with three separate layers so product, engine, and UI conversations stop blurring together. The map is a **first-wave practical guide, not a medical ontology**, and it protects the stage boundaries: deterministic engine logic only in Stage 2; statistics tooling and AI-facing wrappers in Stage 3; teaching and presentation in Stage 4.

### Layer 1 — First-wave health directions

A direction is in the first wave only if **the warehouse already carries enough data to answer real questions about it today**.

| Direction | Why first-wave | Backing data already present |
|---|---|---|
| **Sleep & recovery** | Densest daily data; the canonical "did something change" case | `sleep_rating`, `sleep_deep_pct`, sleep intervals, `hrv_rmssd_overnight`, `resp_rate` |
| **Cardiovascular fitness & training load** | Strong multi-source coverage, clear trend/comparison questions | `vo2_max`, `training_load`, `resting_hr`, `heart_rate`, `intensity_minutes`, `steps` |
| **Metabolic health & body composition** | Slow-moving signals where freshness and trend matter most | `weight`, `body_fat_pct`, `bmi`, `height`, plus shipped lab ratios |
| **Stress & autonomic balance** | High-cadence wearable data; pairs with sleep/recovery | `stress`, `body_battery`, `hrv_rmssd_overnight`, `resp_rate`, `skin_temperature` |
| **General overview** | The default "I don't know where to start" entry | Composed from the four above via the signal selector |

**Deferred directions (named, not chosen):** *Mental/cognitive* (no committed metrics yet), *Gut* (stool reports land as qualitative notes, not numeric signals yet), and *standalone lab depth* (needs profile context — sex, age — that is the issue #6 dependency; surface lab ratios *inside* the metabolic direction for now).

### Layer 2 — Recurring question shapes

The shapes of question Stage 2 helps answer first. Each is direction-agnostic — "trend over time" is the same shape whether the input is weight or HRV.

| # | Question shape | Plain-English form |
|---|---|---|
| Q1 | **Current status** | "What is my X right now, and is that value still trustworthy?" |
| Q2 | **Trend over time** | "Is my X going up, down, or flat over recent weeks/months?" |
| Q3 | **Comparison to a baseline** | "How does my X now compare to my *own* normal?" |
| Q4 | **Change after an event** | "Did my X shift after I started/stopped doing something?" |
| Q5 | **Compound interpretation** | "What do these signals say *together* about this direction?" |

Two boundary reminders baked into the shapes: Q3 means the user's **own** rolling baseline (population/reference comparison and significance are Stage 3), and Q5 produces a derived *number* in Stage 2 while the *interpretation* ("you're under-recovered") is Stage 4 teaching.

### Layer 3 — Engine function families

Each question shape maps to a family of engine functions. Each family is deterministic, network-free, AI-free, and reproducible from the warehouse alone.

| Question shape | Function family | What the engine produces (deterministic) | Confidence |
|---|---|---|:--:|
| Q1 Current status | **Freshness-aware status** | Latest in-window value plus a validity verdict (current / stale-past-window) | strong |
| Q2 Trend over time | **Trend / summary** | A windowed series plus a plain direction descriptor, with an `is_imputed` mask | strong |
| Q3 Own-baseline | **Self-baseline summary** | The user's own rolling baseline and where the current value sits relative to it | strong |
| Q4 Change after event | **Change detection** | A before/after split around a user-supplied date and the shift — numbers only, no causation | moderate |
| Q5 Compound | **Derived signals / ratios** | A new signal computed from ≥1 inputs, saved under `derived:` with `revision` stamped | moderate |
| (cross-cutting) | **Signal selector** | Ranks which of the above *this* warehouse can answer — named but unshipped today | exploratory |

### The load-bearing boundary — what stays OUT of Stage 2

This is the part that protects trust. Each family has a near neighbour that must **not** migrate into Stage 2:

- **Statistics (Pearson/Spearman correlation, t-tests, regression, change-*point* tests, anything returning a p-value, confidence interval, or significance verdict) → Stage 3.** Stage 2's "change detection" is a plain before/after delta, never a significance test.
- **PubMed lookups, citations, population/reference ranges → Stage 3** (network + external evidence).
- **Anything an AI model calls → Stage 3** (the only AI-facing stage).
- **Plain-language metric intros, prose interpretation, charts, progressive disclosure → Stage 4** (teaching/presentation). A freshness verdict is Stage 2; the *sentence explaining what "stale" means* is Stage 4.

A proposal that returns a p-value or teaches a concept is in the wrong stage *before* its grounding is even assessed.

*(Taxonomy detail: `research/02-stage2-taxonomy.md`.)*

---

## 5. The admission rule: grounding, contract, gate, and seam disposition (FR-003, FR-004, FR-005, FR-006)

This is the mission's safety promise turned into a usable decision rule. It gives a contributor three things: how a function is judged for grounding, the exact package they must hand in, and a short reviewer gate that decides whether it lands. It borrows the *discipline* of the existing parser contract (`src/premura/parsers/CONTRACT.md`) — one source-of-truth file, a short objective checklist, same-PR vocabulary additions, a real test, honest caveat notes — but adds two demands parsers never face: **prove the function is scientifically grounded**, and **prove it stays inside Stage 2**.

### 5.1 Grounding rubric (FR-003)

Run the Section 4 boundary pre-filter first; if a proposal is out of stage, it is REJECT before evidence is even considered. A function is "scientifically grounded" when **the relationship it computes is recognised in mainstream clinical or sports-physiology practice, and the computation is faithful to that recognised definition.** The evidence bar scales with the claim:

- **Descriptive functions** (current value + freshness, own-baseline mean, trend direction, before/after delta) assert nothing about the body beyond "here is your own number over time." The bar is **honest computation** — correct window, validity-gated, imputation disclosed. No external citation needed.
- **Interpretive / compound functions** (a derived ratio or multi-signal composite) carry a **higher bar**: a real, recognised definition of the composite (e.g. NCEP ATP III lipid guidance for lipid ratios; the De Ritis AST/ALT ratio; Task Force 1996 HRV interpretation — cited honestly, never fabricated), with the *interpretation* kept in Stage 4.

A grounded function must also be honest about limits: stale-input behaviour (never present stale as current without explicit override), missing-data handling (`is_imputed` mask + named policy, or an explicit decline), population scope (who the definition applies to), and an explicit statement of what it does **not** claim (no significance, no causation).

**Verdicts:**
- **ACCEPT** — in-stage; maps to exactly one family; evidence meets its bar; caveats addressed; inputs are real canonical metrics realistically present for the targeted direction.
- **DEFER** — plausible and in-stage, but evidence is only suggestive, or a required input/profile attribute is not reliably available, or caveat handling is fixably incomplete. DEFER means "good idea, not yet" — record what would move it to ACCEPT.
- **REJECT** — fails the boundary pre-filter, asserts a body claim with no basis (or a fabricated citation), misrepresents uncertainty, or duplicates an existing signal with no added value.

### 5.2 Contributor submission package (FR-004)

The minimum a contributor or coding agent hands in. Compact and concrete — one short block per item in the PR description, plus the code and test. The reviewer gate reads directly off this package, so a complete package leaves nothing to debate.

1. **Intended user question** — the plain-English question, plus which direction + question shape it serves (e.g. "Sleep & recovery / Q2 trend").
2. **Required inputs** — the canonical `metric_id`(s); flag any input that needs profile context (sex/age/height) as a dependency on issue #6.
3. **Output shape** — what it returns; if it persists, the `derived:` metric id, unit, and row shape; state `priority` and `auto_safe` with one line each.
4. **Function family + rationale** — which one family, and why this belongs in Stage 2 (not Stage 3 stats or Stage 4 teaching).
5. **Evidence basis** — descriptive (state so) or interpretive (the real recognised reference). No fabricated citations.
6. **Caveats / uncertainty handling** — behaviour on stale inputs, on missing data, population scope, and an explicit list of what it does NOT claim.
7. **Notes for review** — the same-PR `dim_metric.yaml` diff (if a new metric), the fixture test name, the `revision` value, and any field deliberately skipped.

### 5.3 Reviewer gate — exactly 10 pass/fail checks (FR-005, NFR-003)

Run top to bottom; any FAIL stops the function from landing. Checks 1–2 are the fast boundary/grounding pre-filter, 3–7 substance, 8–10 review readiness. **Total: 10 checks (≤10 per NFR-003 / SC-004).**

1. **In-stage** — deterministic, network-free, AI-free; returns no p-value / CI / significance verdict, does no reference lookup, is not Stage 4 teaching.
2. **Family-mapped** — maps to exactly one function family.
3. **Grounded** — verdict is ACCEPT under the rubric (descriptive computed honestly, or interpretive with a real recognised reference).
4. **Inputs real & present** — every input metric exists (or is added same-PR) and is realistically present for the direction; profile dependencies are named, not invented.
5. **Honest about uncertainty** — stale behaviour stated, missing-data handled or declined, population scope stated, non-claims listed.
6. **Output & namespace correct** — if it persists, `output` starts with `derived:`, the matching `dim_metric.yaml` row is in the same PR, unit/shape specified, `priority`/`auto_safe` justified.
7. **Deterministic test ships** — at least one fixture-driven test fixes inputs and asserts exact output.
8. **Local-first respected** — no new telemetry, no cleartext leaving the machine, no network call anywhere in the path.
9. **Submission package complete** — all seven items above present.
10. **No silent collision / drift** — `name` does not collide with an existing registration; `revision` is set (and bumped if logic changed); any skipped field has a one-line note.

### 5.4 Worked examples (proof the rule is usable, FR-003 requires ≥3)

- **ACCEPT — `resting_hr_7day_trend`:** "Is my resting HR trending up/down/flat this week?" Cardiovascular, Q2 trend. Descriptive → evidence bar is faithful computation, met. Declines on stale input, marks gaps via `is_imputed`, claims no significance/causation. All 10 checks PASS. → **ACCEPT.**
- **DEFER — `metabolic_syndrome_composite`:** Metabolic, Q5 compound. The relationship is recognised, but `waist_circumference` is not reliably in the warehouse and the cut-points need **sex and age** (an open profile dependency, issue #6). Gate check 4 FAILs. → **DEFER**; to reach ACCEPT, land issue #6 and reliable input ingest, then resubmit.
- **REJECT — `sleep_stress_correlation`:** returns a Pearson `r` with a p-value and a significance verdict — a statistical claim, which is the Stage 3 `correlate` tool. Gate check 1 FAILs immediately. → **REJECT**; the Stage-2-legal sibling is a Q4 change-detection function returning a plain delta.

### 5.5 The existing code seam: keep / change / defer (FR-006)

The Stage 2 seam already exists in code. Each element gets exactly one disposition at the contract level (keep = the contribution model inherits it unchanged; change = the contract must revise what it promises; defer = leave it to a later mission because it depends on work this mission does not own).

| Seam element | Disposition | One-line rationale |
|---|---|---|
| `SignalSpec` core fields (`name`, `domain`, `inputs`, `output`, `fn`) | **Keep** | Already carry exactly what a registration needs: identity, discovery tags, input/output ids, and the body. |
| `SignalSpec.priority` | **Keep** | A stable three-level knob that only drives missing-input surfacing. |
| `SignalSpec.auto_safe` | **Keep** | Harmless metadata a future auto-precompute can consume; conservative `False` default. |
| `SignalSpec.revision` | **Keep** | The only staleness anchor for `derived:` rows; the missing piece is a *command*, not the field. |
| `SignalSpec` as the **whole** contributor surface | **Change** | A registration record has no slot for rationale, evidence, caveats, tests, or review notes — the contract (5.2) must wrap/extend it. |
| `REGISTRY` + `@signal(...)` + lazy load | **Keep** | A module dict populated by a decorator, collisions caught at review, already supports the open-boundary goal. |
| `compute(spec_name, conn)` entrypoint | **Change** | A signal's only input being a DuckDB `conn` cannot express functions that also need profile context — the entrypoint must gain a declared way to receive it. |
| `list_by_domain` (+ `list_auto_safe`) | **Keep** | Pure tag-based discovery, correctly separate from availability; nothing blocks the contribution model. |
| `check_inputs_available` / `list_unavailable` | **Change** | Availability assumes every input is a timestamped metric with a `validity_window`; it must also express a *profile precondition* ("needs the operator's height"). |
| `derived:` persistence (same-source/same-timestamp join, `dedupe_key`) | **Defer** | Mechanics are sound for measurement-derived signals, but how a *profile-dependent* output gets a `ts_utc`/`source_id` depends on issue #6. |

**Summary:** the *mechanism* of the seam is largely **keep**. The two **change** items are both about *what a function may depend on* — the contributor surface must grow beyond a bare registration record, and `compute` + availability must learn to express a baseline-profile precondition. The one **defer** is persistence of profile-dependent outputs, which is downstream of issue #6.

Out of scope (named so it is not mistaken for a gap): whether engine functions become a *third-party plugin/skill system* like parsers is **explicitly undecided and not decided here**. This is a contribution contract, not a plugin-loader spec.

*(Grounding/contract/gate detail: `research/03-grounding-and-contribution-gate.md`. Seam audit detail: `research/04-engine-seam-and-profile-dependency.md` §1–§2.)*

---

## 6. The parked dependency: baseline profile data and issue #6 (FR-007)

Some obviously-useful functions need **stable or slowly-changing personal context** — not events at a timestamp:

- **Sex / biological sex** — fixed; needed for sex-specific lab ranges, body-composition norms, HR/HRV context.
- **Birth date → age** — birth date fixed, age derived and continuously changing; needed for age-adjusted interpretation.
- **Height** — effectively fixed; needed by ratio functions (BMI = weight / height², the example issue #6 itself names).

**Why these break the measurement model.** Premura stores *what was observed, at a timestamp, in canonical units, with provenance*. Profile attributes break that in concrete ways: (1) they are context, not observations — forcing a `ts_utc`/`source_id` onto sex corrupts those columns; (2) the validity model is built for freshness, so a `validity_window` on a birth date is a category error; (3) the engine's only demonstrated way to combine inputs is the lab-ratio join on identical `source_id` **and** `ts_utc`, and a timeless attribute has neither key; (4) in practice, `height`/`bmi` exist only because a smart scale happens to emit them, with no fallback when none did — and **sex** and **birth date / age** simply do **not exist** as metrics in `dim_metric.yaml` today.

**This is exactly why the `compute` entrypoint and the availability contract are marked "change" in Section 5.5:** a function must be able to *declare* it needs height/sex/age as a precondition, rather than silently assuming a measurement row exists.

**This is not for this mission to solve.** It is tracked as **GitHub issue [#6 — "Model baseline personal profile attributes for engine functions"](https://github.com/nicofirst1/premura/issues/6)**, which leaves open: scope (which attributes), where they live, stable-vs-time-varying representation, provenance/recompute, and privacy/UX. Until #6 decides, **how profile data is stored and updated is genuinely undecided.**

**Guidance for any future implementation until #6 resolves:** treat profile data as an explicit precondition (fail loudly, surface a "we need your height/sex/birth date" prompt the way `list_unavailable` surfaces a missing lab); never back-door profile data into `fact_measurement`; leave a named slot in the contract for "this function depends on baseline profile attribute X"; and carry the dependency as a first-class, issue-#6-blocking risk, not an aside.

*(Profile-dependency detail: `research/04-engine-seam-and-profile-dependency.md` §3–§4.)*

---

## 7. The quick-win shortlist (FR-008, NFR-002, NFR-004, NFR-005)

Candidates were generated against one filter — **does the warehouse already carry the input today, and does the function belong in exactly one Stage 2 family?** — then scored transparently on six 1–5 criteria (user value, input availability, scientific clarity, caveat burden, Stage 2 fit, profile independence; unweighted sum out of 30, recomputable by any reader). The two profile-blocked ideas (BMI, age-adjusted RHR) were scored and deliberately kept *out* of the shortlist; they are parked in Section 8.

**Six** candidates make the shortlist (within the required 3–7). Each is pre-graded ACCEPT through the rubric and the 10-check gate. Every candidate carries one confidence tag. **Five of the six run purely on commonly-available non-lab wearable/phone data (SC-002, ≥2 required).** None requires the network, silent sharing, or any boundary bypass (NFR-005); none is blocked on issue #6.

| Rank | Function | Question answered | Direction / shape / family | Required inputs | Confidence | Profile dep. |
|---|---|---|---|---|:--:|:--:|
| #1 | `resting_hr_status` | "What is my resting HR right now, and can I trust it?" | Cardiovascular / Q1 / Freshness-aware status | `resting_hr` (HC + Garmin; `P1D`, LOCF) | **strong** | None |
| #2 | `resting_hr_trend` | "Is my resting HR trending up/down/flat over recent weeks?" | Cardiovascular / Q2 / Trend | `resting_hr` | **strong** | None |
| #3 | `steps_trend` | "Are my daily steps trending up or down this month?" | Cardiovascular / Q2 / Trend | `steps` (`fact_interval`; `P1D`, no imputation) | **strong** | None |
| #4 | `weight_trend` | "Is my weight rising/falling/flat over the last month?" | Metabolic / Q2 / Trend | `weight` (HC + BMT; `P1W`, LOCF) | **strong** | None |
| #5 | `sleep_deep_pct_baseline` | "Was last night's deep-sleep % below my own recent normal?" | Sleep & recovery / Q3 / Self-baseline | `sleep_deep_pct` (+`sleep_rating`) | **moderate** | None |
| #6 | `hrv_change_around_date` | "Did my overnight HRV shift after a date I name (e.g. cut alcohol)?" | Sleep & recovery / Q4 / Change detection | `hrv_rmssd_overnight` (Garmin) + a user-supplied date | **exploratory** | None |

**Per-candidate value and caveats** (SC-003 — each has inputs, value, confidence, caveats, and profile dependency):

- **#1 `resting_hr_status` (strong).** The most common health question on the densest universal metric; the cleanest demonstration of Stage 2's purpose — it answers *with a freshness verdict* instead of a raw read, directly closing the direct-read debt. Caveats: pure descriptive value; must return current-vs-stale verdict and never present stale as current without explicit override; no significance/causation.
- **#2 `resting_hr_trend` (strong).** The trend twin of #1 (the worked-example ACCEPT). Caveats: windowed series + plain rising/falling/flat descriptor with `is_imputed` mask where LOCF filled gaps; declines/marks across long gaps; no significance claim.
- **#3 `steps_trend` (strong).** Steps are the most universally collected signal (every phone counts them). Caveats: because `missing_data_policy` is `none`, it must **decline to impute** missing days and report them as gaps; no significance claim.
- **#4 `weight_trend` (strong).** Weight is common and slow-moving; exactly where freshness windows and LOCF earn their keep (weigh-ins are irregular, `P1W`). Caveats: disclose LOCF via `is_imputed`; do not present a >1-week-old value as current weight without flagging staleness. (This is *raw weight* trend, **not** BMI — BMI is the profile-blocked candidate, kept separate.)
- **#5 `sleep_deep_pct_baseline` (moderate).** The canonical "was last night worse than my normal" question; the user's *own* rolling baseline keeps it inside Stage 2 (no population reference). Moderate because `sleep_deep_pct` is a vendor-summarised percentage (device staging accuracy varies). Caveats: own-baseline only; must state it is a device estimate; honest about gaps; no causation.
- **#6 `hrv_change_around_date` (exploratory).** The Stage-2-legal sibling the rubric points to as the correct alternative to a rejected correlation idea: a plain before/after delta around a user-supplied date. Exploratory because overnight rMSSD is Garmin-only/vendor-proprietary and change-detection sits closest to the Stage 3 line. Caveats: returns `before_mean`, `after_mean`, and the delta with an `is_imputed` note **and nothing else**; must explicitly disclaim significance and causation (significance is a Stage 3 `paired_t_test`, not this function).

**Confidence spread:** 4 strong, 1 moderate, 1 exploratory — every candidate tagged (NFR-004).

*(Scoring detail: `research/05-quick-win-ranking-and-alignment.md` §1–§3.)*

---

## 8. What to build next (FR-009)

### Build now (implementation missions, in order)

1. **Mission A — Descriptive Stage 2 functions: status + trend on common wearable data.** Implements shortlist **#1–#4** (`resting_hr_status`, `resting_hr_trend`, `steps_trend`, `weight_trend`) as one first wave. They share one shape, need no new ontology rows and no profile data, and are pre-graded ACCEPT. Building them together exercises the contribution contract end-to-end on the easiest, highest-value functions and starts closing the direct-read debt by giving Stage 3 validity-gated functions to call. **Recommended next mission.**
2. **Mission B — Self-baseline + change-detection functions.** Implements shortlist **#5** (`sleep_deep_pct_baseline`) and **#6** (`hrv_change_around_date`). Sequenced second because both carry heavier caveats (vendor-estimate disclosure; Q4 boundary discipline) and are best built after Mission A has proven the pattern and the gate. **Recommended second mission.**

### Stays research (answer first)

3. **The signal selector** stays a research/design question, not yet an implementation mission. It ranks *which* signals can answer a question for *this* warehouse, and needs a population of real functions to rank — so scope it only after Mission A exists.
4. **Stage 3 statistics tooling** (correlation, paired tests, change-*point* statistics, reference ranges) stays out of this mission family entirely — this is a *correct boundary exclusion*, recorded so a future reader does not mistake it for a gap.

### Stays deferred (correct to wait)

5. **Profile-dependent functions** — BMI as a function and age-adjusted interpretation — stay **blocked on issue #6** until it lands a storage decision; they must not be back-doored into `fact_measurement`.
6. **Lab-depth functions beyond the shipped ratios** stay deferred until lab coverage is denser and the same profile context (sex/age) is available; surface the existing `derived:` lab ratios *inside* the metabolic direction rather than building a lab-first mission now.

*(Sequence detail: `research/05-quick-win-ranking-and-alignment.md` §4.)*

---

## 9. Docs to realign after acceptance (FR-010)

Once the maintainer accepts this shortlist and sequence, update the docs **materially affected** by these decisions (docs that merely mention Stage 2 in passing are excluded):

| Doc | Why | What changes |
|---|---|---|
| `docs/architecture/STAGES.md` | Source of truth for the Stage 2 contract; currently lists responsibilities abstractly with the direct-read exception as headline debt. | Record that the first concrete non-lab functions are in scope, note that each one narrows the direct-read exception, and point to the Section 5 gate as the admission rule. |
| `docs/operations/STATUS.md` | Live "what is shipped" snapshot; currently lists only the three lab ratios. | *After Mission A/B land*, add the new descriptive functions to "What's working end-to-end" and the engine row. |
| `docs/product/ROADMAP.md` | "Concrete build order" positions engine functions as a vague future item. | Replace with the Section 8 sequence: descriptive first, self-baseline/change-detection second, selector as research, Stage 3 stats kept separate. |
| `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` | Named source of truth for phase planning; lists deeper Stage 2 as still-missing v2 payoff. | Convert "deeper Stage 2 is missing" into the Section 8 phased plan, with the issue #6 profile dependency named as a blocker on BMI/age-adjusted work. |
| `docs/history/product/VISION.md` | Pillars 4–5 (teaching, Jobs-to-be-Done) motivate the question shapes; Pillar 6 (privacy) is the constraint every candidate respects. Aspirational, so a light change. | Cross-reference that the first-wave directions/shapes and quick wins are the concrete expression of Pillars 4–5, with no change to privacy posture. |
| `src/premura/parsers/CONTRACT.md` (contributor guidance) | No engine-side contributor contract existed; Section 5 produced one. | Add a sibling pointer routing an engine-function contributor to the Section 5 grounding rubric + reviewer gate (a short `src/premura/engine/CONTRACT.md` or a cross-link). |
| GitHub issue [#6](https://github.com/nicofirst1/premura/issues/6) | This mission confirms which quick wins are blocked on it (BMI, age-adjusted RHR) and which are not. | Comment with the Section 8 deferred list so the profile-data work has a clear, prioritised set of functions waiting on its decision. |

Explicitly unchanged: `docs/architecture/UPDATE_STRATEGY.md` and the `revision`/revalidation story — none of the six shortlisted functions persists new `derived:` rows (the lab-ratio reuse already exists), so no new invalidation work is introduced.

*(Doc-alignment detail: `research/05-quick-win-ranking-and-alignment.md` §5.)*

---

## 10. Requirement traceability (coverage check)

Every functional requirement maps to the section that satisfies it; the non-functional requirements and success criteria are confirmed below.

| Requirement | Satisfied by | How |
|---|---|---|
| **FR-001** Stage 2 intent: committed / debt / open | §3 | Separate "Settled", "Accepted debt", "Open questions" lists, each repo-cited. |
| **FR-002** Plain-English taxonomy | §4 | Layer 1 directions, Layer 2 question shapes, Layer 3 function families, each with examples. |
| **FR-003** Grounding acceptance standard | §5.1, §5.4 | ACCEPT/DEFER/REJECT rubric + three worked examples. |
| **FR-004** Contribution contract | §5.2 | 7-item contributor submission package. |
| **FR-005** Quality gates | §5.3 | Reviewer gate of 10 named pass/fail checks. |
| **FR-006** Seam keep/change/defer | §5.5 | One disposition per seam element, with rationale. |
| **FR-007** Baseline profile data + issue #6 | §6 | Dedicated section naming categories, why they break the model, and routing to issue #6. |
| **FR-008** Quick-win shortlist | §7 | 6 ranked candidates with inputs, value, confidence, caveats, profile dependency. |
| **FR-009** Next-mission sequence | §8 | Implement / research / deferred items naming Missions A and B. |
| **FR-010** Doc-alignment list | §9 | Named files + purpose of each update. |

**Non-functional requirements:**
- **NFR-001** (traceability) — every top-level claim cites a repo source, an upstream artifact, or issue #6.
- **NFR-002** (decision-ready shortlist) — exactly 6 ranked candidates, each with rationale and recommendation status (§7).
- **NFR-003** (compact gate) — the reviewer gate is exactly 10 checks (§5.3).
- **NFR-004** (confidence levels) — all 6 candidates and all 6 function families are tagged strong/moderate/exploratory or scoped (§4, §7).
- **NFR-005** (local-first compatible) — 0 candidates require network, silent sharing, or boundary bypass (§7).
- **NFR-006** (readable for a non-engineer) — executive summary is 10 bullets; contract terms glossed in plain English on first use (header + §1).

**Success criteria:**
- **SC-001** single coherent answer to both halves — yes (§1 one-sentence answer; whole document).
- **SC-002** 3–7 shortlist, ≥2 from common non-lab data — 6 candidates, 5 non-lab (§7).
- **SC-003** each quick win has inputs/value/confidence/caveats/profile need — yes (§7 per-candidate notes).
- **SC-004** gate executable in ≤10 checks — exactly 10 (§5.3).
- **SC-005** names seam keep/change/defer — yes (§5.5).
- **SC-006** names the follow-on for profile attributes, not buried — yes, issue #6 (§6).
- **SC-007** names docs needing alignment — yes (§9).
- **SC-008** no unresolved clarification markers — confirmed: this document contains no open placeholders.
