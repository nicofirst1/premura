# 02 — Stage 2 Taxonomy (directions, question shapes, function families)

> Mission: `grounded-extensible-engine-research-01KSD0D1` · WP02 · supports FR-002
> Purpose: give this mission one shared map with three layers — **health directions** (where a user enters), **question shapes** (what they keep asking), and **engine function families** (what Stage 2 builds to answer) — so WP03 (contract + grounding) and WP05 (quick-win ranking) can cite this instead of re-deriving it.

This builds directly on `research/01-repo-baseline.md` (WP01, approved). That document already normalized the vocabulary, separated direction from a signal's `domain` tag, and listed the four Stage 2 responsibilities. This document does **not** repeat that evidence; it cites it. It reuses WP01's wording exactly: **health direction**, **signal**, **derived signal**, **engine function**, **engine function family** (WP01 "Terminology notes").

Three rules govern the whole taxonomy:

1. It is a **first-wave practical map**, not a medical ontology. A maintainer should be able to read it in one sitting and use it to scope Stage 2 work.
2. It keeps the three layers separate. A direction is not a question; a question shape is not a function; a function family is not a tool menu.
3. It protects stage boundaries. Stage 2 is deterministic engine logic only. Statistics tooling and model-facing wrappers stay in Stage 3; teaching and presentation stay in Stage 4 (`docs/architecture/STAGES.md` "Boundary contracts"; WP01 Stable Commitments 1–2).

---

## Layer 1 — First-wave health directions (T005)

A **health direction** is the user-facing area a person enters through — a routing choice, not a metric and not a UI tab (WP01 "Terminology notes"; `CONTEXT.md`). The repo already names a candidate set in two places that mostly agree:

- VISION Pillar 4 interview list: *Sleep & recovery · Cardiovascular fitness & training load · Metabolic health & body composition · Stress & autonomic balance · Mental / cognitive · General overview* (`docs/history/product/VISION.md` Pillar 4).
- STAGES §4 interview list: *sleep, cardio, metabolic, stress, mental, gut, lab/cardiometabolic, overview* (`docs/architecture/STAGES.md` §4).

We do **not** adopt the whole union. The first-wave filter is simple and defensible: **a direction is in the first wave only if the warehouse already carries enough signal to answer real questions about it today**, using the metrics inventoried in `docs/operations/STATUS.md` "Warehouse contents" and the policies in `src/premura/dim_metric.yaml`. This keeps Stage 2 work pointed at data that exists rather than at aspirational coverage.

### First-wave set (5 directions)

| Direction | Why it's first-wave | Backing data already in the warehouse |
|---|---|---|
| **Sleep & recovery** | Densest daily data; the canonical "did something change" use case. | `sleep_rating`, `sleep_deep_pct`, `sleep_stage`/`sleep_session` intervals, `hrv_rmssd_overnight`, `resp_rate` (STATUS warehouse table). |
| **Cardiovascular fitness & training load** | Strong multi-source coverage and clear trend/comparison questions. | `vo2_max`, `training_load`, `training_readiness`, `resting_hr`, `heart_rate`, `intensity_minutes`, `steps` (STATUS; `dim_metric.yaml`). |
| **Metabolic health & body composition** | Slow-moving signals where freshness windows and trend matter most. | `weight`, `body_fat_pct`, `bmi`, `height`, plus the shipped lab ratios `derived:ldl_hdl_ratio`, `derived:tg_hdl_ratio` (STATUS; `lab_ratios.py`; WP01 Stable Commitment 9). |
| **Stress & autonomic balance** | High-cadence wearable data; pairs naturally with sleep and recovery. | `stress`, `body_battery`, `hrv_rmssd_overnight`, `resp_rate`, `skin_temperature` (STATUS; `dim_metric.yaml`). |
| **General overview** | The default "I don't know where to start" entry; routes to whichever of the above has fresh data. | Composed from the four above via the signal selector (WP01 Stable Commitment 3; STAGES §2 "Signal selector"). |

### Deferred from the first wave (named, not chosen)

- **Mental / cognitive** — VISION and STAGES both list it, but the warehouse has no committed mental/cognitive metrics today (STATUS warehouse table shows none). Defer until a source supplies them.
- **Gut** — STAGES §4 lists it and stool reports now ingest as clinical notes, but those land as qualitative `fact_clinical_note` commentary, not yet as answerable numeric signals (STATUS; ROADMAP "clinical labs"). Defer the *direction* even though lab ingest shipped.
- **Liver / cardiometabolic lab depth** — the lab ratios exist, but a full lab-direction needs profile context (sex, age) that is an open dependency, not a Stage 2 deliverable (WP01 Open Question 5; GitHub issue #6). Surface lab ratios *inside* the metabolic direction for now rather than as their own first-wave direction.

**Example (direction layer):** a user picks "Sleep & recovery." That is a routing choice. It does not yet name a question or a function — it only narrows which signals Stage 2 will be asked about.

---

## Layer 2 — Recurring user-question shapes (T006)

Before naming any function, name the **shapes of question** Stage 2 helps answer first. These are patterns that recur across every first-wave direction — not one-off feature ideas. The Jobs-to-be-Done framing in VISION Pillar 5 ("when I sense something about my body changed … I want to know what my data says") is the source of why these five recur.

| # | Question shape | Plain-English form | Applies across directions |
|---|---|---|---|
| Q1 | **Current status** | "What is my X right now, and is that value still trustworthy?" | All five |
| Q2 | **Trend over time** | "Is my X going up, down, or flat over the last weeks/months?" | All five |
| Q3 | **Comparison to a baseline** | "How does my X now compare to my own normal / a reference?" | All five |
| Q4 | **Change after an event or intervention** | "Did my X shift after I started/stopped doing something?" | Sleep, Cardio, Stress especially |
| Q5 | **Compound interpretation from multiple signals** | "What do these signals say *together* about this direction?" | Recovery, Overview especially |

Notes that keep these as patterns, not functions:

- A question shape is **direction-agnostic**. "Trend over time" is the same shape whether X is weight or HRV; only the input signal changes.
- Q1 (current status) is where Stage 2's freshness obligation bites hardest: a stale value must not be answered as "current" without an explicit override (STAGES §2 time-validity; WP01 Stable Commitment 8).
- Q3 (baseline) here means **the user's own rolling baseline**. Population/reference comparison and statistical significance are *not* Stage 2 — they are Stage 3 (see boundary table below).
- Q5 (compound) is where derived signals live, but the **interpretation** ("this means you're under-recovered") is Stage 4 teaching, not Stage 2.

**Example (question-shape layer):** inside "Sleep & recovery," the recurring questions are: *what was last night's sleep and is it fresh enough to trust* (Q1), *is my deep-sleep % trending down this month* (Q2), *is last night below my own 30-day normal* (Q3), *did my HRV change after I cut alcohol* (Q4), *do low HRV + high stress + poor sleep together say I'm under-recovered* (Q5).

---

## Layer 3 — Question shapes → Stage 2 function families (T007)

Now map each question shape to **engine function families**. An *engine function* is one registered Stage 2 signal function (one `SignalSpec` + its `fn`); a *family* is a class of them (WP01 "Terminology notes"). STAGES §2 already names Stage 2's four responsibilities (time-validity, missing-data policy, derived signals, signal selector); the families below are the engine functions that sit on top of those responsibilities (`docs/architecture/STAGES.md` §2; WP01 Stable Commitment 3).

This is **not a tool menu** and **not a UI plan**. Each family is deterministic, network-free, LLM-free, and reproducible from the warehouse alone (STAGES §2; WP01 Stable Commitment 1).

| Question shape | Stage 2 function family | What the engine produces (deterministic) |
|---|---|---|
| Q1 Current status | **Freshness-aware status** | The latest in-window value of a signal plus a validity verdict (current / stale-past-window). Built on the shipped `check_inputs_available` validity gate (WP01 Stable Commitment 8). |
| Q2 Trend over time | **Trend / summary** | A windowed series and a plain direction descriptor (rising/falling/flat over window N), with an `is_imputed` mask where gaps were filled (STAGES §2 missing-data). |
| Q3 Comparison to a baseline | **Self-baseline summary** | The user's own rolling baseline (e.g. 30-day mean) and the current value's position relative to it. *Own baseline only* — no population reference, no significance. |
| Q4 Change after an event | **Change detection (deterministic)** | A simple before/after window split around a user-supplied date and the magnitude of shift. The engine returns the numbers; it does not assert causation. |
| Q5 Compound interpretation | **Derived signals / ratios** | A new signal computed from ≥1 inputs, persisted under `derived:` with `revision` stamped — the shipped lab-ratio pattern generalized (WP01 Stable Commitments 7, 9; `src/premura/engine/lab_ratios.py`). |
| (cross-cutting, all Q) | **Signal selector** | Given a direction or question, ranks which of the above signals *this* warehouse can actually answer with, given current contents and validity. Named-but-unshipped today (WP01 Known Debt 2; STAGES §2). |

### Stage boundary — what stays OUT of Stage 2

This is the load-bearing part of the taxonomy. Each family above has a near neighbor that must **not** migrate into Stage 2:

| Concern | Stage | Why it is not Stage 2 |
|---|---|---|
| Pearson/Spearman correlation, t-tests, Mann-Whitney, regression, change-*point* statistics, lag-correlation | **Stage 3** | These are the deterministic *statistics tools* exposed as MCP tools for a model to call, returning `{effect, n, p, ci}` (STAGES §3; ROADMAP "deterministic stat tools"; VISION Pillar 3). Stage 2's "change detection" is a plain before/after delta, **not** a significance test. |
| Anything that returns a p-value, confidence interval, or significance verdict | **Stage 3** | Significance is a statistical claim, not a signal. Stage 2 reports values and deltas; Stage 3 decides whether a difference is significant. |
| PubMed lookup, citation round-trip, population/reference ranges | **Stage 3** | Network + evidence; Stage 2 has no network and no external dependency (STAGES §2–§3; WP01 Stable Commitment 1). |
| Anything model-facing (an LLM calls it) | **Stage 3** | Stage 3 is the only model-facing and only network-touching stage (WP01 Stable Commitment 2). |
| "Explain rMSSD", plain-language metric intros, dual-coded charts, progressive disclosure, prose interpretation ("you're under-recovered") | **Stage 4** | Teaching and presentation (VISION Pillars 4–5; STAGES §4). A freshness verdict is Stage 2; the *sentence that teaches what stale means* is Stage 4. |
| Interview routing UI, unit display preferences | **Stage 4** | The interview is a UI flow that *calls* the signal selector; the selector is Stage 2, the asking is Stage 4 (STAGES §4 sample-placement table). |

Two watchouts WP03 and WP05 should carry forward:

- **Do not let the taxonomy become a tool menu.** `correlate`, `paired_t_test`, `change_point` are Stage 3 tool names (ROADMAP "Concrete build order" item 2). If a proposed engine function returns a p-value or CI, it is in the wrong stage.
- **Do not let UI teaching masquerade as an engine function.** "Introduce this metric in plain language" is Stage 4 content, not a `SignalSpec`.

**Example (function-family layer):** the Q4 question "did my HRV change after I cut alcohol" maps to the **change-detection** family in Stage 2 — the engine returns `before_mean`, `after_mean`, and the delta with an `is_imputed` note. Whether that delta is *statistically* meaningful is a Stage 3 `paired_t_test` call; the sentence "your overnight recovery improved" is Stage 4 teaching. All three layers cooperate; only the first is Stage 2.

---

## How later WPs should use this taxonomy

- **WP03 (grounding rubric + contribution contract + gate)** can treat the six function families as the universe a new engine function must classify into, and use the "what stays OUT of Stage 2" table as a fast reject filter (a proposal that returns a p-value or teaches a concept is out of scope before grounding is even assessed).
- **WP05 (quick wins + follow-on)** should rank within the **first-wave directions** and bias toward the commonly-available metrics behind them (steps, weight, height, resting/heart rate, sleep, HRV — STATUS warehouse table), mapping each quick win to exactly one function family from Layer 3 and noting the direct-read debt it helps close (WP01 Known Debt 1).
- Both should keep the three layers labeled separately in their own artifacts so the contract and the quick-win ranking stay coherent.
