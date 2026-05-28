# 05 — Quick-Win Ranking, Next-Mission Sequence, Doc Alignment

> Mission: `grounded-extensible-engine-research-01KSD0D1` · WP05 · supports FR-008, FR-009, FR-010, NFR-002, NFR-004, NFR-005
> Purpose: turn the earlier research framework into a **decision-ready shortlist** of quick-win Stage 2 engine functions, then say **what to build next** and **which docs to realign** once the maintainer accepts these conclusions.

This is the end of the meta-work. WP01–WP04 built the map; this WP picks the first roads to pave. It builds directly on, and reuses the exact vocabulary of, the approved upstream artifacts and cites them rather than re-deriving:

- `research/01-repo-baseline.md` (WP01) — stable commitments, known debt, open questions, and the binding vocabulary (*signal*, *derived signal*, *engine function* = "one registered Stage 2 signal function", *health direction* kept distinct from a signal's `domain` tag).
- `research/02-stage2-taxonomy.md` (WP02) — the five first-wave **health directions**, the five **question shapes** (Q1–Q5), the six **engine function families**, and the "what stays OUT of Stage 2" boundary table.
- `research/03-grounding-and-contribution-gate.md` (WP03) — the ACCEPT / DEFER / REJECT grounding rubric (Part B) and the 10-check reviewer gate (Part D). Every candidate below is pre-graded through these.
- `research/04-engine-seam-and-profile-dependency.md` (WP04) — the baseline-profile dependency and its routing to GitHub issue [#6](https://github.com/nicofirst1/premura/issues/6). Any candidate touching height/sex/age is flagged **blocked on #6** as WP04 §4.2 demands.
- `docs/operations/STATUS.md` — what is *actually in the warehouse today*; candidates are biased toward this.
- `src/premura/dim_metric.yaml` — metric coverage and per-metric `validity_window` / `missing_data_policy`.

Plain English throughout (NFR-006). Every top-level recommendation is traceable to one of the above (NFR-001).

A scope reminder the whole document leans on (WP01 Stable Commitment 1; WP02 boundary table): Stage 2 is **deterministic, network-free, LLM-free, reproducible from the warehouse alone**. Nothing recommended here reaches the network, shares data silently, or steps outside the Stage 2/3/4 boundaries (NFR-005). The recurring reason this mission exists — Stage 2 is thin, so Stage 3 reaches past it (WP01 Known Debt 1) — is the gap each quick win helps close.

---

## How to read this document

- **§1 Candidate pool (T018)** — the full set of plausible early functions, biased toward data already in the warehouse, before any ranking.
- **§2 Scoring (T019)** — a transparent, reproducible scoring table over six criteria, so the ranking is evidence-backed, not intuitive.
- **§3 Ranked shortlist (T020)** — the 3–7 quick wins, each with rationale, inputs, a `strong` / `moderate` / `exploratory` confidence tag, caveats, and profile-data dependency.
- **§4 Next-mission sequence (T021)** — which next steps become implementation missions, which stay research, which stay deferred.
- **§5 Doc-alignment list (T022)** — the specific docs to update after acceptance, and why each.

---

## 1. Candidate pool (T018)

The candidates below are generated against a single filter: **does the warehouse already carry the input today, per STATUS.md "Warehouse contents", and does the function clearly belong in exactly one WP02 Stage 2 family?** A proposal that needs data Premura does not yet hold, or that drifts into Stage 3 statistics or Stage 4 teaching, is excluded before scoring (WP02 boundary table; WP03 Part D check 1).

To keep the bias toward commonly-available **non-lab** data explicit, each candidate is tagged by data class:

- **[wearable-common]** — built only on dense wearable/phone data many people already have (steps, resting/heart rate, sleep, HRV, stress, weight). No lab, no profile attribute.
- **[lab]** — depends on `lab:*` markers (sparser; many users will not have them).
- **[profile-blocked]** — needs a stable personal attribute (height/sex/age) that the measurement model cannot supply cleanly — **blocked on issue #6** (WP04 §3.3, §4.2).

| # | Candidate (working name) | Plain-English question it answers | Direction (WP02 L1) | Question shape (WP02 L2) | Family (WP02 L3) | Primary inputs (warehouse-present?) | Data class |
|---|---|---|---|---|---|---|---|
| C1 | `resting_hr_trend` | "Is my resting heart rate trending up, down, or flat over the last weeks?" | Cardiovascular fitness | Q2 trend | Trend / summary | `resting_hr` ✅ (HC + Garmin UDS) | [wearable-common] |
| C2 | `resting_hr_status` | "What is my resting heart rate right now, and is that value still fresh enough to trust?" | Cardiovascular fitness | Q1 current status | Freshness-aware status | `resting_hr` ✅ | [wearable-common] |
| C3 | `weight_trend` | "Is my body weight rising, falling, or flat over the last month?" | Metabolic / body composition | Q2 trend | Trend / summary | `weight` ✅ (HC + BMT) | [wearable-common] |
| C4 | `sleep_deep_pct_baseline` | "Was last night's deep-sleep % below my own recent normal?" | Sleep & recovery | Q3 self-baseline | Self-baseline summary | `sleep_deep_pct` ✅, `sleep_rating` ✅ | [wearable-common] |
| C5 | `hrv_overnight_baseline` | "Is my overnight HRV below my own rolling baseline lately?" | Sleep & recovery / Stress | Q3 self-baseline | Self-baseline summary | `hrv_rmssd_overnight` ✅ (Garmin) | [wearable-common] |
| C6 | `hrv_change_around_date` | "Did my overnight HRV shift after a date I name (e.g. cut alcohol)?" | Sleep & recovery | Q4 change after event | Change detection (delta only) | `hrv_rmssd_overnight` ✅ | [wearable-common] |
| C7 | `steps_trend` | "Are my daily steps trending up or down this month?" | Cardiovascular fitness | Q2 trend | Trend / summary | `steps` ✅ (`fact_interval`) | [wearable-common] |
| C8 | `stress_baseline` | "Is my daily stress score above my own recent normal?" | Stress & autonomic balance | Q3 self-baseline | Self-baseline summary | `stress` ✅ (Garmin) | [wearable-common] |
| C9 | `pulse_pressure` | "What is my pulse pressure (systolic minus diastolic) from my last BP reading?" | Cardiovascular fitness | Q5 compound (derived) | Derived signals / ratios | `bp_systolic` ✅, `bp_diastolic` ✅ (Garmin BP file) | [wearable-common] |
| C10 | `tg_hdl_status` | "What is my triglyceride/HDL ratio, and is that lab still in-window?" | Metabolic (lab depth) | Q1 current status | Freshness-aware status | `derived:tg_hdl_ratio` ✅ (shipped), `lab:triglycerides`, `lab:hdl` | [lab] |
| C11 | `bmi_as_function` | "What is my BMI right now?" | Metabolic / body composition | Q5 compound (derived) | Derived signals / ratios | `weight` ✅, **height-as-attribute** | [profile-blocked] |
| C12 | `age_adjusted_rhr_context` | "How does my resting HR compare to an age-adjusted norm?" | Cardiovascular fitness | Q3 baseline (reference) | Self-baseline summary | `resting_hr` ✅, **age** | [profile-blocked] |

Pool notes (so the ranking is defensible, not arbitrary — WP05 reviewer guidance):

- **C11 and C12 are included deliberately as cautionary entries**, not as quick wins. WP04 §3.3 names BMI and age-adjusted RHR as the exact functions whose *math is simple but whose context is missing*. They sit in the pool so the scoring can show *why* they rank below the wearable-common set, and so the shortlist's profile-dependency column has something concrete to point at.
- **C12 also brushes the Stage 2 boundary**: an *age-adjusted norm* is a population reference, and WP02 Q3 is the user's *own* baseline — population reference is Stage 3. C12 is therefore doubly disfavoured (boundary risk + profile dependency) and never reaches the shortlist.
- **Mental/cognitive and gut directions produced no candidates** — the warehouse carries no answerable numeric signals for them today (WP02 Layer 1 "Deferred from the first wave"; STATUS warehouse table). Correctly absent from the pool.
- Functions that would return a p-value, confidence interval, correlation, or significance verdict (e.g. "is my sleep correlated with stress") are **excluded at generation time** — they are Stage 3, the exact `correlate` / `paired_t_test` tools in the WP02 boundary table (WP03 Part E Example 3 rejects this very idea).

---

## 2. Scoring (T019)

Each candidate is scored on the six criteria the WP prompt names, each on a simple **1 (poor) → 5 (excellent)** scale, so the ranking is reproducible by anyone re-reading the same sources. The scale anchors are fixed below so scoring is not a matter of taste:

| Criterion | What it measures | 1 = | 5 = |
|---|---|---|---|
| **User value** | How often a real user asks this question (WP02 Q-shapes recur) | Niche / rarely asked | Asked constantly across many users |
| **Input availability** | Is the input actually in the warehouse today, densely, for many people (STATUS warehouse table) | Input absent or rare | Dense, multi-source, common |
| **Scientific clarity** | How clean the grounding is under WP03 Part B | Needs contested interpretation | Plain descriptive stat, no claim beyond "your own number" |
| **Caveat burden** | How *little* uncertainty machinery it must carry (higher = lighter burden) | Heavy caveats (population scope, interpretation risk) | Almost none beyond freshness |
| **Stage 2 fit** | How cleanly it maps to exactly one WP02 family with no boundary risk | Brushes Stage 3/4 boundary | Squarely one family, no drift |
| **Profile independence** | How free it is of the issue #6 profile-data dependency (higher = freer) | Blocked on #6 | No profile attribute needed at all |

`Total` is the unweighted sum (max 30). No hidden weighting — a reader can recompute it. Confidence tags in §3 follow directly from this profile (high totals with clean grounding → `strong`; mid totals or a real-but-manageable caveat → `moderate`; boundary/profile risk → `exploratory` or dropped).

| # | Candidate | User value | Input avail. | Sci. clarity | Caveat burden (light=high) | Stage 2 fit | Profile indep. | **Total /30** |
|---|---|:--:|:--:|:--:|:--:|:--:|:--:|:--:|
| C1 | `resting_hr_trend` | 5 | 5 | 5 | 4 | 5 | 5 | **29** |
| C2 | `resting_hr_status` | 5 | 5 | 5 | 4 | 5 | 5 | **29** |
| C4 | `sleep_deep_pct_baseline` | 5 | 4 | 4 | 4 | 5 | 5 | **27** |
| C7 | `steps_trend` | 4 | 5 | 5 | 4 | 5 | 5 | **28** |
| C5 | `hrv_overnight_baseline` | 4 | 4 | 4 | 3 | 5 | 5 | **25** |
| C3 | `weight_trend` | 4 | 4 | 5 | 4 | 5 | 5 | **27** |
| C6 | `hrv_change_around_date` | 4 | 4 | 4 | 3 | 4 | 5 | **24** |
| C8 | `stress_baseline` | 3 | 4 | 3 | 3 | 5 | 5 | **23** |
| C9 | `pulse_pressure` | 3 | 3 | 5 | 4 | 5 | 5 | **25** |
| C10 | `tg_hdl_status` | 4 | 2 | 4 | 3 | 5 | 5 | **23** |
| C11 | `bmi_as_function` | 4 | 2 | 5 | 3 | 4 | 1 | **19** |
| C12 | `age_adjusted_rhr_context` | 3 | 4 | 2 | 2 | 2 | 1 | **14** |

How to read the spread:

- The **wearable-common descriptive functions (C1, C2, C7, C3, C4)** cluster at the top (27–29) because they score high on every axis at once: common dense input, plain descriptive grounding (WP03 Part B "evidence bar is faithful computation"), and zero profile dependency.
- **C5/C6/C8** drop a little on caveat burden and sci-clarity: HRV and stress are real but vendor-proprietary scores (`stress`, Garmin overnight rMSSD) with more interpretation risk, and change-detection (C6) brushes nearer the Stage 3 line (it must return a *plain delta*, never a significance claim — WP02 Q4).
- **C9 `pulse_pressure`** scores well on clarity (a simple subtraction with a recognised name) but lower on user value/availability (BP is present only via the Garmin BP file, not for most users).
- **C10 `tg_hdl_status`** is grounded and shipped-adjacent (it reuses the existing `derived:tg_hdl_ratio`), but input availability is low — it is **[lab]**, and most users will not have a lipid panel.
- **C11/C12** sit at the bottom precisely because of the profile-independence collapse (score 1): their math is trivial but they are **blocked on issue #6** (WP04 §3.3). C12 falls further on Stage-2-fit because age-adjusted *reference* comparison is Stage 3, not Stage 2's own-baseline Q3.

---

## 3. Ranked shortlist of quick wins (T020, NFR-002, NFR-004, NFR-005)

**Six** candidates make the shortlist (within the required 3–7, NFR-002). Each is pre-graded through the WP03 rubric (Part B) and the 10-check gate (Part D) and arrives as **ACCEPT**; the two that carry a real caveat are tagged accordingly. Every candidate carries exactly one confidence tag — `strong` / `moderate` / `exploratory` (NFR-004) — and none requires background network access, silent external sharing, or any Stage 2/3/4 boundary bypass (NFR-005): all six are deterministic, local-only, single-family functions.

**Non-lab guarantee (SC-002):** five of the six shortlisted candidates (#1–#5: `resting_hr_status`, `resting_hr_trend`, `steps_trend`, `weight_trend`, `sleep_deep_pct_baseline`) are **[wearable-common]** — answerable purely from commonly-available non-lab data. That is comfortably ≥2.

---

### #1 — `resting_hr_status`  ·  confidence: **strong**

- **Rationale.** The single most common health question ("what is my X right now, and can I trust it") on the densest, most universally available wearable metric. It is also the cleanest demonstration of Stage 2's reason to exist: it answers *with a freshness verdict* instead of a raw fact-table read, directly closing the direct-read debt (WP01 Known Debt 1). WP03 Part E Example 1 already grades this family ACCEPT.
- **Required inputs.** `resting_hr` (warehouse-present, HC + Garmin UDS; `validity_window: P1D`, `missing_data_policy: last_observation_carried_forward`).
- **Family.** Freshness-aware status (WP02 Q1).
- **Scientific caveats.** Pure descriptive value — asserts nothing beyond "this is your latest in-window resting HR." Must return the validity verdict (current vs stale-past-window) and never present a stale value as current without explicit override (WP01 Stable Commitment 8). No significance, no causation.
- **Profile-data dependency.** None.

### #2 — `resting_hr_trend`  ·  confidence: **strong**

- **Rationale.** The Q2 trend twin of #1; the WP03 worked-example ACCEPT (Part E Example 1) verbatim. Highest scoring (29/30) alongside #1. Trend over time is the second most-asked shape and the clearest "did something change" use case on common data.
- **Required inputs.** `resting_hr` (as above).
- **Family.** Trend / summary (WP02 Q2).
- **Scientific caveats.** Descriptive only: a windowed series plus a plain rising/falling/flat descriptor with an `is_imputed` mask where LOCF filled gaps (WP02 Q2; WP01 Known Debt 5). Declines or marks imputed rather than guessing across long gaps. No significance claim about the trend.
- **Profile-data dependency.** None.

### #3 — `steps_trend`  ·  confidence: **strong**

- **Rationale.** Steps are the most universally collected signal of all (every phone counts them) and live in `fact_interval` already. A trend on steps is a textbook descriptive summary with essentially no interpretation risk — an ideal early function for users with no wearable beyond a phone.
- **Required inputs.** `steps` (warehouse-present in `fact_interval`; `validity_window: P1D`, `missing_data_policy: none`).
- **Family.** Trend / summary (WP02 Q2).
- **Scientific caveats.** Descriptive. Because `missing_data_policy` is `none`, it must **decline to impute** missing days and instead report them as gaps (WP03 Part B "if it cannot tolerate gaps, it must say so and decline"). No significance claim.
- **Profile-data dependency.** None.

### #4 — `weight_trend`  ·  confidence: **strong**

- **Rationale.** Weight is common (HC + BMT smart-scale), slow-moving, and a question users ask constantly. A trend over weeks is exactly where Stage 2's freshness windows and LOCF imputation earn their keep, since weigh-ins are irregular (`validity_window: P1W`).
- **Required inputs.** `weight` (warehouse-present, HC + BMT).
- **Family.** Trend / summary (WP02 Q2).
- **Scientific caveats.** Descriptive. Must disclose LOCF imputation via the `is_imputed` mask when carrying a stale weigh-in forward, and must not present a >1-week-old value as a current weight without flagging staleness. No significance, no causation.
- **Profile-data dependency.** None. (Note: this is the *raw weight* trend, **not** BMI — BMI is the profile-blocked C11, deliberately kept separate.)

### #5 — `sleep_deep_pct_baseline`  ·  confidence: **moderate**

- **Rationale.** Densest daily data and the canonical "was last night worse than my normal" question (WP02 Layer 1 "Sleep & recovery"). The user's *own* rolling baseline keeps it firmly inside Stage 2 (Q3 own-baseline only — no population reference). Tagged **moderate** rather than strong because `sleep_deep_pct` is a vendor-summarised percentage (sleep-staging accuracy varies by device), so the descriptive answer carries a little more "your device's estimate" caveat than a raw heart-rate count.
- **Required inputs.** `sleep_deep_pct` (warehouse-present, Garmin sleepData); optionally `sleep_rating` for context. `validity_window: P1D`.
- **Family.** Self-baseline summary (WP02 Q3) — the user's own rolling normal (e.g. 30-day mean) and where last night sits relative to it.
- **Scientific caveats.** Own-baseline only; explicitly *not* a population norm and *not* a significance test (that line is Stage 3 — WP02 Q3 note). Must state that deep-sleep % is a device estimate. Honest about gaps via `is_imputed`. No causation.
- **Profile-data dependency.** None.

### #6 — `hrv_change_around_date`  ·  confidence: **exploratory**

- **Rationale.** This is the Stage-2-legal sibling that WP03 Part E Example 3 explicitly points to as the *correct* alternative to the rejected correlation idea: a Q4 change-detection function returning a **plain before/after delta** around a user-supplied date (e.g. "did my overnight HRV shift after I cut alcohol"). High user value, common-ish input. Tagged **exploratory** — the lowest-scoring shortlist entry (24/30) — for two honest reasons: overnight rMSSD is Garmin-only and vendor-proprietary, and change-detection sits closest to the Stage 3 boundary, so it must be built with discipline to return numbers only, never a significance verdict.
- **Required inputs.** `hrv_rmssd_overnight` (warehouse-present, Garmin-only; `validity_window: P1D`), plus a user-supplied split date (a function argument, not a warehouse input).
- **Family.** Change detection / deterministic before-after (WP02 Q4).
- **Scientific caveats.** Returns `before_mean`, `after_mean`, and the delta with an `is_imputed` note — **and nothing else**. It must explicitly disclaim significance and causation (WP02 Q4 example: "the engine returns the numbers; it does not assert causation"). Whether the delta is statistically meaningful is a Stage 3 `paired_t_test` call, not this function. Garmin-only availability stated.
- **Profile-data dependency.** None.

---

**Shortlist summary.** 6 candidates (3–7 ✅). Confidence spread: **4 strong** (#1–#4), **1 moderate** (#5), **1 exploratory** (#6) — every candidate tagged (NFR-004 ✅). Non-lab common-data candidates: **5 of 6** (#1–#5) (SC-002 ≥2 ✅). No candidate touches network, external sharing, or boundary bypass (NFR-005 ✅), and none is blocked on issue #6 — the profile-blocked ideas (BMI, age-adjusted RHR) were deliberately kept *out* of the shortlist and parked for §4, per WP04 §4.2.

---

## 4. Next-mission sequence (T021, FR-009)

The shortlist translates into a concrete follow-on order. Each item is labelled **implement** (ready to build now), **research** (a question still to answer first), or **deferred** (correct to wait).

### Becomes an implementation mission (build next, in this order)

1. **Mission A — "Descriptive Stage 2 functions: status + trend on common wearable data."** Implements shortlist **#1 `resting_hr_status`, #2 `resting_hr_trend`, #3 `steps_trend`, #4 `weight_trend`** as a single first wave. These four share one shape (freshness-aware status + trend/summary over a single common metric), need no new ontology rows, no profile data, and are pre-graded ACCEPT (WP03 Part D). Building them together exercises the WP03 contribution contract end-to-end on the easiest, highest-value functions and starts closing the direct-read debt (WP01 Known Debt 1) by giving Stage 3 validity-gated functions to call instead of raw `fact_measurement` reads. **This is the recommended next mission.**
2. **Mission B — "Self-baseline + change-detection Stage 2 functions."** Implements shortlist **#5 `sleep_deep_pct_baseline`** and **#6 `hrv_change_around_date`**. Sequenced second because both carry slightly heavier caveats (vendor-estimate disclosure; the Q4 change-detection boundary discipline) and are best built *after* Mission A has proven the descriptive pattern and the gate. **This is the recommended second mission.**

### Stays research (answer the question before building)

3. **The signal selector remains a research/design question, not yet an implementation mission.** It is named-but-unshipped (WP01 Known Debt 2; WP02 Layer 3 cross-cutting row) and ranks *which* signals can answer a question for *this* warehouse. It should be scoped only after Mission A exists, because a selector needs a population of real functions to rank — there is nothing to select among today.
4. **Stage 3 statistics tooling stays out of this mission family entirely (boundary, not deferral).** Correlation, paired tests, change-*point* statistics, population/reference ranges are Stage 3 by design (WP02 boundary table). The shortlist intentionally produced no candidate here; this is a *correct exclusion*, recorded so a future reader does not mistake it for a gap.

### Stays deferred (correct to wait)

5. **Profile-dependent functions — BMI as a function (C11) and age-adjusted interpretation (C12) — stay deferred and blocked on GitHub issue [#6](https://github.com/nicofirst1/premura/issues/6).** Their math is trivial but they need stable personal context the measurement model cannot supply cleanly (WP04 §3.3). They must not be back-doored into `fact_measurement` (WP04 §4.2 item 2). They become buildable only once issue #6 lands a storage decision; until then they are a named dependency, not a quick win.
6. **Lab-depth functions beyond the shipped ratios (e.g. C10 `tg_hdl_status` surfacing) stay deferred** until lab coverage is denser for more users, and a full lab *direction* additionally needs the same profile context (sex/age) that issue #6 owns (WP02 Layer 1 "Deferred"; WP04 §3.1). Surface the existing `derived:` lab ratios *inside* the metabolic direction rather than building a lab-first mission now.

---

## 5. Doc-alignment list (T022, FR-010)

Once the maintainer accepts this shortlist and sequence, these specific docs need realignment so repo intent matches the research conclusions. The list is deliberately scoped to docs **materially affected** by this mission's decisions; docs that merely mention Stage 2 in passing are excluded.

| Doc | Why it needs an update | What changes |
|---|---|---|
| `docs/architecture/STAGES.md` | It is the source of truth for the Stage 2 contract and currently lists the four responsibilities abstractly, with the **direct-read operator-tool exception** as the headline debt (WP01 Known Debt 1). | Record that the first concrete *non-lab* Stage 2 functions (status/trend/self-baseline/change-detection on common wearable data) are now in scope, and note that each one built narrows the direct-read exception. Add a pointer to the WP03 contribution gate as the admission rule. |
| `docs/operations/STATUS.md` | It is the live "what is shipped today" snapshot and currently lists only the three derived lab ratios under "Signal engine foundations" (WP01 Stable Commitment 9). | After Mission A/B land, add the new descriptive functions to "What's working end-to-end" and the engine row, so the shipped-reality snapshot stays accurate. (Update *after* implementation, not on acceptance of this research.) |
| `docs/product/ROADMAP.md` | Its "Concrete build order" positions engine-backed signal functions as a future item; this mission fixes the *first* concrete order (Mission A then B, selector as research). | Replace the vague "engine functions later" framing with the §4 sequence: descriptive functions first, self-baseline/change-detection second, signal selector as a research follow-on, Stage 3 stats kept separate. |
| `docs/product/FULL_APP_DEVELOPMENT_PLAN.md` | It is the named source of truth for phase planning and currently lists deeper Stage 2 work as still-missing v2 payoff (WP01 Known Debt 7). | Convert "deeper Stage 2 is missing" into the concrete phased plan from §4, with the issue #6 profile dependency named as an explicit blocker on the BMI/age-adjusted slice. |
| `docs/history/product/VISION.md` | Pillar 4 (teaching) and the Jobs-to-be-Done framing motivate these question shapes, and Pillar 6 (privacy) is the constraint every candidate respects (NFR-005). It is labelled aspirational, so the change is light. | Cross-reference that the first-wave directions and question shapes (WP02) and the quick-win functions (this WP) are the concrete expression of Pillars 4–5, with no change to the privacy posture. |
| `src/premura/parsers/CONTRACT.md` (contributor guidance) | There is no engine-side contributor contract today (WP01 Open Question 1); WP03 produced one. Contributors currently only have the *parser* contract to look at. | Add a sibling pointer so a contributor proposing an engine function is routed to the WP03 grounding rubric + reviewer gate, mirroring the parser contract's role. (Either a short `src/premura/engine/CONTRACT.md` or a cross-link; the *content* is WP03's, this is the routing.) |
| GitHub issue [#6](https://github.com/nicofirst1/premura/issues/6) | This mission concretely confirms which quick wins are blocked on it (BMI C11, age-adjusted RHR C12) and which are not. | Comment on #6 with the §4 deferred list so the profile-data work has a clear, prioritised set of functions waiting on its decision (WP04 §4.2 item 4). |

Out of scope for doc alignment (named so the list stays honest): `docs/architecture/UPDATE_STRATEGY.md` and the `revision`/revalidation story are unchanged by this mission — none of the six shortlisted functions persists `derived:` rows except the lab-ratio reuse, which already exists, so no new invalidation work is introduced here (WP04 §2 item 10 defers profile-dependent persistence anyway).

---

## 6. Traceability recap (NFR-001)

- **Candidate pool** → WP02 Layer 1 directions + Layer 3 families; STATUS warehouse table; `dim_metric.yaml` coverage.
- **Scoring criteria** → the six criteria named in the WP05 prompt T019; anchors fixed so any reader recomputes the same totals.
- **Each shortlist confidence tag** → the WP03 Part B rubric + Part D gate (`strong` = clean descriptive ACCEPT on common data; `moderate` = ACCEPT with a vendor-estimate caveat; `exploratory` = ACCEPT but boundary-adjacent and vendor-only).
- **Profile-dependency flags & the deferred BMI/age functions** → WP04 §3.3 + §4.2 and GitHub issue #6.
- **Next-mission sequence** → directly from the §2 scoring spread and the WP01 Known Debt 1 direct-read gap each function helps close.
- **Doc-alignment list** → the WP01 source map (authoritative vs aspirational docs) and the open questions this mission closes.
